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

Username/password are sourced from server-side Settings, never request
input -- but they were originally spliced directly into f-string SQL
text (a `PASSWORD '{password}'` literal and an ad hoc `"{username}"`
identifier with no escaping), which breaks outright if either value
ever contains a quote character, and is the wrong pattern to leave
sitting in the codebase regardless of today's trust level. Postgres
does not accept a bind parameter in a role-DDL PASSWORD clause (verified
directly: `ALTER ROLE x PASSWORD $1` is a syntax error), so this instead
defines a session-local `pg_temp` PL/pgSQL function that takes
username/password as ordinary, properly bound SQL function arguments
and uses Postgres's own `format(... %I ... %L ...)` to build the DDL
text server-side -- %I and %L apply Postgres's real identifier/literal
quoting (embedded quotes and backslashes included), not Python string
escaping. `pg_temp` functions are session-local and auto-dropped when
this migration's connection closes, so nothing lingers afterward.
"""

from collections.abc import Sequence

from alembic import op
from app.core.config import get_settings
from sqlalchemy import text
from sqlalchemy.engine import make_url

revision: str = "20260720_0040"
down_revision: str | None = "20260720_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CREATE_ROLE_HELPER_SQL = """
CREATE FUNCTION pg_temp.gap_closure_apply_app_role(
    p_username text, p_password text, p_exists boolean
) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
  IF p_exists THEN
    EXECUTE format(
        'ALTER ROLE %I WITH LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD %L', p_username, p_password
    );
  ELSE
    EXECUTE format(
        'CREATE ROLE %I WITH LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD %L', p_username, p_password
    );
  END IF;
END;
$$
"""

_GRANT_HELPER_SQL = """
CREATE FUNCTION pg_temp.gap_closure_grant_app_role(p_username text, p_database text) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', p_database, p_username);
  EXECUTE format('GRANT USAGE ON SCHEMA public TO %I', p_username);
  EXECUTE format(
      'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO %I', p_username
  );
  EXECUTE format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO %I', p_username);
  EXECUTE format(
      'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
      'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I', p_username
  );
  EXECUTE format(
      'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO %I',
      p_username
  );
END;
$$
"""

_REVOKE_HELPER_SQL = """
CREATE FUNCTION pg_temp.gap_closure_revoke_app_role(p_username text, p_database text) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
  EXECUTE format(
      'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
      'REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM %I', p_username
  );
  EXECUTE format(
      'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE USAGE, SELECT ON SEQUENCES FROM %I',
      p_username
  );
  EXECUTE format('REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM %I', p_username);
  EXECUTE format('REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM %I', p_username);
  EXECUTE format('REVOKE USAGE ON SCHEMA public FROM %I', p_username);
  EXECUTE format('REVOKE CONNECT ON DATABASE %I FROM %I', p_database, p_username);
  EXECUTE format('DROP ROLE IF EXISTS %I', p_username);
END;
$$
"""


def _app_role_credentials() -> tuple[str, str]:
    url = make_url(get_settings().database_app_url)
    if url.username is None or url.password is None:
        raise RuntimeError("database_app_url must include a username and password")
    return url.username, url.password


def upgrade() -> None:
    username, password = _app_role_credentials()
    connection = op.get_bind()
    exists = bool(
        connection.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :username"), {"username": username}
        ).scalar()
    )
    connection.execute(text(_CREATE_ROLE_HELPER_SQL))
    connection.execute(
        text("SELECT pg_temp.gap_closure_apply_app_role(:username, :password, :exists)"),
        {"username": username, "password": password, "exists": exists},
    )
    database_name = connection.exec_driver_sql("SELECT current_database()").scalar()
    connection.execute(text(_GRANT_HELPER_SQL))
    connection.execute(
        text("SELECT pg_temp.gap_closure_grant_app_role(:username, :database)"),
        {"username": username, "database": database_name},
    )


def downgrade() -> None:
    username, _ = _app_role_credentials()
    connection = op.get_bind()
    database_name = connection.exec_driver_sql("SELECT current_database()").scalar()
    connection.execute(text(_REVOKE_HELPER_SQL))
    connection.execute(
        text("SELECT pg_temp.gap_closure_revoke_app_role(:username, :database)"),
        {"username": username, "database": database_name},
    )
