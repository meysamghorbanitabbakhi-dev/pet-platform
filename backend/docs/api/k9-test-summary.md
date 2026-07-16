# K9 test summary

Base revision: `1da656bcd5e08310596a5c77e5cad4f421e74691`

Final verification results are updated during the K9.4 verification pass.

| Command | Result |
|---|---|
| `ruff check .` | exit 0 |
| `mypy app` | success, 135 source files |
| `pytest` | 102 passed, 136 warnings |
| `alembic heads` | `20260716_0021 (head)` |
| PostgreSQL upgrade → downgrade → upgrade | exit 0 in isolated Compose project `pet-platform-k94` |
| OpenAPI export/comparison | exported, 1 passed |
| `docker compose config --quiet` | exit 0 using temporary `.env` copied from tracked `.env.example` |
| `git diff --check` | exit 0 |
| Archive extraction verification | files=260, one Alembic head, compile/import check passed, manifest and OpenAPI matched |
