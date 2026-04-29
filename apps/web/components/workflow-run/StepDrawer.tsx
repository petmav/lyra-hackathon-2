"use client";

import type { StepRun, WorkflowRun } from "@/lib/api/types";
import { Drawer } from "@/components/primitives/Drawer";
import { Badge } from "@/components/primitives/Badge";
import { AgentDetail } from "@/components/agent-detail/AgentDetail";
import { useEventStream } from "@/lib/ws/stream";
import { Hairline } from "@/components/primitives/Hairline";
import { Timestamp } from "@/components/data/Timestamp";

/**
 * Drawer that opens when a workflow step is clicked in the DAG.
 *
 * For `agent` step types it embeds the same three-pane <AgentDetail /> used
 * for production agent supervision — confirming visually that the workflow
 * agent is just another supervised asset. For non-agent steps (hooks,
 * gates, finding emit), it shows a compact step-summary view.
 */
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
  const wfaAssetId =
    step?.step_id === "scan" ? "asset_wfa_scan" : step?.step_id === "propose" ? "asset_wfa_propose" : "asset_wfa_scan";
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
          {isAgent ? (
            <AgentForStep stepRun={step} wfaAssetId={wfaAssetId} runId={run.id} />
          ) : (
            <NonAgentBody step={step} />
          )}
        </div>
      )}
    </Drawer>
  );
}

function AgentForStep({ stepRun, wfaAssetId, runId }: { stepRun: StepRun; wfaAssetId: string; runId: string }) {
  const { events } = useEventStream({ kind: "workflowRun", id: runId });
  const stepEvents = events.filter((e) => e.workflow_step_id === stepRun.step_id);
  return (
    <AgentDetail
      asset={{
        id: wfaAssetId,
        urn: `urn:praetor:asset:workflow_agent:${runId}:${stepRun.step_id}`,
        type: "workflow_agent",
        name: `${stepRun.step_id} agent · ${stepRun.step_type}`,
        risk_tier: "L2",
        lifecycle: "governed"
      }}
      events={stepEvents}
      compact
    />
  );
}

function NonAgentBody({ step }: { step: StepRun }) {
  return (
    <div className="grid gap-6">
      <Field label="Step type">
        <span className="font-mono text-paper">{step.step_type}</span>
      </Field>
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
      <Field label="Inputs (redacted)">
        <pre className="font-mono text-[12px] text-paper-dim whitespace-pre-wrap break-words border-l border-rule pl-3">
          {JSON.stringify(step.inputs_redacted, null, 2)}
        </pre>
      </Field>
      <Field label="Outputs (redacted)">
        <pre className="font-mono text-[12px] text-paper-dim whitespace-pre-wrap break-words border-l border-rule pl-3">
          {JSON.stringify(step.outputs_redacted, null, 2)}
        </pre>
      </Field>
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
        {step.started_at ? <Timestamp ts={step.started_at} mode="precise" /> : <span className="text-paper-fade">—</span>}
      </Field>
      <Field label="Finished">
        {step.finished_at ? <Timestamp ts={step.finished_at} mode="precise" /> : <span className="text-paper-fade">—</span>}
      </Field>
    </dl>
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
