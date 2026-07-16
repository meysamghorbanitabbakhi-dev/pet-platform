from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.phone import normalize_iranian_mobile
from app.core.config import Settings, get_settings
from app.core.rate_limit import CounterStore, FixedWindowRateLimiter
from app.core.redis import get_redis
from app.db.session import get_db_session
from app.integrations.otp.factory import (
    OtpProviderNotConfiguredError,
    build_otp_provider,
)
from app.modules.identity.otp import (
    OtpCooldownError,
    OtpDeliveryError,
    OtpService,
)
from app.modules.identity.sessions import SessionError, SessionService

router = APIRouter(prefix="/auth", tags=["authentication"])
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


class OtpRequestBody(BaseModel):
    mobile: str = Field(min_length=10, max_length=32)
    device_id: str | None = Field(default=None, min_length=8, max_length=128)


class OtpRequestResponse(BaseModel):
    challenge_id: UUID
    expires_in_seconds: int


class OtpVerifyBody(BaseModel):
    challenge_id: UUID
    code: str = Field(pattern=r"^\d{6}$")


class OtpVerifyResponse(BaseModel):
    state: Literal["verified", "invalid", "expired", "consumed", "locked", "not_found"]
    identity_id: UUID | None = None
    attempts_remaining: int | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: Literal["bearer"] | None = None
    expires_in_seconds: int | None = None


class RefreshBody(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=512)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in_seconds: int


def _service(settings: Settings) -> OtpService:
    return OtpService(
        pepper=settings.otp_pepper,
        ttl_seconds=settings.otp_ttl_seconds,
        resend_cooldown_seconds=settings.otp_resend_cooldown_seconds,
        max_attempts=settings.otp_max_attempts,
    )


def _sessions(settings: Settings) -> SessionService:
    return SessionService(
        pepper=settings.jwt_secret,
        access_ttl_seconds=settings.access_token_ttl_seconds,
        refresh_ttl_seconds=settings.refresh_token_ttl_seconds,
    )


@router.post(
    "/otp/request", response_model=OtpRequestResponse, status_code=status.HTTP_202_ACCEPTED
)
async def request_otp(
    body: OtpRequestBody,
    request: Request,
    response: Response,
    session: SessionDependency,
    settings: SettingsDependency,
) -> OtpRequestResponse:
    try:
        normalized_mobile = normalize_iranian_mobile(body.mobile)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="invalid_mobile_number",
        ) from exc
    limiter = FixedWindowRateLimiter(cast(CounterStore, get_redis()))
    subjects = [
        (
            "otp-ip",
            request.client.host if request.client else "unknown",
            settings.otp_ip_limit_per_10_minutes,
        ),
        ("otp-mobile", normalized_mobile, settings.otp_mobile_limit_per_10_minutes),
    ]
    if body.device_id:
        subjects.append(("otp-device", body.device_id, settings.otp_device_limit_per_10_minutes))
    for scope, subject, limit in subjects:
        rate_result = await limiter.check(
            scope=scope, subject=subject, limit=limit, window_seconds=600
        )
        if not rate_result.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="otp_rate_limit_exceeded",
                headers={"Retry-After": str(rate_result.retry_after_seconds)},
            )
    try:
        provider = build_otp_provider(settings)
    except OtpProviderNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="otp_provider_not_configured",
        ) from exc
    try:
        result = await _service(settings).request_code(
            session, provider, raw_mobile=normalized_mobile
        )
    except OtpCooldownError as exc:
        response.headers["Retry-After"] = str(exc.retry_after_seconds)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="otp_requested_too_recently",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except OtpDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="otp_delivery_failed"
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="invalid_mobile_number",
        ) from exc
    finally:
        await provider.aclose()
    return OtpRequestResponse(
        challenge_id=result.challenge_id,
        expires_in_seconds=result.expires_in_seconds,
    )


@router.post("/otp/verify", response_model=OtpVerifyResponse)
async def verify_otp(
    body: OtpVerifyBody,
    request: Request,
    session: SessionDependency,
    settings: SettingsDependency,
) -> OtpVerifyResponse:
    result = await _service(settings).verify_code(
        session, challenge_id=body.challenge_id, candidate_code=body.code
    )
    tokens = None
    if result.state == "verified" and result.identity_id is not None:
        tokens = await _sessions(settings).issue(
            session,
            identity_id=result.identity_id,
            source_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    return OtpVerifyResponse(
        state=result.state,
        identity_id=result.identity_id,
        attempts_remaining=result.attempts_remaining,
        access_token=tokens.access_token if tokens else None,
        refresh_token=tokens.refresh_token if tokens else None,
        token_type="bearer" if tokens else None,
        expires_in_seconds=tokens.access_expires_in_seconds if tokens else None,
    )


@router.post("/session/refresh", response_model=TokenResponse)
async def refresh_session(
    body: RefreshBody,
    request: Request,
    session: SessionDependency,
    settings: SettingsDependency,
) -> TokenResponse:
    try:
        tokens = await _sessions(settings).rotate(
            session,
            refresh_token=body.refresh_token,
            source_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except SessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_session"
        ) from exc
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in_seconds=tokens.access_expires_in_seconds,
    )


@router.post("/session/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshBody,
    session: SessionDependency,
    settings: SettingsDependency,
) -> None:
    await _sessions(settings).revoke(session, refresh_token=body.refresh_token)
