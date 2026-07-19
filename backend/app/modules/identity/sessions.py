from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time import utc_now
from app.modules.identity.models import AuthIdentity, AuthSession


class SessionError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class SessionTokens:
    access_token: str
    refresh_token: str
    access_expires_in_seconds: int
    refresh_expires_in_seconds: int


class SessionService:
    def __init__(
        self,
        *,
        pepper: str,
        access_ttl_seconds: int = 900,
        refresh_ttl_seconds: int = 2_592_000,
    ) -> None:
        if len(pepper) < 32:
            raise ValueError("session pepper must be at least 32 characters")
        self._pepper = pepper.encode()
        self._access_ttl = access_ttl_seconds
        self._refresh_ttl = refresh_ttl_seconds

    async def issue(
        self,
        session: AsyncSession,
        *,
        identity_id: UUID,
        source_ip: str | None,
        user_agent: str | None,
    ) -> SessionTokens:
        identity = await session.get(AuthIdentity, identity_id)
        if identity is None or identity.status != "active":
            raise SessionError("identity is unavailable")
        access_token, refresh_token = self._new_pair()
        session.add(
            AuthSession(
                identity_id=identity_id,
                access_token_hash=self._digest(access_token),
                access_expires_at=utc_now() + timedelta(seconds=self._access_ttl),
                refresh_token_hash=self._digest(refresh_token),
                source_ip=source_ip,
                user_agent=user_agent,
                expires_at=utc_now() + timedelta(seconds=self._refresh_ttl),
            )
        )
        await session.commit()
        return self._result(access_token, refresh_token)

    async def authenticate(self, session: AsyncSession, *, access_token: str) -> AuthIdentity:
        auth_session = await session.scalar(
            select(AuthSession).where(
                AuthSession.access_token_hash == self._digest(access_token),
                AuthSession.revoked_at.is_(None),
                AuthSession.access_expires_at > utc_now(),
            )
        )
        if auth_session is None:
            raise SessionError("invalid access token")
        identity = await session.get(AuthIdentity, auth_session.identity_id)
        if identity is None or identity.status != "active":
            raise SessionError("identity is unavailable")
        return identity

    async def rotate(
        self,
        session: AsyncSession,
        *,
        refresh_token: str,
        source_ip: str | None,
        user_agent: str | None,
    ) -> SessionTokens:
        now = utc_now()
        auth_session = await session.scalar(
            select(AuthSession)
            .where(AuthSession.refresh_token_hash == self._digest(refresh_token))
            .with_for_update()
        )
        if (
            auth_session is None
            or auth_session.revoked_at is not None
            or auth_session.expires_at <= now
        ):
            raise SessionError("invalid refresh token")
        access_token, new_refresh_token = self._new_pair()
        auth_session.access_token_hash = self._digest(access_token)
        auth_session.access_expires_at = now + timedelta(seconds=self._access_ttl)
        auth_session.refresh_token_hash = self._digest(new_refresh_token)
        auth_session.source_ip = source_ip
        auth_session.user_agent = user_agent
        auth_session.expires_at = now + timedelta(seconds=self._refresh_ttl)
        await session.commit()
        return self._result(access_token, new_refresh_token)

    async def revoke(self, session: AsyncSession, *, refresh_token: str) -> None:
        auth_session = await session.scalar(
            select(AuthSession)
            .where(AuthSession.refresh_token_hash == self._digest(refresh_token))
            .with_for_update()
        )
        if auth_session is not None and auth_session.revoked_at is None:
            auth_session.revoked_at = utc_now()
            await session.commit()

    def _digest(self, token: str) -> str:
        return hmac.new(self._pepper, token.encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def _new_pair() -> tuple[str, str]:
        return secrets.token_urlsafe(32), secrets.token_urlsafe(48)

    def _result(self, access_token: str, refresh_token: str) -> SessionTokens:
        return SessionTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_in_seconds=self._access_ttl,
            refresh_expires_in_seconds=self._refresh_ttl,
        )
