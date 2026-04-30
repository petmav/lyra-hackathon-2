"use client";

import { use, useEffect, useState } from "react";
import { notFound } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Asset, Finding, ProposedChange, StepRun, Workflow, WorkflowRun } from "@/lib/api/types";
import { PageHeader } from "@/components/shell/PageHeader";
import { Section } from "@/components/primitives/Section";
import { Badge } from "@/components/primitives/Badge";
import { Hairline } from "@/components/primitives/Hairline";
import { Button } from "@/components/primitives/Button";
import { StatusDot } from "@/components/primitives/StatusDot";
import { Timestamp } from "@/components/data/Timestamp";
import { Urn } from "@/components/data/Urn";
import { WorkflowGraph } from "@/components/workflow-graph/WorkflowGraph";
import { StepDrawer } from "@/components/workflow-run/StepDrawer";
import { SelfGovernancePanel } from "@/components/workflow-run/SelfGovernancePanel";
import { FindingCard } from "@/components/finding-card/FindingCard";
import { ProposedChangeView } from "@/components/proposed-change/ProposedChangeView";
import { ActivityFeed } from "@/components/workflow-run/ActivityFeed";

const TERMINAL_RUN_STATUSES = new Set(["succeeded", "failed", "cancelled"]);

/**
 * Workflow Run page — the demo's centre of gravity.
 *
 *  §03 ─ Workflow Runtime
 *
 *  Code Compliance Scan — running
 *  ┌──────────────────────────────────────┐ ┌─────────────────────┐
 *  │  DAG (custom SVG, click to drill)    │ │ Findings, accumul.  │
 *  │  ◯ pull → ◯═scan═► ◯ gate ...        │ │ Proposed change     │
 *  └──────────────────────────────────────┘ └─────────────────────┘
 *
 *  §03·a — Self-governance
 *  ┌────────────────────────┬────────────────────────┐
 *  │   <AgentDetail />      │   <AgentDetail />      │
 *  │   workflow agent       │   support-bot          │
 *  └────────────────────────┴────────────────────────┘
 *
 * Clicking a step opens the drawer. For agent steps, the drawer embeds the
 * three-pane live view. For other step types, it shows a step-summary view.
 */
export default function WorkflowRunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [proposals, setProposals] = useState<ProposedChange[]>([]);
  const [productionAgent, setProductionAgent] = useState<Asset | null>(null);
  const [activeStepId, setActiveStepId] = useState<string | undefined>(undefined);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    let poll: ReturnType<typeof setTimeout> | undefined;

    async function loadRun() {
      const r = await api.workflowRuns.get(id);
      if (!alive) return;
      const [indexedFindings, indexedProposals] = await Promise.all([
        api.findings.list({ workflow_run_id: id }),
        api.proposedChanges.list(),
      ]);
      if (!alive) return;
      const outputFindings = findingsFromRunOutputs(r);
      const f = indexedFindings.length > 0 ? indexedFindings : outputFindings;
      const outputProposals = proposalsFromRunOutputs(r);
      const findingIds = new Set(f.map((finding) => finding.id));
      const indexedAttachedProposals = indexedProposals.filter((pc) => findingIds.has(pc.finding_id));
      setRun(r);
      setFindings(f);
      setProposals(indexedAttachedProposals.length > 0 ? indexedAttachedProposals : outputProposals);
      const running = r?.step_runs.find((s) => s.status === "running");
      const agent = r?.step_runs.find((s) => s.step_type === "agent");
      setActiveStepId(running?.step_id ?? agent?.step_id);
      if (r?.workflow_id) {
        const wf = await api.workflows.get(r.workflow_id).catch(() => null);
        if (alive) setWorkflow(wf);
      }
      if (r?.asset_id) {
        const prod = await api.assets.get(r.asset_id).catch(() => null);
        if (alive) setProductionAgent(prod);
      }
      setLoading(false);
      if (r && !TERMINAL_RUN_STATUSES.has(r.status)) {
        poll = setTimeout(loadRun, 2500);
      }
    }

    loadRun();
    return () => {
      alive = false;
      if (poll) clearTimeout(poll);
    };
  }, [id]);

  if (loading) return <div className="pt-20 text-center text-paper-fade text-[12px] italic">loading run…</div>;
  if (!run) return notFound();

  const activeStep = run.step_runs.find((s) => s.step_id === activeStepId) ?? null;
  const workflowAgent = workflowAgentFromRun(run);

  return (
    <div>
      <PageHeader
        number="03"
        kicker={`Workflow run · ${run.status}`}
        title={
          <>
            Code <span className="ed-display-italic">Compliance</span> Scan
          </>
        }
        subtitle={
          <>
            Run <span className="font-mono text-paper">{run.id}</span> — every
            agent step runs in a sandbox and is itself a governed Asset under
            this control plane.
          </>
        }
        aside={
          <div className="flex flex-col items-end gap-2">
            <span className="inline-flex items-center gap-2">
              <StatusDot
                tone={
                  run.status === "running"
                    ? "gold"
                    : run.status === "awaiting_approval"
                    ? "warn"
                    : run.status === "failed" || run.status === "cancelled"
                    ? "crit"
                    : run.status === "succeeded"
                    ? "ok"
                    : "neutral"
                }
                live={run.status === "running" || run.status === "awaiting_approval"}
              />
              <span className="font-mono text-[12px] text-paper">{run.status}</span>
            </span>
            <Urn urn={run.urn} />
            <div className="flex gap-2">
              {run.status === "awaiting_approval" ? (
                <>
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={async () => {
                      const next = await api.workflowRuns.resume(run.id, true);
                      if (next) setRun(next);
                    }}
                  >
                    approve
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={async () => {
                      const next = await api.workflowRuns.resume(run.id, false);
                      if (next) setRun(next);
                    }}
                  >
                    reject
                  </Button>
                </>
              ) : (
                <>
                  <Button size="sm" variant="ghost">re-run</Button>
                  {run.status === "running" && <Button size="sm" variant="danger">cancel</Button>}
                </>
              )}
            </div>
          </div>
        }
      />

      <div className="mt-8 grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <Section number="03·1" eyebrow="DAG" title="Steps" className="!py-0 mt-2">
          <WorkflowGraph
            steps={run.step_runs}
            activeStepId={activeStepId}
            onStepClick={(sid) => {
              setActiveStepId(sid);
              setDrawerOpen(true);
            }}
          />
          <RunMeta run={run} />
        </Section>

        <Section number="03·2" eyebrow="Outputs" title="Findings · Proposed changes" className="!py-0 mt-2">
          {findings.length === 0 ? (
            <div className="border border-rule px-6 py-12 text-center text-[12px] text-paper-fade italic">
              {run.status === "succeeded" ? "No compliance findings were emitted." : "No findings yet — scan in progress."}
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {findings.map((f) => (
                <Link key={f.id} href={`/findings/${f.id}`}>
                  <FindingCard finding={f} compact />
                </Link>
              ))}
              {proposals.map((p) => (
                <div key={p.id}>
                  <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-paper-fade mb-2">
                    Proposed change · attached
                  </div>
                  <ProposedChangeView change={p} compact />
                </div>
              ))}
            </div>
          )}
        </Section>
      </div>

      <div className="mt-6">
        <ActivityFeed run={run} />
      </div>

      <Hairline tone="display" className="my-12" />

      {workflowAgent && productionAgent && (
        <SelfGovernancePanel workflowAgent={workflowAgent} productionAgent={productionAgent} />
      )}

      <StepDrawer
        step={activeStep}
        run={run}
        workflow={workflow}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
}

function workflowAgentFromRun(run: WorkflowRun): Pick<Asset, "id" | "urn" | "type" | "name" | "risk_tier" | "lifecycle"> | null {
  const agentStep = run.step_runs.find((step) => step.step_type === "agent" && typeof step.outputs_redacted?.workflow_agent_asset_id === "string")
    ?? run.step_runs.find((step) => step.step_type === "agent");
  if (!agentStep) return null;
  const externalId = agentStep.outputs_redacted?.workflow_agent_asset_id;
  const urn = agentStep.outputs_redacted?.workflow_agent_asset_urn;
  return {
    id: typeof externalId === "string" && externalId.length > 0 ? externalId : `asset_wfa_${run.id}_${agentStep.step_id}`,
    urn: typeof urn === "string" && urn.length > 0 ? urn : `urn:praetor:asset:workflow_agent:${run.id}:${agentStep.step_id}`,
    type: "workflow_agent",
    name: `${agentStep.step_id} workflow agent`,
    risk_tier: "L3",
    lifecycle: "ephemeral"
  };
}

function RunMeta({ run }: { run: WorkflowRun }) {
  return (
    <dl className="mt-6 grid gap-x-8 gap-y-2 text-[12px] md:grid-cols-3">
      <Field label="Triggered by"><span className="font-mono text-paper-dim">{run.triggered_by}</span></Field>
      <Field label="Triggered at"><Timestamp ts={run.triggered_at} mode="precise" /></Field>
      <Field label="Inputs">
        <span className="font-mono text-paper-dim text-[11.5px] truncate inline-block max-w-full align-middle">
          {summariseInputs(run.inputs)}
        </span>
      </Field>
    </dl>
  );
}
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="smallcaps mb-0.5">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
function summariseInputs(o: Record<string, unknown>) {
  return Object.entries(o)
    .map(([k, v]) => `${k}=${typeof v === "string" ? v : Array.isArray(v) ? `[${v.length}]` : JSON.stringify(v)}`)
    .join(" · ");
}

function findingsFromRunOutputs(run: WorkflowRun | null): Finding[] {
  const raw = run?.outputs?.findings;
  if (!run || !Array.isArray(raw)) return [];
  return raw
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((item, index) => ({
      id: String(item.id ?? `finding_${index + 1}`),
      urn: String(item.urn ?? `urn:praetor:finding:${item.id ?? index + 1}`),
      workflow_run_id: run.id,
      asset_id: run.asset_id,
      title: String(item.title ?? "Compliance finding"),
      description: String(item.description ?? ""),
      severity: severityOf(item.severity),
      obligations_cited: stringArray(item.obligations_cited),
      documents_cited: documentCitations(item.documents_cited),
      confidence: typeof item.confidence === "number" ? item.confidence : Number(item.confidence ?? 0),
      status: findingStatusOf(item.status),
      proposed_change_ids: stringArray(item.proposed_change_ids),
      created_at: run.finished_at ?? run.updated_at ?? run.created_at,
    }));
}

function proposalsFromRunOutputs(run: WorkflowRun | null): ProposedChange[] {
  const raw = run?.outputs?.proposed_changes;
  if (!run || !Array.isArray(raw)) return [];
  return raw
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((item, index) => ({
      id: String(item.id ?? `change_${index + 1}`),
      urn: String(item.urn ?? `urn:praetor:proposed_change:${item.id ?? index + 1}`),
      finding_id: String(item.finding_id ?? ""),
      kind: changeKindOf(item.kind),
      diff: String(item.diff ?? ""),
      diff_format: diffFormatOf(item.diff_format),
      target_asset_id: run.asset_id,
      obligations_addressed: stringArray(item.obligations_addressed),
      residual_risk_estimate: riskEstimate(item.residual_risk_estimate),
      status: "awaiting_approval",
      created_at: run.finished_at ?? run.updated_at ?? run.created_at,
    }));
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function documentCitations(value: unknown): Finding["documents_cited"] {
  if (!Array.isArray(value)) return [];
  return value.map((item, index) => {
    if (item && typeof item === "object") return item as Finding["documents_cited"][number];
    const text = String(item);
    return {
      document_id: text,
      document_title: text,
      chunk_ord: index + 1,
      citation_path: text,
    };
  });
}

function severityOf(value: unknown): Finding["severity"] {
  return value === "critical" || value === "high" || value === "medium" || value === "low" || value === "info" ? value : "medium";
}

function findingStatusOf(value: unknown): Finding["status"] {
  return value === "accepted" || value === "rejected" || value === "remediated" || value === "wontfix" ? value : "open";
}

function changeKindOf(value: unknown): ProposedChange["kind"] {
  return value === "config" || value === "policy" || value === "process" || value === "doc" ? value : "code";
}

function diffFormatOf(value: unknown): ProposedChange["diff_format"] {
  return value === "json-patch" || value === "config" || value === "markdown" ? value : "unified";
}

function riskEstimate(value: unknown): number {
  if (typeof value === "number") return value;
  if (typeof value === "string" && value.trim().length > 0) return 0.25;
  return 0;
}
