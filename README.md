# Praetor

Praetor is a governed runtime for agentic GRC workflows. It runs compliance
workflows against a customer's systems, supervises production AI agents, records
policy decisions and tool calls, and produces evidence/audit packets from the
same event trail.

This repository was built for the 2026 Lyra x Relevance AI x January Capital x
OpenAI hackathon.

## What is in this repo

| Path | Purpose |
| --- | --- |
| `apps/web` | Next.js 15 + React 19 operator UI |
| `apps/api` | FastAPI control-plane API |
| `apps/workflow` | Typed DAG workflow runtime and bundled templates |
| `apps/sandbox` | Sandbox orchestrator used for agent/proposed-change replay |
| `packages/sdk-py` | Small Python SDK helpers |
| `packages/hooks` | MCP-style hook stubs used by the local stack |
| `content` | Seed corpora, obligations, and policy controls |
| `infra/compose` | Docker Compose stack for API, web, worker, data stores, OPA, and stubs |
| `scripts` | Setup, run, seed, test, e2e, and audit verification scripts |
| `docs` | API, workflow, demo, testing, integration, and handoff notes |

## Platform shape

Praetor has two related surfaces:

- Workflow runtime: agentic compliance workflows such as code compliance scans,
  vendor risk reviews, policy gap analysis, evidence collection, and AI system
  intake.
- Supervision: runtime governance for production agents, tools, datasets, hooks,
  findings, approvals, and audit evidence.

Both surfaces share the same control plane concepts: assets, workflows,
hash-chained events, policy gates, human gates, sandbox runs, findings,
proposed changes, evidence records, and audit packets.

## Prerequisites

- Node.js 20 or newer
- npm
- Python 3.12 or newer
- Docker Desktop or Docker Engine with Compose, for the full stack

Optional provider/integration keys can be supplied through the env files in
`infra/compose`. The default local auth token is `dev`.

## Setup

Install the local web and Python packages from the repo root:

```bash
npm run setup
```

That wraps:

```bash
npm install --prefix apps/web
python -m pip install -e "apps/api[dev]"
python -m pip install -e apps/workflow
```

For Python isolation, create and activate a virtual environment before running
`npm run setup`.

## Quick start

Start API and web in deterministic demo mode:

```bash
npm run demo
```

Open:

- Web UI: `http://localhost:3000`
- API health: `http://localhost:8000/health`
- API docs: `http://localhost:8000/docs`

Demo mode uses in-memory backend state and seeds deterministic data. It is the
fastest path for the hackathon demo and UI exploration.

## Common commands

```bash
npm run setup          # install web dependencies and editable Python packages
npm run demo           # API + web in demo mode
npm run prod           # API + web in production mode
npm run demo:api       # API only, demo mode
npm run prod:api       # API only, production mode
npm run demo:web       # web only, Next dev server
npm run prod:web       # web only, built Next server
npm run seed:prod      # seed production Postgres demo data
npm run reset:prod     # clear and reseed production data
npm run clear:prod     # clear production rows
npm test               # API tests, workflow tests, sandbox tests, web typecheck/build
npm run test:e2e       # live platform e2e checks against a running stack
npm run test:e2e:web   # Playwright UI suite
```

On Windows without `make`, use the npm scripts above or `scripts/test.ps1`.

## Runtime modes

The API has two data modes:

- `PRAETOR_DATA_MODE=demo`: deterministic in-memory services.
- `PRAETOR_DATA_MODE=production`: Postgres-backed services with Redis event
  streaming and production-shaped persistence.

The frontend has three data source modes:

- `NEXT_PUBLIC_DATA_SOURCE=fixtures`: UI fixture data only, no API product data.
- `NEXT_PUBLIC_DATA_SOURCE=api`: API-only, no fixture fallback.
- `NEXT_PUBLIC_DATA_SOURCE=hybrid`: API with fixture fallback for local demos.

The run scripts set sensible defaults. For manual work, the most important env
vars are:

```bash
PRAETOR_DATA_MODE=demo
PRAETOR_SEED_DEMO_DATA=1
PRAETOR_AUTH_MODE=dev_bearer
DEV_BEARER=dev
NEXT_PUBLIC_API_BASE=http://localhost:8000
NEXT_PUBLIC_API_TOKEN=dev
NEXT_PUBLIC_DATA_SOURCE=hybrid
```

Model calls are controlled by:

```bash
DEFAULT_MODEL_PROVIDER=openai
DEFAULT_MODEL_NAME=gpt-5.4-mini
PRAETOR_AGENT_MODEL_MODE=auto
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
```

`PRAETOR_AGENT_MODEL_MODE=auto` uses a live provider when a key exists and falls
back to deterministic dry-run output otherwise. Use `dry_run` to avoid external
model calls entirely, or `live` to require a configured provider.

## Full Docker stack

The Compose stack includes Postgres with pgvector, Redis, MinIO, OPA, FastAPI,
the workflow worker, sandbox orchestrator, MCP hook stubs, and the Next.js web
app.

Demo-flavoured Compose run:

```powershell
$env:PRAETOR_ENV_FILE='.env.demo.example'
$env:NEXT_PUBLIC_DATA_SOURCE='fixtures'
$env:NEXT_PUBLIC_PRAETOR_DATA_MODE='demo'
docker compose -f infra/compose/docker-compose.yml up --build
```

Production-shaped Compose run:

```powershell
$env:PRAETOR_ENV_FILE='.env.production.example'
$env:NEXT_PUBLIC_DATA_SOURCE='api'
$env:NEXT_PUBLIC_PRAETOR_DATA_MODE='production'
docker compose -f infra/compose/docker-compose.yml up --build
```

Equivalent Unix shell:

```bash
PRAETOR_ENV_FILE=.env.production.example \
NEXT_PUBLIC_DATA_SOURCE=api \
NEXT_PUBLIC_PRAETOR_DATA_MODE=production \
docker compose -f infra/compose/docker-compose.yml up --build
```

The production API startup runs `alembic upgrade head` by default. Set
`PRAETOR_AUTO_MIGRATE=0` only when migrations are handled by separate release
automation.

## API surface

Local demo auth uses:

```bash
Authorization: Bearer dev
```

Core endpoints include:

- `GET /health`, `GET /runtime/config`, `GET /runtime/readiness`
- `GET /workflows`, `POST /workflows/{id}:run`
- `GET /workflow-runs`, `GET /workflow-runs/{id}`
- `POST /workflow-runs/{id}:resume`, `POST /workflow-runs/{id}:cancel`
- `GET /events?workflow_run_id=...`
- `WS /ws/v1/workflow-runs/{id}/stream?token=dev`
- `GET /assets`, `GET /obligations`, `GET /controls`
- `POST /corpora/{id}/documents:ingest`, `POST /corpora/{id}:search`
- `GET /hooks`, `POST /hooks/{id}:test`, `POST /hooks/{id}:call`
- `GET /findings`, `GET /evidence-records`
- `POST /proposed-changes/{id}:sandbox-run`
- `POST /proposed-changes/{id}:approve`, `POST /proposed-changes/{id}:apply`
- `POST /audit-packets:generate`
- `GET /models/providers`, `POST /models:check`, `POST /models:complete`,
  `POST /models:stream`

See `docs/API.md` for request/response detail.

## Workflow templates

Bundled deterministic templates:

- `code_compliance_scan`
- `code_compliance_scan_full`
- `vendor_risk_review`
- `policy_gap_analysis`
- `evidence_collection`
- `ai_system_intake`

Workflow steps support hook reads/writes, corpus queries, agent execution,
transforms, policy gates, human gates, findings, and proposed changes. Production
mode persists workflow runs, step runs, event history, policy decisions,
sandbox runs, hook calls, findings, proposed changes, evidence, and audit
packets.

## Testing

Run the default local verification:

```bash
npm test
```

This runs API pytest, workflow pytest, sandbox pytest, web typecheck, and web
production build through a cross-platform Node script.

Run live platform checks after starting a stack:

```bash
npm run test:e2e
```

Run only API-side e2e checks:

```bash
python scripts/e2e_platform.py --skip-web
```

Run the Playwright UI suite:

```bash
npm run test:e2e:web
```

See `docs/TESTING.md` for the full test matrix.

## Evidence and audit verification

Generate audit packets through the UI or `POST /audit-packets:generate`.
Verify an exported packet sidecar and signature with:

```bash
npm run verify:audit -- <json-sidecar> --signature <signature>
```

## Useful docs

- `docs/DEMO.md`: demo and runtime script notes
- `docs/API.md`: endpoint reference
- `docs/WORKFLOWS.md`: operator walkthrough and UI flows
- `docs/TESTING.md`: local, e2e, and UI test instructions
- `docs/INTEGRATIONS_AND_NODE_WORKFLOWS.md`: integration and workflow runtime architecture
- `docs/AUTH_AND_SECRETS.md`: auth modes, JWT/OIDC, and secret backends
- `docs/IMPLEMENTATION_HANDOFF.md`: current platform state and remaining hardening work

## Development notes

- The web app is intentionally routed through `apps/web/lib/api/index.ts`; pages
  call named API helpers rather than raw `fetch`.
- Demo data is deterministic so the same workflow paths can be replayed for
  pitches and regression checks.
- Production mode is still local-production-shaped: it exercises persistence,
  migrations, auth boundaries, secrets, Redis streams, sandbox replay, and hook
  dispatch, but live external writes should stay in dry-run mode unless the
  destination secret and approval path are configured.
- Generated files such as `.egg-info`, screenshots, logs, and output artifacts
  are not part of the source handoff unless explicitly needed.
