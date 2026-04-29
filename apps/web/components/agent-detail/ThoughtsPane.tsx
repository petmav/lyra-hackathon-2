"use client";

import { cn } from "@/lib/utils/cn";
import type { AgentEvent } from "@/lib/api/types";
import { Timestamp } from "@/components/data/Timestamp";
import { HashChain } from "@/components/data/HashChain";
import { Badge } from "@/components/primitives/Badge";

/**
 * The "thoughts" column of the three-pane agent live view.
 *
 * Renders agent.thought, agent.tool.called, sandbox.launched, sandbox.exited,
 * workflow.step.{started,finished} events in a single thread that reads as
 * an annotated transcript. Each entry shows a hash-chain hairline beneath
 * — the chain is part of the prose, not chrome.
 *
 * The same component is used for the production support-bot and for the
 * workflow_agent in `code_compliance_scan` — that parity is the demo's
 * "self-governance" claim made visually literal.
 */
const VISIBLE_TYPES = new Set([
  "agent.thought",
  "agent.tool.called",
  "agent.tool.refused",
  "sandbox.launched",
  "sandbox.exited",
  "workflow.step.started",
  "workflow.step.finished"
]);

export function ThoughtsPane({ events }: { events: AgentEvent[] }) {
  const filtered = events.filter((e) => VISIBLE_TYPES.has(e.type));
  return (
    <div className="flex flex-col">
      <PaneHeader label="Thoughts · Tools · Boundary" count={filtered.length} />
      <ul className="flex-1 overflow-y-auto">
        {filtered.length === 0 && (
          <li className="px-4 py-8 text-[12px] text-paper-fade italic">No thoughts yet.</li>
        )}
        {filtered.map((e, i) => (
          <li
            key={e.id}
            className={cn(
              "px-4 py-3 border-b border-rule",
              i === filtered.length - 1 && "event-new"
            )}
          >
            <div className="flex items-baseline gap-3">
              <Timestamp ts={e.ts} mode="timecode" />
              <Badge tone={chipToneFor(e.type)} className="shrink-0">
                {chipLabel(e.type)}
              </Badge>
              <span className="font-mono text-[11px] text-paper-fade">{e.actor}</span>
            </div>
            <Body event={e} />
            <HashChain
              prev={e.hash_chain_prev}
              self={e.hash_chain_self}
              live={i === filtered.length - 1}
              className="mt-2"
            />
          </li>
        ))}
      </ul>
    </div>
  );
}

function PaneHeader({ label, count }: { label: string; count: number }) {
  return (
    <header className="sticky top-0 z-10 flex items-center justify-between border-b border-rule bg-ink-2 px-4 py-2.5">
      <div className="smallcaps">{label}</div>
      <span className="font-mono text-[10.5px] text-paper-fade tabular-nums">{count}</span>
    </header>
  );
}

function Body({ event }: { event: AgentEvent }) {
  switch (event.type) {
    case "agent.thought":
      return <p className="mt-2 text-[13px] text-paper leading-snug">{(event.payload.text as string) ?? ""}</p>;
    case "agent.tool.called":
      return (
        <p className="mt-2 text-[12.5px] leading-snug">
          <span className="text-paper-fade">→ tool </span>
          <span className="font-mono text-paper">{event.payload.name as string}</span>
          <span className="text-paper-fade">(</span>
          <span className="font-mono text-[11.5px] text-paper-dim">
            {summariseArgs(event.payload.args)}
          </span>
          <span className="text-paper-fade">)</span>
        </p>
      );
    case "agent.tool.refused":
      return (
        <p className="mt-2 text-[12.5px] leading-snug text-crit">
          <span className="text-paper-fade">↺ refused </span>
          <span className="font-mono text-paper">{event.payload.name as string}</span>
          <span className="text-paper-dim"> — {event.payload.reason as string}</span>
        </p>
      );
    case "sandbox.launched":
      return (
        <p className="mt-2 text-[12.5px] text-paper-dim leading-snug">
          ⤴ sandbox up · {String(event.payload.mem_mb)} MB · wall {String(event.payload.wall_s)}s ·{" "}
          <span className="font-mono">{String(event.payload.network)}</span>
        </p>
      );
    case "sandbox.exited":
      return (
        <p className="mt-2 text-[12.5px] text-paper-dim leading-snug">
          ⤵ sandbox down · {String(event.payload.status ?? "succeeded")}
        </p>
      );
    case "workflow.step.started":
      return (
        <p className="mt-2 text-[12.5px] text-paper-dim leading-snug">
          ⊳ step <span className="font-mono text-paper">{event.payload.step as string}</span> ·{" "}
          {event.payload.type as string}
        </p>
      );
    case "workflow.step.finished":
      return (
        <p className="mt-2 text-[12.5px] text-paper-dim leading-snug">
          ⊠ step <span className="font-mono text-paper">{event.payload.step as string}</span> ·{" "}
          {event.payload.status as string}
        </p>
      );
    default:
      return null;
  }
}

function chipLabel(t: string) {
  if (t === "agent.thought") return "thought";
  if (t === "agent.tool.called") return "tool";
  if (t === "agent.tool.refused") return "refused";
  if (t.startsWith("sandbox.")) return "sandbox";
  if (t.startsWith("workflow.step.")) return "step";
  return t;
}

function chipToneFor(t: string) {
  if (t === "agent.tool.refused") return "crit" as const;
  if (t === "agent.tool.called") return "info" as const;
  if (t === "agent.thought") return "muted" as const;
  if (t.startsWith("sandbox.")) return "muted" as const;
  return "muted" as const;
}

function summariseArgs(args: unknown) {
  if (!args || typeof args !== "object") return "";
  const entries = Object.entries(args as Record<string, unknown>).slice(0, 3);
  return entries
    .map(([k, v]) => `${k}=${typeof v === "string" ? truncate(v, 32) : JSON.stringify(v).slice(0, 32)}`)
    .join(" · ");
}
function truncate(s: string, n: number) {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}
