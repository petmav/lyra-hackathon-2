"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { notFound, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Workflow } from "@/lib/api/types";
import { PageHeader } from "@/components/shell/PageHeader";
import { Section } from "@/components/primitives/Section";
import { Badge } from "@/components/primitives/Badge";
import { Button } from "@/components/primitives/Button";
import { Hairline } from "@/components/primitives/Hairline";
import { Urn } from "@/components/data/Urn";
import { WorkflowSwimlanes } from "@/components/workflow-graph/WorkflowSwimlanes";
import { WorkflowCanvas } from "@/components/workflow-graph/WorkflowCanvas";
import { Pencil } from "lucide-react";

export default function WorkflowPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api.workflows.get(id).then((w) => {
      if (!alive) return;
      setWorkflow(w);
      setLoading(false);
    });
    return () => { alive = false; };
  }, [id]);

  if (loading) return <div className="pt-20 text-center text-paper-fade text-[12px] italic">loading workflow...</div>;
  if (!workflow) return notFound();

  async function instantiateRun() {
    if (!workflow || running) return;
    setRunning(true);
    setRunError(null);
    try {
      const result = await api.workflows.run(workflow.id, defaultInputsFor(workflow));
      router.push(`/workflow-runs/${encodeURIComponent(result.workflow_run_id)}`);
    } catch (error) {
      setRunError(error instanceof Error ? error.message : "Unable to instantiate workflow.");
      setRunning(false);
    }
  }

  return (
    <div>
      <PageHeader
        number="03.t"
        kicker={`${workflow.template_origin === "user-defined" ? "Custom" : "Template"} / ${workflow.trigger}`}
        title={workflow.name}
        subtitle={workflow.description}
        aside={
          <div className="flex flex-col items-end gap-2">
            <Urn urn={workflow.urn} />
            <div className="flex items-center gap-2">
              {workflow.template_origin === "user-defined" && (
                <Link href={`/workflows/${workflow.id}/edit`}>
                  <Button variant="ghost" size="sm">
                    <Pencil size={11} strokeWidth={1.75} />
                    edit
                  </Button>
                </Link>
              )}
              <Button variant="primary" onClick={instantiateRun} disabled={running}>
                {running ? "instantiating" : "instantiate run"}
              </Button>
            </div>
            {runError && <span className="max-w-[280px] text-right text-[11px] text-crit">{runError}</span>}
          </div>
        }
      />

      {workflow.graph && workflow.graph.nodes.length > 0 && (
        <Section number="a" eyebrow="Graph" title="Pre · Assess · Post" className="!py-0 mt-6">
          <div className="space-y-3">
            <WorkflowCanvas graph={workflow.graph} />
            <details className="group">
              <summary className="cursor-pointer text-[11px] uppercase tracking-[0.08em] text-paper-fade hover:text-paper">
                Show static swimlane render
              </summary>
              <div className="mt-3">
                <WorkflowSwimlanes graph={workflow.graph} />
              </div>
            </details>
          </div>
        </Section>
      )}

      <div className="mt-10 grid gap-6 lg:grid-cols-[2fr_1fr]">
        <Section number="a" eyebrow="Definition" title={<>YAML</>} className="!py-0 mt-2">
          <pre className="border border-rule bg-ink-2 p-5 font-mono text-[12px] leading-[1.6] overflow-x-auto">
            {workflow.definition.split("\n").map((line, i) => (
              <div key={i} className="grid grid-cols-[40px_1fr]">
                <span className="text-paper-fade text-right pr-3 select-none">{i + 1}</span>
                <span className="text-paper-dim">{line || " "}</span>
              </div>
            ))}
          </pre>
        </Section>

        <Section number="b" eyebrow="Inputs" title="Required" className="!py-0 mt-2">
          <dl className="border border-rule">
            {Object.entries(workflow.inputs_schema).map(([k, v], i, arr) => (
              <div key={k} className={`flex items-baseline justify-between gap-4 px-4 py-3 ${i < arr.length - 1 ? "border-b border-rule" : ""}`}>
                <dt className="font-mono text-[12.5px] text-paper">{k}</dt>
                <dd className="font-mono text-[11px] text-paper-fade">{String(v)}</dd>
              </div>
            ))}
          </dl>
          <Hairline className="my-6" />
          <div className="smallcaps mb-2">Required hooks</div>
          <div className="flex flex-wrap gap-1.5">
            {workflow.required_hooks.length === 0 ? <span className="text-paper-fade text-[12px]">none</span> :
              workflow.required_hooks.map((h) => <Badge key={h} tone="info">{h}</Badge>)}
          </div>
          <div className="smallcaps mb-2 mt-6">Default policy set</div>
          <div className="font-mono text-[12px] text-paper-dim">{workflow.default_policy_set}</div>
        </Section>
      </div>
    </div>
  );
}

function defaultInputsFor(workflow: Workflow): Record<string, unknown> {
  const inputs: Record<string, unknown> = {};
  if ("repo_url" in workflow.inputs_schema || workflow.id.includes("code_compliance_scan")) {
    inputs.repo_url = "stub://support-bot";
  }
  if ("corpus_ids" in workflow.inputs_schema || workflow.required_corpora.length > 0) {
    inputs.corpus_ids = workflow.required_corpora;
  }
  return inputs;
}
