"""Replace evidence_path strings with evidence_file_id FKs (Workstream 5B).

Revision ID: 20260720_0037
Revises: 20260720_0036

trust_supplier_assurances.evidence_path and
trust_reference_price_evidence.evidence_path were always populated from a
real EvidenceFile.storage_key at insert time (see the operator routes
this migration's paired app-code change updates), so the backfill below
is a lossless, exact join on that unique column -- not a best-effort
guess. Storage existence and checksum validation already happened once,
at upload time (app.api.routes.operator.upload_evidence_file writes the
file to storage before creating the EvidenceFile row), so the new FK
inherits that guarantee by construction; nothing here re-validates the
filesystem.

evidence_path itself is intentionally left in place, unmapped from the
ORM as of this revision, rather than dropped in the same migration that
introduces its replacement -- see the "avoid destructive column removal
until replacement data is verified" migration requirement. It is relaxed
to nullable (existing rows keep their value; the ORM simply stops writing
it) since new rows are created through evidence_file_id from here on. A
follow-up migration can drop both evidence_path columns once this has run
in production for a while with no fallback needed.

Rollback limitation: downgrade restores evidence_path to NOT NULL, which
will fail if any row inserted after this migration ran has a NULL
evidence_path (expected, since the application no longer populates it) --
downgrading past this revision requires either backfilling evidence_path
by hand first or accepting data loss on those rows.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_0037"
down_revision: str | None = "20260720_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ASSURANCES = "trust_supplier_assurances"
_REFERENCE_EVIDENCE = "trust_reference_price_evidence"
_FILES = "trust_evidence_files"


def _add_backfill_and_lock(table: str) -> None:
    op.add_column(table, sa.Column("evidence_file_id", sa.Uuid(), nullable=True))
    op.execute(
        f"UPDATE {table} SET evidence_file_id = {_FILES}.id "
        f"FROM {_FILES} WHERE {_FILES}.storage_key = {table}.evidence_path"
    )
    connection = op.get_bind()
    unresolved = connection.execute(
        sa.text(f"SELECT count(*) FROM {table} WHERE evidence_file_id IS NULL")
    ).scalar_one()
    if unresolved:
        raise RuntimeError(
            f"{table}: {unresolved} row(s) have an evidence_path that does not match any "
            f"{_FILES}.storage_key -- cannot backfill evidence_file_id safely. Investigate "
            "before re-running this migration."
        )
    op.alter_column(table, "evidence_file_id", nullable=False)
    op.create_foreign_key(
        f"{table}_evidence_file_id_fkey", table, _FILES, ["evidence_file_id"], ["id"]
    )
    # The ORM no longer writes evidence_path; relax the legacy NOT NULL so
    # new inserts (which populate evidence_file_id only) succeed. Existing
    # rows keep their value untouched.
    op.alter_column(table, "evidence_path", nullable=True)


def upgrade() -> None:
    _add_backfill_and_lock(_ASSURANCES)
    _add_backfill_and_lock(_REFERENCE_EVIDENCE)


def downgrade() -> None:
    op.alter_column(_REFERENCE_EVIDENCE, "evidence_path", nullable=False)
    op.drop_constraint(
        f"{_REFERENCE_EVIDENCE}_evidence_file_id_fkey", _REFERENCE_EVIDENCE, type_="foreignkey"
    )
    op.drop_column(_REFERENCE_EVIDENCE, "evidence_file_id")
    op.alter_column(_ASSURANCES, "evidence_path", nullable=False)
    op.drop_constraint(f"{_ASSURANCES}_evidence_file_id_fkey", _ASSURANCES, type_="foreignkey")
    op.drop_column(_ASSURANCES, "evidence_file_id")
