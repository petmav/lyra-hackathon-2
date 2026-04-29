# Praetor API Surface

All endpoints require `Authorization: Bearer dev` in local demo mode. Production can set
`PRAETOR_AUTH_MODE=jwt` to require signed JWTs with role-based read/write checks.

## Model Providers

- `GET /models/providers` lists configured providers and available model IDs.
- `GET /models/readiness` reports model provider key readiness without making a network call.
- `POST /models:check` validates one selected provider/model; set `live: true` to make a small upstream call.
- `POST /models:complete` runs a provider-neutral completion request.
- `POST /models:stream` runs the same provider-neutral request and returns normalized Server-Sent Events.

Example:

```json
{
  "provider": "openai",
  "model": "gpt-5.4-mini",
  "prompt": "Summarize this compliance gap",
  "dry_run": true
}
```

Supported provider adapters:

- `openai` via `OPENAI_API_KEY`
- `anthropic` via `ANTHROPIC_API_KEY`
- `google` via `GOOGLE_API_KEY`

`dry_run` defaults to `true`; set it to `false` only when the matching API key is configured.

Streaming responses use `text/event-stream` and normalize provider-native streaming into:

- `start` with selected provider/model metadata.
- `delta` with incremental text.
- `usage` when a provider emits incremental token usage.
- `done` with final text and usage metadata when available.
- `error` with a redacted provider/API error.

Example:

```bash
curl -N -X POST http://localhost:8000/models:stream \
  -H "Authorization: Bearer dev" \
  -H "Content-Type: application/json" \
  -d '{"provider":"anthropic","model":"claude-sonnet-4-20250514","prompt":"Summarize SOC 2 CC7.2","dry_run":true}'
```

The frontend API client exposes this as `api.models.stream(...)`; `/hooks/validate` includes a provider stream probe for dry-run streaming verification across OpenAI, Anthropic, and Google selections.

Workflow agent steps use `PRAETOR_AGENT_MODEL_MODE`:

- `auto` calls the selected provider when its key is configured, otherwise records a deterministic dry-run model call.
- `live` requires the selected provider key and marks the agent step failed if the provider call fails.
- `dry_run` never calls external model providers.

## External Hooks

- `GET /hooks` lists externally reliant hook connections.
- `GET /hooks/{hook_id}` returns one hook, including a stored custom JSON Stack manifest when present.
- `POST /hooks/{hook_id}:test` checks hook reachability.
- `POST /hooks/{hook_id}:call` records and executes a hook operation.
- `GET /hook-calls` lists hook calls.
- `GET /hooks/json-stack/catalog` lists proprietary JSON Hook Stack templates.
- `GET /hooks/json-stack/catalog/{stack_id}` returns a JSON Stack manifest.
- `POST /hooks/json-stack:validate` validates a user-provided JSON Stack manifest.
- `POST /hooks/json-stack:import-openapi` accepts OpenAPI JSON or YAML and converts selected operations into a JSON Stack manifest, including supported security scheme metadata.
- `POST /hooks/json-stack:preview` renders a dry-run request for a stack operation.
- `POST /hooks/json-stack` validates and persists a user-provided JSON Stack manifest as a first-class `hook` record in production mode.

The frontend `/hooks/validate` page includes an OpenAPI JSON/YAML importer that extracts selected operations, infers JSON Stack direction/effect metadata, builds input schemas and output maps, imports OpenAPI `securitySchemes`, and saves the generated manifest through `POST /hooks/json-stack`.

Demo hook operations:

- `github_stub` with `read_repo` or `open_pr`
- `slack_stub` with `request_approval`
- `localfiles_stub` with `read`
- `onedrive_json` with `list_children` or `upload_small_file`
- `power_platform_json` with `import_openapi_connector`
- `salesforce_json` with `describe_sobject` or `create_sobject`
- `servicenow_grc_json` with `query_table` or `create_issue`
- `onetrust_grc_json` with `list_risks` or `create_evidence`
- `github_json` with `list_pull_requests` or `create_pull_request`
- `gitlab_json` with `list_merge_requests` or `create_merge_request`
- `azure_devops_json` with `create_pull_request`
- `jira_json` with `search_issues` or `create_issue`
- `confluence_json` with `search_content` or `create_page`
- `google_drive_json` with `list_files`
- `slack_json` with `post_message`
- `teams_json` with `send_channel_message`
- `microsoft_mail_json` with `send_mail`
- `notion_json` with `create_page`
- `linear_json` with `create_issue` or `graphql`
- `okta_json` with `list_users`
- `datadog_json` with `query_events`
- `splunk_hec_json` with `send_event`
- `zendesk_json` with `create_ticket`
- `s3_presigned_json` with `put_object_presigned`

In production mode, hook health and calls go through an MCP-style adapter first. The bundled stub containers expose `GET /resources` and `POST /call`; if a stub is unavailable during local tests, the API records a deterministic fallback result.
The MCP adapter now attempts JSON-RPC-style `initialize`, `tools/list`, `resources/list`, and `tools/call` exchanges at `/mcp` before falling back to the older HTTP stub endpoints.
MCP calls now use the Streamable HTTP session shape: initialize negotiates protocol version and server capabilities, subsequent requests include `MCP-Session-Id`, `MCP-Protocol-Version`, `Mcp-Method`, and `Mcp-Name` where applicable, and hook `auth_ref` values are sent as bearer tokens when configured. Health checks also negotiate `tools/list`, `resources/list`, and `prompts/list`.
When a remote MCP server requires OAuth and advertises protected-resource metadata, the MCP client can discover authorization-server metadata and perform RFC 7591 dynamic client registration when a `registration_endpoint` is available. Registered client secrets are redacted in health output.

For `kind=json_stack` hooks, production mode uses the proprietary JSON Hook Stack renderer. Dry-run previews are safe by default and redact `auth_ref` material.
Non-dry-run JSON Stack calls resolve `auth_ref` values from environment variables and fail with `missing-secret` when the required token is absent. No secret values are returned by the API.
Effectful non-dry-run production calls to external hooks require an approval marker. Direct `POST /hooks/{hook_id}:call` requests can pass `effect_approved: true`; proposed-change dispatch sets that marker only after the change has passed sandbox replay and has been approved.
Hook calls return an `idempotency_key`. Non-dry-run calls with the same hook, operation, scope, and input hash replay the previous successful `HookCall` instead of sending a second external write; callers can also pass an explicit `idempotency_key` in service code. JSON Stack live responses include provider-specific mapped fields under `outputs_redacted.mapped` when an operation declares `output_map`.

Persist a custom internal system:

```json
{
  "spec": {
    "id": "internal_ticketing",
    "name": "Internal Ticketing",
    "provider": "internal_ticketing",
    "version": "2026-04",
    "base_url": "https://tickets.internal.example",
    "auth": {
      "kind": "bearer",
      "auth_ref": "secret:internal_ticketing_token",
      "scopes": ["tickets.write"]
    },
    "operations": {
      "create_ticket": {
        "direction": "out",
        "effect_radius": "external_trusted",
        "method": "POST",
        "path": "/api/tickets",
        "body_template": {"title": "{title}", "body": "{body}"},
        "input_schema": {"title": "string", "body": "string"},
        "output_map": {"id": "$.id"}
      }
    }
  },
  "enabled": true
}
```

## Workflow Runtime

- `GET /workflows`
- `GET /workflows/{id}`
- `POST /workflows/{id}:run`
- `GET /workflow-runs/{id}`
- `GET /workflow-runs`
- `POST /workflow-runs/{id}:resume`
- `POST /workflow-runs/{id}:cancel`
- `POST /workflow-runs:drain`
- `GET /events?workflow_run_id=...`
- `GET /events?asset_id=...`
- `WS /ws/v1/workflow-runs/{id}/stream?token=dev`
- `WS /ws/v1/assets/{id}/stream?token=dev`

Workflow runs accept `model_provider` and `model` at request time.
Set `PRAETOR_WORKFLOW_EXECUTION_MODE=sync` to execute a run inside the API request, or
`PRAETOR_WORKFLOW_EXECUTION_MODE=queued` to persist runs as `queued` and let the workflow worker
drain them through `POST /workflow-runs:drain`. The Compose `workflow` service runs this drain loop
and periodically calls `POST /evidence-records:consume` to materialize evidence in the background.
In production mode, evidence consumption first uses a Redis Streams consumer group over the
hash-chained event stream and ACKs entries only after evidence rows commit; if Redis is unavailable,
the endpoint falls back to the persisted event table cursor.

Workflow definition responses include the full frontend contract: `trigger_config`, `inputs_schema`,
`outputs_schema`, `required_hooks`, `required_corpora`, `default_policy_set`, and optional
`template_origin`.

Workflow-run responses include entity metadata, `asset_id`, `evidence_record_ids`, normalized
step fields, and DAG `depends_on` edges. The frontend creates production runs through
`POST /workflows/{id}:run`; fixture run ids such as `wfr_2026_04_28_001` are demo-only.
Workflow `agent` steps create first-class `workflow_agent` assets, launch through the sandbox
orchestrator/replay contract, persist linked `sandbox_run` rows, and expose `sandbox_run_id` in
their step response.

Production mode registers the bundled deterministic workflow templates:

- `code_compliance_scan`
- `code_compliance_scan_full`
- `vendor_risk_review`
- `policy_gap_analysis`
- `evidence_collection`
- `ai_system_intake`

Workflow runs now publish hash-chained events. In `demo` mode the stream is backed by an in-memory event log. In `production` mode the stream service writes to Redis Streams.
Production runs that pause at `gate.human` can be resumed through `POST /workflow-runs/{id}:resume`; cancelled runs are marked through `POST /workflow-runs/{id}:cancel`.

## Inventory, Obligations, Controls

- `GET /assets`
- `GET /assets/{id}`
- `GET /assets/{id}/children`
- `GET /obligations`
- `GET /obligations/{id-or-urn}`
- `GET /controls`

## Knowledge And Evidence

- `POST /corpora/{id}/documents:ingest`
- `POST /corpora/{id}:search`
- `GET /findings`
- `POST /proposed-changes/{id}:sandbox-run`
- `POST /proposed-changes/{id}:approve`
- `POST /proposed-changes/{id}:apply`
- `GET /evidence-records`
- `POST /evidence-records:sweep`
- `POST /evidence-records:consume`
- `GET /sandbox-runs`
- `GET /sandbox-runs/{id}`
- `GET /sandbox-runs/{id}/logs`
- `POST /audit-packets:generate`

Production sandbox runs call the `apps/sandbox` orchestrator when `SANDBOX_ORCHESTRATOR_URL` is configured. The orchestrator exposes `GET /health` and `POST /launch`, attempts Docker execution, and returns deterministic replay output when Docker is unavailable.
Sandbox launch manifests include a hardened default isolation profile: no network except the configured mock network, read-only root filesystem, `/tmp` tmpfs, memory limit, PID limit, dropped Linux capabilities, and `no-new-privileges`.
Sandbox logs stream as newline-delimited JSON from `GET /sandbox-runs/{id}/logs`.

Approved proposed changes can be dispatched to any supported outbound hook, not only source control. `POST /proposed-changes/{id}:apply` accepts:

```json
{
  "hook_id": "jira_json",
  "operation": "create_issue",
  "dry_run": true,
  "inputs": {
    "site": "northwind"
  }
}
```

Built-in dispatch options include GitHub pull requests, Jira issues, Linear issues, Microsoft Graph email, Slack messages, and ServiceNow records. `dry_run` defaults to `true` and returns `status: dispatch_previewed` without marking the change applied; set it to `false` only after configuring the destination secret.

## Runtime Mode

- `GET /health` reports `data_mode` and `data_backend`.
- `GET /runtime/config` reports runtime mode, `seed_demo_data`, plus default model provider/model.
- `GET /runtime/readiness` reports configured model providers, agent model mode, and JSON Stack integration secret readiness.

Modes:

- `demo` uses in-memory deterministic services for hackathon flows.
- `production` selects the Postgres data backend configuration. Production route migration is tracked in `docs/PHASE_STATUS.md`.
- `PRAETOR_AUTH_MODE=dev_bearer` keeps demo bearer auth; `PRAETOR_AUTH_MODE=jwt` enables HS256 JWT verification with viewer/operator/admin RBAC.
- `PRAETOR_SECRET_BACKEND=env|vault|env_then_vault|vault_then_env` controls how model/API/hook `secret:` references resolve.
- `PRAETOR_SEED_DEMO_DATA=0` keeps production routes from auto-creating demo findings/proposals/evidence on read.
- `PRAETOR_SEED_DEMO_DATA=1` is only for explicit demo seeding and local demo flows.
- `PRAETOR_AUTO_MIGRATE=1` runs `alembic upgrade head` during production API startup. This is the Docker/default path for fresh Postgres volumes.
- `PRAETOR_AUTO_MIGRATE=0` disables startup migrations when an external release process owns schema changes.

Frontend data sources:

- `NEXT_PUBLIC_DATA_SOURCE=fixtures` uses frontend fixture data only and does not call the API for product data.
- `NEXT_PUBLIC_DATA_SOURCE=api` uses the API only and does not fall back to fixture records.
- `NEXT_PUBLIC_DATA_SOURCE=hybrid` is available for local development only; it uses the API with fixture fallback.
