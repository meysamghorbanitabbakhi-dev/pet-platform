# K9 changed-file manifest

Base revision: `1da656bcd5e08310596a5c77e5cad4f421e74691`

This manifest records the final K9 worktree content expected for handoff and archive packaging.

## K9.4 additions

- `GATE_K9_PROGRESS.md`
- `BACKEND_FRONTEND_INTEGRATION_CONTRACT.md`
- `K9_CHANGED_FILE_MANIFEST.md`
- `docs/api/k9-test-summary.md`
- `docs/migrations/k9-migration-notes.md`
- `fixtures/demo/v2-frontend.json`
- `migrations/versions/20260716_0013_knowledge_lifecycle.py`
- `tests/unit/test_k9_4_acceptance.py`

## Existing K9 artifacts reconciled in K9.4

- `API_ENDPOINT_CATALOG.md`
- `BACKEND_SYSTEM_MAP.md`
- `docs/adr/ADR-004-k9-policy-boundaries.md`
- `docs/api/examples.json`
- `docs/api/frontend-integration.md`
- `docs/api/openapi.json`
- `openapi.json`

## Package exclusions

The final archive excludes `.git`, `.env`, secrets, caches, virtual environments, temporary files, pytest output and older archives.
