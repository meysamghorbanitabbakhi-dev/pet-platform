# Pet Platform Frontend - Gate 5.2D-A

Next.js App Router + React + strict TypeScript implementation of the Gate 5.2D-A frontend slice.

## Stack

- Next.js App Router
- React
- TypeScript strict mode
- pnpm
- TanStack Query
- OpenAPI-generated types via `openapi-typescript`
- React Hook Form + Zod
- Vitest + Testing Library
- Playwright + axe accessibility checks
- Bundled Fontsource fonts only

## Commands

```bash
pnpm install
pnpm generate:api
pnpm check:contract
pnpm typecheck
pnpm lint
pnpm format
pnpm test
pnpm test:e2e
pnpm build
```

`pnpm check:contract` verifies `../../backend/openapi.json`, required schemas, policy field count, migration head compatibility, and generated type drift.

## Runtime

Set `NEXT_PUBLIC_API_BASE_URL` to the backend origin. Test-only fixture mode is available with:

```bash
GATE_FIXTURE_MODE=1
```

Do not enable fixture mode in production.

## Docker

```bash
docker build -t pet-platform-frontend:gate-5.2d-a .
docker compose up frontend
```

The image uses Next.js standalone output.
