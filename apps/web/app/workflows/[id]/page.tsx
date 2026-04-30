"use client";

import { use, useEffect, useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { notFound, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Workflow, WorkflowGraphNode } from "@/lib/api/types";
import { PageHeader } from "@/components/shell/PageHeader";
import { Section } from "@/components/primitives/Section";
import { Badge } from "@/components/primitives/Badge";
import { Button } from "@/components/primitives/Button";
import { Hairline } from "@/components/primitives/Hairline";
import { Urn } from "@/components/data/Urn";
import { WorkflowSwimlanes } from "@/components/workflow-graph/WorkflowSwimlanes";
import { WorkflowCanvas } from "@/components/workflow-graph/WorkflowCanvas";
import { Pencil, Play, Repeat, ShieldCheck } from "lucide-react";

type RunMode = "queued" | "sync" | "schedule" | "continuous";

export default function WorkflowPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [runMode, setRunMode] = useState<RunMode>("queued");
  const [inputValues, setInputValues] = useState<Record<string, string>>({});
  const [recurrencePreset, setRecurrencePreset] = useState("daily");
  const [intervalSeconds, setIntervalSeconds] = useState("300");
  const [scheduleMessage, setScheduleMessage] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api.workflows.get(id).then((w) => {
      if (!alive) return;
      if (!w) {
        setWorkflow(null);
        setLoading(false);
        return;
      }
      setWorkflow(w);
      setInputValues(inputsToForm(defaultInputsFor(w), w));
      const mode = String(w.trigger_config?.mode ?? "");
      if (mode === "continuous") setRunMode("continuous");
      else if (mode === "schedule") setRunMode("schedule");
      setLoading(false);
    });
    return () => { alive = false; };
  }, [id]);

  if (loading) return <div className="pt-20 text-center text-paper-fade text-[12px] italic">loading workflow...</div>;
  if (!workflow) return notFound();
  const selectedNode = workflow.graph?.nodes.find((node) => node.id === selectedNodeId) ?? workflow.graph?.nodes[0] ?? null;

  async function instantiateRun() {
    if (!workflow || running) return;
    setRunning(true);
    setRunError(null);
    setScheduleMessage(null);
    try {
      const inputs = formToInputs(inputValues, workflow);
      if (runMode === "schedule" || runMode === "continuous") {
        const continuous = runMode === "continuous";
        const updated = await api.workflows.schedule(workflow.id, {
          inputs,
          enabled: true,
          continuous_monitoring: continuous,
          recurrence: {
            preset: continuous ? "continuous" : recurrencePreset,
            interval_seconds: Number(intervalSeconds) || (continuous ? 300 : 3600)
          }
        });
        setWorkflow(updated);
        setScheduleMessage(continuous ? "Continuous monitoring is active." : "Recurring workflow is scheduled.");
        setRunning(false);
        return;
      }
      const result = await api.workflows.run(workflow.id, inputs, { execution_mode: runMode });
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
                {runMode === "schedule" || runMode === "continuous" ? <Repeat size={12} strokeWidth={1.75} /> : <Play size={12} strokeWidth={1.75} />}
                {running ? "submitting" : runMode === "schedule" ? "schedule" : runMode === "continuous" ? "monitor" : "run"}
              </Button>
            </div>
            {runError && <span className="max-w-[280px] text-right text-[11px] text-crit">{runError}</span>}
            {scheduleMessage && <span className="max-w-[280px] text-right text-[11px] text-ok">{scheduleMessage}</span>}
          </div>
        }
      />

      {workflow.graph && workflow.graph.nodes.length > 0 && (
        <Section number="a" eyebrow="Graph" title="Pre · Assess · Post" className="!py-0 mt-6">
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
            <div className="space-y-3 min-w-0">
              <WorkflowCanvas
                graph={workflow.graph}
                selectedId={selectedNode?.id ?? null}
                onSelectNode={setSelectedNodeId}
              />
              <details className="group">
                <summary className="cursor-pointer text-[11px] uppercase tracking-[0.08em] text-paper-fade hover:text-paper">
                  Show static swimlane render
                </summary>
                <div className="mt-3">
                  <WorkflowSwimlanes graph={workflow.graph} />
                </div>
              </details>
            </div>
            <StepBreakdown node={selectedNode} workflow={workflow} />
          </div>
        </Section>
      )}

      <Section number="b" eyebrow="Run" title="Configure" className="!py-0 mt-8">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
          <RunConfigurator
            workflow={workflow}
            values={inputValues}
            onChange={setInputValues}
            runMode={runMode}
            onRunMode={setRunMode}
            recurrencePreset={recurrencePreset}
            onRecurrencePreset={setRecurrencePreset}
            intervalSeconds={intervalSeconds}
            onIntervalSeconds={setIntervalSeconds}
          />
          <div className="border border-rule bg-ink-2 p-4">
            <div className="smallcaps mb-2">Required hooks</div>
            <div className="flex flex-wrap gap-1.5">
              {workflow.required_hooks.length === 0 ? <span className="text-paper-fade text-[12px]">none</span> :
                workflow.required_hooks.map((h) => <Badge key={h} tone="info">{h}</Badge>)}
            </div>
            <div className="smallcaps mb-2 mt-6">Default policy set</div>
            <div className="font-mono text-[12px] text-paper-dim">{workflow.default_policy_set}</div>
            <Hairline className="my-4" />
            <div className="text-[12px] leading-snug text-paper-dim">
              Runs use the values on the left. Recurring and 24/7 modes save this same input payload for the worker.
            </div>
          </div>
        </div>
      </Section>

      <div className="mt-10 grid gap-6">
        <Section number="c" eyebrow="Definition" title={<>YAML</>} className="!py-0 mt-2 min-w-0">
          <pre className="border border-rule bg-ink-2 p-5 font-mono text-[12px] leading-[1.6] overflow-x-auto">
            {workflow.definition.split("\n").map((line, i) => (
              <div key={i} className="grid grid-cols-[40px_1fr]">
                <span className="text-paper-fade text-right pr-3 select-none">{i + 1}</span>
                <span className="text-paper-dim">{line || " "}</span>
              </div>
            ))}
          </pre>
        </Section>
      </div>
    </div>
  );
}

function RunConfigurator({
  workflow,
  values,
  onChange,
  runMode,
  onRunMode,
  recurrencePreset,
  onRecurrencePreset,
  intervalSeconds,
  onIntervalSeconds
}: {
  workflow: Workflow;
  values: Record<string, string>;
  onChange: (values: Record<string, string>) => void;
  runMode: RunMode;
  onRunMode: (mode: RunMode) => void;
  recurrencePreset: string;
  onRecurrencePreset: (value: string) => void;
  intervalSeconds: string;
  onIntervalSeconds: (value: string) => void;
}) {
  const fields = inputFieldKeys(workflow);
  return (
    <div className="border border-rule bg-ink-2">
      <div className="grid grid-cols-2 border-b border-rule">
        {([
          ["queued", "Queued"],
          ["sync", "Immediate"],
          ["schedule", "Recurring"],
          ["continuous", "24/7"]
        ] as Array<[RunMode, string]>).map(([mode, label]) => (
          <button
            key={mode}
            type="button"
            onClick={() => onRunMode(mode)}
            className={`px-3 py-2 text-[11.5px] font-mono border-r border-b border-rule last:border-r-0 transition-colors ${
              runMode === mode ? "bg-gold text-ink" : "text-paper-dim hover:text-paper"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="p-4 space-y-4">
        {fields.map((key) => (
          <FieldControl
            key={key}
            name={key}
            hint={String(workflow.inputs_schema[key] ?? "")}
            value={values[key] ?? ""}
            onChange={(value) => onChange({ ...values, [key]: value })}
          />
        ))}
        {(runMode === "schedule" || runMode === "continuous") && (
          <div className="border border-rule p-3">
            <div className="flex items-center gap-2 smallcaps mb-3">
              {runMode === "continuous" ? <ShieldCheck size={12} strokeWidth={1.75} /> : <Repeat size={12} strokeWidth={1.75} />}
              {runMode === "continuous" ? "Continuous monitor" : "Recurrence"}
            </div>
            {runMode === "schedule" && (
              <select
                value={recurrencePreset}
                onChange={(event) => onRecurrencePreset(event.target.value)}
                className="w-full bg-ink border border-rule px-3 py-2 text-[12px] text-paper"
              >
                <option value="hourly">Hourly</option>
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="custom">Custom interval</option>
              </select>
            )}
            {(runMode === "continuous" || recurrencePreset === "custom") && (
              <label className="mt-3 block">
                <span className="smallcaps block mb-1">Interval seconds</span>
                <input
                  value={intervalSeconds}
                  onChange={(event) => onIntervalSeconds(event.target.value)}
                  className="w-full bg-ink border border-rule px-3 py-2 font-mono text-[12px] text-paper"
                  inputMode="numeric"
                />
              </label>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function FieldControl({
  name,
  hint,
  value,
  onChange
}: {
  name: string;
  hint: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="flex items-baseline justify-between gap-3">
        <span className="font-mono text-[12px] text-paper">{name}</span>
        {hint && <span className="text-[10.5px] text-paper-fade text-right">{hint}</span>}
      </span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 w-full bg-ink border border-rule px-3 py-2 font-mono text-[12px] text-paper"
      />
    </label>
  );
}

function StepBreakdown({ node, workflow }: { node: WorkflowGraphNode | null; workflow: Workflow }) {
  if (!node) {
    return (
      <aside className="border border-rule bg-ink-2 p-4 text-[12px] text-paper-fade">
        Select a workflow step to inspect its inputs, dependencies, and configuration.
      </aside>
    );
  }
  const step = workflow.steps?.find((candidate) => candidate.id === node.id);
  const dependsOn = node.depends_on?.length ? node.depends_on : step?.depends_on ?? [];
  const config = node.config ?? step?.with ?? {};
  const entries = Object.entries(config).filter(([, value]) => value !== undefined && value !== null && value !== "");
  return (
    <aside className="border border-rule bg-ink-2 p-4 h-full">
      <div className="smallcaps">Step breakdown</div>
      <h3 className="mt-2 text-[16px] text-paper font-medium">{node.label || node.id}</h3>
      <dl className="mt-4 grid gap-3 text-[12px]">
        <BreakdownField label="ID"><span className="font-mono text-paper-dim">{node.id}</span></BreakdownField>
        <BreakdownField label="Type"><span className="font-mono text-paper-dim">{node.type}</span></BreakdownField>
        <BreakdownField label="Phase"><Badge tone={phaseTone(node.phase)}>{node.phase}</Badge></BreakdownField>
        <BreakdownField label="Depends on">
          {dependsOn.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {dependsOn.map((id) => (
                <span key={id} className="font-mono text-[11px] text-paper-dim border border-rule px-1.5 py-0.5 rounded-sm">
                  {id}
                </span>
              ))}
            </div>
          ) : (
            <span className="text-paper-fade">none</span>
          )}
        </BreakdownField>
      </dl>
      <Hairline className="my-4" />
      <div className="smallcaps mb-2">Configuration</div>
      {entries.length === 0 ? (
        <div className="text-[12px] text-paper-fade italic">No static configuration.</div>
      ) : (
        <ul className="divide-y divide-rule border border-rule">
          {entries.map(([key, value]) => (
            <li key={key} className="px-3 py-2">
              <div className="font-mono text-[11px] text-paper-fade">{key}</div>
              <div className="mt-1 font-mono text-[11.5px] text-paper-dim break-words">{formatBreakdownValue(value)}</div>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}

function BreakdownField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="smallcaps mb-1">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function phaseTone(phase: WorkflowGraphNode["phase"]) {
  if (phase === "pre") return "info" as const;
  if (phase === "assess") return "gold" as const;
  return "warn" as const;
}

function formatBreakdownValue(value: unknown): string {
  if (Array.isArray(value)) return value.length === 0 ? "[]" : `[${value.join(", ")}]`;
  if (typeof value === "object" && value !== null) return JSON.stringify(value);
  return String(value);
}

function defaultInputsFor(workflow: Workflow): Record<string, unknown> {
  const inputs: Record<string, unknown> = {};
  if ("repo_url" in workflow.inputs_schema || workflow.id.includes("code_compliance_scan")) {
    inputs.repo_url = workflow.id === "github_corpus_code_compliance"
      ? "https://github.com/petmav/lyra-hackathon-2"
      : "stub://support-bot";
  }
  if ("corpus_ids" in workflow.inputs_schema || workflow.required_corpora.length > 0) {
    inputs.corpus_ids = workflow.required_corpora.length > 0 ? workflow.required_corpora : ["iso_42001", "internal_data_min"];
  }
  if (workflow.id === "github_corpus_code_compliance") {
    inputs.github_ref = "main";
    inputs.github_base_branch = "main";
    inputs.live_github_dispatch = false;
  }
  return inputs;
}

function inputFieldKeys(workflow: Workflow): string[] {
  const keys = Object.keys(workflow.inputs_schema ?? {}).filter((key) => key !== "type");
  if (keys.length > 0) return keys;
  return Object.keys(defaultInputsFor(workflow));
}

function inputsToForm(inputs: Record<string, unknown>, workflow: Workflow): Record<string, string> {
  const fields = inputFieldKeys(workflow);
  const values: Record<string, string> = {};
  for (const key of fields) {
    const value = inputs[key];
    values[key] = Array.isArray(value) ? value.join(", ") : value === undefined || value === null ? "" : String(value);
  }
  return values;
}

function formToInputs(values: Record<string, string>, workflow: Workflow): Record<string, unknown> {
  const inputs: Record<string, unknown> = {};
  for (const key of inputFieldKeys(workflow)) {
    const raw = values[key] ?? "";
    if (key.endsWith("_ids") || key === "corpus_ids") {
      inputs[key] = raw.split(",").map((item) => item.trim()).filter(Boolean);
    } else if (raw === "true" || raw === "false") {
      inputs[key] = raw === "true";
    } else {
      inputs[key] = raw;
    }
  }
  return inputs;
}
