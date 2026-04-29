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
  const [workflowAgent, setWorkflowAgent] = useState<Asset | null>(null);
  const [productionAgent, setProductionAgent] = useState<Asset | null>(null);
  const [activeStepId, setActiveStepId] = useState<string | undefined>(undefined);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    Promise.all([
      api.workflowRuns.get(id),
      api.findings.list({ workflow_run_id: id }),
      api.proposedChanges.list(),
      api.assets.get("asset_wfa_scan"),
      api.assets.get("asset_support_bot")
    ]).then(async ([r, f, p, wfa, prod]) => {
      if (!alive) return;
      setRun(r);
      setFindings(f);
      setProposals(p.filter((pc) => f.some((ff) => ff.id === pc.finding_id)));
      setWorkflowAgent(wfa);
      setProductionAgent(prod);
      const running = r?.step_runs.find((s) => s.status === "running");
      setActiveStepId(running?.step_id);
      if (r?.workflow_id) {
        const wf = await api.workflows.get(r.workflow_id).catch(() => null);
        if (alive) setWorkflow(wf);
      }
      setLoading(false);
    });
    return () => { alive = false; };
  }, [id]);

  if (loading) return <div className="pt-20 text-center text-paper-fade text-[12px] italic">loading run…</div>;
  if (!run) return notFound();

  const activeStep = run.step_runs.find((s) => s.step_id === activeStepId) ?? null;

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
              <StatusDot tone={run.status === "running" ? "gold" : "neutral"} live={run.status === "running"} />
              <span className="font-mono text-[12px] text-paper">{run.status}</span>
            </span>
            <Urn urn={run.urn} />
            <div className="flex gap-2">
              <Button size="sm" variant="ghost">re-run</Button>
              {run.status === "running" && <Button size="sm" variant="danger">cancel</Button>}
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
              No findings yet — scan in progress.
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
