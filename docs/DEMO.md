# Praetor Demo

This repository currently has a polished fixture-backed frontend plus a deterministic backend demo path.

## Local checks

```bash
npm test
cd apps/web && npm run build
docker compose -f infra/compose/docker-compose.yml config
```

On Windows shells without `make`, use `npm test` or `scripts/test.ps1`.

## Runtime scripts

```bash
npm run demo      # API + web, demo mode, in-memory data
npm run prod      # API + web, production mode, Postgres data backend
npm run demo:api  # API only, demo mode
npm run prod:api  # API only, production mode
npm run demo:web  # web only, dev server
npm run prod:web  # web only, built Next server
npm run seed:prod # seed production Postgres demo data
npm run reset:prod # clear and reseed production Postgres demo data
npm run clear:prod # clear production Postgres rows without demo reseed
npm run verify:audit -- <json-sidecar> --signature <signature>
```

Production API startup runs `alembic upgrade head` automatically before Uvicorn by default. Set
`PRAETOR_AUTO_MIGRATE=0` only when migrations are managed by separate deployment automation.

Frontend data source modes:

```powershell
$env:NEXT_PUBLIC_DATA_SOURCE='fixtures' # frontend-only demo, no API product data
$env:NEXT_PUBLIC_DATA_SOURCE='api'      # production API only, no fixture fallback
$env:NEXT_PUBLIC_DATA_SOURCE='hybrid'   # local dev only, API with fixture fallback
```

For Docker Compose, choose the env file explicitly:

```powershell
$env:PRAETOR_ENV_FILE='.env.demo.example'
$env:NEXT_PUBLIC_DATA_SOURCE='fixtures'
$env:NEXT_PUBLIC_PRAETOR_DATA_MODE='demo'
docker compose -f infra/compose/docker-compose.yml up

$env:PRAETOR_ENV_FILE='.env.production.example'
$env:NEXT_PUBLIC_DATA_SOURCE='api'
$env:NEXT_PUBLIC_PRAETOR_DATA_MODE='production'
docker compose -f infra/compose/docker-compose.yml up
```

The Docker Compose default is now production/API-only. Use the demo env and `NEXT_PUBLIC_DATA_SOURCE=fixtures` explicitly when you want the scripted fixture frontend.

## Live Docker verification

The current Compose stack has been booted and checked locally:

1. API, web, workflow, sandbox, Postgres, Redis, MinIO, OPA, and MCP stubs start from `infra/compose/docker-compose.yml`.
2. OPA, Postgres, Redis, and MinIO report healthy.
3. `GET http://localhost:8000/health` returns demo mode with the in-memory backend.
4. `GET http://localhost:3000` returns HTTP 200.
5. `POST /workflows/code_compliance_scan:run` emits a valid hash-chained event history through `GET /events`.
6. `/ws/v1/workflow-runs/{id}/stream?token=dev` accepts a live WebSocket connection and streams workflow events.
7. `alembic upgrade head` succeeds inside the API container and creates the initial Postgres schema.
8. A production-mode workflow persistence smoke test inside the API container writes and reads the `code_compliance_scan` workflow, asset, run, step-run, selected model/provider, and finding rows in Postgres.
9. A production-mode event persistence smoke test inside the API container writes six `agent_event` rows and reads a valid hash chain back from Postgres.
10. A production-mode hook persistence smoke test inside the API container seeds hook registry rows and records a `github_stub/open_pr` call in Postgres.
11. A production-mode corpus persistence smoke test inside the API container seeds corpus rows, persists document/chunk rows, and returns the expected lexical search result.
12. A production-mode review/evidence/audit smoke test inside the API container persists finding/proposal/sandbox lifecycle state, writes an evidence record, and creates PDF + JSON audit artifacts with an Ed25519 signature.
13. The frontend API client calls the FastAPI gateway for implemented routes when `NEXT_PUBLIC_API_BASE` is set and opens real WebSockets unless `NEXT_PUBLIC_MOCK_STREAMS=1`.
14. The sandbox service exposes `/health` and `/launch`; launch runs through the mounted Docker socket with `compose-sandbox:latest` and falls back to deterministic replay if Docker is unavailable.
15. Production-mode DB integration tests run against local/CI Postgres and Redis with `PRAETOR_RUN_DB_TESTS=1`.
16. Production API startup auto-applies Alembic migrations for fresh Docker volumes, and `GET /hooks`, `GET /hook-calls`, and `GET /evidence-records` return HTTP 200 with CORS headers for `http://localhost:3000`.

The default Compose stack now uses production/API-only mode. Production mode has Postgres-backed slices for workflow templates, workflow event history, deterministic hook operations, corpus ingest/search, findings, proposed changes, sandbox run state, evidence records, and audit packets. The frontend no longer falls back to fixtures when `NEXT_PUBLIC_DATA_SOURCE=api`.

Production mode now registers and runs every bundled deterministic workflow template through Postgres-backed workflow-run and step-run persistence. The next runtime milestone is durable node-run scheduling with pause/resume, retries, parallel joins, and graph snapshots as described in `docs/INTEGRATIONS_AND_NODE_WORKFLOWS.md`.

## Implemented backend path

1. `GET /health` requires `Authorization: Bearer dev`.
2. `POST /policy:evaluate` denies Northwind `send_email` calls to non-allowlisted domains and prompt-injection content.
3. `POST /workflows/code_compliance_scan:run` creates a deterministic run that emits a high-severity finding.
4. `POST /corpora/{id}/documents:ingest` and `POST /corpora/{id}:search` provide minimal markdown chunking and lexical search.
5. `POST /hooks/github_stub:test` verifies the hook registry surface and uses the MCP-style adapter boundary in production mode.
6. `POST /proposed-changes/{id}:sandbox-run`, `:approve`, and `:apply` drive the demo remediation path.
7. `POST /audit-packets:generate` returns a deterministic signed-packet stand-in.
8. `GET /models/providers`, `GET /models/readiness`, `POST /models:check`, and `POST /models:complete` allow per-request model/provider selection across OpenAI, Anthropic, and Google adapters.
9. `GET /runtime/readiness` reports model key and JSON Stack integration secret readiness without exposing secret values.
10. `POST /hooks/{id}:call` records externally reliant GitHub, Slack, local-files, and JSON Stack operations; non-dry-run JSON Stack calls resolve `auth_ref` secrets from environment variables.
11. `GET /events` and `WS /ws/v1/.../stream?token=dev` expose hash-chained workflow events.
12. `npm run test:e2e` runs the critical live platform path in one command across API readiness, workflows, MCP/JSON Stack hooks, corpus, sandbox logs, evidence sweep, audit packets, and web routes.
13. `npm run test:e2e:web` runs the Playwright UI suite across desktop and mobile. By default it starts an isolated fixture-mode web server on port 3100 and writes PNG evidence to `screenshots/e2e/`; set `PRAETOR_E2E_USE_EXISTING_SERVER=1` to point it at a running Docker/web stack.

The current backend is intentionally deterministic. It is ready for replacing in-memory services with Postgres/Redis-backed implementations behind the same routes.
