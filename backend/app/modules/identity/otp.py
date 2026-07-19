from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.phone import normalize_iranian_mobile
from app.common.time import utc_now
from app.integrations.otp.port import OtpProvider
from app.modules.identity.models import AuthIdentity, OtpChallenge


class OtpCooldownError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("OTP was requested too recently")
        self.retry_after_seconds = retry_after_seconds


class OtpDeliveryError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class OtpRequestResult:
    challenge_id: UUID
    expires_in_seconds: int


@dataclass(frozen=True, slots=True)
class OtpVerificationResult:
    state: Literal["verified", "invalid", "expired", "consumed", "locked", "not_found"]
    identity_id: UUID | None = None
    attempts_remaining: int | None = None


def generate_otp_code(length: int = 6) -> str:
    if not 4 <= length <= 8:
        raise ValueError("OTP length must be between 4 and 8 digits")
    upper = 10**length
    return f"{secrets.randbelow(upper):0{length}d}"


def hash_otp_code(*, pepper: str, challenge_id: UUID, mobile_e164: str, code: str) -> str:
    message = f"{challenge_id}:{mobile_e164}:{code}".encode()
    return hmac.new(pepper.encode(), message, hashlib.sha256).hexdigest()


def otp_matches(*, pepper: str, challenge: OtpChallenge, candidate_code: str) -> bool:
    candidate_hash = hash_otp_code(
        pepper=pepper,
        challenge_id=challenge.id,
        mobile_e164=challenge.mobile_e164,
        code=candidate_code,
    )
    return hmac.compare_digest(candidate_hash, challenge.code_hash)


class OtpService:
    def __init__(
        self,
        *,
        pepper: str,
        ttl_seconds: int = 120,
        resend_cooldown_seconds: int = 60,
        max_attempts: int = 5,
    ) -> None:
        self._pepper = pepper
        self._ttl_seconds = ttl_seconds
        self._resend_cooldown_seconds = resend_cooldown_seconds
        self._max_attempts = max_attempts

    async def request_code(
        self, session: AsyncSession, provider: OtpProvider, *, raw_mobile: str
    ) -> OtpRequestResult:
        now = utc_now()
        mobile_e164 = normalize_iranian_mobile(raw_mobile)
        latest = await session.scalar(
            select(OtpChallenge)
            .where(
                OtpChallenge.mobile_e164 == mobile_e164,
                OtpChallenge.delivery_status.in_(("pending", "sent")),
            )
            .order_by(desc(OtpChallenge.created_at))
            .limit(1)
        )
        if latest is not None:
            age = (now - latest.created_at).total_seconds()
            if age < self._resend_cooldown_seconds:
                raise OtpCooldownError(max(1, int(self._resend_cooldown_seconds - age)))

        challenge_id = uuid4()
        code = generate_otp_code()
        challenge = OtpChallenge(
            id=challenge_id,
            mobile_e164=mobile_e164,
            code_hash=hash_otp_code(
                pepper=self._pepper,
                challenge_id=challenge_id,
                mobile_e164=mobile_e164,
                code=code,
            ),
            attempts=0,
            max_attempts=self._max_attempts,
            expires_at=now + timedelta(seconds=self._ttl_seconds),
            delivery_status="pending",
        )
        session.add(challenge)
        await session.commit()

        try:
            provider_reference = await provider.send_code(
                mobile_e164=mobile_e164,
                code=code,
                correlation_id=str(challenge_id),
            )
        except Exception as exc:
            challenge.delivery_status = "failed"
            challenge.delivery_error = type(exc).__name__
            await session.commit()
            raise OtpDeliveryError("OTP delivery failed") from exc

        challenge.delivery_status = "sent"
        challenge.provider_reference = provider_reference
        await session.commit()
        return OtpRequestResult(challenge_id=challenge_id, expires_in_seconds=self._ttl_seconds)

    async def verify_code(
        self, session: AsyncSession, *, challenge_id: UUID, candidate_code: str
    ) -> OtpVerificationResult:
        now = utc_now()
        challenge = await session.scalar(
            select(OtpChallenge).where(OtpChallenge.id == challenge_id).with_for_update()
        )
        if challenge is None or challenge.delivery_status != "sent":
            return OtpVerificationResult(state="not_found")
        if challenge.consumed_at is not None:
            return OtpVerificationResult(state="consumed")
        if challenge.expires_at <= now:
            return OtpVerificationResult(state="expired")
        if challenge.attempts >= challenge.max_attempts:
            return OtpVerificationResult(state="locked", attempts_remaining=0)

        if not otp_matches(pepper=self._pepper, challenge=challenge, candidate_code=candidate_code):
            challenge.attempts += 1
            remaining = max(0, challenge.max_attempts - challenge.attempts)
            await session.commit()
            return OtpVerificationResult(
                state="locked" if remaining == 0 else "invalid",
                attempts_remaining=remaining,
            )

        challenge.consumed_at = now
        identity_id = await self._get_or_create_customer_identity(
            session, mobile_e164=challenge.mobile_e164
        )
        await session.commit()
        return OtpVerificationResult(state="verified", identity_id=identity_id)

    async def _get_or_create_customer_identity(
        self, session: AsyncSession, *, mobile_e164: str
    ) -> UUID:
        statement = (
            insert(AuthIdentity)
            .values(identity_type="customer", mobile_e164=mobile_e164, status="active")
            .on_conflict_do_nothing(index_elements=["mobile_e164"])
            .returning(AuthIdentity.id)
        )
        identity_id = await session.scalar(statement)
        if identity_id is not None:
            return identity_id
        existing = await session.scalar(
            select(AuthIdentity.id).where(AuthIdentity.mobile_e164 == mobile_e164)
        )
        if existing is None:
            raise RuntimeError("identity disappeared during OTP verification")
        return existing
