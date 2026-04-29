"use client";

import { useCallback, useMemo, useReducer } from "react";
import type { WorkflowGraph, WorkflowGraphEdge, WorkflowGraphNode, WorkflowPhase } from "@/lib/api/types";

type State = {
  nodes: WorkflowGraphNode[];
  edges: WorkflowGraphEdge[];
};

type Action =
  | { kind: "set"; graph: WorkflowGraph }
  | { kind: "add-node"; node: WorkflowGraphNode }
  | { kind: "update-node"; id: string; patch: Partial<WorkflowGraphNode> }
  | { kind: "remove-node"; id: string }
  | { kind: "add-edge"; edge: WorkflowGraphEdge }
  | { kind: "remove-edge"; id: string }
  | { kind: "move-node"; id: string; position: { x: number; y: number } };

const PHASE_X: Record<WorkflowPhase, number> = { pre: 80, assess: 380, post: 680 };

function reducer(state: State, action: Action): State {
  switch (action.kind) {
    case "set":
      return {
        nodes: (action.graph.nodes ?? []).map((n) => ({ ...n })),
        edges: (action.graph.edges ?? []).map((e) => ({ ...e }))
      };
    case "add-node":
      return { ...state, nodes: [...state.nodes, action.node] };
    case "update-node":
      return {
        ...state,
        nodes: state.nodes.map((n) => (n.id === action.id ? { ...n, ...action.patch } : n))
      };
    case "remove-node":
      return {
        nodes: state.nodes.filter((n) => n.id !== action.id),
        edges: state.edges.filter((e) => e.from !== action.id && e.to !== action.id)
      };
    case "add-edge": {
      const exists = state.edges.find((e) => e.from === action.edge.from && e.to === action.edge.to);
      if (exists) return state;
      return { ...state, edges: [...state.edges, action.edge] };
    }
    case "remove-edge":
      return { ...state, edges: state.edges.filter((e) => e.id !== action.id) };
    case "move-node":
      return {
        ...state,
        nodes: state.nodes.map((n) => (n.id === action.id ? { ...n, position: action.position } : n))
      };
    default:
      return state;
  }
}

export function useWorkflowGraph(initial?: WorkflowGraph) {
  const [state, dispatch] = useReducer(reducer, undefined, () => ({
    nodes: initial?.nodes?.map((n) => ({ ...n })) ?? [],
    edges: initial?.edges?.map((e) => ({ ...e })) ?? []
  }));

  const setGraph = useCallback((graph: WorkflowGraph) => dispatch({ kind: "set", graph }), []);

  const addNode = useCallback((node: Omit<WorkflowGraphNode, "id" | "position"> & { id?: string; position?: { x: number; y: number } }) => {
    const baseId = node.id ?? slugify(`${node.type}-${Date.now().toString(36).slice(-4)}`);
    const id = ensureUniqueId(baseId, state.nodes.map((n) => n.id));
    const phaseNodes = state.nodes.filter((n) => n.phase === node.phase);
    const position = node.position ?? { x: PHASE_X[node.phase], y: 80 + phaseNodes.length * 140 };
    dispatch({
      kind: "add-node",
      node: {
        id,
        type: node.type,
        phase: node.phase,
        label: node.label,
        config: node.config ?? {},
        depends_on: node.depends_on,
        position
      }
    });
    return id;
  }, [state.nodes]);

  const updateNode = useCallback((id: string, patch: Partial<WorkflowGraphNode>) => dispatch({ kind: "update-node", id, patch }), []);
  const removeNode = useCallback((id: string) => dispatch({ kind: "remove-node", id }), []);
  const moveNode = useCallback((id: string, position: { x: number; y: number }) => dispatch({ kind: "move-node", id, position }), []);

  const connect = useCallback((from: string, to: string, kind: WorkflowGraphEdge["kind"] = "control") => {
    if (from === to) return;
    if (createsCycle(state.edges, from, to)) return;
    dispatch({ kind: "add-edge", edge: { id: `${from}__${to}`, from, to, kind } });
  }, [state.edges]);

  const disconnect = useCallback((edgeId: string) => dispatch({ kind: "remove-edge", id: edgeId }), []);

  const graph: WorkflowGraph = useMemo(
    () => ({ nodes: state.nodes, edges: state.edges, phases: ["pre", "assess", "post"] }),
    [state.nodes, state.edges]
  );

  return {
    graph,
    nodes: state.nodes,
    edges: state.edges,
    setGraph,
    addNode,
    updateNode,
    removeNode,
    moveNode,
    connect,
    disconnect
  };
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "") || "node";
}

function ensureUniqueId(baseId: string, existing: string[]): string {
  if (!existing.includes(baseId)) return baseId;
  let n = 2;
  while (existing.includes(`${baseId}_${n}`)) n += 1;
  return `${baseId}_${n}`;
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
