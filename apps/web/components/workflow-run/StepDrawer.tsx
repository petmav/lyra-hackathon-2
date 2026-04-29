"use client";

import type { AgentEvent, StepRun, WorkflowRun } from "@/lib/api/types";
import { Drawer } from "@/components/primitives/Drawer";
import { Badge } from "@/components/primitives/Badge";
import { AgentDetail } from "@/components/agent-detail/AgentDetail";
import { useEventStream } from "@/lib/ws/stream";
import { Hairline } from "@/components/primitives/Hairline";
import { Timestamp } from "@/components/data/Timestamp";

export function StepDrawer({
  step,
  run,
  open,
  onClose
}: {
  step: StepRun | null;
  run: WorkflowRun;
  open: boolean;
  onClose: () => void;
}) {
  const isAgent = step?.step_type === "agent";
  const { events, connected } = useEventStream({ kind: "workflowRun", id: run.id }, { live: open });
  const stepEvents = step ? events.filter((e) => e.workflow_step_id === step.step_id) : [];
  const wfaAssetId = workflowAgentAssetId(step);
  const wfaAssetUrn = workflowAgentAssetUrn(step, run.id);

  return (
    <Drawer
      open={open}
      onClose={onClose}
      width={isAgent ? "xl" : "wide"}
      subtitle={`Step - ${step?.step_type ?? "-"}`}
      title={step ? <span className="font-mono">{step.step_id}</span> : "Step"}
    >
      {step && (
        <div className="px-6 py-5">
          <Meta step={step} run={run} />
          <Hairline className="my-6" />
          <StepTrace step={step} events={stepEvents} connected={connected} />
          <Hairline className="my-6" />
          {isAgent ? (
            <AgentForStep stepRun={step} wfaAssetId={wfaAssetId} wfaAssetUrn={wfaAssetUrn} events={stepEvents} />
          ) : (
            <NonAgentBody step={step} />
          )}
        </div>
      )}
    </Drawer>
  );
}

function AgentForStep({
  stepRun,
  wfaAssetId,
  wfaAssetUrn,
  events
}: {
  stepRun: StepRun;
  wfaAssetId: string;
  wfaAssetUrn: string;
  events: AgentEvent[];
}) {
  return (
    <AgentDetail
      asset={{
        id: wfaAssetId,
        urn: wfaAssetUrn,
        type: "workflow_agent",
        name: `${stepRun.step_id} agent - ${stepRun.step_type}`,
        risk_tier: "L2",
        lifecycle: "ephemeral"
      }}
      events={events}
      compact
    />
  );
}

function StepTrace({ step, events, connected }: { step: StepRun; events: AgentEvent[]; connected: boolean }) {
  const traceEvents = events.length > 0 ? events : fallbackEvents(step);
  return (
    <section>
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <div className="smallcaps">Runtime trace</div>
          <div className="mt-1 text-[12px] text-paper-dim">
            Auditable work log, final outputs, tool use, policy decisions, and sandbox status.
          </div>
        </div>
        <Badge tone={connected ? "ok" : "muted"}>{connected ? "stream connected" : "history"}</Badge>
      </div>
      <ol className="border-l border-rule">
        {traceEvents.map((event, index) => {
          const entry = traceEntry(event);
          return (
            <li key={event.id ?? `${event.type}-${index}`} className="relative ml-4 pb-4 last:pb-0">
              <span className="absolute -left-[21px] top-1 h-2 w-2 border border-gold bg-ink" aria-hidden />
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <Badge tone={eventTone(event.type)}>{event.type}</Badge>
                <span className="font-mono text-[11px] text-paper-fade">{event.actor}</span>
                {event.ts && <Timestamp ts={event.ts} mode="relative" />}
              </div>
              <div className="mt-2 text-[13px] text-paper">{entry.title}</div>
              {entry.detail && <div className="mt-1 text-[12px] text-paper-dim">{entry.detail}</div>}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function NonAgentBody({ step }: { step: StepRun }) {
  return (
    <div className="grid gap-6">
      <Field label="Step type">
        <span className="font-mono text-paper">{step.step_type}</span>
      </Field>
      {step.sandbox_run_id && (
        <Field label="Sandbox run">
          <span className="font-mono text-paper-dim">{step.sandbox_run_id}</span>
        </Field>
      )}
      {step.hook_call_id && (
        <Field label="Hook call">
          <span className="font-mono text-paper-dim">{step.hook_call_id}</span>
        </Field>
      )}
      {step.policy_decision_id && (
        <Field label="Policy decision">
          <span className="font-mono text-paper-dim">{step.policy_decision_id}</span>
        </Field>
      )}
      {step.approval_id && (
        <Field label="Approval">
          <span className="font-mono text-paper-dim">{step.approval_id}</span>
        </Field>
      )}
      <JsonField label="Inputs (redacted)" value={step.inputs_redacted} />
      <JsonField label="Outputs (redacted)" value={step.outputs_redacted} />
    </div>
  );
}

function Meta({ step, run }: { step: StepRun; run: WorkflowRun }) {
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-[12px]">
      <Field label="Status">
        <Badge tone={statusTone(step.status)}>{step.status}</Badge>
      </Field>
      <Field label="Run">
        <span className="font-mono text-paper-dim">{run.id}</span>
      </Field>
      <Field label="Started">
        {step.started_at ? <Timestamp ts={step.started_at} mode="precise" /> : <span className="text-paper-fade">-</span>}
      </Field>
      <Field label="Finished">
        {step.finished_at ? <Timestamp ts={step.finished_at} mode="precise" /> : <span className="text-paper-fade">-</span>}
      </Field>
    </dl>
  );
}

function JsonField({ label, value }: { label: string; value: unknown }) {
  return (
    <Field label={label}>
      <pre className="font-mono text-[12px] text-paper-dim whitespace-pre-wrap break-words border-l border-rule pl-3">
        {JSON.stringify(value ?? {}, null, 2)}
      </pre>
    </Field>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="smallcaps mb-1">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function statusTone(s: StepRun["status"]) {
  if (s === "running") return "gold" as const;
  if (s === "succeeded") return "ok" as const;
  if (s === "failed") return "crit" as const;
  if (s === "awaiting_approval") return "warn" as const;
  return "muted" as const;
}

function workflowAgentAssetId(step: StepRun | null) {
  const value = step?.outputs_redacted?.workflow_agent_asset_id;
  return typeof value === "string" && value.length > 0 ? value : `asset_wfa_${step?.step_id ?? "step"}`;
}

function workflowAgentAssetUrn(step: StepRun | null, runId: string) {
  const value = step?.outputs_redacted?.workflow_agent_asset_urn;
  return typeof value === "string" && value.length > 0
    ? value
    : `urn:praetor:asset:workflow_agent:${runId}:${step?.step_id ?? "step"}`;
}

function fallbackEvents(step: StepRun): AgentEvent[] {
  return [
    {
      id: `fallback-${step.step_id}`,
      ts: step.finished_at ?? step.started_at ?? new Date().toISOString(),
      asset_id: "workflow_runtime",
      workflow_step_id: step.step_id,
      type: "workflow.step.finished",
      actor: "workflow_runtime",
      payload: {
        step_id: step.step_id,
        step_type: step.step_type,
        status: step.status,
        outputs_redacted: step.outputs_redacted
      },
      hash_chain_prev: "",
      hash_chain_self: ""
    }
  ];
}

function traceEntry(event: AgentEvent) {
  const payload = event.payload ?? {};
  const summary = asText(payload.summary);
  switch (event.type) {
    case "workflow.step.started":
      return { title: `Started ${asText(payload.step_type) || "workflow"} step.`, detail: redactSummary(payload.inputs_redacted) };
    case "workflow.step.finished":
      return { title: `Finished with status ${asText(payload.status) || "unknown"}.`, detail: redactSummary(payload.outputs_redacted) };
    case "hook.in.called":
      return { title: summary || "Inbound hook returned source artefacts.", detail: compactPairs(payload, ["repo_url", "files_returned"]) };
    case "hook.out.called":
      return { title: summary || "Outbound hook completed.", detail: compactPairs(payload, ["hook_id", "operation", "url"]) };
    case "corpus.query":
      return { title: summary || "Corpus retrieval completed.", detail: compactPairs(payload, ["query", "chunks_returned", "top_score"]) };
    case "agent.thought":
      return { title: asText(payload.text) || "Agent recorded an auditable rationale summary.", detail: compactPairs(payload, ["model_provider", "model", "model_mode", "findings_count"]) };
    case "agent.tool.called":
      return { title: summary || `Tool ${asText(payload.name) || "call"} completed.`, detail: compactPairs(payload, ["name", "status", "items"]) };
    case "policy.decision.warm":
    case "policy.decision.hot":
      return { title: summary || "Policy gate evaluated the step.", detail: compactPairs(payload, ["outcome", "severity", "policy_set", "package"]) };
    case "approval.requested":
      return { title: "Human approval requested.", detail: compactPairs(payload, ["role_required"]) };
    case "approval.decided":
      return { title: `Human approval ${asText(payload.outcome) || "decided"}.`, detail: compactPairs(payload, ["approver"]) };
    case "sandbox.launched":
      return { title: "Sandbox launched for isolated execution.", detail: compactPairs(payload, ["sandbox_run_id", "workflow_agent_asset_id", "mode"]) };
    case "sandbox.exited":
      return { title: "Sandbox execution finished.", detail: compactPairs(payload, ["sandbox_run_id", "exit_code", "fallback_reason"]) };
    case "finding.emitted":
      return { title: findingTitle(payload), detail: compactPairs(payload.finding, ["severity", "confidence"]) };
    case "change.proposed":
      return { title: changeTitle(payload), detail: compactPairs(payload.change, ["kind", "diff_format", "finding_id"]) };
    default:
      return { title: summary || "Runtime event recorded.", detail: redactSummary(payload) };
  }
}

function eventTone(type: AgentEvent["type"]) {
  if (type.includes("failed") || type.includes("refused")) return "crit" as const;
  if (type.includes("policy") || type.includes("approval")) return "warn" as const;
  if (type.includes("finished") || type.includes("emitted") || type.includes("proposed")) return "ok" as const;
  return "muted" as const;
}

function compactPairs(value: unknown, keys: string[]) {
  if (!isRecord(value)) return undefined;
  const pairs = keys
    .map((key) => [key, value[key]] as const)
    .filter(([, v]) => v !== undefined && v !== null && v !== "");
  if (pairs.length === 0) return undefined;
  return pairs.map(([key, v]) => `${key}=${formatValue(v)}`).join(" - ");
}

function redactSummary(value: unknown) {
  if (!isRecord(value)) return undefined;
  const keys = Object.keys(value);
  if (keys.length === 0) return undefined;
  return keys.slice(0, 4).map((key) => `${key}=${formatValue(value[key])}`).join(" - ");
}

function findingTitle(payload: Record<string, unknown>) {
  const finding = payload.finding;
  if (isRecord(finding) && typeof finding.title === "string") return `Finding emitted: ${finding.title}`;
  return "Finding emitted.";
}

function changeTitle(payload: Record<string, unknown>) {
  const change = payload.change;
  if (isRecord(change) && typeof change.id === "string") return `Proposed change ${change.id} created.`;
  return "Proposed change created.";
}

function formatValue(value: unknown) {
  if (Array.isArray(value)) return `[${value.length}]`;
  if (typeof value === "object" && value !== null) return "{...}";
  return String(value);
}

function asText(value: unknown) {
  return typeof value === "string" ? value : undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
