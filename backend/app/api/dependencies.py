from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.modules.households.models import HouseholdMembership
from app.modules.identity.models import AuthIdentity
from app.modules.identity.sessions import SessionError, SessionService

bearer = HTTPBearer(auto_error=False)


async def apply_rls_context(session: AsyncSession, identity: AuthIdentity) -> None:
    """Row-level-security defense-in-depth (ADR-011's amendment): stores
    this request's authorization facts on the session for
    app/db/session.py's after_begin event to re-apply on every
    transaction, and issues SET LOCAL immediately for the transaction
    already open at this point (the one get_current_identity used to
    look up the bearer token). A customer's household_ids is recomputed
    fresh from HouseholdMembership on every request -- never cached
    across requests -- so a membership change takes effect on the very
    next request, not at some future cache-invalidation point.
    """
    is_operator = identity.identity_type == "operator"
    session.info["rls_is_operator"] = is_operator
    session.info["rls_identity_id"] = identity.id
    # SET LOCAL's grammar does not accept a bind parameter in place of its
    # value (Postgres requires a literal there) -- set_config(...) is a
    # regular function call and takes one normally; its third argument
    # (is_local=true) makes it behave exactly like SET LOCAL, scoped to
    # the current transaction only.
    #
    # is_operator and identity_id are set BEFORE the household_ids query
    # below runs, not after: households_memberships itself is RLS-
    # protected, and its policy's bootstrap branch
    # (identity_id = app_identity_id()) is what lets a customer discover
    # their own household_ids in the first place -- querying it with no
    # identity_id set yet would be a chicken-and-egg deadlock (need
    # household_ids to pass the policy, need the policy to pass to learn
    # household_ids).
    await session.execute(
        text("SELECT set_config('app.is_operator', :v, true)"),
        {"v": "true" if is_operator else "false"},
    )
    await session.execute(
        text("SELECT set_config('app.identity_id', :v, true)"), {"v": str(identity.id)}
    )
    household_ids: list[object] = []
    if not is_operator:
        household_ids = list(
            (
                await session.scalars(
                    select(HouseholdMembership.household_id).where(
                        HouseholdMembership.identity_id == identity.id
                    )
                )
            ).all()
        )
    session.info["rls_household_ids"] = household_ids
    await session.execute(
        text("SELECT set_config('app.household_ids', :v, true)"),
        {"v": ",".join(str(item) for item in household_ids)},
    )


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


async def _identity_with_rls_context(
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthIdentity:
    """A separate outer dependency, rather than calling apply_rls_context
    directly inside get_current_identity, specifically so tests that do
    `app.dependency_overrides[get_current_identity] = lambda: identity`
    (the established pattern throughout this codebase's test suite,
    faking authentication without a real bearer token) still get correct
    RLS context applied for whatever identity they injected -- FastAPI
    substitutes the override only for get_current_identity itself, and
    still calls this wrapper normally, so nothing about the existing
    test suite needed to change for RLS to apply to real HTTP traffic."""
    await apply_rls_context(session, identity)
    return identity


CurrentIdentity = Annotated[AuthIdentity, Depends(_identity_with_rls_context)]


async def get_current_operator(identity: CurrentIdentity) -> AuthIdentity:
    if identity.identity_type != "operator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="operator_required")
    return identity


CurrentOperator = Annotated[AuthIdentity, Depends(get_current_operator)]
