"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Corpus, WorkflowGraphNode, WorkflowPhase } from "@/lib/api/types";
import { Button } from "@/components/primitives/Button";
import { Input } from "@/components/primitives/Input";
import { Badge } from "@/components/primitives/Badge";
import { Drawer } from "@/components/primitives/Drawer";
import { Hairline } from "@/components/primitives/Hairline";
import { useWorkflowGraph } from "./useWorkflowGraph";
import { WorkflowCanvas } from "./WorkflowCanvas";
import { Plus, Trash2 } from "lucide-react";

type CatalogEntry = Awaited<ReturnType<typeof api.workflows.nodeCatalog>>[number];

const PHASE_LABEL: Record<WorkflowPhase, { title: string; subtitle: string }> = {
  pre: { title: "1 · Pre-assessment", subtitle: "Collect inputs, retrieve obligations, prepare context." },
  assess: { title: "2 · Assessment", subtitle: "The agent reasons inside its sandbox." },
  post: { title: "3 · Post-assessment", subtitle: "Gates, evidence, proposals, notifications." }
};

export function WorkflowFormEditor({
  initial,
  workflowId,
  mode
}: {
  initial?: { name: string; description?: string; required_corpora?: string[]; required_hooks?: string[]; graph?: { nodes: WorkflowGraphNode[]; edges: { id: string; from: string; to: string; kind: string }[] } };
  workflowId?: string;
  mode: "create" | "edit";
}) {
  const router = useRouter();
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [requiredCorpora, setRequiredCorpora] = useState<string[]>(initial?.required_corpora ?? []);
  const [requiredHooks, setRequiredHooks] = useState<string[]>(initial?.required_hooks ?? []);
  const [catalog, setCatalog] = useState<CatalogEntry[]>([]);
  const [corpora, setCorpora] = useState<Corpus[]>([]);
  const [savingError, setSavingError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  const {
    nodes,
    edges,
    addNode,
    updateNode,
    removeNode,
    connect,
    disconnect,
    graph,
    setGraph
  } = useWorkflowGraph(initial?.graph as Parameters<typeof useWorkflowGraph>[0]);

  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    void api.workflows.nodeCatalog().then(setCatalog);
    void api.corpora.list().then(setCorpora).catch(() => undefined);
  }, []);

  const catalogByPhase = useMemo(() => {
    const groups: Record<WorkflowPhase, CatalogEntry[]> = { pre: [], assess: [], post: [] };
    for (const entry of catalog) groups[entry.phase].push(entry);
    return groups;
  }, [catalog]);

  const addFromCatalog = (entry: CatalogEntry, keepOpen = false) => {
    addNode({
      type: entry.type,
      phase: entry.phase,
      label: entry.label,
      config: {}
    });
    if (!keepOpen) setPaletteOpen(false);
  };

  const save = async () => {
    if (!name.trim()) {
      setSavingError("Name is required.");
      return;
    }
    if (nodes.length === 0) {
      setSavingError("Add at least one node before saving.");
      return;
    }
    setSavingError(null);
    setBusy(true);
    try {
      const payload = {
        name: name.trim(),
        description: description.trim() || undefined,
        trigger: "manual",
        required_corpora: requiredCorpora,
        required_hooks: requiredHooks,
        graph
      };
      if (mode === "create") {
        const created = await api.workflows.create(payload);
        router.push(`/workflows/${encodeURIComponent(created.id)}`);
      } else if (workflowId) {
        await api.workflows.update(workflowId, payload);
        router.push(`/workflows/${encodeURIComponent(workflowId)}`);
      }
    } catch (e) {
      setSavingError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const nodesByPhase = useMemo(() => {
    const groups: Record<WorkflowPhase, WorkflowGraphNode[]> = { pre: [], assess: [], post: [] };
    for (const node of nodes) groups[node.phase].push(node);
    return groups;
  }, [nodes]);

  return (
    <div className="space-y-6">
      <div className="space-y-6">
        <header className="space-y-3">
          <Field label="Workflow name">
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Custom compliance scan" />
          </Field>
          <Field label="Description" hint="Markdown-friendly overview shown on the workflow card">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full bg-transparent text-paper placeholder:text-paper-fade border border-rule rounded-sm px-3 py-2 text-[13px] focus:border-gold outline-none resize-y"
              placeholder="What does this workflow assess? When should it run?"
            />
          </Field>
          <div className="grid grid-cols-2 gap-5">
            <Field label="Required corpora" hint="Uploaded documents from these corpora are bundled into the agent sandbox at run time.">
              <CorpusPicker corpora={corpora} value={requiredCorpora} onChange={setRequiredCorpora} />
            </Field>
            <Field label="Required hooks" hint="Comma-separated hook ids (existing or new).">
              <Input
                value={requiredHooks.join(", ")}
                onChange={(e) => setRequiredHooks(e.target.value.split(",").map((s) => s.trim()).filter(Boolean))}
                placeholder="github_stub, slack_json"
              />
            </Field>
          </div>
        </header>

        <Hairline />

        <section className="space-y-2">
          <header className="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <h3 className="ed-h3 text-paper">Visual canvas</h3>
              <p className="text-[12px] text-paper-fade">
                Drag nodes to lay them out. Drag the right port of one node to the left port of another to connect. Click a connection to remove it.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-[11px] text-paper-fade font-mono">{nodes.length} nodes · {edges.length} edges</span>
              <Button onClick={() => setPaletteOpen(true)} variant="primary" size="sm">
                <Plus size={12} strokeWidth={1.75} />
                Add node
              </Button>
            </div>
          </header>
          <WorkflowCanvas
            graph={graph}
            editable
            selectedId={selectedId}
            onSelectNode={setSelectedId}
            onChange={setGraph}
          />
        </section>

        <Hairline />

        {(["pre", "assess", "post"] as WorkflowPhase[]).map((phase) => (
          <section key={phase} className="space-y-3">
            <header className="flex items-center justify-between gap-3">
              <div>
                <h3 className="ed-h3 text-paper">{PHASE_LABEL[phase].title}</h3>
                <p className="text-[12px] text-paper-fade">{PHASE_LABEL[phase].subtitle}</p>
              </div>
              <span className="text-[11px] text-paper-fade font-mono tabular-nums">
                {nodesByPhase[phase].length} node{nodesByPhase[phase].length === 1 ? "" : "s"}
              </span>
            </header>
            {nodesByPhase[phase].length === 0 ? (
              <div className="border border-dashed border-rule rounded-sm px-4 py-6 text-center text-[12px] text-paper-fade">
                {phase === "assess" ? "Required: add an agent or model.complete node." : "Optional — add nodes from the right palette."}
              </div>
            ) : (
              <ul className="space-y-2">
                {nodesByPhase[phase].map((node) => (
                  <li key={node.id}>
                    <NodeEditor
                      node={node}
                      allNodes={nodes}
                      catalog={catalog}
                      edges={edges}
                      onChange={(patch) => updateNode(node.id, patch)}
                      onRemove={() => removeNode(node.id)}
                      onConnect={(parentId) => connect(parentId, node.id)}
                      onDisconnect={(edgeId) => disconnect(edgeId)}
                    />
                  </li>
                ))}
              </ul>
            )}
          </section>
        ))}

        {savingError && (
          <div className="border border-crit/40 bg-crit/5 text-crit px-4 py-2 text-[12px] rounded-sm">
            {savingError}
          </div>
        )}

        <div className="flex items-center justify-end gap-2 pt-2">
          <Button onClick={() => router.back()} variant="ghost">Cancel</Button>
          <Button onClick={save} variant="primary" disabled={busy || !name || nodes.length === 0}>
            {busy ? "Saving…" : mode === "create" ? "Create workflow" : "Save changes"}
          </Button>
        </div>
      </div>

      <Drawer
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        title="Add a node"
        subtitle="Prefab catalog"
        width="wide"
      >
        <div className="px-6 py-5 space-y-5">
          <p className="text-[12px] text-paper-fade leading-snug">
            Click a prefab to add it to the canvas. Hold Shift to keep the drawer open and add several at once.
          </p>
          {(["pre", "assess", "post"] as WorkflowPhase[]).map((phase) => (
            <div key={phase}>
              <div className="text-[10.5px] font-medium uppercase tracking-[0.08em] text-paper-fade mb-1.5">
                {PHASE_LABEL[phase].title}
              </div>
              <p className="text-[11.5px] text-paper-fade italic mb-2">{PHASE_LABEL[phase].subtitle}</p>
              <ul className="space-y-1.5">
                {catalogByPhase[phase].map((entry) => (
                  <li key={entry.type}>
                    <button
                      type="button"
                      onClick={(e) => addFromCatalog(entry, e.shiftKey)}
                      className="w-full text-left border border-rule rounded-sm px-3 py-2 hover:border-rule-bright hover:bg-ink-2 transition-colors"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-mono text-[12px] text-paper truncate">{entry.label}</span>
                        <Plus size={12} strokeWidth={1.75} className="text-paper-fade shrink-0" />
                      </div>
                      <div className="text-[11px] text-paper-fade leading-snug mt-0.5">{entry.summary}</div>
                    </button>
                  </li>
                ))}
                {catalogByPhase[phase].length === 0 && (
                  <li className="text-[11.5px] text-paper-fade italic px-3 py-2">No prefabs in this phase yet.</li>
                )}
              </ul>
            </div>
          ))}
        </div>
      </Drawer>
    </div>
  );
}

function NodeEditor({
  node,
  allNodes,
  catalog,
  edges,
  onChange,
  onRemove,
  onConnect,
  onDisconnect
}: {
  node: WorkflowGraphNode;
  allNodes: WorkflowGraphNode[];
  catalog: CatalogEntry[];
  edges: { id: string; from: string; to: string }[];
  onChange: (patch: Partial<WorkflowGraphNode>) => void;
  onRemove: () => void;
  onConnect: (parentId: string) => void;
  onDisconnect: (edgeId: string) => void;
}) {
  const entry = catalog.find((c) => c.type === node.type);
  const upstreamOptions = allNodes.filter((n) => n.id !== node.id);
  const incomingEdges = edges.filter((e) => e.to === node.id);
  const incomingIds = new Set(incomingEdges.map((e) => e.from));

  return (
    <div className="border border-rule rounded-sm bg-ink-2 p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1 grid grid-cols-2 gap-3">
          <Field label="Label" inline>
            <Input value={node.label} onChange={(e) => onChange({ label: e.target.value })} />
          </Field>
          <Field label="Id (slug)" inline>
            <Input
              value={node.id}
              onChange={(e) => onChange({ id: e.target.value.replace(/[^a-z0-9_]/gi, "_") })}
              className="text-[12.5px]"
            />
          </Field>
        </div>
        <button
          type="button"
          onClick={onRemove}
          aria-label={`Remove ${node.label}`}
          className="text-paper-fade hover:text-crit p-1.5 rounded-sm hover:bg-ink-3"
        >
          <Trash2 size={14} strokeWidth={1.75} />
        </button>
      </div>

      <div className="flex items-center gap-2 text-[11.5px]">
        <Badge tone="info">{node.type}</Badge>
        {entry && <span className="text-paper-fade">{entry.summary}</span>}
      </div>

      {entry && Object.keys(entry.config_schema ?? {}).length > 0 && (
        <div className="space-y-2 pt-1">
          <div className="text-[10.5px] font-medium uppercase tracking-[0.08em] text-paper-fade">
            Configuration
          </div>
          {Object.entries(entry.config_schema).map(([key, type]) => (
            <ConfigField
              key={key}
              keyName={key}
              type={type}
              value={node.config[key]}
              onChange={(value) => onChange({ config: { ...node.config, [key]: value } })}
            />
          ))}
        </div>
      )}

      <div className="space-y-1.5 pt-1">
        <div className="text-[10.5px] font-medium uppercase tracking-[0.08em] text-paper-fade">
          Depends on
        </div>
        {upstreamOptions.length === 0 ? (
          <p className="text-[11px] text-paper-fade">Add another node first to wire dependencies.</p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {upstreamOptions.map((other) => {
              const edge = incomingEdges.find((e) => e.from === other.id);
              const active = incomingIds.has(other.id);
              return (
                <button
                  key={other.id}
                  type="button"
                  onClick={() => active && edge ? onDisconnect(edge.id) : onConnect(other.id)}
                  className={`h-6 px-2 inline-flex items-center gap-1 border rounded-sm text-[11px] transition-colors ${active ? "border-gold text-gold bg-gold/5" : "border-rule text-paper-dim hover:text-paper hover:border-rule-bright"}`}
                >
                  {active ? "✓" : "+"} {other.label}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function ConfigField({
  keyName,
  type,
  value,
  onChange
}: {
  keyName: string;
  type: string;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  if (type === "list[string]") {
    const arr = Array.isArray(value) ? value : [];
    return (
      <Field inline label={keyName}>
        <Input
          value={arr.join(", ")}
          onChange={(e) => onChange(e.target.value.split(",").map((v) => v.trim()).filter(Boolean))}
          placeholder="comma-separated"
        />
      </Field>
    );
  }
  if (type === "number") {
    return (
      <Field inline label={keyName}>
        <Input
          type="number"
          value={typeof value === "number" ? String(value) : ""}
          onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))}
        />
      </Field>
    );
  }
  return (
    <Field inline label={keyName}>
      <Input
        value={typeof value === "string" ? value : value === undefined ? "" : String(value)}
        onChange={(e) => onChange(e.target.value)}
      />
    </Field>
  );
}

function CorpusPicker({
  corpora,
  value,
  onChange
}: {
  corpora: Corpus[];
  value: string[];
  onChange: (next: string[]) => void;
}) {
  const toggle = (id: string) => {
    if (value.includes(id)) onChange(value.filter((v) => v !== id));
    else onChange([...value, id]);
  };
  if (corpora.length === 0) {
    return <div className="text-[12px] text-paper-fade">No corpora available — create one in /corpora first.</div>;
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {corpora.map((corpus) => {
        const active = value.includes(corpus.id);
        return (
          <button
            key={corpus.id}
            type="button"
            onClick={() => toggle(corpus.id)}
            className={`h-7 px-2 border rounded-sm text-[12px] transition-colors ${active ? "border-gold text-gold bg-gold/5" : "border-rule text-paper-dim hover:text-paper hover:border-rule-bright"}`}
          >
            {active ? "✓ " : ""}{corpus.name}
          </button>
        );
      })}
    </div>
  );
}

function Field({ label, hint, inline, children }: { label: string; hint?: string; inline?: boolean; children: React.ReactNode }) {
  return (
    <label className={`block ${inline ? "" : ""}`}>
      <div className={`${inline ? "text-[10px]" : "text-[10.5px]"} font-medium uppercase tracking-[0.08em] text-paper-fade mb-1`}>
        {label}
      </div>
      {children}
      {hint && <div className="mt-1 text-[11px] text-paper-fade">{hint}</div>}
    </label>
  );
}
