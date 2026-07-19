from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.modules.identity.models import AuthIdentity
from app.modules.identity.sessions import SessionError, SessionService

bearer = HTTPBearer(auto_error=False)


async def get_current_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthIdentity:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication_required"
        )
    service = SessionService(
        pepper=settings.jwt_secret,
        access_ttl_seconds=settings.access_token_ttl_seconds,
        refresh_ttl_seconds=settings.refresh_token_ttl_seconds,
    )
    try:
        return await service.authenticate(session, access_token=credentials.credentials)
    except SessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_session"
        ) from exc


CurrentIdentity = Annotated[AuthIdentity, Depends(get_current_identity)]


async def get_current_operator(identity: CurrentIdentity) -> AuthIdentity:
    if identity.identity_type != "operator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="operator_required")
    return identity


CurrentOperator = Annotated[AuthIdentity, Depends(get_current_operator)]
