"use client";

import { useMemo } from "react";
import type { WorkflowGraph, WorkflowGraphNode, WorkflowPhase } from "@/lib/api/types";

const PHASE_LABEL: Record<WorkflowPhase, string> = {
  pre: "1 · Pre-assessment",
  assess: "2 · Assessment",
  post: "3 · Post-assessment"
};

const PHASE_NOTE: Record<WorkflowPhase, string> = {
  pre: "Triggers, source pulls, retrieval, prep",
  assess: "Sandboxed agent reasoning",
  post: "Gates, evidence, proposals, notifications"
};

const NODE_W = 220;
const NODE_H = 86;
const X_GAP = 48;
const Y_GAP = 28;
const LANE_PAD_Y = 56;
const LANE_HEADER_H = 48;

/**
 * Read-only graph render in three vertical swimlanes (pre / assess / post).
 * Edges are drawn as bezier curves between right-port → left-port. The
 * layout is computed deterministically from node phase + topo position so
 * the same workflow always renders identically — handy for audit packets.
 */
export function WorkflowSwimlanes({ graph }: { graph: WorkflowGraph }) {
  const layout = useMemo(() => computeLayout(graph), [graph]);

  return (
    <div className="border border-rule rounded-sm bg-ink-2 overflow-x-auto">
      <svg
        width={layout.width}
        height={layout.height}
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        role="img"
        aria-label="Workflow graph"
        className="block"
      >
        {/* lane backgrounds + headers */}
        {(["pre", "assess", "post"] as WorkflowPhase[]).map((phase, index) => {
          const x = layout.laneXs[phase] - 24;
          const w = NODE_W + 48;
          return (
            <g key={phase}>
              <rect
                x={x}
                y={0}
                width={w}
                height={layout.height}
                fill={index === 1 ? "rgba(196,165,114,0.04)" : "rgba(255,255,255,0.015)"}
                stroke="rgba(255,255,255,0.06)"
                strokeWidth={1}
              />
              <text x={x + 16} y={22} className="ed-display-italic" fontSize={13} fill="rgb(196,165,114)" fontFamily="serif">
                {PHASE_LABEL[phase]}
              </text>
              <text x={x + 16} y={38} fontSize={10.5} fill="rgba(245,239,230,0.45)" fontFamily="monospace" letterSpacing="0.06em">
                {PHASE_NOTE[phase].toUpperCase()}
              </text>
            </g>
          );
        })}

        {/* edges */}
        {layout.edges.map((edge) => (
          <path
            key={edge.id}
            d={edge.path}
            fill="none"
            stroke="rgba(196,165,114,0.5)"
            strokeWidth={1.25}
            markerEnd="url(#arrow)"
          />
        ))}

        <defs>
          <marker id="arrow" viewBox="0 -5 10 10" refX="8" refY="0" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M0,-5L10,0L0,5" fill="rgba(196,165,114,0.7)" />
          </marker>
        </defs>

        {/* nodes */}
        {layout.nodes.map((node) => (
          <g key={node.id} transform={`translate(${node.x},${node.y})`}>
            <rect
              width={NODE_W}
              height={NODE_H}
              rx={3}
              ry={3}
              fill="#101418"
              stroke="rgba(245,239,230,0.18)"
              strokeWidth={1}
            />
            <text x={12} y={22} fontSize={10.5} fill="rgba(245,239,230,0.55)" fontFamily="monospace" letterSpacing="0.06em">
              {node.type.toUpperCase()}
            </text>
            <text x={12} y={44} fontSize={13} fill="rgba(245,239,230,0.95)" fontFamily="serif">
              {clip(node.label, 26)}
            </text>
            <text x={12} y={62} fontSize={11} fill="rgba(245,239,230,0.5)" fontFamily="monospace">
              {node.id}
            </text>
            {node.configKeys.length > 0 && (
              <text x={12} y={78} fontSize={10.5} fill="rgba(196,165,114,0.7)" fontFamily="monospace">
                {clip(node.configKeys.join(", "), 30)}
              </text>
            )}
            {/* ports */}
            <circle cx={0} cy={NODE_H / 2} r={3} fill="rgba(196,165,114,0.85)" />
            <circle cx={NODE_W} cy={NODE_H / 2} r={3} fill="rgba(196,165,114,0.85)" />
          </g>
        ))}
      </svg>
    </div>
  );
}

type LaidOutNode = { id: string; type: string; label: string; configKeys: string[]; x: number; y: number; phase: WorkflowPhase };
type LaidOutEdge = { id: string; path: string };

function computeLayout(graph: WorkflowGraph): { nodes: LaidOutNode[]; edges: LaidOutEdge[]; width: number; height: number; laneXs: Record<WorkflowPhase, number> } {
  const phaseNodes: Record<WorkflowPhase, WorkflowGraphNode[]> = { pre: [], assess: [], post: [] };
  for (const node of graph.nodes) phaseNodes[node.phase].push(node);
  for (const phase of Object.keys(phaseNodes) as WorkflowPhase[]) {
    phaseNodes[phase].sort((a, b) => topoOrder(graph, a) - topoOrder(graph, b));
  }
  const laneXs: Record<WorkflowPhase, number> = {
    pre: 32 + 24,
    assess: 32 + 24 + (NODE_W + X_GAP * 2),
    post: 32 + 24 + 2 * (NODE_W + X_GAP * 2)
  };
  const positions = new Map<string, { x: number; y: number }>();
  let height = LANE_HEADER_H + LANE_PAD_Y;
  for (const phase of ["pre", "assess", "post"] as WorkflowPhase[]) {
    const nodes = phaseNodes[phase];
    nodes.forEach((node, i) => {
      const x = laneXs[phase];
      const y = LANE_HEADER_H + LANE_PAD_Y + i * (NODE_H + Y_GAP);
      positions.set(node.id, { x, y });
      const bottom = y + NODE_H + Y_GAP;
      if (bottom > height) height = bottom;
    });
  }
  height = Math.max(height + 24, 320);

  const laidOutNodes: LaidOutNode[] = graph.nodes.map((node) => {
    const pos = positions.get(node.id) ?? { x: laneXs[node.phase], y: LANE_HEADER_H + LANE_PAD_Y };
    return {
      id: node.id,
      type: node.type,
      label: node.label,
      configKeys: Object.keys(node.config ?? {}),
      x: pos.x,
      y: pos.y,
      phase: node.phase
    };
  });

  const edges: LaidOutEdge[] = graph.edges.map((edge) => ({
    id: edge.id,
    path: bezierPath(positions.get(edge.from), positions.get(edge.to))
  })).filter((e) => e.path);

  const width = laneXs.post + NODE_W + 48;
  return { nodes: laidOutNodes, edges, width, height, laneXs };
}

function topoOrder(graph: WorkflowGraph, node: WorkflowGraphNode): number {
  const incoming = graph.edges.filter((e) => e.to === node.id).length;
  return incoming === 0 ? graph.nodes.indexOf(node) : graph.nodes.indexOf(node) + 1000;
}

function bezierPath(from?: { x: number; y: number }, to?: { x: number; y: number }): string {
  if (!from || !to) return "";
  const startX = from.x + NODE_W;
  const startY = from.y + NODE_H / 2;
  const endX = to.x;
  const endY = to.y + NODE_H / 2;
  const dx = Math.max(40, (endX - startX) * 0.5);
  return `M ${startX} ${startY} C ${startX + dx} ${startY}, ${endX - dx} ${endY}, ${endX} ${endY}`;
}

function clip(value: string, max: number): string {
  return value.length > max ? value.slice(0, max - 1) + "…" : value;
}
