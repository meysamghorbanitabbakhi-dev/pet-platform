"""Backend-owned Persian catalog offer search (G5-SHOP-14).

Revision ID: 20260719_0027
Revises: 20260718_0026

Adds a real, indexed, backend-owned search capability over the existing
catalog_offers table instead of client-side filtering of whatever page of
/shop happens to be loaded. Normalization mirrors
app.modules.pet_knowledge.search.normalize_persian_search exactly (NFKC,
Arabic-to-Persian yeh/kaf/teh-marbuta/heh-hamza folding, stripping Unicode
combining marks -- i.e. Arabic diacritics -- ZWNJ collapsed to a space,
casefold, whitespace collapse), re-implemented in SQL as an IMMUTABLE
function so it can back a STORED GENERATED column and a real index rather
than a Python-side scan. Verified byte-for-byte equivalent to the Python
reference function against a live PostgreSQL 17 instance for mixed
Arabic/Persian text, embedded diacritics, ZWNJ, mixed-script input, and
empty/whitespace input before this migration was written.

title_fa_search/sku_search are STORED GENERATED columns (computed by
PostgreSQL itself from title_fa/sku), so every existing row is populated as
part of adding the column -- no separate backfill step, and no risk of the
generated value drifting from a Python-side write path. pg_trgm GIN indexes
back substring ("contains") search at catalog scale.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0027"
down_revision: str | None = "20260718_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "catalog_offers"

_NORMALIZE_FUNCTION_SQL = "\nCREATE OR REPLACE FUNCTION fa_normalize_search_text(input text)\nRETURNS text\nLANGUAGE sql\nIMMUTABLE\nPARALLEL SAFE\nAS $$\n  SELECT trim(\n    regexp_replace(\n      lower(\n        replace(\n          regexp_replace(\n            translate(\n              normalize(coalesce(input, ''), NFKC),\n              E'يكةۀ',\n              E'یکهه'\n            ),\n            E'[\\u0610-\\u061a\\u064b-\\u065f\\u0670\\u06d6-\\u06dc\\u06df-\\u06e4\\u06e7-\\u06e8\\u06ea-\\u06ed\\u08ca-\\u08e1\\u08e3-\\u08ff]', '', 'g'\n          ),\n          E'\u200c', ' '\n        )\n      ),\n      '\\s+', ' ', 'g'\n    )\n  )\n$$;\n"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(_NORMALIZE_FUNCTION_SQL)
    op.add_column(
        _TABLE,
        sa.Column(
            "title_fa_search",
            sa.Text(),
            sa.Computed("fa_normalize_search_text(title_fa)", persisted=True),
            nullable=False,
        ),
    )
    op.add_column(
        _TABLE,
        sa.Column(
            "sku_search",
            sa.Text(),
            sa.Computed("fa_normalize_search_text(sku)", persisted=True),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_catalog_offers_title_fa_search_trgm",
        _TABLE,
        ["title_fa_search"],
        postgresql_using="gin",
        postgresql_ops={"title_fa_search": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_catalog_offers_sku_search_trgm",
        _TABLE,
        ["sku_search"],
        postgresql_using="gin",
        postgresql_ops={"sku_search": "gin_trgm_ops"},
    )


def downgrade() -> None:
    # pg_trgm is intentionally left installed on downgrade: it is a shared,
    # harmless extension, and dropping it could break other future users of
    # it. Only this migration's own objects are removed.
    op.drop_index("ix_catalog_offers_sku_search_trgm", table_name=_TABLE)
    op.drop_index("ix_catalog_offers_title_fa_search_trgm", table_name=_TABLE)
    op.drop_column(_TABLE, "sku_search")
    op.drop_column(_TABLE, "title_fa_search")
    op.execute("DROP FUNCTION IF EXISTS fa_normalize_search_text(text)")
