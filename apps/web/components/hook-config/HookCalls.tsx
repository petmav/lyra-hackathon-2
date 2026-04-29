"use client";

import { Badge } from "@/components/primitives/Badge";
import { DataTable } from "@/components/primitives/DataTable";
import { Timestamp } from "@/components/data/Timestamp";
import type { HookCall } from "@/lib/api/types";
import { ms } from "@/lib/utils/format";

/**
 * Recent hook-call ledger. Used both on the Hooks page and embedded in
 * audit-packet drilldowns.
 */
export function HookCalls({ calls }: { calls: HookCall[] }) {
  return (
    <DataTable
      rows={calls}
      columns={[
        { key: "ts", header: "When", width: "120px", render: (r) => <Timestamp ts={r.ts} /> },
        { key: "hook", header: "Hook", width: "1.2fr", render: (r) => <span className="font-mono text-paper">{r.hook_name}</span> },
        { key: "dir", header: "Dir", width: "60px", render: (r) => <Badge tone={r.direction === "out" ? "warn" : "muted"}>{r.direction}</Badge> },
        { key: "status", header: "Status", width: "80px", render: (r) => <Badge tone={r.status === "ok" ? "ok" : r.status === "denied" ? "warn" : "crit"}>{r.status}</Badge> },
        { key: "lat", header: "Latency", width: "80px", align: "right", render: (r) => <span className="font-mono text-paper-dim">{ms(r.latency_ms)}</span> },
        { key: "io", header: "I/O summary", width: "2fr", render: (r) => (
          <span className="font-mono text-[11.5px] text-paper-fade truncate inline-block max-w-full align-middle">
            {summarise(r.inputs_redacted)} → {summarise(r.outputs_redacted)}
          </span>
        ) }
      ]}
      empty="No hook calls in this window."
    />
  );
}

function summarise(o: Record<string, unknown>): string {
  const entries = Object.entries(o);
  if (entries.length === 0) return "—";
  return entries
    .slice(0, 2)
    .map(([k, v]) => `${k}=${typeof v === "string" ? truncate(v, 18) : JSON.stringify(v).slice(0, 18)}`)
    .join(" · ");
}
function truncate(s: string, n: number) {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}
