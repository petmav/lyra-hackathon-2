"use client";

import { cn } from "@/lib/utils/cn";
import type { AgentEvent } from "@/lib/api/types";
import { Timestamp } from "@/components/data/Timestamp";
import { Badge } from "@/components/primitives/Badge";

/**
 * Memory writes column. Each entry shows the key being written, a taint-score
 * meter, and the provenance pointing back to the corpus chunk that sourced
 * the value (when applicable). Writes whose taint score crosses the
 * quarantine threshold render with a `quarantined` badge.
 *
 * The provenance string format is `doc_internal#chunk_7` — that maps cleanly
 * to a corpus chunk URL, though we don't link out from this pane in the
 * hackathon scope.
 */
export function MemoryPane({ events }: { events: AgentEvent[] }) {
  const writes = events.filter(
    (e) => e.type === "agent.memory.write" || e.type === "agent.memory.read"
  );
  return (
    <div className="flex flex-col">
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-rule bg-ink-2 px-4 py-2.5">
        <div className="smallcaps">Memory · Provenance · Quarantine</div>
        <span className="font-mono text-[10.5px] text-paper-fade tabular-nums">
          {writes.length}
        </span>
      </header>
      <ul className="flex-1 overflow-y-auto">
        {writes.length === 0 && (
          <li className="px-4 py-8 text-[12px] text-paper-fade italic">
            No memory writes yet.
          </li>
        )}
        {writes.map((e) => {
          const taint = (e.payload.taint_score as number | undefined) ?? 0;
          const quarantined = taint > 0.7;
          return (
            <li key={e.id} className="px-4 py-3 border-b border-rule">
              <div className="flex items-baseline gap-3">
                <Timestamp ts={e.ts} mode="timecode" />
                <Badge tone={e.type === "agent.memory.write" ? "info" : "muted"}>
                  {e.type === "agent.memory.write" ? "write" : "read"}
                </Badge>
                {quarantined && <Badge tone="crit">quarantined</Badge>}
              </div>
              <div className="mt-2">
                <div className="font-mono text-[12.5px] text-paper">
                  {(e.payload.key as string) ?? "—"}
                </div>
                {typeof e.payload.provenance === "string" && (
                  <div className="mt-1 text-[11.5px] text-paper-fade">
                    ↳ provenance ·{" "}
                    <span className="font-mono text-paper-dim">
                      {e.payload.provenance}
                    </span>
                  </div>
                )}
                <TaintMeter taint={taint} />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function TaintMeter({ taint }: { taint: number }) {
  const filled = Math.round(taint * 12);
  return (
    <div className="mt-2 flex items-center gap-2">
      <span className="text-[10px] uppercase tracking-[0.18em] text-paper-fade">
        taint
      </span>
      <span aria-hidden className="flex h-1.5 items-stretch gap-px">
        {Array.from({ length: 12 }).map((_, i) => (
          <span
            key={i}
            className={cn(
              "w-[3px]",
              i < filled
                ? taint > 0.7
                  ? "bg-crit"
                  : taint > 0.3
                    ? "bg-warn"
                    : "bg-ok"
                : "bg-rule"
            )}
          />
        ))}
      </span>
      <span className="font-mono text-[10.5px] tabular-nums text-paper-fade">
        {taint.toFixed(2)}
      </span>
    </div>
  );
}
