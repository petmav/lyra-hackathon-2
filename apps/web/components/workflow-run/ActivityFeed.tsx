"use client";

import { useEffect, useRef } from "react";
import type { AgentEvent, WorkflowRun } from "@/lib/api/types";
import { useEventStream } from "@/lib/ws/stream";
import { Timestamp } from "@/components/data/Timestamp";
import { Badge } from "@/components/primitives/Badge";

const FIXTURES_ONLY =
  (process.env.NEXT_PUBLIC_DATA_SOURCE ?? "").toLowerCase() === "fixtures";

const VISIBLE_TYPES = new Set([
  "workflow.run.started",
  "workflow.run.finished",
  "workflow.run.failed",
  "workflow.step.started",
  "workflow.step.finished",
  "agent.thought",
  "agent.tool.called",
  "agent.tool.refused",
  "corpus.query.called",
  "hook.in.called",
  "hook.out.called",
  "policy.decision.hot",
  "human.gate.opened",
  "human.gate.resolved",
  "finding.emitted",
  "change.proposed",
]);

const RUNNING_STATUSES = new Set(["running", "awaiting_approval"]);

export function ActivityFeed({ run }: { run: WorkflowRun }) {
  if (FIXTURES_ONLY) return null;

  const { events, connected } = useEventStream(
    { kind: "workflowRun", id: run.id },
    { live: true }
  );
  const visible = events.filter((e) => VISIBLE_TYPES.has(e.type));
  const tail = visible.slice(-30);

  // Auto-scroll the inner list — never the page — and only when the user is
  // already pinned to the bottom. Once they scroll up to read older events
  // we leave them there until they scroll back down themselves.
  const listRef = useRef<HTMLUListElement | null>(null);
  const stickRef = useRef(true);
  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    if (stickRef.current && RUNNING_STATUSES.has(run.status)) {
      el.scrollTop = el.scrollHeight;
    }
  }, [tail.length, run.status]);

  const onScroll = () => {
    const el = listRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.clientHeight - el.scrollTop;
    stickRef.current = distance < 24;
  };

  return (
    <section className="border border-rule">
      <header className="flex items-center justify-between border-b border-rule px-4 py-2.5">
        <div className="smallcaps">Activity</div>
        <span className="font-mono text-[10.5px] text-paper-fade tabular-nums">
          {connected ? `${visible.length} live` : `${visible.length} ·`}
        </span>
      </header>
      <ul ref={listRef} onScroll={onScroll} className="max-h-[420px] overflow-y-auto overscroll-contain">
        {tail.length === 0 ? (
          <li className="px-4 py-8 text-center text-[12px] italic text-paper-fade">
            No events yet.
          </li>
        ) : (
          tail.map((e) => (
            <li key={e.id} className="border-b border-rule px-4 py-2">
              <Row event={e} />
            </li>
          ))
        )}
      </ul>
    </section>
  );
}

function Row({ event }: { event: AgentEvent }) {
  return (
    <div>
      <div className="flex items-baseline gap-3">
        <Timestamp ts={event.ts} mode="timecode" />
        <Badge tone={toneFor(event.type)} className="shrink-0">
          {chipLabel(event.type)}
        </Badge>
        <span className="font-mono text-[11px] text-paper-fade truncate">{event.actor}</span>
      </div>
      <Body event={event} />
    </div>
  );
}

function Body({ event }: { event: AgentEvent }) {
  const p = (event.payload ?? {}) as Record<string, unknown>;
  switch (event.type) {
    case "agent.thought":
      return <p className="mt-1 text-[13px] leading-snug text-paper">{String(p.text ?? "")}</p>;
    case "agent.tool.called":
      return (
        <p className="mt-1 text-[12.5px] leading-snug">
          <span className="text-paper-fade">→ tool </span>
          <span className="font-mono text-paper">{String(p.name ?? "")}</span>
          <span className="text-paper-fade"> · </span>
          <span className="font-mono text-[11.5px] text-paper-dim">{summariseArgs(p.args)}</span>
        </p>
      );
    case "agent.tool.refused":
      return (
        <p className="mt-1 text-[12.5px] leading-snug text-crit">
          ↺ refused <span className="font-mono">{String(p.name ?? "")}</span>
          <span className="text-paper-dim"> — {String(p.reason ?? "")}</span>
        </p>
      );
    case "corpus.query.called":
      return (
        <p className="mt-1 text-[12.5px] leading-snug text-paper-dim">
          corpus <span className="font-mono">{String(p.corpus_id ?? "")}</span> — “{String(p.query ?? "")}” · {String(p.chunks_returned ?? "0")} chunks
        </p>
      );
    case "hook.in.called":
      return (
        <p className="mt-1 text-[12.5px] leading-snug text-paper-dim">
          ⤵ pulled <span className="font-mono">{String(p.repo_url ?? p.target ?? "")}</span>
        </p>
      );
    case "hook.out.called":
      return (
        <p className="mt-1 text-[12.5px] leading-snug text-paper-dim">
          ⤴ called <span className="font-mono">{String(p.target ?? "")}</span>
        </p>
      );
    case "policy.decision.hot":
      return (
        <p className="mt-1 text-[12.5px] leading-snug text-paper-dim">
          policy <span className="font-mono">{String(p.package ?? "")}</span> · {String(p.outcome ?? "")} ({String(p.latency_ms ?? "?")}ms)
        </p>
      );
    case "human.gate.opened":
      return (
        <p className="mt-1 text-[12.5px] leading-snug text-paper-dim">⏸ human gate · {String(p.reason ?? "awaiting approval")}</p>
      );
    case "human.gate.resolved":
      return (
        <p className="mt-1 text-[12.5px] leading-snug text-paper-dim">
          ▶ resolved by <span className="font-mono">{String(p.approver ?? "?")}</span> · approved={String(p.approved ?? "?")}
        </p>
      );
    case "finding.emitted": {
      const f = (p.finding ?? {}) as Record<string, unknown>;
      return (
        <p className="mt-1 text-[12.5px] leading-snug">
          <span className="text-paper-fade">finding </span>
          <span className="text-paper">{String(f.title ?? "")}</span>
          <span className="text-paper-fade"> · {String(f.severity ?? "")}</span>
        </p>
      );
    }
    case "change.proposed": {
      const c = (p.proposed_change ?? {}) as Record<string, unknown>;
      return (
        <p className="mt-1 text-[12.5px] leading-snug">
          <span className="text-paper-fade">proposed </span>
          <span className="font-mono text-paper">{String(c.kind ?? "")}</span>
          <span className="text-paper-fade"> change · {String(c.id ?? "")}</span>
        </p>
      );
    }
    case "workflow.step.started":
      return (
        <p className="mt-1 text-[12.5px] leading-snug text-paper-dim">
          ⊳ step <span className="font-mono text-paper">{String(p.step_id ?? p.step ?? "")}</span> · {String(p.step_type ?? p.type ?? "")}
        </p>
      );
    case "workflow.step.finished":
      return (
        <p className="mt-1 text-[12.5px] leading-snug text-paper-dim">
          ⊠ step <span className="font-mono text-paper">{String(p.step_id ?? p.step ?? "")}</span> · {String(p.status ?? "succeeded")}
        </p>
      );
    case "workflow.run.started":
      return <p className="mt-1 text-[12.5px] text-paper-dim">▶ run started</p>;
    case "workflow.run.finished":
      return <p className="mt-1 text-[12.5px] text-paper-dim">■ run finished · {String(p.status ?? "")}</p>;
    case "workflow.run.failed":
      return <p className="mt-1 text-[12.5px] text-crit">✖ run failed · {String(p.error ?? "")}</p>;
    default:
      return null;
  }
}

function summariseArgs(args: unknown): string {
  if (!args || typeof args !== "object") return "";
  return Object.entries(args as Record<string, unknown>)
    .slice(0, 3)
    .map(([k, v]) => `${k}=${typeof v === "string" ? v.slice(0, 32) : JSON.stringify(v).slice(0, 32)}`)
    .join(" · ");
}

function chipLabel(t: string): string {
  if (t === "agent.thought") return "thought";
  if (t === "agent.tool.called") return "tool";
  if (t === "agent.tool.refused") return "refused";
  if (t === "corpus.query.called") return "corpus";
  if (t.startsWith("hook.")) return "hook";
  if (t === "policy.decision.hot") return "policy";
  if (t.startsWith("human.gate.")) return "gate";
  if (t === "finding.emitted") return "finding";
  if (t === "change.proposed") return "change";
  if (t.startsWith("workflow.step.")) return "step";
  if (t.startsWith("workflow.run.")) return "run";
  return t;
}

function toneFor(t: string): "info" | "muted" | "crit" {
  if (t === "agent.tool.refused" || t === "workflow.run.failed") return "crit";
  if (t === "agent.tool.called" || t === "finding.emitted" || t === "change.proposed") return "info";
  return "muted";
}
