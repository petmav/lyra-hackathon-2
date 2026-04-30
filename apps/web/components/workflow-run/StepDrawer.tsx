"use client";

import type { AgentEvent, StepRun, Workflow, WorkflowGraphNode, WorkflowRun } from "@/lib/api/types";
import { Drawer } from "@/components/primitives/Drawer";
import { Badge } from "@/components/primitives/Badge";
import { AgentDetail } from "@/components/agent-detail/AgentDetail";
import { useEventStream } from "@/lib/ws/stream";
import { Hairline } from "@/components/primitives/Hairline";
import { Timestamp } from "@/components/data/Timestamp";

export function StepDrawer({
  step,
  run,
  workflow,
  open,
  onClose
}: {
  step: StepRun | null;
  run: WorkflowRun;
  workflow?: Workflow | null;
  open: boolean;
  onClose: () => void;
}) {
  const isAgent = step?.step_type === "agent";
  const { events, connected } = useEventStream({ kind: "workflowRun", id: run.id }, { live: open });
  const stepEvents = step ? events.filter((e) => e.workflow_step_id === step.step_id) : [];
  const wfaAssetId = workflowAgentAssetId(step);
  const wfaAssetUrn = workflowAgentAssetUrn(step, run.id);
  const definition = step ? findStepDefinition(workflow, step) : null;

  return (
    <Drawer
      open={open}
      onClose={onClose}
      width={isAgent ? "xl" : "wide"}
      subtitle={`Step · ${step?.step_type ?? "—"}`}
      title={step ? <span className="font-mono">{step.step_id}</span> : "Step"}
    >
      {step && (
        <div className="px-6 py-5">
          <Meta step={step} run={run} />
          <Hairline className="my-6" />
          <StepDefinition step={step} definition={definition} />
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

function findStepDefinition(workflow: Workflow | null | undefined, step: StepRun): WorkflowGraphNode | null {
  if (!workflow) return null;
  const fromGraph = workflow.graph?.nodes?.find((n) => n.id === step.step_id);
  if (fromGraph) return fromGraph;
  const fromSteps = workflow.steps?.find((s) => s.id === step.step_id);
  if (!fromSteps) return null;
  return {
    id: fromSteps.id,
    type: fromSteps.type,
    phase: (fromSteps.phase ?? "pre"),
    label: fromSteps.label ?? fromSteps.id,
    config: (fromSteps.with ?? {}) as Record<string, unknown>,
    depends_on: fromSteps.depends_on,
    position: { x: 0, y: 0 }
  };
}

const PHASE_TONE: Record<"pre" | "assess" | "post", "info" | "gold" | "warn"> = {
  pre: "info",
  assess: "gold",
  post: "warn"
};

function StepDefinition({ step, definition }: { step: StepRun; definition: WorkflowGraphNode | null }) {
  const dependsOn = definition?.depends_on?.length ? definition.depends_on : step.depends_on;
  const config = definition?.config ?? {};
  const configEntries = Object.entries(config).filter(([, v]) => v !== undefined && v !== null && v !== "");
  return (
    <section>
      <div className="mb-3">
        <div className="smallcaps">Definition</div>
        <div className="mt-1 text-[12px] text-paper-dim">
          The static shape of this step, as defined in the workflow graph.
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-[12px]">
        <Field label="Type">
          <span className="font-mono text-paper">{step.step_type}</span>
        </Field>
        {definition && (
          <Field label="Phase">
            <Badge tone={PHASE_TONE[definition.phase]}>{definition.phase}</Badge>
          </Field>
        )}
        {definition?.label && definition.label !== step.step_id && (
          <Field label="Label">
            <span className="text-paper">{definition.label}</span>
          </Field>
        )}
        <Field label="Depends on">
          {dependsOn && dependsOn.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {dependsOn.map((id) => (
                <span key={id} className="font-mono text-[11.5px] text-paper-dim border border-rule rounded-sm px-1.5 py-0.5">
                  {id}
                </span>
              ))}
            </div>
          ) : (
            <span className="text-paper-fade">none</span>
          )}
        </Field>
      </dl>
      <div className="mt-4">
        <div className="text-[10.5px] font-medium uppercase tracking-[0.08em] text-paper-fade mb-1.5">
          Configuration
        </div>
        {configEntries.length === 0 ? (
          <div className="text-[12px] text-paper-fade italic">
            {definition
              ? "No configuration was set on this step in the workflow definition."
              : "Workflow definition not available — showing runtime data only."}
          </div>
        ) : (
          <ul className="border border-rule rounded-sm divide-y divide-rule">
            {configEntries.map(([key, value]) => (
              <li key={key} className="flex items-baseline gap-3 px-3 py-2 text-[12px]">
                <span className="font-mono text-paper-fade w-32 shrink-0 truncate">{key}</span>
                <span className="font-mono text-paper-dim break-all flex-1">{formatConfigValue(value)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function formatConfigValue(value: unknown): string {
  if (Array.isArray(value)) return value.length === 0 ? "[]" : `[${value.join(", ")}]`;
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
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
  const visibleEvents = events.length > 0 ? events : syntheticAgentEvents(stepRun, wfaAssetId);
  return (
    <section className="space-y-5">
      <AgentOutputSummary step={stepRun} />
      <AgentDetail
        asset={{
          id: wfaAssetId,
          urn: wfaAssetUrn,
          type: "workflow_agent",
          name: `${stepRun.step_id} agent - ${stepRun.step_type}`,
          risk_tier: "L2",
          lifecycle: "ephemeral"
        }}
        events={visibleEvents}
        compact
      />
    </section>
  );
}

function AgentOutputSummary({ step }: { step: StepRun }) {
  const output = step.outputs_redacted ?? {};
  const modelCall = isRecord(output.model_call) ? output.model_call : {};
  const findings = Array.isArray(output.findings) ? output.findings : [];
  const tools = Array.isArray(output.tools) ? output.tools : [];
  const changeRequests = Array.isArray(output.change_requests) ? output.change_requests : [];
  const summary = isRecord(output.verification_summary) ? output.verification_summary : {};
  const thoughtText = typeof modelCall.text === "string" && modelCall.text.length > 0
    ? modelCall.text
    : `Agent completed with status ${String(output.compliance_status ?? step.status)}.`;
  return (
    <div className="border border-rule bg-ink-2">
      <div className="border-b border-rule px-4 py-3">
        <div className="smallcaps">Agent output and thinking</div>
        <div className="mt-1 text-[12px] text-paper-dim">
          Auditable rationale summary, tool calls, findings, and raw sandbox output for this step.
        </div>
      </div>
      <div className="grid gap-4 p-4 xl:grid-cols-[1fr_1fr]">
        <div className="border border-rule p-3">
          <div className="smallcaps mb-2">Thinking summary</div>
          <p className="text-[13px] leading-snug text-paper">{thoughtText}</p>
          <dl className="mt-3 grid grid-cols-2 gap-2 text-[11.5px]">
            <Field label="Provider"><span className="font-mono text-paper-dim">{String(output.model_provider ?? "praetor")}</span></Field>
            <Field label="Model"><span className="font-mono text-paper-dim">{String(output.model ?? "deterministic")}</span></Field>
            <Field label="Files scanned"><span className="font-mono text-paper-dim">{String(summary.source_files_scanned ?? "-")}</span></Field>
            <Field label="Findings"><span className="font-mono text-paper-dim">{String(summary.findings_count ?? findings.length)}</span></Field>
          </dl>
        </div>
        <div className="border border-rule p-3">
          <div className="smallcaps mb-2">Tools</div>
          {tools.length === 0 ? (
            <div className="text-[12px] text-paper-fade italic">No tool calls captured.</div>
          ) : (
            <ul className="space-y-2">
              {tools.map((tool, index) => (
                <li key={index} className="flex items-center justify-between gap-3 border-b border-rule pb-2 last:border-b-0 last:pb-0">
                  <span className="font-mono text-[12px] text-paper">{String((tool as Record<string, unknown>).name ?? "tool")}</span>
                  <span className="font-mono text-[11px] text-paper-dim">
                    {String((tool as Record<string, unknown>).status ?? "ok")} · {String((tool as Record<string, unknown>).items ?? "-")}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <div className="grid gap-4 border-t border-rule p-4 xl:grid-cols-[1fr_1fr]">
        <JsonField label="Findings" value={findings} hasContent={findings.length > 0} />
        <JsonField label="Change requests" value={changeRequests} hasContent={changeRequests.length > 0} />
      </div>
    </div>
  );
}

function StepTrace({ step, events, connected }: { step: StepRun; events: AgentEvent[]; connected: boolean }) {
  const isPending = step.status === "pending";
  const traceEvents = events.length > 0 ? events : (isPending ? [] : fallbackEvents(step));
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
      {traceEvents.length === 0 && (
        <div className="border border-rule rounded-sm px-4 py-4 text-[12px] text-paper-fade italic">
          No runtime events yet. Events will stream in as the step executes.
        </div>
      )}
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
  const hasInputs = isNonEmpty(step.inputs_redacted);
  const hasOutputs = isNonEmpty(step.outputs_redacted);
  const isPending = step.status === "pending";
  const refRows = [
    step.sandbox_run_id && { label: "Sandbox run", value: step.sandbox_run_id },
    step.hook_call_id && { label: "Hook call", value: step.hook_call_id },
    step.policy_decision_id && { label: "Policy decision", value: step.policy_decision_id },
    step.approval_id && { label: "Approval", value: step.approval_id }
  ].filter(Boolean) as Array<{ label: string; value: string }>;

  return (
    <section>
      <div className="mb-3">
        <div className="smallcaps">Runtime data</div>
        <div className="mt-1 text-[12px] text-paper-dim">
          Inputs, outputs, and downstream references captured during execution.
        </div>
      </div>

      {isPending && !hasInputs && !hasOutputs && refRows.length === 0 ? (
        <div className="border border-rule rounded-sm px-4 py-6 text-center">
          <div className="text-[13px] text-paper">This step hasn't run yet.</div>
          <div className="mt-1 text-[12px] text-paper-fade">
            Inputs, outputs, and trace events will populate when the run reaches it.
            See <span className="font-mono">Definition</span> above for the configured shape.
          </div>
        </div>
      ) : (
        <div className="grid gap-5">
          {refRows.length > 0 && (
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-[12px]">
              {refRows.map((row) => (
                <Field key={row.label} label={row.label}>
                  <span className="font-mono text-paper-dim">{row.value}</span>
                </Field>
              ))}
            </dl>
          )}
          <JsonField label="Inputs (redacted)" value={step.inputs_redacted} hasContent={hasInputs} />
          <JsonField label="Outputs (redacted)" value={step.outputs_redacted} hasContent={hasOutputs} />
        </div>
      )}
    </section>
  );
}

function isNonEmpty(value: unknown): boolean {
  if (!value) return false;
  if (typeof value !== "object") return true;
  if (Array.isArray(value)) return value.length > 0;
  return Object.keys(value as Record<string, unknown>).length > 0;
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

function JsonField({ label, value, hasContent }: { label: string; value: unknown; hasContent: boolean }) {
  return (
    <Field label={label}>
      {hasContent ? (
        <pre className="font-mono text-[12px] text-paper-dim whitespace-pre-wrap break-words border-l border-rule pl-3">
          {JSON.stringify(value, null, 2)}
        </pre>
      ) : (
        <span className="text-[12px] text-paper-fade italic">Not captured for this step.</span>
      )}
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
  type = String(type ?? "") as AgentEvent["type"];
  if (type.includes("failed") || type.includes("refused")) return "crit" as const;
  if (type.includes("policy") || type.includes("approval")) return "warn" as const;
  if (type.includes("finished") || type.includes("emitted") || type.includes("proposed")) return "ok" as const;
  return "muted" as const;
}

function syntheticAgentEvents(step: StepRun, assetId: string): AgentEvent[] {
  const output = step.outputs_redacted ?? {};
  const modelCall = isRecord(output.model_call) ? output.model_call : {};
  const tools = Array.isArray(output.tools) ? output.tools : [];
  const ts = step.finished_at ?? step.started_at ?? new Date().toISOString();
  const events: AgentEvent[] = [
    {
      id: `synthetic-thought-${step.id}`,
      ts,
      asset_id: assetId,
      workflow_step_id: step.step_id,
      type: "agent.thought",
      actor: "workflow_agent",
      payload: {
        text: typeof modelCall.text === "string" && modelCall.text.length > 0
          ? modelCall.text
          : `Reviewed inputs and produced ${Array.isArray(output.findings) ? output.findings.length : 0} finding(s).`,
        findings_count: Array.isArray(output.findings) ? output.findings.length : 0,
        model_provider: output.model_provider,
        model: output.model
      },
      hash_chain_prev: "",
      hash_chain_self: ""
    }
  ];
  for (const [index, raw] of tools.entries()) {
    const tool = isRecord(raw) ? raw : {};
    events.push({
      id: `synthetic-tool-${step.id}-${index}`,
      ts,
      asset_id: assetId,
      workflow_step_id: step.step_id,
      type: "agent.tool.called",
      actor: "workflow_agent",
      payload: {
        name: tool.name ?? "tool",
        status: tool.status ?? "ok",
        args: { items: tool.items ?? 0 }
      },
      hash_chain_prev: "",
      hash_chain_self: ""
    });
  }
  return events;
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
