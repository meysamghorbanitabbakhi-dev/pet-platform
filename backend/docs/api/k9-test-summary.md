# K9 test summary

> **Historical snapshot — not current release authority.**
> See `backend/release-contract.json`.

Base revision: `1da656bcd5e08310596a5c77e5cad4f421e74691`

Final verification results are updated during the K9.4 verification pass.

| Command | Result |
|---|---|
| `ruff check .` | exit 0 |
| `mypy app` | success, 135 source files |
| `pytest` | 105 passed, 172 warnings |
| `alembic heads` | `20260716_0021 (head)` |
| PostgreSQL upgrade → downgrade → upgrade | exit 0 in isolated Compose project `pet-platform-policy` |
| OpenAPI export/comparison | exported, 1 passed |
| `docker compose config --quiet` | exit 0 using temporary `.env` copied from tracked `.env.example` |
| `git diff --check` | exit 0 |
| Archive extraction verification | files=260, one Alembic head, compile/import check passed, manifest and OpenAPI matched |

## Warning classification

- Project-owned K9 warnings fixed or outstanding: 0.
- Third-party/environment warnings documented: 172.
- Source: `pytest-asyncio` deprecations on Python 3.14 event-loop policy APIs.
- Count detail: 1 warning at `pytest_asyncio/plugin.py:1216`; 171 repeated warnings across `plugin.py:874`, `772`, `777`, `1183`, `889`, `794`, `942`, `966`, and `978` from 19 async test contexts.
