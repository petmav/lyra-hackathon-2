# Praetor Implementation Handoff

This document summarizes the current platform state, major changes completed so far, and the next likely final productionization step.

## Current State

Praetor is now a production-shaped governed agentic workflow platform with:

- FastAPI backend with demo and production data modes.
- Next.js frontend in explicit fixture/API/hybrid modes.
- Docker Compose topology for API, web, workflow worker, sandbox orchestrator, Postgres, Redis, MinIO, OPA, and MCP stubs.
- Postgres-backed workflow, asset, hook, corpus, obligation, finding, proposed-change, sandbox, evidence, audit, and policy-decision persistence.
- Redis-backed event streaming and evidence consumption.
- Sandbox-backed workflow agent execution.
- Provider-selectable model calls across OpenAI, Anthropic, and Google.
- MCP and proprietary JSON Stack integration layers for external systems.
- Production-oriented auth and secret-management boundaries.

## Major Completed Work

### Runtime And Workflows

- Added queued workflow execution through `PRAETOR_WORKFLOW_EXECUTION_MODE=queued`.
- Added workflow worker drain loop and Compose `workflow` service.
- Added distributed step-run leases, heartbeat fields, attempt counts, and expired lease recovery.
- Added restart-safe queued execution for persisted step runs.
- Added full deterministic DAG support for planned step types:
  - `agent`
  - `corpus.query`
  - `hook.in`
  - `hook.out`
  - `transform`
  - `gate.policy`
  - `gate.human`
  - `finding.emit`
  - `change.propose`
- Added production registration for all bundled workflow templates.
- Added runtime traces per step for hooks, corpus retrieval, agent execution, sandbox, policy gates, approvals, findings, proposals, and outbound hooks.
- Added first-class `policy_decision` persistence for production `gate.policy` steps.

### Sandbox And Agent Execution

- Added sandbox orchestrator service with `/health` and `/launch`.
- Added Docker-socket launch path with deterministic replay fallback.
- Added hardened default sandbox manifest settings:
  - read-only root
  - no-new-privileges
  - dropped capabilities
  - memory/PID limits
  - mock-only network posture
- Changed workflow `agent` steps to run through sandbox harness/replay output instead of directly calling the model adapter after launch.
- Added first-class `workflow_agent` asset rows and `sandbox_run_id` links in step responses.

### Evidence And Audit

- Added checkpointed evidence worker v2.
- Replaced legacy sweep behavior in the workflow worker with `POST /evidence-records:consume`.
- Added Redis Streams consumer-group path for production evidence consumption.
- ACKs Redis Stream entries only after evidence rows commit.
- Retains persisted `agent_event` fallback if Redis is unavailable.
- Added Ed25519 audit packet signing, PDF artifact output, JSON sidecar output, and verification CLI.

### Corpus And Obligations

- Added backend ingestion for all five bundled corpus markdown seed files.
- Added Postgres-backed corpus/document/chunk persistence.
- Added obligation YAML hydration into production Postgres.
- Added Docker-package fallback obligation content and demo fallback.

### Hooks, MCP, And Integrations

- Generalized remediation dispatch beyond GitHub:
  - GitHub PRs
  - Jira issues
  - Linear issues
  - Microsoft Graph email
  - Slack messages
  - ServiceNow records
- Added effect-radius enforcement for live external writes.
- Added approval marker enforcement for effectful hook calls.
- Added idempotency keys for non-dry-run hook calls.
- Added provider response mapping through JSON Stack `output_map`.
- Added custom JSON Stack manifest persistence as first-class production hooks.
- Added JSON Stack catalog entries for systems including:
  - OneDrive/SharePoint
  - Power Platform
  - Salesforce
  - ServiceNow GRC/IRM
  - OneTrust
  - GitHub, GitLab, Azure DevOps
  - Jira, Confluence, Linear
  - Slack, Teams, Microsoft Mail
  - Google Drive, Notion, Okta
  - Datadog, Splunk HEC, Zendesk
  - S3-compatible presigned URLs
- Added OpenAPI-to-JSON-Stack importer in the UI.
- Added backend OpenAPI import endpoint for JSON and YAML.
- Added OpenAPI security scheme mapping for `apiKey`, HTTP bearer/basic, OAuth2, and OpenID Connect.
- Added MCP Streamable HTTP negotiation:
  - `initialize`
  - `tools/list`
  - `resources/list`
  - `prompts/list`
  - `tools/call`
  - session/protocol headers
- Added MCP bearer auth refs and stub enforcement.
- Added remote MCP OAuth discovery and RFC 7591 dynamic client registration when a server advertises a registration endpoint.
- Added persisted MCP OAuth connections, authorization-code callback exchange, refresh endpoint, and MCP hook token selection from authorized connections.

### Model Providers

- Added model provider registry and readiness endpoints.
- Added provider-neutral completion endpoint.
- Added provider-specific adapters for:
  - OpenAI Responses API
  - Anthropic Messages API
  - Google Gemini generateContent
- Added provider-specific streaming endpoint `POST /models:stream`.
- Normalizes OpenAI, Anthropic, and Gemini streams into:
  - `start`
  - `delta`
  - `usage`
  - `done`
  - `error`
- Added frontend `api.models.stream(...)`.
- Added `/hooks/validate` dry-run provider stream probe for OpenAI, Anthropic, and Google selections.

### Auth And Secrets

- Preserved demo bearer auth for local mode.
- Added JWT/RBAC mode:
  - `viewer`
  - `operator`
  - `admin`
- Added HS256 JWT verification for local/simple deployments.
- Added OIDC/JWKS verification for production identity providers:
  - `PRAETOR_JWT_JWKS_URI`
  - `PRAETOR_OIDC_DISCOVERY_URL`
  - issuer validation
  - audience validation
  - expiry/not-before validation
  - role extraction from `roles`, `role`, `groups`, `scope`, or `scp`
- Added Vault KV v2 secret resolution:
  - `PRAETOR_SECRET_BACKEND=env`
  - `vault`
  - `env_then_vault`
  - `vault_then_env`
- Model provider keys can resolve from Vault-backed `secret:` references.
- JSON Stack and MCP auth refs can resolve from the same secret boundary.

### Frontend And Demo/Production Split

- Added explicit frontend data source modes:
  - `fixtures`
  - `api`
  - `hybrid`
- Production frontend is API-only and does not fall back to demo fixture IDs.
- Demo mode remains fixture/in-memory-friendly.
- Fixed production route crashes and fixture ID leakage.
- Added workflow-run detail runtime trace drawers.
- Added hooks validation/import UI.
- Added provider stream probe.

### Testing And Verification

Current standard verification:

```bash
npm test
```

Latest local result:

- API tests: `42 passed, 1 skipped`
- Workflow tests: `6 passed`
- Sandbox tests: `1 passed`
- Web typecheck: passed
- Web production build: passed
- Web Playwright E2E: `14 passed` via `npm --prefix apps/web run e2e`

Other verification paths exist for:

- Docker Compose config validation.
- Live E2E platform sweep.
- Opt-in Postgres/Redis integration tests.
- Audit packet signature verification.
- Playwright screenshots under ignored `screenshots/`.
- Desktop/mobile business-flow screenshots under ignored `screenshots/e2e/`.

## Recent Commits Of Note

- `14557e4 feat(workflows): persist policy gate decisions`
- `77eabb8 feat(auth): verify oidc jwks tokens`
- `872558e feat(web): add provider stream probe`
- `7dd9267 feat(mcp): discover oauth client registration`
- `1daadf4 feat(hooks): import openapi yaml security`
- `7ae0338 feat(evidence): consume events from redis groups`
- `5b479cb feat(security): add jwt auth and vault secrets`
- `7703c5d feat(models): stream provider responses`
- `6003d92 feat(mcp): negotiate authenticated sessions`
- `d0e68eb feat(web): import openapi as json stack hooks`
- `9303456 feat(hooks): map responses and enforce idempotency`
- `ffeb865 feat(hooks): persist custom json stack manifests`
- `870c907 feat(integrations): generalize remediation dispatch`
- `f3d02b7 feat(evidence): add checkpointed event consumer`
- `0830cd5 feat(sandbox): execute workflow agents in harness`
- `9b0953d feat(workflow): add step leases and recovery`

## Remaining Work

The platform is now broadly plug-and-play for demo and initial production wiring. Remaining work is mostly hardening and completing external auth flows.

### Final Platform Step Completed

Persisted MCP OAuth clients and authorization-code/token exchange are implemented.

What landed:

- `mcp_oauth_connection` table and Alembic migration.
- `POST /mcp/oauth:start` for discovery, dynamic registration, PKCE setup, and authorization URL generation.
- `POST /mcp/oauth:callback` for authorization-code token exchange.
- `POST /mcp/oauth/{connection_id}:refresh` for refresh-token renewal.
- `GET /mcp/oauth/connections` with token/client secrets redacted.
- MCP hook calls now prefer authorized OAuth access tokens over static bearer refs.

Remaining hardening:

- Move MCP OAuth client secrets and token sets from Postgres JSONB into Vault/secret-manager write APIs.
- Add browser consent UX around the returned authorization URL.
- Add token revocation and refresh-token rotation history.

### Other Hardening Items

- Add broader OpenAPI import coverage for callbacks, links, multipart bodies, and polymorphic schemas.
- Add live model-stream traces inside workflow step drawers for actual `live` model calls.
- Add JWKS refresh-on-unknown-kid and configurable accepted algorithms beyond RS256.
- Add policy decision API/listing UI for auditors.
- Add stronger sandbox isolation such as gVisor/seccomp profiles and live log tailing while containers are still running.
- Add per-step process isolation and continuous heartbeat for all long-running non-agent step types.
- Verify the Northwind CLI supervision path against a running production API.
- Complete presentation assets: backup video, pitch deck final pass, and rehearsals.
