"use client";

import { cn } from "@/lib/utils/cn";
import type { AgentEvent, Asset } from "@/lib/api/types";
import { ThoughtsPane } from "./ThoughtsPane";
import { MemoryPane } from "./MemoryPane";
import { PolicyPane } from "./PolicyPane";
import { Badge } from "@/components/primitives/Badge";
import { StatusDot } from "@/components/primitives/StatusDot";
import { Urn } from "@/components/data/Urn";

/**
 * The three-pane live view. Used for **both** surfaces:
 *
 *   - Production agents (e.g. support-bot)
 *   - Workflow agents (e.g. code_compliance_scan's `scan` step)
 *
 * The asset's `type` controls only the small chip in the header; everything
 * else is the same component, the same hash chain, the same policy surface.
 * That parity is the demo's "self-governance" claim made visually literal.
 *
 *   ┌──────────────────────────────────────────────────────────────────────┐
 *   │ Thoughts · Tools  ║  Memory · Provenance  ║  Policy · Decisions     │
 *   ├──────────────────────────────────────────────────────────────────────┤
 *   │  ↻ event           ║  write key=…          ║  hot · allow · 4ms      │
 *   │   ┄┄┄ chain ┄┄┄    ║   taint ▌▌░░░         ║   evidence: refusal     │
 *   └──────────────────────────────────────────────────────────────────────┘
 */
export function AgentDetail({
  asset,
  events,
  compact
}: {
  asset: Pick<Asset, "id" | "urn" | "type" | "name" | "risk_tier" | "lifecycle">;
  events: AgentEvent[];
  /** when true, drops some chrome so the view fits inside drawers/side panels */
  compact?: boolean;
}) {
  return (
    <div className={cn("flex flex-col border border-rule bg-ink-2", compact ? "h-auto md:h-[460px]" : "h-auto md:h-[640px]")}>
      <header className="flex flex-col gap-3 border-b border-rule px-4 py-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <StatusDot tone="gold" live />
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="ed-h3 text-paper truncate">{asset.name}</span>
              <Badge tone={asset.type === "workflow_agent" ? "gold" : "info"} className="shrink-0">
                {asset.type === "workflow_agent" ? "workflow agent" : asset.type === "agent" ? "production agent" : asset.type}
              </Badge>
              <Badge tone="muted" className="shrink-0">
                tier {asset.risk_tier}
              </Badge>
            </div>
            <div className="mt-1">
              <Urn urn={asset.urn} />
            </div>
          </div>
        </div>
        <div className="text-left md:text-right">
          <div className="smallcaps">Live · same primitives</div>
          <div className="text-[10.5px] text-paper-fade font-mono">
            workflow_agent and production agent share this view
          </div>
        </div>
      </header>
      <div className="grid flex-1 grid-cols-1 overflow-hidden md:grid-cols-3">
        <div className="h-[260px] overflow-hidden border-b border-rule md:h-auto md:border-b-0 md:border-r">
          <ThoughtsPane events={events} />
        </div>
        <div className="h-[260px] overflow-hidden border-b border-rule md:h-auto md:border-b-0 md:border-r">
          <MemoryPane events={events} />
        </div>
        <div className="h-[260px] overflow-hidden md:h-auto">
          <PolicyPane events={events} />
        </div>
      </div>
    </div>
  );
}
