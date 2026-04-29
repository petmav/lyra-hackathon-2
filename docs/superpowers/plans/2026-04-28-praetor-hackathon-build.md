# Praetor Hackathon Build — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a working Praetor demo in 60 hours: a single control plane that (1) runs governed agentic GRC workflows on a customer's stack and (2) supervises the customer's production AI, with both surfaces visible in the same UI, hash-chained, and audit-packet-able.

**Architecture:** Eight backend subsystems (Inventory, Obligations, Policy, Telemetry, Corpus, Evidence, Workflow Runtime, Sandbox Orchestrator) plus a Hook Layer (MCP-native), behind a FastAPI gateway, fronted by Next.js. Every workflow agent step runs in a Docker sandbox and is itself a first-class governed Asset — that is the architectural moat.

**Tech Stack:** Next.js 15 / React 19 / Tailwind / shadcn / React Flow • FastAPI / Python 3.12 / Pydantic v2 • Postgres 16 + pgvector + TimescaleDB • Redis Streams • MinIO • OPA (Rego) • Docker (gVisor when avail.) • LangGraph • Anthropic SDK (Sonnet/Opus) • MCP SDK • Celery/RQ workers.

**Scope note:** This spec covers multiple independent subsystems. The five heaviest have been spun off into their own sub-plans (referenced inline below). This master plan owns the build sequence, shared contracts, demo critical path, and integration glue. Sub-plans own their subsystem internals at step granularity.

## Sub-plans

- **`2026-04-28-workflow-runtime.md`** — DAG model, templating, runtime advance loop, all 9 step executors, run state machine. Used by Phase 2 Task 2.5 and Phase 3 Tasks 3.1–3.2, 3.6–3.7.
- **`2026-04-28-sandbox-orchestrator.md`** — Docker container lifecycle, harness inside the sandbox, MCP bridge sidecar, replay mode. Used by Phase 3 Task 3.4 (with a throwaway in-process fallback for Phase 2).
- **`2026-04-28-hook-layer-mcp.md`** — MCP client, hook registry, three stub MCP servers (GitHub, Slack, local-files), HTTP fallback proxy, platform-as-MCP-server export, effect-radius gating. Used by Phase 2 Task 2.6 and Phase 3 Task 3.3.
- **`2026-04-28-corpus-management.md`** — corpus + document + chunk schema, ingestion, hybrid retrieval (RRF), versioned snapshots, obligation hydration from YAML, five seed corpora. Used by Phase 2 Task 2.4 and Phase 3 Task 3.8.
- **`2026-04-28-evidence-and-audit-packet.md`** — Evidence Generator worker, ReportLab-backed audit packet PDF, obligation graph rendering, Ed25519 signing, external verification CLI. Used by Phase 4 Tasks 4.1–4.2.

The master plan stays load-bearing for: §0 critical path, §1 file structure, §2 shared contracts (entities/events/endpoints), Phase 1 bootstrap (full step granularity), and Phase 2–5 task ordering and integration glue. Open a sub-plan when starting work on its subsystem.

---

## 0. Demo Critical Path (what MUST work at hour 60)

Cut anything not on this path before adding anything not on this path.

1. `docker compose up` brings the whole stack up clean on a laptop.
2. `make demo` resets state and seeds: 1 production agent (Northwind support-bot), 5 corpora (EU AI Act excerpt, ISO 42001 excerpt, GDPR Art 5, internal data-min policy, OWASP Agent Top 10), 5 workflow templates, 3 stub MCP hooks (GitHub, Slack, local-files), 2 pre-canned past runs, 1 canned violation scenario.
3. **Workflow surface:** GRC analyst opens Workflows → instantiates `code_compliance_scan` → workflow runs → live DAG view streams agent thoughts/memory/policy → Finding emitted with citations → ProposedChange with sandbox-tested patch → human approval → outbound MCP opens GitHub PR.
4. **Supervision surface:** open Northwind support-bot → replay malicious-email injection prompt → tool refusal logged as **evidence**, not violation (because the patch was applied) → live three-pane view identical layout to the workflow agent view.
5. **Audit packet:** click Generate → signed PDF covers workflow run + finding + proposed change + approval + applied PR + supervision evidence + obligation graph.

If hour 50 looks bad, drop in priority order: scheduled triggers, parallel branches, vendor risk + policy gap templates, corpus search UI, hook health checks, multi-asset dashboard polish.

---

## 1. File Structure

This is the target tree. Phase 1 creates the skeleton; later phases fill in.

```
praetor/
├── apps/
│   ├── api/                        # FastAPI gateway + services
│   │   ├── praetor_api/
│   │   │   ├── main.py
│   │   │   ├── settings.py
│   │   │   ├── db.py               # async SQLAlchemy + pgvector
│   │   │   ├── bus.py              # Redis Streams publisher + consumer
│   │   │   ├── hashchain.py        # per-asset hash chain helper
│   │   │   ├── routers/            # one file per resource (assets, events, ...)
│   │   │   ├── services/           # one file per subsystem service
│   │   │   ├── models/             # SQLAlchemy ORM models
│   │   │   ├── schemas/            # Pydantic request/response schemas
│   │   │   └── ws/                 # WebSocket hubs
│   │   └── alembic/
│   ├── workflow/                   # Workflow Runtime worker
│   │   ├── praetor_workflow/
│   │   │   ├── runtime.py          # advance() loop
│   │   │   ├── dag.py              # DAG model + topo + frontier
│   │   │   ├── templating.py       # {{ steps.x.y }} resolver
│   │   │   └── executors/          # one file per step type
│   │   └── templates/              # YAML workflow definitions
│   ├── sandbox/                    # Sandbox Orchestrator worker
│   │   ├── praetor_sandbox/
│   │   │   ├── orchestrator.py
│   │   │   ├── docker_runtime.py
│   │   │   ├── mcp_bridge.py       # outbound-MCP mediator
│   │   │   ├── replay.py
│   │   │   └── harness/entrypoint.py
│   │   └── images/runtime/Dockerfile
│   ├── web/                        # Next.js 15 frontend
│   │   ├── app/                    # one folder per route
│   │   ├── components/             # one folder per feature widget
│   │   └── lib/                    # api client, ws client, types
│   └── demo-agent/
│       └── northwind/              # the production agent we supervise
├── packages/
│   ├── sdk-py/                     # praetor SDK preinstalled in sandbox
│   ├── sdk-ts/
│   └── hooks/
│       ├── mcp_client/
│       ├── connectors/             # native (none real at hackathon)
│       └── http_proxy/
├── content/
│   ├── obligations/                # YAML obligation libraries
│   ├── controls/                   # Rego policies
│   ├── corpora_seed/               # markdown seed docs
│   └── prompts/                    # system prompts for workflow agents
├── infra/compose/
│   ├── docker-compose.yml
│   └── .env.example
├── scripts/
│   ├── seed_demo.py
│   └── demo_run.sh
├── docs/
│   ├── PRAETOR_PLAN.md             # source of truth (the V2 PDF, transcribed)
│   ├── ARCHITECTURE.md
│   ├── WORKFLOW_AUTHORING.md
│   └── DEMO.md
├── Makefile
└── README.md
```

---

## 2. Shared Contracts (used by every phase — define once, reference always)

### 2.1 Core entities (Postgres tables; SQLAlchemy models in `apps/api/praetor_api/models/`)

All entities have: `id` (uuid), `urn`, `created_at`, `updated_at`, `created_by`, `version`. URN format: `urn:praetor:<entity-type>:<tenant>:<slug>`.

| Table | Key columns | Notes |
|---|---|---|
| `asset` | type, name, owner_id, risk_tier(L1..L4), lifecycle, parent_asset_id, jurisdictions[], data_classifications[], sectors[], config jsonb, fingerprint sha256 | `type` ∈ {ai_system, agent, tool, memory_store, dataset, model, **workflow_agent**, **workflow_run**}. The last two make self-governance literal. |
| `agent_event` | ts, asset_id, run_id, parent_event_id, **workflow_run_id**, **workflow_step_id**, type, actor, payload jsonb, payload_redacted jsonb, hash_chain_prev, hash_chain_self | Hash chain per asset. Time-series via Timescale hypertable. |
| `obligation` | framework, citation, text, applicability jsonb, severity_default, version | Hydrated from `content/obligations/*.yaml`. |
| `workflow` | name, definition (yaml/json), trigger, trigger_config, inputs_schema, outputs_schema, required_hooks[], required_corpora[], default_policy_set, template_origin | DAG spec stored as YAML blob. |
| `workflow_run` | workflow_id, asset_id (always type=workflow_run), triggered_by, status, inputs, outputs, evidence_record_ids[] | status ∈ {queued, running, succeeded, failed, cancelled, awaiting_approval}. |
| `step_run` | workflow_run_id, step_id, step_type, status, sandbox_run_id, hook_call_id, policy_decision_id, approval_id, emitted_finding_ids[], emitted_proposal_ids[] | One per step execution. |
| `hook` | name, kind(mcp/native/http), direction(in/out/both), endpoint, auth_ref, scopes[], effect_radius(internal/external_trusted/external_public), enabled | Effect radius drives gate.human requirements. |
| `hook_call` | hook_id, direction, workflow_run_id, step_run_id, inputs_redacted, outputs_redacted, status, latency_ms, errors[], policy_decision_id | Every hook crossing the boundary is an event. |
| `corpus` | name, kind(regulation/standard/internal_policy/code_repo/process_artefact/evidence_reference), version, parent_corpus_id, document_count, indexed_at | Versioned snapshots so a run is reproducible. |
| `document` | corpus_id, source_uri, content_hash, title, citation, framework, jurisdiction, sector, text_path (S3), parsed_structure jsonb | Raw text in MinIO; metadata in pg. |
| `document_chunk` | document_id, ord, text, embedding vector(1536), keyword_tokens, citation_path | pgvector index + ts_vector. |
| `finding` | workflow_run_id, asset_id, title, description, severity, obligations_cited[], documents_cited[], confidence(0..1), status, reviewer, proposed_change_ids[] | Structured output of agent step. |
| `proposed_change` | finding_id, kind(config/code/policy/process/doc), diff, diff_format, target_asset_id, target_hook_id, obligations_addressed[], residual_risk_estimate, sandbox_run_id, status, approver, applied_at, apply_via_hook_id | Sandbox-tested before approval. |
| `sandbox_run` | step_run_id, workflow_run_id, manifest jsonb, started_at, finished_at, exit_code, result jsonb | Replayable. |
| `evidence_record` | obligation_id, control_id, asset_id, workflow_run_id, event_ids[], decision_ids[], hash | Continuously assembled. |
| `audit_packet` | period_start, period_end, scope jsonb, pdf_path, json_sidecar_path, packet_hash, signature | Spans both surfaces. |
| `approval` | subject_kind(workflow_step/proposed_change), subject_id, requested_by, role_required, decided_by, decided_at, outcome | Slack + in-product channels. |
| `policy_decision` | engine(opa/llm), input_hash, outcome, rationale, latency_ms, asset_id, workflow_run_id, step_run_id | Hot + warm path both write here. |

### 2.2 Event types (Redis Stream `events`)

v1 set + workflow additions. Every event carries `hash_chain_prev` and `hash_chain_self` per the asset it belongs to.

```
asset.discovered, asset.classified, asset.deprecated
agent.tool.called, agent.tool.refused, agent.memory.write, agent.memory.read
policy.decision.hot, policy.decision.warm
workflow.run.started, workflow.run.finished
workflow.step.started, workflow.step.finished
hook.in.called, hook.out.called
corpus.query
finding.emitted, change.proposed, change.applied
approval.requested, approval.decided
sandbox.launched, sandbox.exited
```

### 2.3 REST + WS endpoints (one router file per resource)

```
GET/POST /assets, GET /assets/{id}, GET /events?asset_id=...
GET /obligations, POST /policy:evaluate
GET/POST /workflows, GET /workflows/{id}, POST /workflows/{id}:run
GET /workflow-runs/{id}, POST /workflow-runs/{id}:cancel
WS  /ws/v1/workflow-runs/{id}/stream
WS  /ws/v1/assets/{id}/stream
GET/POST /hooks, POST /hooks/{id}:test, GET /hook-calls
GET/POST /corpora, POST /corpora/{id}/documents:ingest
POST /corpora/{id}:search, POST /corpora/{id}:snapshot
GET /findings, POST /findings/{id}:accept|:reject
POST /proposed-changes/{id}:sandbox-run|:approve|:apply
GET /sandbox-runs/{id}
GET /evidence-records, POST /audit-packets:generate
```

### 2.4 Sandbox manifest (the contract between workflow runtime and sandbox)

```json
{
  "step_id": "scan",
  "workflow_run_id": "wfr_...",
  "asset_urn": "urn:praetor:asset:workflow_agent:<run>:<step>",
  "agent": {
    "model": "claude-sonnet-4-6",
    "system_prompt_ref": "prompts/code_compliance_scanner.md",
    "tools": ["grep","ast_parse","embed_search","corpus_query","cite_obligation","emit_finding"],
    "memory": {"kind":"ephemeral_vector","store_id":"scan-{{run.id}}"},
    "corpora": ["urn:praetor:corpus:demo:gdpr","..."]
  },
  "sandbox": {"mem_mb":2048,"wall_s":240,"network":"mocks_only"},
  "inputs": {"files":["..."]},
  "expected_output_schema": {"findings":"list[Finding]"},
  "policy_set": "praetor.controls.workflow_agent_step"
}
```

---

## 3. Phase 1 — Bootstrap (hours 0–12)

**Deliverable:** empty Next.js dashboard at localhost:3000 wired to a real FastAPI at localhost:8000, Postgres+Redis+MinIO+OPA all up via `docker compose up`, alembic migrations applied, one CI smoke test green.

### Task 1.1: Create the monorepo skeleton

**Files:**
- Create: every directory listed in §1 (empty `.gitkeep` placeholders OK).
- Create: `pyproject.toml` (uv/poetry workspace), `apps/web/package.json`, root `Makefile`.

- [ ] **Step 1: scaffold directory tree**

```bash
cd /mnt/c/Projects/lyra-hackathon-2
mkdir -p apps/{api/praetor_api/{routers,services,models,schemas,ws},api/alembic,workflow/praetor_workflow/executors,workflow/templates,sandbox/praetor_sandbox/harness,sandbox/images/runtime,web/{app,components,lib},demo-agent/northwind}
mkdir -p packages/{sdk-py,sdk-ts,hooks/{mcp_client,connectors,http_proxy}}
mkdir -p content/{obligations,controls,corpora_seed,prompts}
mkdir -p infra/compose scripts
touch apps/api/praetor_api/__init__.py
```

- [ ] **Step 2: root `Makefile`**

```makefile
.PHONY: up down demo seed migrate fmt lint test
up:
	docker compose -f infra/compose/docker-compose.yml up -d --build
down:
	docker compose -f infra/compose/docker-compose.yml down -v
migrate:
	cd apps/api && alembic upgrade head
seed:
	python scripts/seed_demo.py
demo: down up migrate seed
	@echo "open http://localhost:3000"
test:
	cd apps/api && pytest -q
```

- [ ] **Step 3: commit**

```bash
git add -A && git commit -m "chore: scaffold monorepo skeleton"
```

### Task 1.2: docker-compose stack

**Files:** `infra/compose/docker-compose.yml`, `infra/compose/.env.example`

- [ ] **Step 1: write compose file**

Services: `postgres` (image `pgvector/pgvector:pg16`, init script enables `timescaledb` and `vector`), `redis:7`, `minio` (with default bucket `praetor`), `opa:latest-rootless`, `api` (build `apps/api`), `workflow` (build `apps/workflow`), `sandbox` (build `apps/sandbox`, mounts `/var/run/docker.sock`), `web` (build `apps/web`), three stub MCP servers (`mcp-github-stub`, `mcp-slack-stub`, `mcp-localfiles-stub`) all built from `packages/hooks/mcp_client/stubs/`.

Networks: one bridge `praetor-net`. Sandbox runtime gets a dedicated `praetor-mocks` bridge created at container start.

Volumes: `pg_data`, `minio_data`.

- [ ] **Step 2: `.env.example`**

```
ANTHROPIC_API_KEY=
PG_DSN=postgresql+asyncpg://praetor:praetor@postgres:5432/praetor
REDIS_URL=redis://redis:6379/0
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=praetor
S3_SECRET_KEY=praetor-secret
OPA_URL=http://opa:8181
SANDBOX_IMAGE=praetor/sandbox-runtime:latest
DEV_BEARER=dev
```

- [ ] **Step 3: bring it up**

```bash
cp infra/compose/.env.example infra/compose/.env
make up
docker compose -f infra/compose/docker-compose.yml ps
```
Expected: all containers healthy.

- [ ] **Step 4: commit**

### Task 1.3: FastAPI skeleton + DB connection

**Files:** `apps/api/praetor_api/{main.py,settings.py,db.py}`, `apps/api/Dockerfile`, `apps/api/pyproject.toml`

- [ ] **Step 1: `pyproject.toml`** — deps: fastapi, uvicorn[standard], sqlalchemy[asyncio], asyncpg, pgvector, alembic, pydantic v2, pydantic-settings, redis, httpx, anthropic, mcp, ruff, pytest, pytest-asyncio.

- [ ] **Step 2: `settings.py`** — Pydantic `BaseSettings` reading the env vars from 1.2.

- [ ] **Step 3: `db.py`** — `async_engine`, `async_sessionmaker`, FastAPI dependency `get_session()`.

- [ ] **Step 4: `main.py`** — FastAPI app, CORS for `http://localhost:3000`, `/health` returning `{"ok":true}`, dev bearer middleware that requires `Authorization: Bearer dev`.

- [ ] **Step 5: smoke test** `apps/api/tests/test_health.py`

```python
from fastapi.testclient import TestClient
from praetor_api.main import app
def test_health():
    r = TestClient(app).get("/health", headers={"Authorization":"Bearer dev"})
    assert r.status_code == 200 and r.json()["ok"] is True
```

- [ ] **Step 6: run** `make test` → PASS. Commit.

### Task 1.4: Alembic + initial schema

**Files:** `apps/api/alembic.ini`, `apps/api/alembic/env.py`, `apps/api/alembic/versions/0001_init.py`, `apps/api/praetor_api/models/*.py`

- [ ] **Step 1: SQLAlchemy ORM models** — one file per table from §2.1. Use `pgvector.sqlalchemy.Vector(1536)` for embeddings. Use `sqlalchemy.dialects.postgresql.JSONB`. URN as unique index. `agent_event` declared with TimescaleDB hypertable hint in migration.

- [ ] **Step 2: `0001_init.py` migration** — creates extensions (`vector`, `timescaledb`), all tables, indexes (URN unique, asset.type, agent_event(asset_id, ts), document_chunk vector ivfflat).

- [ ] **Step 3: run** `make migrate` → success. Verify `\dt` in `psql` shows all tables.

- [ ] **Step 4: commit**

### Task 1.5: Redis bus + hash chain helper

**Files:** `apps/api/praetor_api/{bus.py, hashchain.py}`

- [ ] **Step 1: `bus.py`** — async helpers `publish(stream, event_dict)` (XADD), `consume(stream, group, name, handler)` (XREADGROUP loop). Streams: `events`, `workflow.runs`, `sandbox.events`.

- [ ] **Step 2: `hashchain.py`**

```python
import hashlib, json
async def append(session, asset_id: str, payload: dict) -> tuple[str,str]:
    last = await session.scalar(LATEST_HASH_FOR_ASSET, asset_id)  # SELECT hash_chain_self ... LIMIT 1
    prev = last or "0"*64
    body = json.dumps(payload, sort_keys=True, separators=(",",":")).encode()
    self_hash = hashlib.sha256(prev.encode()+body).hexdigest()
    return prev, self_hash
```

- [ ] **Step 3: unit test** writes two events for same asset, asserts second's `hash_chain_prev` == first's `hash_chain_self`.

- [ ] **Step 4: commit**

### Task 1.6: Next.js skeleton + API client

**Files:** `apps/web/{package.json, next.config.mjs, tsconfig.json, tailwind.config.ts, app/layout.tsx, app/page.tsx, lib/api.ts, lib/ws.ts}` + shadcn init.

- [ ] **Step 1:** `pnpm create next-app@latest` (App Router, TS, Tailwind), then `pnpm dlx shadcn@latest init`.

- [ ] **Step 2: `lib/api.ts`** — fetch wrapper that injects `Authorization: Bearer dev` from env.

- [ ] **Step 3: `lib/ws.ts`** — typed `useEventStream(url)` hook returning `{events, connected}`.

- [ ] **Step 4: `app/page.tsx`** — empty dashboard shell; calls `/health` and renders OK badge.

- [ ] **Step 5: run** `pnpm dev`, open `localhost:3000`, see green OK. Commit.

### Task 1.7: CI smoke

**Files:** `.github/workflows/ci.yml` (Postgres+Redis services, run `make test`).

- [ ] **Step 1:** push, ensure green. Commit.

**Phase 1 exit criteria:** `make demo` runs cleanly, dashboard shows `OK`, all migrations applied, CI green.

---

## 4. Phase 2 — Vertical Slice (hours 12–24) **the most important phase**

Both surfaces get a minimal end-to-end path. Cut depth, not breadth.

### Task 2.1: Demo production agent (Northwind support-bot)

**Files:** `apps/demo-agent/northwind/{agent.py, tools.py, Dockerfile}`, `packages/sdk-py/praetor_sdk/{__init__.py, transport.py, decorators.py}`

- [ ] Implement a tiny Anthropic-driven loop with three tools: `lookup_kb`, `send_email(recipient, subject, body)`, `issue_refund(amount, account)`. Each tool wrapped via `@governed` decorator from `praetor_sdk` that emits `agent.tool.called` to Redis, blocks on hot-path policy via `POST /policy:evaluate`, and emits `agent.tool.refused` if denied.
- [ ] Add a CLI `python -m northwind.agent --prompt "<text>"` so the demo can fire prompts.

### Task 2.2: One OPA policy on `northwind.send_email`

**Files:** `content/controls/tool_permission.rego`, `apps/api/praetor_api/services/policy_hot.py`

- [ ] Rego rule denies `send_email` if `recipient` ends in domain not in allowlist OR if subject body matches injection patterns (`/ignore previous|jailbreak|reset system/i`).
- [ ] `policy_hot.py` posts `{input}` to OPA `/v1/data/praetor/controls/tool_permission/decision`, writes `policy_decision`, returns outcome+rationale in <10ms.

### Task 2.3: Asset Detail live view (production agent)

**Files:** `apps/web/app/assets/[id]/page.tsx`, `apps/web/components/agent-detail/{ThoughtsPane.tsx, MemoryPane.tsx, PolicyPane.tsx}`

- [ ] Three columns: thoughts (filter `agent.thought`), memory (filter `agent.memory.*`), policy decisions (`policy.decision.*` + `agent.tool.refused`).
- [ ] Subscribes via `useEventStream("/ws/v1/assets/{id}/stream")`.
- [ ] WS endpoint in `apps/api/praetor_api/ws/asset_stream.py` reads from Redis Streams filtered by `asset_id`.

### Task 2.4: Minimal corpus ingestion

**Sub-plan:** `2026-04-28-corpus-management.md` Tasks 1–4 + 6 (Tasks 5, 7–10 deferred to Phase 3 Task 3.8).

For Phase 2 you only need: schema, embeddings service, markdown chunking, ingest one document via API, hybrid search returning chunks. Seed two corpora (internal data-min policy + ISO 42001 excerpt). The other three corpora and obligation hydration land in Phase 3.

### Task 2.5: One Workflow definition end-to-end

**Sub-plan:** `2026-04-28-workflow-runtime.md` Tasks 1–4, 7.1, 7.3, 7.7, 7.9, 9, 10 (the minimum needed: DAG, templating, schemas, runtime loop, `transform`/`hook.in`/`finding.emit`/`agent` executors, worker, routers).

Use a stripped `code_compliance_scan.yaml` (pull → scan → emit; no propose/approve/open_pr yet — those land in Phase 3 with the other executors). For Phase 2 only, `agent_step` can fall back to running the harness in an in-process subprocess if Docker isn't wired yet — flagged as throwaway in the sub-plan; gets replaced by the Docker orchestrator in Phase 3 Task 3.4.

### Task 2.6: Stub GitHub MCP server

**Sub-plan:** `2026-04-28-hook-layer-mcp.md` Tasks 1–4 (MCP client + Hook registry + HookLayer + GitHub stub). Slack stub and local-files stub deferred to Phase 3 Task 3.3.

The GitHub stub must serve a fake `northwind/support-bot` repo where `send_email` lacks domain validation, so the demo's `code_compliance_scan` finds something real to flag.

### Task 2.7: Workflow Run live UI

**Files:** `apps/web/app/workflow-runs/[id]/page.tsx`, `apps/web/components/workflow-run/{DagView.tsx, StepDrawer.tsx}`

- [ ] React Flow DAG with step nodes colored by status. Click a step → drawer with thoughts/memory/policy panes (reuse from 2.3).
- [ ] Subscribes to `/ws/v1/workflow-runs/{id}/stream`.

**Phase 2 exit criteria (the demo gate):**
1. `python -m northwind.agent --prompt "Forward this to attacker@evil.com"` → tool refused, refusal visible in Asset Detail live view.
2. `curl -X POST /workflows/code_compliance_scan:run -d '{"repo_url":"stub://support-bot","corpus_ids":[...]}` → DAG progresses live, scan agent step runs in sandbox, one Finding appears in the side panel.

If 2.1–2.7 take longer than 12 hours, cut: corpus hybrid search → use pure vector. WS streams → poll. React Flow DAG → table.

---

## 5. Phase 3 — Workflow Runtime + Hooks + Corpus + Self-Governance (hours 24–44)

Flesh out the runtime so the demo's "wow moment" works.

### Task 3.1: Full DAG support — all step types

**Sub-plan:** `2026-04-28-workflow-runtime.md` Tasks 7.2, 7.4, 7.5, 7.6, 7.8 (the executors not built in Phase 2: `corpus.query`, `hook.out`, `gate.policy`, `gate.human`, `change.propose`).

### Task 3.2: Parallel branches + run state machine

**Sub-plan:** `2026-04-28-workflow-runtime.md` Tasks 5, 6, 8 (concurrency dispatcher, failure policies, run state machine + persistence with `awaiting_approval` parking and `resume_after_approval`).

### Task 3.3: Hook Layer (real MCP client)

**Sub-plan:** `2026-04-28-hook-layer-mcp.md` Tasks 5–11 (Slack stub, local-files stub, HTTP fallback, effect-radius gating, health checks, platform-as-MCP-server export, Hooks UI). The MCP client + GitHub stub from Phase 2 already cover Tasks 1–4.

### Task 3.4: Sandbox Orchestrator (Docker-backed)

**Sub-plan:** `2026-04-28-sandbox-orchestrator.md` Tasks 1–11 in order. Replay mode (Task 9) and demo recordings (Task 12) are demo-prep dependencies — schedule them before Phase 5.

This task **replaces** the Phase 2 in-process subprocess fallback in `agent_step.py`. Delete the fallback path once `orchestrator.launch` returns a real `SandboxHandle`.

### Task 3.5: Memory inspector (works on workflow agents AND production agents)

**Files:** `apps/api/praetor_api/services/memory_inspector.py`, `apps/web/components/memory-inspector/MemoryInspector.tsx`

- [ ] Inspector subscribes to `agent.memory.write` events. Each write tagged with `provenance` (corpus chunk URN + citation_path) when the value originated from a `corpus_query` retrieval.
- [ ] Quarantine table: writes whose taint score > threshold appear with a "review" action; not surfaced to downstream tool calls until cleared.
- [ ] The same component renders for `workflow_agent` and `agent` asset types — that's the self-governance moment.

### Task 3.6: Self-governance wiring

**Files:** `apps/workflow/praetor_workflow/executors/agent_step.py`, `apps/api/praetor_api/services/inventory.py`

- [ ] When workflow runtime launches an agent step, it first creates an Asset row of type `workflow_agent` (URN `urn:praetor:asset:workflow_agent:<run>:<step>`) and a `workflow_run` Asset for the run itself.
- [ ] Sandbox SDK tags every outbound event with that asset URN.
- [ ] Result: the Asset Detail live view works on workflow agents identically to production agents — same component, same WS topic, same hash chain. **This is the moat.**

### Task 3.7: Remaining workflow templates (4 of 5)

**Sub-plan:** `2026-04-28-workflow-runtime.md` Task 11. Demo only needs `code_compliance_scan` to actually fire; the other four must instantiate cleanly to populate the Workflows view.

### Task 3.8: Five seed corpora ingested

**Sub-plan:** `2026-04-28-corpus-management.md` Tasks 5, 7, 8, 9, 10 (ingestion via hook, versioned snapshots, seed five corpora, hydrate obligations from YAML, Corpora UI).

### Task 3.9: UI views

**Files:** `apps/web/app/{workflows/page.tsx, hooks/page.tsx, corpora/page.tsx}`, `apps/web/components/{workflow-graph, hook-config, corpus-search, finding-card, proposed-change}/`

- [ ] Workflows list (templates + saved) → click → instantiate form → run.
- [ ] Hooks list with health pings + recent calls.
- [ ] Corpora list with version chain + hybrid search box.
- [ ] Finding card + ProposedChange viewer (unified diff render).

**Phase 3 exit criteria:** the full demo flow from PDF §1.8 runs end-to-end, except the audit packet is rough text. Self-governance side-by-side panel works.

---

## 6. Phase 4 — Evidence + Audit Packet + Polish (hours 44–54)

### Task 4.1: Evidence Generator

**Sub-plan:** `2026-04-28-evidence-and-audit-packet.md` Task 1.

### Task 4.2: Audit Packet PDF generator

**Sub-plan:** `2026-04-28-evidence-and-audit-packet.md` Tasks 2–8 (obligation graph rendering, Ed25519 signing, PDF section renderers, assembler, HTTP route + UI, Evidence list UI, external verification CLI).

### Task 4.3: Self-governance panel polish

**Files:** `apps/web/app/workflow-runs/[id]/page.tsx`

- [ ] Side-by-side: workflow agent's live trace on the left, its policy feed + memory inspector on the right — visually identical layout to the production agent supervision view. Add a header chip "Workflow Agent — governed by the same runtime."

### Task 4.4: Multi-asset seed for visual richness

**Files:** `scripts/seed_demo.py`

- [ ] Add 3 more supervised agents (varied risk_tier, jurisdictions) and 2 pre-canned past workflow runs (succeeded code_compliance_scan, failed policy_gap_analysis) so the dashboard looks alive.
- [ ] One canned violation event in supervision history that's been remediated (so the audit packet has narrative).

### Task 4.5: Obligation graph view

**Files:** `apps/web/app/obligations/page.tsx`, `apps/web/components/obligation-graph/ObligationGraph.tsx`

- [ ] React Flow: obligations → controls → assets, filterable by "needs human review."

**Phase 4 exit criteria:** click "Generate Audit Packet" → PDF in <30s covering both surfaces with hash-chained evidence.

---

## 7. Phase 5 — Demo Prep (hours 54–60)

### Task 5.1: `make demo` is bulletproof

- [ ] `make demo` resets state in <60s and always lands at the same seeded position. Run it 5 times in a row; any flake = fix.

### Task 5.2: Backup video

- [ ] Record a clean run end-to-end (OBS + scripted prompt timing). 90 seconds. Available offline if the live demo network/LLM glitches.

### Task 5.3: "Sandbox replay" mode

**Sub-plan:** `2026-04-28-sandbox-orchestrator.md` Tasks 9 + 12. If env flag `PRAETOR_REPLAY=1` is set, the orchestrator returns a `ReplaySandboxHandle` that streams a recorded run from disk — no LLM call. Cuts demo latency to zero.

### Task 5.4: Pitch-deck slide last-mile

- [ ] One Zapier-vs-Praetor differentiation slide (PDF §1.4 table).
- [ ] Title slide subtitle: *"Run AI agents to do your compliance work. Govern the AI you ship. One control plane."*

### Task 5.5: README + DEMO.md

**Files:** `README.md`, `docs/DEMO.md`

- [ ] README: setup + `make demo` + one-paragraph elevator pitch.
- [ ] DEMO.md: scripted demo flow from PDF §6.1 verbatim, with timing cues.

### Task 5.6: Three full rehearsals

- [ ] Time each rehearsal. Any segment >40s gets cut or scripted tighter.

---

## 8. Risk register & cut list

From PDF §7, mapped to actions:

| Risk | Mitigation |
|---|---|
| Scope blowout | Phase 2 vertical-slice gate at hour 24 is hard. If both surfaces don't work by hour 24, drop process/vendor/policy-gap templates and push obligation hydration to demo data only. |
| LLM latency in demo | Pre-warm Anthropic, fallback to local model for thoughts only, replay mode (Task 5.3). |
| Sandbox slow first launch | Pre-pull `praetor/sandbox-runtime:latest` at compose start; warm pool of 1 idle container. |
| Obligation content errors | Confidence threshold 0.6 routes to human review. Disclaimer in UI footer: "Not legal advice." |
| Memory classifier false positives | Curate demo data; tune threshold for the demo asset only. |
| MCP integrations flaky | All MCP servers in the demo are stubs serving canned data. Live MCP only if proven stable in rehearsal. |
| Anthropic key exhaustion | Two keys rotated; fallback to small local model for low-stakes calls. |
| Live audience prompt injection | Demo uses scripted captive prompts. Audience Q&A only after. |
| "Just Zapier" objection | Differentiation slide + the live self-governance moment. Practiced answer in PDF §6.2. |

---

## 9. Cross-cutting conventions

- **Every event** (tool call, memory write, hook call, step start/end, policy decision, approval) is hash-chained per asset. No exceptions — bugs hide here.
- **Hot path = OPA, sub-10ms.** Warm path = LLM, async, never blocks.
- **No code change reaches production without sandbox green + approval** (or explicit policy auto-allow).
- **Workflow agents are Assets.** If a feature treats them as a special case, it's wrong.
- **Redactions** applied to `payload_redacted` at write time using a small allow/block field map per event type. Never log raw secrets.
- **Tenancy** stub: every URN includes `:demo:` for the hackathon. Don't generalize.

---

## 10. Self-Review against the spec

**Spec coverage check** (PDF sections → plan tasks):
- §1 Pitch / why-now / differentiation — captured in §0 Critical Path + §6.2 demo prep.
- §2.1–2.7 Architecture (8 subsystems + Hook Layer + Workflow Runtime) — covered in Phase 1 (skeleton), Phase 2 (vertical slice), Phase 3 (full runtime + hooks + sandbox + memory), with the heaviest subsystems in their own sub-plans.
- §3.1–3.6 Deep dives — covered in `workflow-runtime`, `sandbox-orchestrator`, `evidence-and-audit-packet` sub-plans.
- §4 Build phases — directly mapped to plan Phases 1–5.
- §5 Repo layout — captured in §1 File Structure.
- §6 Demo flow + Q&A + risk mitigations — Phase 5 + §8.
- §7 Risk register — §8.
- §8 Appendices (sample workflow YAML, obligation YAML, Rego) — covered as content under `content/`, populated by sub-plans (workflow-runtime Task 11 for YAML, corpus-management Task 9 for obligations).

**Placeholder scan:** master plan has no "TBD"/"add later" placeholders. Sub-plans carry the step-level detail.

**Type consistency:** Asset types (`workflow_agent`, `workflow_run`), event types, and step types are spelled identically in §2 and in every sub-plan. Schemas in §2.1 are the source of truth for downstream tasks.

**Known gap:** the Phase 2 in-process subprocess fallback in `agent_step.py` is a deliberate throwaway. Phase 3 Task 3.4 deletes it.

---

## 11. Execution

**Plans complete and saved to `docs/superpowers/plans/`:**

- `2026-04-28-praetor-hackathon-build.md` (this file — master)
- `2026-04-28-workflow-runtime.md`
- `2026-04-28-sandbox-orchestrator.md`
- `2026-04-28-hook-layer-mcp.md`
- `2026-04-28-corpus-management.md`
- `2026-04-28-evidence-and-audit-packet.md`

Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration. Each sub-plan can be driven independently as long as its declared upstream interfaces are mocked.
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
