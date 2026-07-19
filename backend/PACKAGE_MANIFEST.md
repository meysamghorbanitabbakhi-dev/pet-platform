# Package manifest

This package is the complete backend snapshot through Gate K8.

Included:

- FastAPI application and all domain modules.
- Integration ports and adapters for Zarinpal, Payamak Panel and filesystem storage.
- Outbox worker and scheduler.
- Alembic migrations through the head recorded in `release-contract.json` (`alembic.heads`) — do not hardcode a revision id here.
- Dockerfile, local Docker Compose and hardened production override.
- Automated tests and development configuration.
- Checked OpenAPI JSON; path/operation counts are governed by `release-contract.json`, not restated here.
- Architecture decisions, runbooks, gate reports and deterministic fixtures.
- `BACKEND_SYSTEM_MAP.md` and `API_ENDPOINT_CATALOG.md`.
- The final collector `1.6.1` ZIP as an approved release input, kept as a separate nested archive.

Excluded intentionally (matches `.gitignore`; enforced by `scripts/build-release-archive.sh` at the repo root, which builds the archive via `git archive` — so nothing untracked or gitignored can ever be included — and then verifies the result actually contains what this manifest describes and excludes what it excludes, rather than leaving that as unverified intent):

- Local virtual environment and Python caches.
- Test/type/lint caches.
- Provider credentials, secrets and `.env` runtime values.
- PostgreSQL, Redis and uploaded-media volume contents.
- Superseded and under-review collector working files.

The archive is a source handoff, not proof that live provider or Docker Compose certification has
passed. See `BACKEND_SYSTEM_MAP.md` for current evidence and remaining launch gates.

The included final collector ZIP is evidence-bearing source input. It has been structurally verified
by the implementation workflow and the user confirmed certified veterinary approval. It is not
treated as active application data until an operator records the private reviewer/evidence details
and completes the import and activation workflow against the target PostgreSQL database.
