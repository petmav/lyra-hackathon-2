"use client";

import { useState } from "react";
import { cn } from "@/lib/utils/cn";
import type { ProposedChange } from "@/lib/api/types";
import { Button } from "@/components/primitives/Button";
import { Badge } from "@/components/primitives/Badge";
import { Hairline } from "@/components/primitives/Hairline";
import { Confidence } from "@/components/data/Confidence";
import { Urn } from "@/components/data/Urn";
import { Check, X } from "lucide-react";
import { api } from "@/lib/api";

/**
 * Proposed change view — diff renderer + sandbox replay results + approve/reject.
 *
 * The diff is rendered as monospace lines coloured by leading character
 * (`+ `/`- `/space). Hunks (`@@ … @@`) get an annotation row in muted gold.
 *
 * Below the diff, the sandbox replay battery — each case is a hairline
 * row with a status mark. The point of the visual layout is to make the
 * "everything passed including injection patterns" claim immediately
 * legible without the reader having to scan numbers.
 */
export function ProposedChangeView({ change, compact }: { change: ProposedChange; compact?: boolean }) {
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);

  return (
    <div className="border border-rule rounded-sm">
      <header className="flex items-start justify-between gap-6 px-5 py-4 border-b border-rule">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="gold">{change.kind}</Badge>
            <Badge tone={statusTone(change.status)}>{change.status.replace("_", " ")}</Badge>
            <Urn urn={change.urn} />
          </div>
          <h3 className="mt-3 text-[17px] font-semibold tracking-tight text-paper">
            {summary(change)}
          </h3>
          <div className="mt-3 flex items-center gap-6 text-[11.5px] text-paper-fade">
            <span className="inline-flex items-center gap-2">
              <span className="smallcaps">residual risk</span>
              <Confidence value={change.residual_risk_estimate} />
            </span>
            {change.target_asset_id && (
              <span className="font-mono">target · {change.target_asset_id}</span>
            )}
          </div>
        </div>
        {change.status === "awaiting_approval" && (
          <div className="flex shrink-0 items-center gap-2">
            <Button
              variant="primary"
              onClick={async () => {
                setBusy("approve");
                await api.proposedChanges.approve(change.id);
                setBusy(null);
              }}
              disabled={busy !== null}
            >
              {busy === "approve" ? "approving…" : "approve · apply via hook"}
            </Button>
            <Button
              variant="danger"
              onClick={async () => {
                setBusy("reject");
                await api.proposedChanges.reject(change.id);
                setBusy(null);
              }}
              disabled={busy !== null}
            >
              {busy === "reject" ? "…" : "reject"}
            </Button>
          </div>
        )}
      </header>

      <div className={cn("grid", compact ? "grid-cols-1" : "xl:grid-cols-[1.6fr_1fr]")}>
        <DiffView diff={change.diff} format={change.diff_format} compact={compact} />
        <ReplayResults change={change} />
      </div>
    </div>
  );
}

function summary(c: ProposedChange) {
  switch (c.kind) {
    case "code": return "Code patch · proposed";
    case "config": return "Configuration change · proposed";
    case "policy": return "Policy revision · proposed";
    case "process": return "Process change · proposed";
    case "doc": return "Documentation update · proposed";
  }
}

function statusTone(s: ProposedChange["status"]) {
  if (s === "approved" || s === "applied") return "ok" as const;
  if (s === "rejected") return "crit" as const;
  if (s === "awaiting_approval") return "warn" as const;
  return "muted" as const;
}

function DiffView({ diff, format, compact }: { diff: string; format: ProposedChange["diff_format"]; compact?: boolean }) {
  const lines = diff.split("\n");
  return (
    <div className={cn(compact ? "border-b border-rule" : "xl:border-r xl:border-rule border-b border-rule xl:border-b-0")}>
      <div className="border-b border-rule bg-ink px-4 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-paper-fade flex items-center justify-between">
        <span>Diff · {format}</span>
        <span className="font-mono normal-case tracking-tight text-paper-dim">
          {lines.filter((l) => l.startsWith("+")).length}+ / {lines.filter((l) => l.startsWith("-")).length}-
        </span>
      </div>
      <pre className="overflow-x-auto px-0 py-2 font-mono text-[11.5px] leading-[1.55] tabular-nums">
        {lines.map((line, i) => {
          const tone = lineTone(line);
          return (
            <div
              key={i}
              className={cn(
                "grid grid-cols-[44px_1fr] items-baseline px-2",
                tone === "add" && "bg-ok/5 text-ok",
                tone === "del" && "bg-crit/5 text-crit",
                tone === "hunk" && "text-gold-dim italic"
              )}
            >
              <span className="text-paper-fade text-right pr-3 select-none">{i + 1}</span>
              <span className={cn(tone === "ctx" && "text-paper-dim")}>{line}</span>
            </div>
          );
        })}
      </pre>
    </div>
  );
}

function lineTone(l: string): "add" | "del" | "hunk" | "ctx" {
  if (l.startsWith("+++") || l.startsWith("---")) return "hunk";
  if (l.startsWith("@@")) return "hunk";
  if (l.startsWith("+")) return "add";
  if (l.startsWith("-")) return "del";
  return "ctx";
}

function ReplayResults({ change }: { change: ProposedChange }) {
  const cases = change.sandbox_result?.cases ?? [];
  return (
    <div>
      <div className="border-b border-rule px-4 py-2 flex items-center justify-between">
        <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-paper-fade">Sandbox replay</span>
        <span className="font-mono text-[11px] text-paper-dim">
          {cases.filter((c) => c.status === "pass").length}/{cases.length} pass
        </span>
      </div>
      <ul>
        {cases.map((c, i) => (
          <li key={i} className="grid grid-cols-[18px_1fr] items-start gap-3 px-4 py-3 border-b border-rule last:border-b-0">
            <span className={cn("mt-0.5", c.status === "pass" ? "text-ok" : "text-crit")}>
              {c.status === "pass" ? <Check size={14} strokeWidth={1.5} /> : <X size={14} strokeWidth={1.5} />}
            </span>
            <div>
              <div className="text-[12.5px] text-paper">{c.label}</div>
              {c.detail && <div className="mt-0.5 text-[11px] text-paper-fade italic">{c.detail}</div>}
            </div>
          </li>
        ))}
        {cases.length === 0 && (
          <li className="px-4 py-6 text-[12px] text-paper-fade italic">No replay results yet.</li>
        )}
      </ul>
      {change.sandbox_result?.status === "pass" && (
        <>
          <Hairline />
          <div className="px-4 py-3 text-[11.5px] text-ok flex items-center gap-2">
            <Check size={12} strokeWidth={1.5} />
            All replays green — including known prompt-injection patterns.
          </div>
        </>
      )}
    </div>
  );
}
