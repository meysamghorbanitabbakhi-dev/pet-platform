from collections.abc import AsyncIterator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session as SyncSession

from app.core.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
# Real request traffic connects as the deliberately unprivileged
# database_app_url role instead of `engine`'s superuser role, so row-
# level-security policies actually apply (superusers always bypass RLS
# in Postgres, by design, regardless of policy or FORCE ROW LEVEL
# SECURITY -- see the ADR-011 amendment). `engine`/SessionFactory stay
# on the superuser role deliberately: migrations need DDL privileges,
# and background scheduler jobs (e.g. expire_stale_offers) are trusted
# system code sweeping across every household by design, not acting on
# behalf of any single identity RLS could scope them to.
app_engine = create_async_engine(settings.database_app_url, pool_pre_ping=True)


class _RLSSession(SyncSession):
    """A dedicated sync-Session subclass (rather than registering the event
    below on the generic sqlalchemy.orm.Session) so this app's row-level-
    security context plumbing cannot silently affect any other engine or
    session a test or tool happens to construct."""


@event.listens_for(_RLSSession, "after_begin")
def _apply_rls_context(session: SyncSession, transaction: object, connection: object) -> None:
    """Re-issues the current request's RLS session variables at the start
    of every transaction this session opens, not just the first -- a
    route that commits mid-request and then runs further queries in the
    same session would otherwise silently lose RLS context for anything
    after that commit, since SET LOCAL only lasts one transaction.
    apply_rls_context (app/api/dependencies.py) is what actually
    populates session.info; this event is what makes that survive
    however many transactions the request's session goes through.

    No-ops for a session with no RLS context set yet (the very first
    transaction in a request -- the one used to look up the bearer
    token itself, before an identity is known -- never touches a
    household-scoped table, so this is safe)."""
    is_operator = session.info.get("rls_is_operator")
    if is_operator is None:
        return
    # set_config(...), not SET LOCAL directly -- see apply_rls_context's
    # comment (app/api/dependencies.py): SET LOCAL's grammar does not
    # accept a bind parameter for its value.
    connection.execute(  # type: ignore[attr-defined]
        text("SELECT set_config('app.is_operator', :v, true)"),
        {"v": "true" if is_operator else "false"},
    )
    connection.execute(  # type: ignore[attr-defined]
        text("SELECT set_config('app.identity_id', :v, true)"),
        {"v": str(session.info.get("rls_identity_id") or "")},
    )
    household_ids = session.info.get("rls_household_ids") or []
    connection.execute(  # type: ignore[attr-defined]
        text("SELECT set_config('app.household_ids', :v, true)"),
        {"v": ",".join(str(item) for item in household_ids)},
    )


SessionFactory = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession, sync_session_class=_RLSSession
)
AppSessionFactory = async_sessionmaker(
    app_engine, expire_on_commit=False, class_=AsyncSession, sync_session_class=_RLSSession
)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with AppSessionFactory() as session:
        yield session


async def ping_database() -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def close_database() -> None:
    await engine.dispose()
    await app_engine.dispose()
