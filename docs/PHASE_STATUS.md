# Praetor Phase Status

This is the living tracker for `docs/superpowers/plans/2026-04-28-praetor-hackathon-build.md`.

Legend:

- ~~Done~~ means implemented in this repository.
- ~~Done (demo/stub)~~ means the demo/API surface exists and is tested, but a production-backed implementation still remains.
- Open means not yet implemented.
- Keep this file updated whenever a phase task moves forward.

## Current Verification

- ~~API tests: `27 passed` via `cd apps/api && python -m pytest`.~~
- ~~Workflow tests: `6 passed` via `scripts/test.ps1` / `npm test`.~~
- ~~Alembic head exists: `0001 (head)`.~~
- ~~Compose config validates: `docker compose -f infra/compose/docker-compose.yml config`.~~
- ~~Compose production env validates with `PRAETOR_ENV_FILE=.env.production.example`.~~
- ~~Root npm scripts exist for `npm run demo`, `npm run prod`, `npm run demo:api`, `npm run prod:api`, `npm run demo:web`, `npm run prod:web`.~~
- ~~Web build validates with `NEXT_DIST_DIR=.next-verify npm run build`.~~
- ~~Root `npm test` now runs API tests, workflow tests, web typecheck, and web production build through a cross-platform Node runner.~~
- ~~Default web build validates with `cd apps/web && npm run build`.~~
- ~~Live Docker Compose stack boots API, web, workflow, sandbox, Postgres, Redis, MinIO, OPA, and MCP stubs.~~
- ~~Live Docker health checks pass for OPA, Postgres, Redis, and MinIO.~~
- ~~Live API health returns `{"ok": true, "data_mode": "demo", "data_backend": "in_memory"}`.~~
- ~~Live web route `GET http://localhost:3000` returns HTTP 200.~~
- ~~Live workflow run emits six hash-chained events with a valid chain through `GET /events`.~~
- ~~Live workflow WebSocket stream connects at `/ws/v1/workflow-runs/{id}/stream?token=dev` and receives run events.~~
- ~~Alembic upgrade succeeds against the live Postgres container and creates the initial 19-table schema.~~
- ~~TimescaleDB migration path is optional when the active Postgres image lacks the extension; base schema still applies.~~
- ~~Production workflow persistence smoke test passes inside the API container: `code_compliance_scan` writes and reads workflow, asset, workflow-run, step-run, and finding rows in Postgres.~~
- ~~Step-run lease migration applied: `alembic upgrade head` now includes `0002_step_run_leases` for lease owner, lease expiry, heartbeat, and attempt count.~~
- ~~Production event persistence smoke test passes inside the API container: `code_compliance_scan` writes six `agent_event` rows and reads a valid hash chain back from Postgres.~~
- ~~Production hook persistence smoke test passes inside the API container: hook registry rows are seeded and `github_stub/open_pr` writes a `hook_call` row.~~
- ~~Production corpus persistence smoke test passes inside the API container: corpus rows are seeded, document/chunk rows are persisted, lexical search returns the expected top hit, and document counts update.~~
- ~~Production review/evidence/audit smoke test passes inside the API container: finding/proposal rows, sandbox run row, approval/apply state, evidence row, PDF artifact, JSON sidecar, and Ed25519 signature are produced.~~
- ~~Frontend build validates after backend fetch and WebSocket wiring: `cd apps/web && npm run build`.~~
- ~~Root scripts exist for production seed/reset: `npm run seed:prod` and `npm run reset:prod`.~~
- ~~Opt-in Postgres integration tests exist behind `PRAETOR_RUN_DB_TESTS=1`.~~
- ~~CI config now provisions Postgres and Redis service containers and runs opt-in DB integration tests.~~
- ~~Local opt-in DB integration tests pass against Compose Postgres/Redis: `alembic upgrade head; python -m pytest tests/test_production_repositories.py -q`.~~
- ~~Audit verification CLI validates a generated JSON sidecar and Ed25519 signature.~~
- ~~Sandbox orchestrator modules compile and expose `/health` plus `/launch` with Docker execution and deterministic replay fallback.~~
- ~~Live sandbox launch probe succeeds through the Docker socket using `compose-sandbox:latest` and returns `mode: docker-socket`, `exit_code: 0`.~~
- ~~Compose config validates after adding the sandbox orchestrator healthcheck and API orchestrator URL.~~
- ~~Windows runtime launcher no longer spawns `npm.cmd` directly; it invokes npm through `cmd.exe /d /s /c` to avoid Node `spawn EINVAL`.~~
- ~~Frontend data source is explicit: `fixtures`, `api`, or `hybrid`; production `api` mode does not fall back to fixture IDs/data.~~
- ~~Docker Compose defaults to production env/API-only frontend mode; demo mode now requires explicit demo env + fixture data source.~~
- ~~Production review APIs no longer auto-create demo findings/proposals/evidence unless `PRAETOR_SEED_DEMO_DATA=1`.~~
- ~~Demo API uses stable fixture IDs `finding_send_email` and `pc_send_email_validator` when running in demo mode.~~
- ~~`npm run clear:prod` clears production Postgres rows without reseeding demo data.~~
- ~~Production API startup runs `alembic upgrade head` before Uvicorn when `PRAETOR_AUTO_MIGRATE=1` so fresh Docker volumes have the required Postgres schema.~~
- ~~Production hook registry seeding is idempotent under parallel frontend requests.~~
- ~~Live production endpoints `GET /hooks`, `GET /hook-calls`, and `GET /evidence-records` return HTTP 200 with `access-control-allow-origin: http://localhost:3000`.~~
- ~~Live web routes `/hooks`, `/evidence`, and `/corpora` return HTTP 200 against the production API stack.~~
- ~~Production workflow detail payloads now include the full frontend contract (`trigger_config`, `inputs_schema`, `outputs_schema`, `default_policy_set`, `template_origin`).~~
- ~~Frontend workflow API client normalizes missing workflow schemas/arrays before rendering, preventing `Object.entries(undefined)` crashes on workflow detail pages.~~
- ~~Live route `/workflows/code_compliance_scan_full` returns HTTP 200 against the production API stack.~~
- ~~Workflow template detail no longer links to fixture run `wfr_2026_04_28_001`; it instantiates a real production run through `POST /workflows/{id}:run` and navigates to the returned run id.~~
- ~~Production API now exposes `GET /workflow-runs`, and the frontend workflow-runs page uses it in API mode.~~
- ~~Production workflow-run payloads now include the full frontend contract (`urn`, entity metadata, `asset_id`, `evidence_record_ids`, normalized step fields, and DAG `depends_on`).~~
- ~~Live production run `wfr_ab76a2062c7d` was created from `code_compliance_scan_full`; `GET /workflow-runs/{id}`, `GET /events?workflow_run_id=...`, and `/workflow-runs/{id}` all return HTTP 200.~~
- ~~Main route sweep passed after the workflow-run fix: `/`, `/workflows`, `/workflows/code_compliance_scan_full`, `/workflow-runs`, `/workflow-runs/{id}`, `/corpora`, `/hooks`, `/hooks/validate`, `/evidence`, `/inventory`, `/obligations`, and `/sandbox` return HTTP 200.~~
- ~~API route sweep passed for `/health`, `/runtime/config`, `/workflows`, `/workflow-runs`, `/events`, `/hooks`, `/hook-calls`, `/corpora`, `/evidence-records`, `/findings`, `/proposed-changes`, and `/models/providers`.~~
- ~~Web typecheck passes: `cd apps/web && npm run typecheck`.~~
- ~~Web production build passes: `cd apps/web && npm run build`.~~
- ~~Compose config validates after env-key/readiness additions: `docker compose -f infra/compose/docker-compose.yml config`.~~
- ~~Comprehensive live E2E passes against rebuilt production Compose API/web: `python scripts/e2e_platform.py` (`46 passed, 0 failed`, production/postgres).~~
- ~~Agent workflow steps now execute through the provider-neutral model adapter in `auto`, `live`, or `dry_run` mode.~~
- ~~Runtime readiness now reports model provider keys and JSON Stack integration secret readiness via `GET /runtime/readiness`, `GET /models/readiness`, and `POST /models:check`.~~
- ~~JSON Stack hooks resolve `auth_ref` values from environment variables for non-dry-run calls and fail clearly with `missing-secret` when a token is absent.~~
- ~~Production `change.propose` workflow steps now persist `proposed_change` rows linked to emitted findings.~~
- ~~Windows without `make` is covered by `npm test` and `scripts/test.ps1`; `Makefile test` remains available on shells with make installed.~~
- ~~Latest local web build passes without killing Node processes.~~
- ~~Production `change.propose` step persists proposal rows that can be sandboxed, approved, and applied through the review API.~~
- ~~Production asset inventory, obligations, controls, and sandbox-run listing now have backend API surfaces and API-mode frontend calls.~~
- ~~Partial: evidence sweep materializes records from persisted workflow events without demo seeding.~~
- ~~Sandbox log streaming, hardened isolation defaults, and MCP JSON-RPC stub negotiation are covered by live E2E.~~
- ~~Queued workflow execution mode exists: `PRAETOR_WORKFLOW_EXECUTION_MODE=queued` persists runs as queued, `POST /workflow-runs:drain` processes them, and the Compose `workflow` service now runs the drain loop.~~
- ~~Postgres integration tests cover queued workflow drain execution: `PRAETOR_RUN_DB_TESTS=1 python -m pytest tests/test_production_repositories.py -q` (`4 passed`).~~
- ~~Workflow worker hardening: queued drain now passes a stable worker id and lease TTL; ready `step_run` rows are leased with owner/expiry/heartbeat/attempt count and expired running leases recover to pending on the next drain.~~
- ~~Postgres integration tests cover expired workflow step lease recovery: `PRAETOR_RUN_DB_TESTS=1 python -m pytest tests/test_production_repositories.py -q` (`4 passed`).~~
- ~~Evidence worker v2: `evidence_checkpoint` table tracks consumer progress through persisted `agent_event` rows; `POST /evidence-records:consume` incrementally creates idempotent evidence from events, policy decisions, controls, and YAML obligations.~~
- ~~Workflow worker now calls `POST /evidence-records:consume` instead of the legacy run sweep endpoint.~~
- ~~Remediation dispatch is now provider-neutral: approved proposed changes can route through GitHub PRs, Jira issues, Linear issues, Microsoft Graph email, Slack messages, or ServiceNow records using the JSON Stack hook layer.~~
- ~~Effectful live hook calls now enforce an approval marker, and proposed-change dispatch requires both approval and a sandbox run before non-dry-run external writes.~~
- ~~User-provided JSON Stack manifests now persist as first-class production `hook` records with JSONB config, validation, detail reads, previews, and hook-call execution.~~
- ~~Hook calls now carry stable idempotency keys; non-dry-run repeated external writes replay a previous successful call instead of dispatching again.~~
- ~~JSON Stack live responses now evaluate operation `output_map` fields into normalized mapped outputs with request/response hashes.~~
- ~~Hooks UI now imports OpenAPI JSON, lets users select operations, converts them to JSON Stack manifests, validates them, and persists them as production hooks.~~
- ~~MCP client now performs session-aware Streamable HTTP negotiation with bearer auth refs, protocol/session headers, tool/resource/prompt discovery, and tool-call name routing.~~
- ~~Bundled MCP stubs now support optional bearer auth, session IDs, protocol version headers, prompts/list, and stricter MCP request headers.~~
- ~~Provider-specific model streaming exists through `POST /models:stream`, normalizing OpenAI Responses API, Anthropic Messages API, and Gemini `streamGenerateContent` SSE formats into `start`/`delta`/`usage`/`done`/`error` events.~~
- ~~Workflow `agent` steps now create `workflow_agent` Asset rows, launch through the sandbox orchestrator/replay contract, persist linked `sandbox_run` rows, and expose `sandbox_run_id` in workflow step responses.~~
- ~~Workflow `agent` steps now consume structured `agent_step_output` emitted by the sandbox harness/replay path; backend service code validates and persists the result instead of calling the model adapter directly after launch.~~
- ~~Workflow run step drawers now render an auditable runtime trace per step, including hook calls, corpus retrievals, agent rationale summaries, tool calls, sandbox launch/exit, findings, proposals, policy gates, approvals, and final outputs.~~
- ~~Production workflow events now persist step-start, semantic step trace events, and step-finished records for each workflow step without exposing private chain-of-thought.~~
- ~~Production corpus seeding now idempotently ingests all five bundled corpus markdown documents into Postgres-backed `document` and `document_chunk` rows.~~
- ~~Production obligations now hydrate idempotently from bundled YAML files, with Docker-package fallback content and demo static fallback.~~
- ~~Partial: the Compose `workflow` worker periodically invokes `POST /evidence-records:sweep`, so evidence materialization no longer depends only on frontend/API reads.~~
- ~~Persisted event reads now reconstruct ordering from hash-chain links, avoiding same-transaction timestamp ordering failures.~~
- ~~Partial: polling evidence sweeps are replaced by a checkpointed event consumer over persisted event history with policy-decision and obligation mapping hooks.~~
- ~~Live evidence consumer smoke passes against Compose production API: `POST /evidence-records:consume` created checkpointed evidence records and returned the `evidence-worker-v2` checkpoint.~~
- Open: consume directly from Redis Streams with durable stream IDs instead of polling persisted `agent_event` rows.

## Phase 0 - Demo Critical Path

- ~~`docker compose` topology exists for API, web, workflow, sandbox, Postgres, Redis, MinIO, OPA, and MCP stubs.~~
- ~~Seed/demo data exists in frontend fixtures and deterministic backend services.~~
- ~~Workflow surface can instantiate `code_compliance_scan` through `POST /workflows/code_compliance_scan:run`.~~
- ~~Finding and proposed-change demo flow exists through API routes.~~
- ~~Supervision surface exists in the frontend fixture app.~~
- ~~Audit packet API stand-in exists through `POST /audit-packets:generate`.~~
- ~~`docker compose up` runs end-to-end after fixing OPA healthcheck image compatibility.~~
- ~~Real FastAPI WebSocket endpoints exist for asset and workflow-run streams.~~
- ~~Production stream service writes events to Redis Streams when `PRAETOR_DATA_MODE=production`.~~
- ~~WebSocket streaming verified against the live Docker stack.~~
- ~~Partial: real outbound remediation dispatch path exists through JSON Stack hooks, with GitHub PR as one destination among ticketing, messaging, email, and GRC systems.~~
- ~~Provider-specific response mapping/idempotency for live dispatch results exists at the hook layer through JSON Stack `output_map` evaluation and `HookCall.idempotency_key`.~~
- ~~Signed audit packet artifacts include PDF output, JSON sidecar, packet hash, and Ed25519 signature.~~

## Phase 1 - Bootstrap

- ~~Task 1.1: Create monorepo skeleton.~~
- ~~Task 1.2: Docker Compose stack.~~
- ~~Task 1.3: FastAPI skeleton and DB connection.~~
- ~~Task 1.4: Alembic and initial schema.~~
- ~~Task 1.5: Redis bus and hash-chain helper.~~
- ~~Task 1.6: Next.js frontend scaffold.~~
- ~~Task 1.7: CI smoke workflow.~~
- ~~`docker compose up` and `alembic upgrade head` were run against live Postgres.~~
- ~~Opt-in DB integration tests exist for local/Compose Postgres.~~
- ~~Task 1.7 add CI service containers for Postgres and Redis and run DB integration tests.~~
- ~~Phase 1 hardening: web Docker image now uses Next standalone output and a scoped `.dockerignore`; rebuilt with `docker compose -f infra/compose/docker-compose.yml build web`.~~

## Phase 2 - Vertical Slice

- ~~Task 2.1: Demo production agent, Northwind support-bot.~~
- ~~Task 2.2: Hot policy for `northwind.send_email`.~~
- ~~Task 2.3: Asset Detail live view in frontend fixtures.~~
- ~~Task 2.4: Minimal corpus ingestion and search API.~~
- ~~Task 2.5: One workflow definition end-to-end, deterministic API path.~~
- ~~Task 2.6: Stub GitHub MCP server and hook API surface.~~
- ~~Task 2.7: Workflow Run live UI in frontend fixtures.~~
- ~~Additional: model/provider selection API for OpenAI, Anthropic, and Google.~~
- ~~Additional: external hook call API for GitHub, Slack, and local-files operations.~~
- ~~Additional: explicit demo/production runtime mode through `PRAETOR_DATA_MODE`, `GET /health`, `GET /runtime/config`, root npm scripts, and compose env-file switching.~~
- ~~Additional: explicit frontend data source mode through `NEXT_PUBLIC_DATA_SOURCE`; production is API-only and demo is fixture-only.~~
- ~~Partial: production-mode `code_compliance_scan` persists canonical workflow, asset, workflow run, step runs, emitted finding, selected provider, and selected model in Postgres.~~
- ~~Partial: production-mode hooks persist registry rows and external operation calls in Postgres.~~
- ~~Partial: production-mode corpus ingest/search persists corpus, document, and document chunk rows in Postgres.~~
- ~~Partial: production-mode findings, proposed changes, sandbox runs, evidence records, and audit packets persist in Postgres.~~
- ~~Partial: all bundled deterministic workflow templates are now registered in production mode and can run through Postgres-backed workflow-run and step-run persistence.~~
- ~~Partial: production pause/resume/cancel and retry-attempt metadata exist for persisted workflow step runs.~~
- ~~Partial: durable queued workflow scheduling exists through persisted `queued` workflow runs, pending step rows, a drain endpoint, and the Compose workflow worker.~~
- ~~Partial: ready DAG branches are scheduled in batches during queued drain processing.~~
- ~~Partial: distributed node-run leasing and restart recovery now exist through persisted step leases, heartbeat timestamps, attempt counts, row locks, and expired-lease recovery.~~
- Open: per-step process isolation for all non-agent step types and continuous heartbeat while a long-running executor is still active.
- ~~Frontend API client calls `NEXT_PUBLIC_API_BASE` for implemented backend routes with fixture fallbacks for frontend-only surfaces.~~
- ~~Frontend stream client opens real FastAPI WebSockets when `NEXT_PUBLIC_API_BASE` is set and `NEXT_PUBLIC_MOCK_STREAMS` is not `1`.~~
- Open: verify Northwind CLI against a running API process.

## Phase 3 - Workflow Runtime, Hooks, Corpus, Self-Governance

- ~~Task 3.1: Full DAG support - all planned step types now execute deterministically: `agent`, `corpus.query`, `hook.in`, `hook.out`, `transform`, `gate.policy`, `gate.human`, `finding.emit`, `change.propose`.~~
- ~~Task 3.3: Partial Hook Layer - registry, test endpoint, deterministic call endpoint, MCP stub containers.~~
- ~~Task 3.5: Memory inspector UI exists in frontend fixture surface.~~
- ~~Task 3.6: Self-governance side-by-side UI exists in frontend fixture surface.~~
- ~~Task 3.9: UI views exist in frontend scaffold.~~
- ~~Task 3.7: Remaining workflow templates exist as deterministic definitions: `code_compliance_scan_full`, `vendor_risk_review`, `policy_gap_analysis`, `evidence_collection`, `ai_system_intake`.~~
- ~~Partial: production workflow run persistence exists for the demo `code_compliance_scan` path.~~
- ~~Partial: production hook registry and hook-call persistence exists for deterministic MCP stub operations.~~
- ~~Partial: Task 3.2 production mode persists graph-shaped deterministic runs for every bundled template.~~
- ~~Partial: Task 3.2 persisted pause/resume/cancel and retry-attempt state for synchronous production workflow runs.~~
- ~~Partial: Task 3.2 queued workflow dispatch exists through `PRAETOR_WORKFLOW_EXECUTION_MODE=queued`, `POST /workflow-runs:drain`, and the workflow worker container.~~
- ~~Partial: Task 3.2 ready branch batches execute concurrently inside a drain cycle.~~
- ~~Partial: Task 3.2 distributed node-run leases and worker restart recovery now exist for persisted queued workflow steps.~~
- Open: Task 3.2 true long-running async step isolation and live executor heartbeat while work is still in progress.
- ~~Partial: Task 3.6 workflow agent steps are now represented as first-class `workflow_agent` assets and linked to sandbox runs.~~
- ~~Partial: Task 3.3 MCP client adapter boundary exists for hook health/calls, and MCP stubs now expose `/call`.~~
- ~~Partial: Task 3.3 JSON-RPC MCP session handshake and tool/resource listing/call path exists for stubs.~~
- ~~Partial: Task 3.3 external write effect-radius enforcement exists for hook calls and proposed-change dispatch.~~
- Open: Task 3.3 authenticated MCP sessions and richer production tool/resource negotiation beyond stubs.
- ~~Partial: sandbox runs persist Docker-oriented manifests, orchestrator mode, logs, replay results, and lifecycle state in Postgres.~~
- ~~Partial: Task 3.4 `apps/sandbox` now exposes a launch service that runs containers through the mounted Docker socket and falls back to deterministic replay.~~
- ~~Partial: Task 3.4 workflow agent steps invoke the sandbox launch service/replay path before model/finding output is persisted.~~
- ~~Task 3.4 workflow agent step output now originates from `praetor_sandbox.harness.agent_step` when Docker runs, or from the same typed replay contract when Docker/orchestrator is unavailable.~~
- ~~Partial: Task 3.4 sandbox log streaming endpoint and hardened default Docker isolation profile exist.~~
- Open: Task 3.4 live log tailing while the container is still running and stronger host-level isolation such as gVisor/seccomp profiles.
- ~~Partial: backend corpus storage persists ingested documents and chunks for seeded corpus IDs.~~
- ~~Task 3.8 all five seed corpora now ingest into backend storage from bundled markdown seed files.~~
- ~~Partial: production `code_compliance_scan` writes workflow and step events to `agent_event` with hash-chain continuity.~~
- ~~Runtime events and hash-chain writes are covered for every production workflow template path.~~
- ~~Runtime events now include per-step semantic trace records for hooks, corpus queries, agent execution, sandbox execution, policy gates, approvals, findings, proposals, and outbound hooks.~~
- Open: runtime events and hash-chain writes for non-workflow agent actions.

## Phase 4 - Evidence, Audit Packet, Polish

- ~~Task 4.1: Evidence Generator API stand-in.~~
- ~~Task 4.2: Audit packet API stand-in.~~
- ~~Task 4.3: Self-governance panel polish exists in frontend fixture UI.~~
- ~~Task 4.4: Multi-asset seed exists in frontend fixtures.~~
- ~~Task 4.5: Obligation graph view exists in frontend fixture UI.~~
- ~~Partial: evidence records can be generated from persisted event history.~~
- ~~Partial: evidence sweep assembles records from persisted workflow events and audit generation invokes it.~~
- ~~Partial: evidence worker loop periodically materializes records from workflow events through the production sweep endpoint.~~
- ~~Partial: evidence assembly now uses event-consumer checkpoints and attaches policy decisions plus obligation mappings where available.~~
- Open: first-class policy decision persistence for workflow gates and a Redis Streams consumer group.
- ~~Ed25519 signing for generated audit packets.~~
- ~~PDF artifact output exists for generated audit packets.~~
- ~~JSON sidecar output.~~
- ~~External audit-packet verification CLI exists: `npm run verify:audit -- <json-sidecar> --signature <signature>`.~~
- ~~Backend obligation hydration from YAML now loads bundled obligation libraries into production Postgres and serves them through `/obligations`.~~

## Phase 5 - Demo Prep

- ~~Task 5.3: Sandbox replay mode exists as deterministic API behavior.~~
- ~~Task 5.5: README/DEMO-style documentation exists, including `docs/DEMO.md` and `docs/API.md`.~~
- ~~Task 5.1: Windows-friendly npm scripts exist for demo/prod, seed, reset, and tests.~~
- Open: Task 5.2 backup video.
- Open: Task 5.4 pitch-deck slide last-mile.
- Open: Task 5.6 three full rehearsals.
- ~~Production reset command clears Postgres demo rows and reseeds consistently: `npm run reset:prod`.~~

## External Reliance Surface

- ~~Model provider registry: `GET /models/providers`.~~
- ~~Provider-neutral completion endpoint: `POST /models:complete`.~~
- ~~OpenAI adapter isolated in `services/model_providers.py`.~~
- ~~Anthropic adapter isolated in `services/model_providers.py`.~~
- ~~Google adapter isolated in `services/model_providers.py`.~~
- ~~Hook registry: `GET /hooks`.~~
- ~~Hook health check: `POST /hooks/{id}:test`.~~
- ~~Hook operation calls: `POST /hooks/{id}:call`.~~
- ~~Selected model/provider is persisted for production `code_compliance_scan` workflow runs and agent step inputs.~~
- ~~Production agent workflow steps call the selected model provider when `PRAETOR_AGENT_MODEL_MODE=auto` and the key is configured, or when `PRAETOR_AGENT_MODEL_MODE=live`.~~
- ~~Offline provider readiness endpoint: `GET /models/readiness`.~~
- ~~Provider live smoke-test endpoint: `POST /models:check` with `live=true`.~~
- ~~OpenAI adapter confirmed against official docs fallback search: Responses API uses `/v1/responses`, `model`, `input`, `instructions`, and `output_text`; default OpenAI models updated to GPT-5.x options.~~
- ~~MCP-style stub hook calls now flow through an adapter boundary before falling back to deterministic local simulation.~~
- ~~Proprietary JSON Hook Stack exists for REST/OpenAPI/internal integrations, with catalog, validation, request preview, and production hook-call integration.~~
- ~~Initial JSON Stack catalog includes OneDrive/SharePoint, Power Platform, Salesforce, ServiceNow IRM/GRC, and OneTrust GRC templates.~~
- ~~Expanded JSON Stack catalog includes GitHub, GitLab, Azure DevOps, Jira, Confluence, Google Drive, Slack, Teams, Notion, Linear, Okta, Datadog, Splunk HEC, Zendesk, and S3-compatible presigned URL templates.~~
- ~~Remediation dispatch catalog includes researched endpoint mappings for GitHub PRs, Jira issues, Linear issues, Microsoft Graph email, Slack messages, and ServiceNow records.~~
- ~~Custom JSON Stack manifests persist through `POST /hooks/json-stack` and can be called like catalog-backed hooks.~~
- ~~OpenAPI-to-JSON-Stack importer exists on `/hooks/validate` for internal REST systems and vendor APIs.~~
- ~~MCP hook auth refs can be backed by `MCP_GITHUB_TOKEN`, `MCP_SLACK_TOKEN`, and `MCP_LOCALFILES_TOKEN`; Compose stubs enforce them when set.~~
- ~~Provider-specific streaming endpoint: `POST /models:stream`.~~
- Open: store model/provider choice on real `policy_decision` rows when policy decisions move out of deterministic fixtures.
- ~~Environment-backed secret resolution exists for JSON Stack `auth_ref` values, with redacted readiness reporting and missing-secret failures.~~
- Open: replace environment-backed secret resolution with a production secret manager or vault.

## Next Implementation Queue

1. Replace dev bearer/plain env API keys with real auth and vault-backed secret management.
2. Convert the checkpointed evidence consumer from persisted `agent_event` polling to Redis Streams consumer groups.
3. Add YAML parsing and richer OpenAPI security scheme import.
4. Add dynamic OAuth client registration for remote MCP servers beyond preconfigured bearer auth refs.
5. Add provider streaming to the frontend/runtime views where live partial output is useful.

## Update Rules For Future Work

1. When a task is implemented and tested, cross it out here.
2. If a task is only covered by deterministic data or an in-memory service, mark it as `Done (demo/stub)` in prose.
3. Add the command used to verify the task under `Current Verification` if it is new.
4. Keep open production replacements visible rather than hiding them under completed demo work.
