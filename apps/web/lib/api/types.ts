/**
 * Praetor entity types.
 *
 * Mirror the data model in `docs/superpowers/plans/2026-04-28-praetor-hackathon-build.md`
 * §2.1. The frontend treats the backend as authoritative for shapes; if the
 * backend changes, this file should be regenerated. Keep this file
 * implementation-light — it is a contract, not a runtime.
 *
 * Conventions:
 * - Every entity has a stable `id` (uuid string) and a human-readable `urn`.
 * - URNs follow `urn:praetor:<entity-type>:<tenant>:<slug>`.
 * - Timestamps are ISO 8601 strings (the API already serialises Postgres
 *   timestamptz this way).
 * - Numeric "score"-style fields are doubles in [0, 1] unless noted.
 */

// ─── shared ───────────────────────────────────────────────────────────────

export type ID = string;
export type URN = string;
export type ISOTimestamp = string;
export type SHA256 = string;

export interface Entity {
  id: ID;
  urn: URN;
  created_at: ISOTimestamp;
  updated_at: ISOTimestamp;
  created_by: string;
  version: number;
}

// ─── assets ───────────────────────────────────────────────────────────────

export type AssetType =
  | "ai_system"
  | "agent"
  | "tool"
  | "memory_store"
  | "dataset"
  | "model"
  | "workflow_agent"
  | "workflow_run";

export type RiskTier = "L1" | "L2" | "L3" | "L4";
export type Lifecycle = "discovered" | "classified" | "governed" | "ephemeral" | "deprecated";

export interface Asset extends Entity {
  type: AssetType;
  name: string;
  description?: string;
  owner_id: string;
  risk_tier: RiskTier;
  lifecycle: Lifecycle;
  parent_asset_id?: ID;
  jurisdictions: string[]; // e.g. ["eu", "us"]
  data_classifications: string[]; // e.g. ["pii", "phi"]
  sectors: string[]; // e.g. ["health"]
  tags: string[];
  fingerprint: SHA256;
  metadata: Record<string, unknown>;
  config: Record<string, unknown>;
}

// ─── obligations & controls ───────────────────────────────────────────────

export type Severity = "critical" | "high" | "medium" | "low" | "info";

export interface Obligation {
  id: ID;
  urn: URN;
  framework: string; // "eu_ai_act" | "iso_42001" | "gdpr" | ...
  citation: string; // "Annex III(5)(a)"
  text: string;
  applicability: {
    sectors?: string[];
    operator_roles?: string[];
    jurisdictions?: string[];
    asset_types?: AssetType[];
    high_risk?: boolean;
  };
  severity_default: "block" | "warn" | "info";
  version: string; // "2026.04"
}

export interface Control {
  id: ID;
  urn: URN;
  name: string;
  package: string; // OPA package, e.g. "praetor.controls.tool_permission"
  obligations_implemented: URN[];
  description?: string;
}

// ─── events ───────────────────────────────────────────────────────────────

export type EventType =
  | "asset.discovered"
  | "asset.classified"
  | "asset.deprecated"
  | "agent.thought"
  | "agent.tool.called"
  | "agent.tool.refused"
  | "agent.memory.write"
  | "agent.memory.read"
  | "policy.decision.hot"
  | "policy.decision.warm"
  | "workflow.run.started"
  | "workflow.run.finished"
  | "workflow.step.started"
  | "workflow.step.finished"
  | "hook.in.called"
  | "hook.out.called"
  | "corpus.query"
  | "finding.emitted"
  | "change.proposed"
  | "change.applied"
  | "approval.requested"
  | "approval.decided"
  | "sandbox.launched"
  | "sandbox.exited";

export interface AgentEvent {
  id: ID;
  ts: ISOTimestamp;
  asset_id: ID;
  asset_urn?: URN;
  run_id?: ID;
  parent_event_id?: ID;
  workflow_run_id?: ID;
  workflow_step_id?: string;
  type: EventType;
  actor: string; // human or agent identifier
  payload: Record<string, unknown>;
  payload_redacted?: Record<string, unknown>;
  hash_chain_prev: SHA256;
  hash_chain_self: SHA256;
}

// ─── workflows ────────────────────────────────────────────────────────────

export type StepType =
  | "agent"
  | "corpus.query"
  | "hook.in"
  | "hook.out"
  | "transform"
  | "gate.policy"
  | "gate.human"
  | "finding.emit"
  | "change.propose";

export type Trigger = "manual" | "schedule" | "webhook" | "event";

export type WorkflowPhase = "pre" | "assess" | "post";

export interface WorkflowGraphNode {
  id: string;
  type: string;
  phase: WorkflowPhase;
  label: string;
  config: Record<string, unknown>;
  depends_on?: string[];
  position: { x: number; y: number };
}

export interface WorkflowGraphEdge {
  id: string;
  from: string;
  to: string;
  kind: "data" | "control" | "approval" | "error";
}

export interface WorkflowGraph {
  nodes: WorkflowGraphNode[];
  edges: WorkflowGraphEdge[];
  phases?: WorkflowPhase[];
}

export interface WorkflowStep {
  id: string;
  type: string;
  phase?: WorkflowPhase;
  label?: string;
  with?: Record<string, unknown>;
  depends_on?: string[];
}

export interface Workflow extends Entity {
  name: string;
  description: string;
  definition: string; // YAML blob
  trigger: Trigger;
  trigger_config: Record<string, unknown>;
  inputs_schema: Record<string, unknown>;
  outputs_schema: Record<string, unknown>;
  required_hooks: string[];
  required_corpora: string[];
  default_policy_set: string;
  template_origin?: string;
  graph?: WorkflowGraph;
  steps?: WorkflowStep[];
}

export type WorkflowRunStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "awaiting_approval";

export type StepStatus =
  | "pending"
  | "running"
  | "succeeded"
  | "failed"
  | "skipped"
  | "blocked"
  | "awaiting_approval";

export interface StepRun {
  id: ID;
  workflow_run_id: ID;
  step_id: string;
  step_type: StepType;
  status: StepStatus;
  started_at?: ISOTimestamp;
  finished_at?: ISOTimestamp;
  inputs_redacted: Record<string, unknown>;
  outputs_redacted: Record<string, unknown>;
  lease_owner?: string;
  lease_expires_at?: ISOTimestamp;
  heartbeat_at?: ISOTimestamp;
  attempt_count?: number;
  sandbox_run_id?: ID;
  hook_call_id?: ID;
  policy_decision_id?: ID;
  approval_id?: ID;
  emitted_finding_ids: ID[];
  emitted_proposal_ids: ID[];
  /** Free-text edges from upstream steps (for UI graph layout). */
  depends_on: string[];
}

export interface WorkflowRun extends Entity {
  workflow_id: ID;
  asset_id: ID; // always type=workflow_run
  triggered_by: string;
  triggered_at: ISOTimestamp;
  finished_at?: ISOTimestamp;
  status: WorkflowRunStatus;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  step_runs: StepRun[];
  evidence_record_ids: ID[];
}

// ─── hooks ────────────────────────────────────────────────────────────────

export type HookKind = "mcp" | "native" | "http" | "json_stack";
export type HookDirection = "in" | "out" | "both";
export type EffectRadius = "internal" | "external_trusted" | "external_public";

export interface Hook extends Entity {
  name: string;
  kind: HookKind;
  direction: HookDirection;
  endpoint: string;
  auth_ref: string;
  scopes: string[];
  effect_radius: EffectRadius;
  enabled: boolean;
  source?: "catalog" | "custom";
  json_stack_id?: string | null;
  json_stack?: JsonStackManifest;
  last_health_check?: ISOTimestamp;
  health_status?: "ok" | "degraded" | "down";
}

export interface HookCall {
  id: ID;
  ts: ISOTimestamp;
  hook_id: ID;
  hook_name: string;
  direction: "in" | "out";
  workflow_run_id?: ID;
  step_run_id?: ID;
  inputs_redacted: Record<string, unknown>;
  outputs_redacted: Record<string, unknown>;
  status: "ok" | "failed" | "denied";
  idempotency_key?: string;
  latency_ms: number;
  errors: string[];
}

// ─── JSON Stack catalog ──────────────────────────────────────────────────

export type JsonStackCategory =
  | "code"
  | "ticketing"
  | "docs"
  | "collaboration"
  | "crm"
  | "identity"
  | "observability"
  | "grc"
  | "storage"
  | "platform";

export interface JsonStackOperationSummary {
  name: string;
  direction: HookDirection;
  effect_radius: EffectRadius;
  method: string;
  path: string;
}

export interface JsonStackCatalogEntry {
  id: string;
  name: string;
  provider: string;
  version: string;
  operations: JsonStackOperationSummary[];
}

export interface JsonStackOperation {
  direction: HookDirection;
  effect_radius: EffectRadius;
  method: string;
  path: string;
  body_template?: unknown;
  input_schema?: Record<string, string>;
  output_map?: Record<string, string>;
}

export interface JsonStackAuth {
  kind: string;
  auth_ref: string | null;
  scopes?: string[];
  scheme_name?: string;
  api_key_in?: string;
  api_key_name?: string;
  flows?: Record<string, unknown>;
  openIdConnectUrl?: string;
}

export interface JsonStackManifest {
  id: string;
  name: string;
  provider: string;
  version: string;
  base_url: string;
  auth: JsonStackAuth;
  operations: Record<string, JsonStackOperation>;
}

export interface JsonStackValidateResult {
  ok: boolean;
  errors: string[];
}

export interface JsonStackPreviewRequest {
  stack_id?: string;
  spec?: JsonStackManifest;
  operation: string;
  inputs: Record<string, unknown>;
}

export interface JsonStackPersistResult {
  ok: boolean;
  hook?: Hook;
  errors?: string[];
}

export interface JsonStackOpenApiImportRequest {
  document: string;
  stack_id: string;
  provider: string;
  auth_ref?: string | null;
  selected_operations?: string[];
}

export interface JsonStackOpenApiImportResult {
  ok: boolean;
  manifest: JsonStackManifest;
  errors: string[];
}

export interface ModelStreamRequest {
  provider?: string;
  model?: string;
  prompt: string;
  system?: string;
  dry_run?: boolean;
}

export interface ModelStreamEvent {
  type: "start" | "delta" | "usage" | "done" | "error";
  provider?: string;
  model?: string;
  text?: string;
  usage?: Record<string, unknown>;
  error?: unknown;
}

export interface JsonStackPreviewRendered {
  method: string;
  url: string;
  headers: Record<string, string>;
  json?: unknown;
  body?: unknown;
}

export interface JsonStackPreviewResult {
  ok: boolean;
  outputs: {
    mode: string;
    provider: string;
    operation: string;
    request: JsonStackPreviewRendered;
    output_map?: Record<string, string>;
  };
  latency_ms: number;
  error: string | null;
}

// ─── corpora ──────────────────────────────────────────────────────────────

export type CorpusKind =
  | "regulation"
  | "standard"
  | "internal_policy"
  | "code_repo"
  | "process_artefact"
  | "evidence_reference";

export interface Corpus extends Entity {
  name: string;
  description: string;
  kind: CorpusKind;
  framework?: string;
  jurisdiction?: string;
  parent_corpus_id?: ID;
  document_count: number;
  indexed_at: ISOTimestamp;
  retention?: string;
}

export interface PraetorDocument {
  id: ID;
  corpus_id: ID;
  source_uri: string;
  content_hash: SHA256;
  title: string;
  citation?: string;
  framework?: string;
  jurisdiction?: string;
  sector?: string;
  text_path: string; // S3 key
  parsed_structure?: Record<string, unknown>;
  chunk_count: number;
}

export interface DocumentChunk {
  id: ID;
  document_id: ID;
  ord: number;
  text: string;
  citation_path: string; // "Article 5 / paragraph 1 / point c"
  /** retrieval score, 0..1, present only when returned from search */
  score?: number;
}

// ─── findings & proposed changes ─────────────────────────────────────────

export type FindingStatus = "open" | "accepted" | "rejected" | "remediated" | "wontfix";

export interface DocumentCitation {
  document_id: ID;
  document_title: string;
  chunk_ord: number;
  citation_path: string;
  excerpt?: string;
}

export interface Finding {
  id: ID;
  urn: URN;
  workflow_run_id?: ID;
  asset_id: ID;
  title: string;
  description: string;
  severity: Severity;
  obligations_cited: URN[];
  documents_cited: DocumentCitation[];
  confidence: number; // 0..1
  status: FindingStatus;
  reviewer?: string;
  reviewed_at?: ISOTimestamp;
  proposed_change_ids: ID[];
  created_at: ISOTimestamp;
}

export type ChangeKind = "config" | "code" | "policy" | "process" | "doc";
export type DiffFormat = "unified" | "json-patch" | "config" | "markdown";
export type ProposedChangeStatus =
  | "draft"
  | "tested"
  | "awaiting_approval"
  | "approved"
  | "rejected"
  | "applied";

export interface ProposedChange {
  id: ID;
  urn: URN;
  finding_id: ID;
  kind: ChangeKind;
  diff: string;
  diff_format: DiffFormat;
  target_asset_id?: ID;
  target_hook_id?: ID;
  obligations_addressed: URN[];
  residual_risk_estimate: number; // 0..1
  sandbox_run_id?: ID;
  sandbox_result?: SandboxRunResult;
  status: ProposedChangeStatus;
  approver?: string;
  approved_at?: ISOTimestamp;
  applied_at?: ISOTimestamp;
  apply_via_hook_id?: ID;
}

// ─── sandbox ──────────────────────────────────────────────────────────────

export type SandboxStatus = "launching" | "running" | "succeeded" | "failed" | "timeout" | "oom";

export interface SandboxRun {
  id: ID;
  step_run_id?: ID;
  workflow_run_id?: ID;
  proposed_change_id?: ID;
  manifest: Record<string, unknown>;
  status: SandboxStatus;
  started_at: ISOTimestamp;
  finished_at?: ISOTimestamp;
  exit_code?: number;
  result?: Record<string, unknown>;
  /** When this run is testing a remediation, the input battery results. */
  replay_results?: SandboxReplayResult[];
}

export interface SandboxReplayResult {
  label: string;
  status: "pass" | "fail";
  detail?: string;
}

export interface SandboxRunResult {
  status: "pass" | "fail";
  cases: SandboxReplayResult[];
}

// ─── policy decisions ─────────────────────────────────────────────────────

export interface PolicyDecision {
  id: ID;
  ts: ISOTimestamp;
  engine: "opa" | "llm";
  package: string;
  outcome: "allow" | "block" | "warn";
  rationale: string;
  latency_ms: number;
  asset_id?: ID;
  workflow_run_id?: ID;
  step_run_id?: ID;
  input_hash: SHA256;
}

// ─── approvals ────────────────────────────────────────────────────────────

export type ApprovalSubjectKind = "workflow_step" | "proposed_change";
export type ApprovalOutcome = "pending" | "approved" | "rejected";

export interface Approval {
  id: ID;
  subject_kind: ApprovalSubjectKind;
  subject_id: ID;
  requested_by: string;
  role_required: string;
  decided_by?: string;
  decided_at?: ISOTimestamp;
  outcome: ApprovalOutcome;
  notes?: string;
  context: { title: string; summary: string };
}

// ─── evidence & audit packets ─────────────────────────────────────────────

export interface EvidenceRecord {
  id: ID;
  obligation_ids: URN[];
  control_id?: ID;
  asset_id?: ID;
  workflow_run_id?: ID;
  event_ids: ID[];
  decision_ids: ID[];
  hash: SHA256;
  ts: ISOTimestamp;
  summary: string;
}

export type AuditPacketStatus = "queued" | "generating" | "ready" | "failed";

export interface AuditPacket {
  id: ID;
  period_start: ISOTimestamp;
  period_end: ISOTimestamp;
  scope: {
    asset_ids?: ID[];
    workflow_run_ids?: ID[];
    obligation_urns?: URN[];
    label?: string;
  };
  status: AuditPacketStatus;
  pdf_path?: string;
  json_sidecar_path?: string;
  packet_hash?: SHA256;
  signature?: string;
  pubkey_fingerprint?: string;
  generated_at?: ISOTimestamp;
  /** counts populated in `ready` state — drives the dashboard chip */
  counts?: {
    workflow_runs: number;
    findings: number;
    proposed_changes: number;
    supervision_events: number;
    evidence_records: number;
  };
}

// ─── alerts (UI-only, derived) ────────────────────────────────────────────

export type AlertKind = "finding" | "violation" | "approval" | "system";

export interface Alert {
  id: ID;
  kind: AlertKind;
  ts: ISOTimestamp;
  title: string;
  detail: string;
  severity: Severity;
  href?: string;
}
