# Integrations And Node Workflows

This document is the working architecture note for turning Praetor's deterministic workflow templates into a production node-based agentic workflow system.

## Integration Surface

Praetor should treat every external dependency as a governed integration record, not as ad hoc code inside a workflow step.

Core integration categories:

- Source control: GitHub, GitLab, Bitbucket.
- Collaboration: Slack, Microsoft Teams, email.
- Work tracking: Jira, Linear, GitHub Issues.
- Knowledge stores: Google Drive, SharePoint, Confluence, Notion.
- Object storage: S3, GCS, Azure Blob, MinIO.
- Observability and SIEM: Datadog, Splunk, Elastic, CloudWatch.
- Identity and org context: Okta, Microsoft Entra ID, HRIS systems.
- Model providers: OpenAI, Anthropic, Google, local/vLLM-compatible gateways.
- Policy engines: OPA, Cedar-compatible services, internal approval systems.
- Vector/search systems: Postgres pgvector, Pinecone, Weaviate, OpenSearch.

Each integration should have:

- `id`, `provider`, `display_name`, `kind`, `environment`, `status`.
- Auth reference, never raw secrets: `secret_ref`, `oauth_connection_id`, or workload identity.
- Declared capabilities: read/write operations, scopes, rate limits, supported payload schemas.
- Safety metadata: effect radius, approval requirement, sandbox availability, idempotency support.
- Health metadata: last checked time, latency, version, degraded reason.
- Audit metadata: created by, approved by, rotation policy, last used, last write operation.

## Node Workflow Model

The workflow runtime should move from named linear templates toward persisted graphs. Templates remain useful, but they compile to graph definitions.

Canonical node types:

- `trigger.manual`, `trigger.schedule`, `trigger.webhook`, `trigger.event`.
- `hook.in`: read from source control, files, tickets, docs, storage, or observability systems.
- `corpus.query`: retrieve obligations, policy clauses, examples, and evidence candidates.
- `model.complete`: one provider-neutral model call with selected provider/model and prompt envelope.
- `agent.run`: multi-step agent loop with tool budget, memory scope, and guardrails.
- `transform`: deterministic shaping, filtering, extraction, normalization.
- `gate.policy`: OPA or policy-service decision point.
- `gate.human`: approval, rejection, comment, escalation, and timeout.
- `sandbox.run`: execute a proposed change or command in an isolated replay container.
- `finding.emit`: persist findings and citations.
- `change.propose`: create a patch, config change, ticket, or PR draft.
- `evidence.generate`: bind events, decisions, citations, and artifacts into an evidence record.
- `audit.packet`: assemble signed audit material.
- `notify`: send Slack, Teams, email, ticket, or webhook notifications.

Graph edges should be typed:

- `data`: downstream node consumes upstream outputs.
- `control`: downstream node waits for upstream lifecycle state.
- `approval`: downstream node can only continue after a human or policy gate.
- `error`: compensating path for failure, timeout, or rejected gate.

## Runtime Semantics

Every workflow run should persist a graph snapshot. This avoids template drift changing the meaning of old evidence.

Required persisted records:

- `workflow_run`: graph snapshot, input payload, status, selected model/provider defaults.
- `node_run`: node id, node type, attempt, status, start/end timestamps, input/output redactions.
- `edge_event`: node-to-node activation, payload hash, and reason.
- `integration_call`: provider, operation, request hash, response hash, idempotency key.
- `model_call`: provider, model, prompt hash, response hash, token/cost metadata.
- `policy_decision`: policy set, input hash, decision, explanation, model/provider when model-assisted.
- `sandbox_run`: manifest, image, command, logs, result, exit code.

Execution rules:

- A node can run when every required inbound control edge is satisfied.
- Parallel branches run independently; joins specify `all`, `any`, or quorum semantics.
- Every effectful node needs an idempotency key derived from workflow run id, node id, attempt, and operation.
- Retries are per-node and policy-controlled. Retried nodes never overwrite prior attempts.
- Human gates pause the graph rather than blocking a worker process.
- Model and integration calls are deterministic from Praetor's perspective once their hashes and outputs are stored.

## UI Direction

The frontend should expose graph editing and graph execution as separate modes.

Graph editor:

- Left palette of node types grouped by trigger, retrieve, reason, gate, act, evidence.
- Center canvas with typed ports and hairline edges matching the existing editorial terminal system.
- Right inspector for node config, integration binding, model/provider, retry policy, and redaction rules.
- Validation panel for missing integrations, unsafe write nodes, unapproved scopes, and cycles.

Run view:

- Graph snapshot, not the mutable template.
- Node state overlays: queued, running, succeeded, failed, awaiting approval, skipped.
- Inspector tabs for inputs, outputs, logs, policy decisions, model calls, hook calls, evidence.
- Time-correlated event ledger with hash-chain verification.

## Migration Path

1. Keep existing deterministic templates as source templates.
2. Compile every template into a graph-shaped workflow definition.
3. Persist workflow, workflow-run, step/node-run, and event history for all templates.
4. Add node-run state transitions, retries, and pause/resume for gates.
5. Replace deterministic hook calls with MCP/integration-client calls behind the same node contract.
6. Add the graph editor only after the persisted graph runtime is stable.

## Near-Term Implementation Slices

- Persist all bundled workflow templates and let production mode run each deterministic graph.
- Add `sandbox.run` orchestration through `apps/sandbox`, with deterministic replay fallback.
- Add CI Postgres/Redis services and run opt-in DB tests in CI.
- Add an integration registry table/API after hook calls and model calls share the same audit contract.
- Add protocol-level MCP client support under the hook adapter boundary.
- Promote JSON Hook Stack manifests from catalog templates into persisted integration records so internal systems can be linked without bespoke code.
