/**
 * WebSocket-backed event stream with fixture fallback.
 *
 * The real backend exposes:
 *   WS /ws/v1/assets/{id}/stream
 *   WS /ws/v1/workflow-runs/{id}/stream
 *
 * `useEventStream(topic)` yields historical events first. When
 * NEXT_PUBLIC_API_BASE is set and NEXT_PUBLIC_MOCK_STREAMS is not "1", it
 * opens the FastAPI WebSocket stream. Otherwise it uses a curated fixture tape.
 */

"use client";

import { useEffect, useRef, useState } from "react";
import type { AgentEvent } from "@/lib/api/types";
import { api } from "@/lib/api";

type StreamTopic =
  | { kind: "asset"; id: string }
  | { kind: "workflowRun"; id: string };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "");
const API_TOKEN = process.env.NEXT_PUBLIC_API_TOKEN ?? process.env.NEXT_PUBLIC_DEV_BEARER ?? "dev";
const MOCK_STREAMS = process.env.NEXT_PUBLIC_MOCK_STREAMS === "1";

function websocketUrl(topic: StreamTopic): string | null {
  if (!API_BASE || MOCK_STREAMS) return null;
  const base = API_BASE.replace(/^http:/, "ws:").replace(/^https:/, "wss:");
  const path =
    topic.kind === "asset"
      ? `/ws/v1/assets/${encodeURIComponent(topic.id)}/stream`
      : `/ws/v1/workflow-runs/${encodeURIComponent(topic.id)}/stream`;
  return `${base}${path}?token=${encodeURIComponent(API_TOKEN)}`;
}

/** A small curated tape of "future" events used to keep the stream alive. */
const continuationTape: Array<Pick<AgentEvent, "type" | "actor" | "payload">> = [
  { type: "agent.thought", actor: "scan-agent", payload: { text: "Re-checking issue_refund and lookup_kb for analogous gaps." } },
  { type: "agent.tool.called", actor: "scan-agent", payload: { name: "embed_search", args: { query: "tool argument validation" } } },
  { type: "corpus.query", actor: "praetor:corpus", payload: { corpus_id: "corp_owasp", query: "tool argument validation", chunks_returned: 3, top_score: 0.74 } },
  { type: "agent.memory.write", actor: "scan-agent", payload: { key: "owasp:a04", taint_score: 0.09, provenance: "doc_owasp#chunk_5" } },
  { type: "policy.decision.hot", actor: "praetor:policy", payload: { package: "praetor.controls.workflow_agent_step", outcome: "allow", latency_ms: 2 } },
  { type: "agent.thought", actor: "scan-agent", payload: { text: "issue_refund cap is enforced server-side. No additional finding." } },
  { type: "workflow.step.started", actor: "praetor:runtime", payload: { step: "gate", type: "gate.policy" } },
  { type: "policy.decision.hot", actor: "praetor:policy", payload: { package: "praetor.controls.workflow_findings_gate", outcome: "allow", latency_ms: 4 } },
  { type: "workflow.step.finished", actor: "praetor:runtime", payload: { step: "gate", status: "succeeded" } },
  { type: "workflow.step.started", actor: "praetor:runtime", payload: { step: "emit", type: "finding.emit" } }
];

export function useEventStream(topic: StreamTopic, opts: { live?: boolean } = {}) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const idCounter = useRef(0);

  useEffect(() => {
    let cancelled = false;
    setConnected(false);

    const fetchHistory = async () => {
      const history =
        topic.kind === "asset"
          ? await api.events.forAsset(topic.id)
          : await api.events.forWorkflowRun(topic.id);
      if (cancelled) return;
      setEvents(history);
      idCounter.current = history.length;
      setConnected(true);
    };
    fetchHistory();

    if (opts.live === false) return () => { cancelled = true; };

    const wsUrl = websocketUrl(topic);
    if (wsUrl) {
      const socket = new WebSocket(wsUrl);
      socket.onopen = () => {
        if (!cancelled) setConnected(true);
      };
      socket.onmessage = (message) => {
        if (cancelled) return;
        const event = JSON.parse(message.data) as AgentEvent;
        setEvents((prev) => {
          if (prev.some((candidate) => candidate.id === event.id)) return prev;
          const next = [...prev, event];
          return next.length > 400 ? next.slice(-400) : next;
        });
      };
      socket.onclose = () => {
        if (!cancelled) setConnected(false);
      };
      socket.onerror = () => {
        if (!cancelled) setConnected(false);
      };
      return () => {
        cancelled = true;
        socket.close();
      };
    }

    const interval = setInterval(() => {
      if (cancelled) return;
      const tape = continuationTape[idCounter.current % continuationTape.length];
      const id = `evt_live_${idCounter.current++}`;
      const newEvent: AgentEvent = {
        id,
        ts: new Date().toISOString(),
        asset_id:
          topic.kind === "asset" ? topic.id : "asset_wfa_scan",
        workflow_run_id: topic.kind === "workflowRun" ? topic.id : undefined,
        workflow_step_id: "scan",
        type: tape.type,
        actor: tape.actor,
        payload: tape.payload,
        hash_chain_prev: "0".repeat(64),
        hash_chain_self: "0".repeat(64)
      };
      setEvents((prev) => {
        const next = [...prev, newEvent];
        return next.length > 400 ? next.slice(-400) : next;
      });
    }, 2400);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [topic.kind, topic.id, opts.live]);

  return { events, connected };
}
