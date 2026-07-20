"""Create the unprivileged app role RLS enforcement depends on (Workstream 9).

Revision ID: 20260720_0040
Revises: 20260720_0039

ADR-011 originally deferred PostgreSQL Row-Level Security, reasoning that
the platform has a single database role for all application queries and
no per-request session-local context. Investigating what it would take to
adopt RLS surfaced a sharper version of that same problem: the role
`database_url` connects as (`pet_platform` in every environment set up so
far) is a Postgres **superuser** -- and Postgres unconditionally bypasses
row security for superusers, with no override. Every RLS policy this
program adds would be silently inert against that role regardless of how
carefully it's written.

This migration creates `settings.database_app_url`'s role -- ordinary
LOGIN, explicitly NOSUPERUSER, NOBYPASSRLS -- and grants it read/write on
every existing table plus a default-privileges rule so future migrations'
new tables are covered automatically without a follow-up grant each time.
`app/db/session.py`'s request-serving engine connects as this role;
migrations and background scheduler jobs keep using the original
superuser role (DDL needs elevated privileges, and scheduler sweeps are
trusted system code crossing every household by design, not scoped to a
single identity RLS could restrict them to).

The role is created here, by the migration (running as the superuser),
rather than assumed to pre-exist, so `alembic upgrade head` alone
provisions a working RLS-capable environment from empty. The password
below is a placeholder matching this codebase's existing convention for
database_url's own default (see Settings.database_app_url's docstring) --
production must already have overridden DATABASE_APP_URL to a real
password before this migration runs there, or requests will be unable to
authenticate as this role after this migration (see Consequences in the
paired ADR-011 amendment for the operational sequencing this implies).
"""

from collections.abc import Sequence

from alembic import op
from app.core.config import get_settings
from sqlalchemy.engine import make_url

revision: str = "20260720_0040"
down_revision: str | None = "20260720_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _app_role_credentials() -> tuple[str, str]:
    url = make_url(get_settings().database_app_url)
    if url.username is None or url.password is None:
        raise RuntimeError("database_app_url must include a username and password")
    return url.username, url.password


def upgrade() -> None:
    username, password = _app_role_credentials()
    connection = op.get_bind()
    # username/password come from server-side Settings, never request
    # input, so direct interpolation here carries the same trust level
    # as the CREATE ROLE/GRANT statements below (which must interpolate
    # regardless, since role/database names cannot be bind parameters in
    # DDL) -- not a SQL-injection-relevant string.
    exists = connection.exec_driver_sql(
        f"SELECT 1 FROM pg_roles WHERE rolname = '{username}'"
    ).scalar()
    if exists:
        # Password may have been rotated since the role was first created
        # (e.g. redeploying this migration's environment) -- keep it in
        # sync with the current DATABASE_APP_URL rather than assuming
        # the original value is still correct.
        connection.exec_driver_sql(
            f'ALTER ROLE "{username}" WITH LOGIN NOSUPERUSER NOBYPASSRLS '
            f"PASSWORD '{password}'"
        )
    else:
        connection.exec_driver_sql(
            f'CREATE ROLE "{username}" WITH LOGIN NOSUPERUSER NOBYPASSRLS '
            f"PASSWORD '{password}'"
        )
    database_name = connection.exec_driver_sql("SELECT current_database()").scalar()
    connection.exec_driver_sql(f'GRANT CONNECT ON DATABASE "{database_name}" TO "{username}"')
    connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{username}"')
    connection.exec_driver_sql(
        f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{username}"'
    )
    connection.exec_driver_sql(
        f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "{username}"'
    )
    connection.exec_driver_sql(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "{username}"'
    )
    connection.exec_driver_sql(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f'GRANT USAGE, SELECT ON SEQUENCES TO "{username}"'
    )


def downgrade() -> None:
    username, _ = _app_role_credentials()
    connection = op.get_bind()
    connection.exec_driver_sql(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f'REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM "{username}"'
    )
    connection.exec_driver_sql(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f'REVOKE USAGE, SELECT ON SEQUENCES FROM "{username}"'
    )
    connection.exec_driver_sql(
        f'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM "{username}"'
    )
    connection.exec_driver_sql(
        f'REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM "{username}"'
    )
    connection.exec_driver_sql(f'REVOKE USAGE ON SCHEMA public FROM "{username}"')
    database_name = connection.exec_driver_sql("SELECT current_database()").scalar()
    connection.exec_driver_sql(
        f'REVOKE CONNECT ON DATABASE "{database_name}" FROM "{username}"'
    )
    connection.exec_driver_sql(f'DROP ROLE IF EXISTS "{username}"')
