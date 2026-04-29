"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { WorkflowGraph, WorkflowGraphEdge, WorkflowGraphNode, WorkflowPhase } from "@/lib/api/types";

const NODE_W = 220;
const NODE_HEADER = 28;
const PORT_R = 6;

const PHASE_TINT: Record<WorkflowPhase, string> = {
  pre: "rgba(86, 162, 232, 0.18)",
  assess: "rgba(196,165,114,0.22)",
  post: "rgba(212, 132, 110, 0.18)"
};

const PHASE_BORDER: Record<WorkflowPhase, string> = {
  pre: "rgba(86, 162, 232, 0.55)",
  assess: "rgba(196,165,114,0.7)",
  post: "rgba(212, 132, 110, 0.55)"
};

const EDGE_KIND_STROKE: Record<WorkflowGraphEdge["kind"], string> = {
  data: "rgba(196,165,114,0.9)",
  control: "rgba(196,165,114,0.55)",
  approval: "rgba(212, 132, 110, 0.85)",
  error: "rgba(232, 96, 96, 0.85)"
};

type CanvasProps = {
  graph: WorkflowGraph;
  editable?: boolean;
  onChange?: (graph: WorkflowGraph) => void;
  onSelectNode?: (id: string | null) => void;
  selectedId?: string | null;
};

/**
 * ComfyUI-inspired graph canvas. Nodes render as absolutely-positioned
 * cards inside a pannable/zoomable wrapper; edges are drawn as bezier
 * curves in an SVG layer underneath. In `editable` mode, nodes can be
 * dragged, ports can be wired, and the parent owns the persisted graph
 * state (the canvas just emits onChange).
 */
export function WorkflowCanvas({
  graph,
  editable = false,
  onChange,
  onSelectNode,
  selectedId
}: CanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const surfaceRef = useRef<HTMLDivElement>(null);
  const [view, setView] = useState({ tx: 0, ty: 0, scale: 1 });
  const [drag, setDrag] = useState<DragState | null>(null);
  const [pendingEdge, setPendingEdge] = useState<{ from: string; pointer: { x: number; y: number } } | null>(null);

  // Compute node heights based on config keys so edges line up at port centers.
  const layout = useMemo(() => layoutNodes(graph.nodes), [graph.nodes]);

  // Translate page → world coordinates for the SVG/HTML overlay.
  const toWorld = useCallback((clientX: number, clientY: number) => {
    const container = containerRef.current;
    if (!container) return { x: 0, y: 0 };
    const rect = container.getBoundingClientRect();
    return {
      x: (clientX - rect.left - view.tx) / view.scale,
      y: (clientY - rect.top - view.ty) / view.scale
    };
  }, [view]);

  // Pan with middle button or background-left-drag.
  const onPointerDownBackground = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.target !== event.currentTarget && !(event.target as HTMLElement).classList.contains("wf-canvas-bg")) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    setDrag({ kind: "pan", startClientX: event.clientX, startClientY: event.clientY, startTx: view.tx, startTy: view.ty });
    onSelectNode?.(null);
  };

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!drag) {
      if (pendingEdge) {
        const world = toWorld(event.clientX, event.clientY);
        setPendingEdge({ ...pendingEdge, pointer: world });
      }
      return;
    }
    if (drag.kind === "pan") {
      const dx = event.clientX - drag.startClientX;
      const dy = event.clientY - drag.startClientY;
      setView((v) => ({ ...v, tx: drag.startTx + dx, ty: drag.startTy + dy }));
    }
    if (drag.kind === "node") {
      const dx = (event.clientX - drag.startClientX) / view.scale;
      const dy = (event.clientY - drag.startClientY) / view.scale;
      const newPosition = { x: drag.startNodeX + dx, y: drag.startNodeY + dy };
      onChange?.({
        ...graph,
        nodes: graph.nodes.map((n) => (n.id === drag.nodeId ? { ...n, position: newPosition } : n))
      });
    }
  };

  const onPointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    setDrag(null);
    if (pendingEdge) {
      const target = (event.target as HTMLElement).closest<HTMLElement>("[data-port-in]");
      const targetId = target?.dataset.portIn;
      if (targetId && targetId !== pendingEdge.from && !createsCycle(graph.edges, pendingEdge.from, targetId)) {
        const id = `${pendingEdge.from}__${targetId}`;
        if (!graph.edges.some((e) => e.id === id)) {
          onChange?.({
            ...graph,
            edges: [...graph.edges, { id, from: pendingEdge.from, to: targetId, kind: "control" }]
          });
        }
      }
      setPendingEdge(null);
    }
  };

  const onWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    event.preventDefault();
    const delta = -event.deltaY * 0.0015;
    const nextScale = Math.min(2, Math.max(0.4, view.scale + delta));
    if (nextScale === view.scale) return;
    // Zoom toward the pointer.
    const container = containerRef.current;
    if (!container) {
      setView((v) => ({ ...v, scale: nextScale }));
      return;
    }
    const rect = container.getBoundingClientRect();
    const px = event.clientX - rect.left;
    const py = event.clientY - rect.top;
    const wx = (px - view.tx) / view.scale;
    const wy = (py - view.ty) / view.scale;
    const tx = px - wx * nextScale;
    const ty = py - wy * nextScale;
    setView({ tx, ty, scale: nextScale });
  };

  const onNodePointerDown = (event: React.PointerEvent<HTMLDivElement>, node: WorkflowGraphNode) => {
    if (!editable) return;
    if ((event.target as HTMLElement).closest("[data-port]")) return;
    event.stopPropagation();
    onSelectNode?.(node.id);
    setDrag({
      kind: "node",
      nodeId: node.id,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startNodeX: node.position.x,
      startNodeY: node.position.y
    });
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onPortOutDown = (event: React.PointerEvent<HTMLElement>, nodeId: string) => {
    if (!editable) return;
    event.stopPropagation();
    const world = toWorld(event.clientX, event.clientY);
    setPendingEdge({ from: nodeId, pointer: world });
  };

  const onEdgeClick = (event: React.MouseEvent, edgeId: string) => {
    if (!editable) return;
    event.stopPropagation();
    if (!confirm("Remove this connection?")) return;
    onChange?.({ ...graph, edges: graph.edges.filter((e) => e.id !== edgeId) });
  };

  const fit = useCallback(() => {
    const container = containerRef.current;
    if (!container || graph.nodes.length === 0) {
      setView({ tx: 16, ty: 16, scale: 1 });
      return;
    }
    const rect = container.getBoundingClientRect();
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const node of graph.nodes) {
      const h = layout.heights.get(node.id) ?? 86;
      minX = Math.min(minX, node.position.x);
      minY = Math.min(minY, node.position.y);
      maxX = Math.max(maxX, node.position.x + NODE_W);
      maxY = Math.max(maxY, node.position.y + h);
    }
    const w = maxX - minX + 80;
    const h = maxY - minY + 80;
    const scale = Math.min(1.1, Math.min(rect.width / w, rect.height / h));
    setView({ tx: -minX * scale + 40, ty: -minY * scale + 40, scale });
  }, [graph.nodes, layout.heights]);

  useEffect(() => {
    fit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph.nodes.length === 0]);

  return (
    <div className="border border-rule rounded-sm bg-ink-2 overflow-hidden relative" style={{ height: 480 }}>
      <div
        ref={containerRef}
        className="relative h-full w-full select-none touch-none"
        onPointerDown={onPointerDownBackground}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
        onWheel={onWheel}
        style={{ cursor: drag?.kind === "pan" ? "grabbing" : drag?.kind === "node" ? "grabbing" : "grab" }}
      >
        <div className="wf-canvas-bg absolute inset-0" style={{ backgroundImage: gridBackground(view.scale, view.tx, view.ty), backgroundSize: `${24 * view.scale}px ${24 * view.scale}px`, backgroundPosition: `${view.tx}px ${view.ty}px` }} />

        <svg
          className="absolute inset-0 pointer-events-none"
          width="100%"
          height="100%"
        >
          <defs>
            <marker id="wf-arrow" viewBox="0 -5 10 10" refX="6" refY="0" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0,-5L10,0L0,5" fill="rgba(196,165,114,0.85)" />
            </marker>
          </defs>
          <g transform={`translate(${view.tx},${view.ty}) scale(${view.scale})`}>
            {graph.edges.map((edge) => {
              const path = edgePath(edge, graph.nodes, layout);
              if (!path) return null;
              return (
                <path
                  key={edge.id}
                  d={path}
                  fill="none"
                  stroke={EDGE_KIND_STROKE[edge.kind]}
                  strokeWidth={1.6 / view.scale}
                  markerEnd="url(#wf-arrow)"
                  className="pointer-events-auto cursor-pointer"
                  onClick={(e) => onEdgeClick(e, edge.id)}
                />
              );
            })}
            {pendingEdge && (() => {
              const fromNode = graph.nodes.find((n) => n.id === pendingEdge.from);
              if (!fromNode) return null;
              const fromPort = portPosition(fromNode, "out", layout);
              return (
                <path
                  d={`M ${fromPort.x} ${fromPort.y} C ${fromPort.x + 80} ${fromPort.y}, ${pendingEdge.pointer.x - 80} ${pendingEdge.pointer.y}, ${pendingEdge.pointer.x} ${pendingEdge.pointer.y}`}
                  fill="none"
                  stroke="rgba(196,165,114,0.6)"
                  strokeDasharray="4 4"
                  strokeWidth={1.6 / view.scale}
                />
              );
            })()}
          </g>
        </svg>

        <div
          ref={surfaceRef}
          className="absolute top-0 left-0"
          style={{ transform: `translate(${view.tx}px, ${view.ty}px) scale(${view.scale})`, transformOrigin: "0 0" }}
        >
          {graph.nodes.map((node) => {
            const height = layout.heights.get(node.id) ?? 86;
            const isSelected = selectedId === node.id;
            return (
              <div
                key={node.id}
                onPointerDown={(e) => onNodePointerDown(e, node)}
                style={{
                  position: "absolute",
                  left: node.position.x,
                  top: node.position.y,
                  width: NODE_W,
                  height,
                  background: "#0e1216",
                  border: `1px solid ${isSelected ? "rgb(196,165,114)" : PHASE_BORDER[node.phase]}`,
                  boxShadow: isSelected ? "0 0 0 2px rgba(196,165,114,0.25)" : "0 1px 0 rgba(0,0,0,0.4)",
                  borderRadius: 3,
                  cursor: editable ? "grab" : "default"
                }}
              >
                <div
                  style={{
                    height: NODE_HEADER,
                    background: PHASE_TINT[node.phase],
                    borderBottom: `1px solid ${PHASE_BORDER[node.phase]}`,
                    padding: "0 10px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    fontFamily: "monospace",
                    fontSize: 10.5,
                    color: "rgba(245,239,230,0.75)",
                    letterSpacing: "0.06em",
                    textTransform: "uppercase"
                  }}
                >
                  <span>{node.type}</span>
                  <span style={{ color: "rgba(245,239,230,0.5)" }}>{node.phase}</span>
                </div>
                <div style={{ padding: "8px 12px", color: "rgba(245,239,230,0.95)" }}>
                  <div style={{ fontSize: 13, fontFamily: "serif" }}>{node.label}</div>
                  <div style={{ marginTop: 2, fontSize: 11, fontFamily: "monospace", color: "rgba(245,239,230,0.5)" }}>
                    {node.id}
                  </div>
                  {Object.keys(node.config ?? {}).length > 0 && (
                    <div style={{ marginTop: 6, fontSize: 10.5, fontFamily: "monospace", color: "rgba(196,165,114,0.7)", lineHeight: "1.4" }}>
                      {Object.keys(node.config).slice(0, 4).join(", ")}
                    </div>
                  )}
                </div>
                <span
                  data-port="in"
                  data-port-in={node.id}
                  style={portStyle("left")}
                />
                <span
                  data-port="out"
                  data-port-out={node.id}
                  onPointerDown={(e) => onPortOutDown(e, node.id)}
                  style={portStyle("right")}
                />
              </div>
            );
          })}
        </div>

        <div className="absolute bottom-3 right-3 flex items-center gap-1.5 z-10">
          <Mini onClick={fit} title="Fit to view">⤢</Mini>
          <Mini onClick={() => setView((v) => ({ ...v, scale: Math.min(2, v.scale + 0.1) }))} title="Zoom in">+</Mini>
          <Mini onClick={() => setView((v) => ({ ...v, scale: Math.max(0.4, v.scale - 0.1) }))} title="Zoom out">−</Mini>
          <span className="ml-2 font-mono text-[11px] text-paper-fade tabular-nums">{Math.round(view.scale * 100)}%</span>
        </div>
        {editable && (
          <div className="absolute top-3 left-3 text-[11px] text-paper-fade font-mono z-10 bg-ink/85 border border-rule px-3 py-1.5 rounded-sm">
            drag node header to move · drag right port to a left port to wire · click an edge to remove
          </div>
        )}
      </div>
    </div>
  );
}

type DragState =
  | { kind: "pan"; startClientX: number; startClientY: number; startTx: number; startTy: number }
  | { kind: "node"; nodeId: string; startClientX: number; startClientY: number; startNodeX: number; startNodeY: number };

function Mini({ children, onClick, title }: { children: React.ReactNode; onClick: () => void; title: string }) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className="h-7 w-7 inline-flex items-center justify-center bg-ink border border-rule rounded-sm text-paper-dim hover:text-paper hover:border-rule-bright transition-colors"
    >
      {children}
    </button>
  );
}

function layoutNodes(nodes: WorkflowGraphNode[]): { heights: Map<string, number> } {
  const heights = new Map<string, number>();
  for (const node of nodes) {
    const baseHeight = 80;
    const configRows = Object.keys(node.config ?? {}).length > 0 ? 16 : 0;
    heights.set(node.id, baseHeight + configRows + NODE_HEADER);
  }
  return { heights };
}

function portPosition(node: WorkflowGraphNode, side: "in" | "out", layout: { heights: Map<string, number> }) {
  const height = layout.heights.get(node.id) ?? 96;
  const cy = node.position.y + height / 2;
  return {
    x: side === "in" ? node.position.x : node.position.x + NODE_W,
    y: cy
  };
}

function edgePath(edge: WorkflowGraphEdge, nodes: WorkflowGraphNode[], layout: { heights: Map<string, number> }): string | null {
  const fromNode = nodes.find((n) => n.id === edge.from);
  const toNode = nodes.find((n) => n.id === edge.to);
  if (!fromNode || !toNode) return null;
  const a = portPosition(fromNode, "out", layout);
  const b = portPosition(toNode, "in", layout);
  const dx = Math.max(60, (b.x - a.x) * 0.5);
  return `M ${a.x} ${a.y} C ${a.x + dx} ${a.y}, ${b.x - dx} ${b.y}, ${b.x} ${b.y}`;
}

function portStyle(side: "left" | "right"): React.CSSProperties {
  return {
    position: "absolute",
    top: `calc(50% + ${NODE_HEADER / 2}px)`,
    transform: "translateY(-50%)",
    [side]: -PORT_R,
    width: PORT_R * 2,
    height: PORT_R * 2,
    borderRadius: "50%",
    background: "rgba(196,165,114,0.95)",
    border: "1px solid rgba(0,0,0,0.4)",
    cursor: "crosshair",
    zIndex: 2
  };
}

function gridBackground(scale: number, _tx: number, _ty: number): string {
  const dotColor = "rgba(245,239,230,0.06)";
  const major = Math.max(1, Math.floor(scale * 24));
  return `radial-gradient(${dotColor} 1px, transparent ${major / 12}px)`;
}

function createsCycle(edges: WorkflowGraphEdge[], from: string, to: string): boolean {
  const adj = new Map<string, string[]>();
  for (const e of [...edges, { id: "_probe", from, to, kind: "control" } as WorkflowGraphEdge]) {
    if (!adj.has(e.from)) adj.set(e.from, []);
    adj.get(e.from)!.push(e.to);
  }
  const visited = new Set<string>();
  const stack = new Set<string>();
  const dfs = (node: string): boolean => {
    if (stack.has(node)) return true;
    if (visited.has(node)) return false;
    visited.add(node);
    stack.add(node);
    for (const next of adj.get(node) ?? []) if (dfs(next)) return true;
    stack.delete(node);
    return false;
  };
  return dfs(from);
}
