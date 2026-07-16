"""Resumable knowledge release activation runs.

Revision ID: 20260716_0016
Revises: 20260716_0015
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0016"
down_revision: str | None = "20260716_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pet_knowledge_activation_runs",
        sa.Column("release_id", sa.Uuid(), nullable=False),
        sa.Column("previous_release_id", sa.Uuid()),
        sa.Column("evidence_file_id", sa.Uuid(), nullable=False),
        sa.Column("expected_release_checksum_sha256", sa.String(64), nullable=False),
        sa.Column("expected_guidance_count", sa.Integer(), nullable=False),
        sa.Column("expected_benchmark_candidate_count", sa.Integer(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_review_at", sa.DateTime(timezone=True)),
        sa.Column("limitations_fa", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("preflight_report", postgresql.JSONB(), nullable=False),
        sa.Column("result_report", postgresql.JSONB()),
        sa.Column("created_by_operator_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("rolled_back_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(100)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('ready','blocked','running','completed','rolled_back','failed')",
            name="ck_pet_knowledge_activation_runs_valid_status",
        ),
        sa.CheckConstraint(
            "expected_guidance_count >= 0 AND expected_benchmark_candidate_count >= 0",
            name="ck_pet_knowledge_activation_runs_nonnegative_expected_counts",
        ),
        sa.ForeignKeyConstraint(
            ["release_id"], ["pet_knowledge_releases.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["previous_release_id"], ["pet_knowledge_releases.id"]
        ),
        sa.ForeignKeyConstraint(["evidence_file_id"], ["trust_evidence_files.id"]),
        sa.ForeignKeyConstraint(
            ["created_by_operator_id"], ["identity_auth_identities.id"]
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pet_knowledge_activation_runs"),
        sa.UniqueConstraint(
            "release_id", name="uq_pet_knowledge_activation_runs_one_activation_per_release"
        ),
    )
    for column in ("release_id", "previous_release_id", "created_by_operator_id"):
        op.create_index(
            f"ix_pet_knowledge_activation_runs_{column}",
            "pet_knowledge_activation_runs",
            [column],
        )


def downgrade() -> None:
    op.drop_table("pet_knowledge_activation_runs")
