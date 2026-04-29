"use client";

import { cn } from "@/lib/utils/cn";
import type { AgentEvent } from "@/lib/api/types";
import { Timestamp } from "@/components/data/Timestamp";
import { Badge } from "@/components/primitives/Badge";
import { ms } from "@/lib/utils/format";

/**
 * Policy decisions column. Renders policy.decision.{hot,warm} events plus
 * agent.tool.refused (the visible consequence of a hot-path block).
 *
 * Crucially, refusals are framed as evidence, not as alarm. The policy
 * surface is the place where Praetor's "evidence not violation" stance
 * becomes obvious — a refusal here is a check passing, not a thing going
 * wrong. The visual choices reinforce that: refusals get a small ok-tone
 * badge, never a red flash, because in the post-patch world they're
 * exactly what should happen.
 */
const VISIBLE_TYPES = new Set([
  "policy.decision.hot",
  "policy.decision.warm",
  "agent.tool.refused"
]);

export function PolicyPane({ events }: { events: AgentEvent[] }) {
  const decisions = events.filter((e) => VISIBLE_TYPES.has(e.type));
  return (
    <div className="flex flex-col">
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-rule bg-ink-2 px-4 py-2.5">
        <div className="smallcaps">Policy · Decisions · Evidence</div>
        <span className="font-mono text-[10.5px] text-paper-fade tabular-nums">
          {decisions.length}
        </span>
      </header>
      <ul className="flex-1 overflow-y-auto">
        {decisions.length === 0 && (
          <li className="px-4 py-8 text-[12px] text-paper-fade italic">
            No decisions yet.
          </li>
        )}
        {decisions.map((e) => (
          <li key={e.id} className={cn("px-4 py-3 border-b border-rule")}>
            <div className="flex items-baseline gap-3">
              <Timestamp ts={e.ts} mode="timecode" />
              <DecisionBadge event={e} />
              {typeof e.payload.latency_ms === "number" && (
                <span className="ml-auto font-mono text-[10.5px] text-paper-fade">
                  {ms(e.payload.latency_ms as number)}
                </span>
              )}
            </div>
            {(e.payload.package as string) && (
              <div className="mt-2 font-mono text-[11.5px] text-paper-dim">
                {e.payload.package as string}
              </div>
            )}
            {(e.payload.rationale as string) && (
              <p className="mt-1 text-[12.5px] text-paper leading-snug">
                {e.payload.rationale as string}
              </p>
            )}
            {e.type === "agent.tool.refused" && (
              <p className="mt-1 text-[12.5px] text-paper leading-snug">
                <span className="text-paper-fade">refused </span>
                <span className="font-mono">{e.payload.name as string}</span>
                <span className="text-paper-fade"> — </span>
                {e.payload.reason as string}
              </p>
            )}
            <div className="mt-2 text-[10.5px] text-paper-fade">
              ↳ logged as evidence (not a violation)
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function DecisionBadge({ event }: { event: AgentEvent }) {
  if (event.type === "agent.tool.refused") {
    return <Badge tone="ok">refusal · evidence</Badge>;
  }
  const outcome = event.payload.outcome as "allow" | "block" | "warn" | undefined;
  const tone = outcome === "block" ? "ok" : outcome === "warn" ? "warn" : "muted";
  const label =
    event.type === "policy.decision.hot"
      ? `hot · ${outcome ?? "—"}`
      : `warm · ${outcome ?? "—"}`;
  return <Badge tone={tone}>{label}</Badge>;
}
