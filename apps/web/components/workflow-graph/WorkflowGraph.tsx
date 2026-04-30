"use client";

import { cn } from "@/lib/utils/cn";
import type { StepRun } from "@/lib/api/types";

/**
 * Custom SVG DAG renderer. We do not pull in React Flow — this hand-rendered
 * graph keeps the aesthetic terse and dependency-free, and gives us total
 * control over the hairline rules and pulses.
 *
 * Layout: a simple longest-path layering (`x = depth from a source`,
 * `y = stable position within layer`). For the demo's seven-step linear
 * scan-propose pipeline this looks tidy without a real layout engine.
 *
 *   ◯─── ◯═══►◯─── ◯─── ◯─── ◯─── ◯
 *   pull scan gate emit prop appr open_pr
 *
 * The currently-running step pulses; pending steps are hairline only;
 * succeeded steps fill with a gold-dim center dot. Edges flowing into the
 * running step animate (`step-pulse`) on the line itself.
 */
export function WorkflowGraph({
  steps,
  activeStepId,
  onStepClick
}: {
  steps: StepRun[];
  activeStepId?: string;
  onStepClick?: (stepId: string) => void;
}) {
  const layout = layoutDag(steps);
  const W = 880;
  const H = layout.maxLayer * 110 + 80;

  return (
    <div className="border border-rule bg-ink-2 p-6">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="Workflow DAG">
        {/* edges first */}
        {layout.edges.map((e, i) => (
          <Edge key={i} from={e.from} to={e.to} active={e.toStep.status === "running"} />
        ))}
        {/* nodes */}
        {layout.nodes.map((n) => (
          <Node
            key={n.step.id}
            step={n.step}
            x={n.x}
            y={n.y}
            isActive={n.step.step_id === activeStepId}
            onClick={() => onStepClick?.(n.step.step_id)}
          />
        ))}
      </svg>

      <div className="mt-4 flex items-center gap-6 text-[10.5px] text-paper-fade">
        <Legend tone="ok" label="succeeded" />
        <Legend tone="gold" label="running" pulse />
        <Legend tone="muted" label="pending" />
        <Legend tone="warn" label="awaiting approval" />
        <Legend tone="crit" label="failed" />
      </div>
    </div>
  );
}

function Edge({ from, to, active }: { from: { x: number; y: number }; to: { x: number; y: number }; active?: boolean }) {
  // straight line with a tiny step
  const midX = (from.x + to.x) / 2;
  const path = `M ${from.x} ${from.y} L ${midX} ${from.y} L ${midX} ${to.y} L ${to.x} ${to.y}`;
  return (
    <path
      d={path}
      stroke={active ? "var(--gold)" : "var(--rule-bright)"}
      strokeWidth={active ? 1.25 : 0.75}
      fill="none"
      strokeDasharray={active ? "0" : "0"}
      className={cn(active && "animate-step-pulse")}
    />
  );
}

function Node({
  step,
  x,
  y,
  isActive,
  onClick
}: {
  step: StepRun;
  x: number;
  y: number;
  isActive: boolean;
  onClick?: () => void;
}) {
  const tone = toneFor(step.status);
  const fill = step.status === "succeeded" ? "var(--gold-dim)" : "transparent";
  const stroke = isActive ? "var(--gold)" : tone;
  const w = 140;
  const h = 56;
  return (
    <g
      transform={`translate(${x - w / 2}, ${y - h / 2})`}
      style={{ cursor: onClick ? "pointer" : undefined }}
      onClick={onClick}
    >
      <rect
        x={0}
        y={0}
        width={w}
        height={h}
        fill="var(--ink)"
        stroke={stroke}
        strokeWidth={isActive ? 1.25 : 0.75}
        className={cn(step.status === "running" && "animate-step-pulse")}
      />
      <rect x={4} y={4} width={6} height={6} fill={fill} stroke={tone} strokeWidth={0.75} />
      <text
        x={16}
        y={18}
        fontFamily="JetBrains Mono"
        fontSize="10"
        fill="var(--paper-fade)"
        letterSpacing="0.12em"
      >
        {step.step_type}
      </text>
      <text
        x={16}
        y={36}
        fontFamily="General Sans"
        fontSize="13"
        fill="var(--paper)"
        fontWeight={500}
      >
        {step.step_id}
      </text>
      <text
        x={16}
        y={50}
        fontFamily="JetBrains Mono"
        fontSize="10"
        fill={tone}
      >
        {step.status}
      </text>
    </g>
  );
}

function Legend({ tone, label, pulse }: { tone: string; label: string; pulse?: boolean }) {
  const fill = toneFor(tone);
  return (
    <span className="inline-flex items-center gap-2">
      <span aria-hidden style={{ width: 8, height: 8, background: fill }} className={pulse ? "animate-step-pulse" : ""} />
      <span>{label}</span>
    </span>
  );
}

function toneFor(s: string): string {
  switch (s) {
    case "running": return "var(--gold)";
    case "succeeded": return "var(--ok)";
    case "failed": return "var(--crit)";
    case "awaiting_approval": return "var(--warn)";
    case "skipped": return "var(--paper-fade)";
    case "warn": return "var(--warn)";
    case "ok": return "var(--ok)";
    case "crit": return "var(--crit)";
    case "gold": return "var(--gold)";
    case "muted": return "var(--paper-fade)";
    default: return "var(--rule-bright)";
  }
}

interface NodeLayout { step: StepRun; x: number; y: number }
interface EdgeLayout { from: { x: number; y: number }; to: { x: number; y: number }; toStep: StepRun }

function layoutDag(steps: StepRun[]): { nodes: NodeLayout[]; edges: EdgeLayout[]; maxLayer: number } {
  // longest-path layering
  const layer = new Map<string, number>();
  const byId = new Map(steps.map((s) => [s.step_id, s]));
  const visit = (id: string): number => {
    if (layer.has(id)) return layer.get(id)!;
    const s = byId.get(id);
    if (!s) return 0;
    const deps = s.depends_on ?? [];
    const v = deps.length === 0 ? 0 : 1 + Math.max(...deps.map(visit));
    layer.set(id, v);
    return v;
  };
  steps.forEach((s) => visit(s.step_id));

  // group by layer for stable y placement
  const layers = new Map<number, StepRun[]>();
  for (const s of steps) {
    const l = layer.get(s.step_id) ?? 0;
    if (!layers.has(l)) layers.set(l, []);
    layers.get(l)!.push(s);
  }

  const nodes: NodeLayout[] = [];
  const sortedLayers = [...layers.keys()].sort((a, b) => a - b);
  // For the demo (7-step linear pipeline), this lays them out vertically in a single column.
  // For DAGs with parallel branches, multiple steps share a layer and stack horizontally.
  const colWidth = 240;
  const rowHeight = 110;
  const baseX = 130;
  for (const l of sortedLayers) {
    const group = layers.get(l)!;
    group.forEach((s, i) => {
      // Single-step layers go in column 0; multi-step layers fan out.
      const x = baseX + (group.length === 1 ? 0 : (i - (group.length - 1) / 2) * colWidth);
      const y = 50 + l * rowHeight;
      nodes.push({ step: s, x, y });
    });
  }

  const nodeMap = new Map(nodes.map((n) => [n.step.step_id, n]));
  const edges: EdgeLayout[] = [];
  for (const s of steps) {
    const to = nodeMap.get(s.step_id);
    if (!to) continue;
    for (const dep of s.depends_on ?? []) {
      const from = nodeMap.get(dep);
      if (!from) continue;
      edges.push({
        from: { x: from.x, y: from.y + 28 },
        to: { x: to.x, y: to.y - 28 },
        toStep: to.step
      });
    }
  }

  return { nodes, edges, maxLayer: sortedLayers[sortedLayers.length - 1] ?? 0 };
}
