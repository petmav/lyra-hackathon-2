# Praetor API Surface

All endpoints require `Authorization: Bearer dev` in local demo mode.

## Model Providers

- `GET /models/providers` lists configured providers and available model IDs.
- `GET /models/readiness` reports model provider key readiness without making a network call.
- `POST /models:check` validates one selected provider/model; set `live: true` to make a small upstream call.
- `POST /models:complete` runs a provider-neutral completion request.

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

Workflow agent steps use `PRAETOR_AGENT_MODEL_MODE`:

- `auto` calls the selected provider when its key is configured, otherwise records a deterministic dry-run model call.
- `live` requires the selected provider key and marks the agent step failed if the provider call fails.
- `dry_run` never calls external model providers.

## External Hooks

- `GET /hooks` lists externally reliant hook connections.
- `POST /hooks/{hook_id}:test` checks hook reachability.
- `POST /hooks/{hook_id}:call` records and executes a hook operation.
- `GET /hook-calls` lists hook calls.
- `GET /hooks/json-stack/catalog` lists proprietary JSON Hook Stack templates.
- `GET /hooks/json-stack/catalog/{stack_id}` returns a JSON Stack manifest.
- `POST /hooks/json-stack:validate` validates a user-provided JSON Stack manifest.
- `POST /hooks/json-stack:preview` renders a dry-run request for a stack operation.

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
- `notion_json` with `create_page`
- `linear_json` with `graphql`
- `okta_json` with `list_users`
- `datadog_json` with `query_events`
- `splunk_hec_json` with `send_event`
- `zendesk_json` with `create_ticket`
- `s3_presigned_json` with `put_object_presigned`

In production mode, hook health and calls go through an MCP-style adapter first. The bundled stub containers expose `GET /resources` and `POST /call`; if a stub is unavailable during local tests, the API records a deterministic fallback result.
The MCP adapter now attempts JSON-RPC-style `initialize`, `tools/list`, `resources/list`, and `tools/call` exchanges at `/mcp` before falling back to the older HTTP stub endpoints.

For `kind=json_stack` hooks, production mode uses the proprietary JSON Hook Stack renderer. Dry-run previews are safe by default and redact `auth_ref` material.
Non-dry-run JSON Stack calls resolve `auth_ref` values from environment variables and fail with `missing-secret` when the required token is absent. No secret values are returned by the API.

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
and periodically calls `POST /evidence-records:sweep` to materialize evidence in the background.

Workflow definition responses include the full frontend contract: `trigger_config`, `inputs_schema`,
`outputs_schema`, `required_hooks`, `required_corpora`, `default_policy_set`, and optional
`template_origin`.

Workflow-run responses include entity metadata, `asset_id`, `evidence_record_ids`, normalized
step fields, and DAG `depends_on` edges. The frontend creates production runs through
`POST /workflows/{id}:run`; fixture run ids such as `wfr_2026_04_28_001` are demo-only.

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
- `GET /sandbox-runs`
- `GET /sandbox-runs/{id}`
- `GET /sandbox-runs/{id}/logs`
- `POST /audit-packets:generate`

Production sandbox runs call the `apps/sandbox` orchestrator when `SANDBOX_ORCHESTRATOR_URL` is configured. The orchestrator exposes `GET /health` and `POST /launch`, attempts Docker execution, and returns deterministic replay output when Docker is unavailable.
Sandbox launch manifests include a hardened default isolation profile: no network except the configured mock network, read-only root filesystem, `/tmp` tmpfs, memory limit, PID limit, dropped Linux capabilities, and `no-new-privileges`.
Sandbox logs stream as newline-delimited JSON from `GET /sandbox-runs/{id}/logs`.

## Runtime Mode

- `GET /health` reports `data_mode` and `data_backend`.
- `GET /runtime/config` reports runtime mode, `seed_demo_data`, plus default model provider/model.
- `GET /runtime/readiness` reports configured model providers, agent model mode, and JSON Stack integration secret readiness.

Modes:

- `demo` uses in-memory deterministic services for hackathon flows.
- `production` selects the Postgres data backend configuration. Production route migration is tracked in `docs/PHASE_STATUS.md`.
- `PRAETOR_SEED_DEMO_DATA=0` keeps production routes from auto-creating demo findings/proposals/evidence on read.
- `PRAETOR_SEED_DEMO_DATA=1` is only for explicit demo seeding and local demo flows.
- `PRAETOR_AUTO_MIGRATE=1` runs `alembic upgrade head` during production API startup. This is the Docker/default path for fresh Postgres volumes.
- `PRAETOR_AUTO_MIGRATE=0` disables startup migrations when an external release process owns schema changes.

Frontend data sources:

- `NEXT_PUBLIC_DATA_SOURCE=fixtures` uses frontend fixture data only and does not call the API for product data.
- `NEXT_PUBLIC_DATA_SOURCE=api` uses the API only and does not fall back to fixture records.
- `NEXT_PUBLIC_DATA_SOURCE=hybrid` is available for local development only; it uses the API with fixture fallback.
