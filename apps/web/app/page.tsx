import Link from "next/link";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/shell/PageHeader";
import { Section } from "@/components/primitives/Section";
import { DataTable } from "@/components/primitives/DataTable";
import { Badge } from "@/components/primitives/Badge";
import { Hairline } from "@/components/primitives/Hairline";
import { StatusDot } from "@/components/primitives/StatusDot";
import { Timestamp } from "@/components/data/Timestamp";
import { Urn } from "@/components/data/Urn";
import { Confidence } from "@/components/data/Confidence";
import { ArrowUpRight } from "lucide-react";

export const dynamic = "force-dynamic";

/**
 * Dashboard.
 *
 * Editorial layout — feels more like the front page of an audit ledger
 * than a SaaS dashboard. Five horizontal stats at the top in Fraunces
 * (the section "headline"), followed by sections: Live workflows, Open
 * findings, Recent supervision events, Audit packets in motion. Each
 * section uses a §-numbered eyebrow that runs through the day's filing.
 */
export default async function DashboardPage() {
  const [runs, findings, packets, alerts, assets] = await Promise.all([
    api.workflowRuns.list(),
    api.findings.list(),
    api.auditPackets.list(),
    api.alerts.list(),
    api.assets.list()
  ]);

  const liveRuns = runs.filter((r) => r.status === "running" || r.status === "awaiting_approval");
  const primaryRun = liveRuns[0] ?? runs[0];
  const openFindings = findings.filter((f) => f.status === "open");
  const supervisedAgents = assets.filter((a) => a.type === "agent" || a.type === "ai_system");
  const workflowAgents = assets.filter((a) => a.type === "workflow_agent");

  return (
    <div>
      <PageHeader
        number="01"
        kicker="Operations · 2026-04-28"
        title={
          <>
            Today's <span className="ed-display-italic">filing.</span>
          </>
        }
        subtitle="One control plane, two surfaces. The agents that do your compliance work are governed by the same runtime you offer for the AI you ship."
        aside={
          <Link
            href={primaryRun ? `/workflow-runs/${primaryRun.id}` : "/workflow-runs"}
            className="inline-flex items-center gap-2 border border-gold px-3 py-2 text-[11px] uppercase tracking-[0.16em] text-gold hover:bg-gold hover:text-ink transition-colors"
          >
            {primaryRun ? "View live run" : "View runs"}
            <ArrowUpRight size={13} strokeWidth={1.5} />
          </Link>
        }
      />

      {/* top stats — editorial */}
      <div className="mt-10 grid grid-cols-2 gap-x-12 gap-y-6 border-y border-rule py-6 md:grid-cols-5">
        <Stat label="governed assets" v={assets.length} suffix={`${supervisedAgents.length} prod · ${workflowAgents.length} workflow`} />
        <Stat label="live workflows" v={liveRuns.length} suffix="all green" />
        <Stat label="open findings" v={openFindings.length} suffix={`${openFindings.filter((f) => f.severity === "high" || f.severity === "critical").length} high+`} />
        <Stat label="pending approvals" v={alerts.filter((a) => a.kind === "approval").length} suffix="↗ alerts tray" />
        <Stat label="audit packets" v={packets.length} suffix={`${packets.filter((p) => p.status === "ready").length} ready`} />
      </div>

      <Section
        number="02"
        eyebrow="Workflow runtime"
        title="Workflow runs · live"
        aside={<Link href="/workflows" className="smallcaps text-paper-dim hover:text-paper">Templates →</Link>}
      >
        <DataTable
          rows={runs.slice(0, 5)}
          rowHref={(r) => `/workflow-runs/${r.id}`}
          columns={[
            { key: "status", header: "Status", width: "140px", render: (r) => (
              <span className="inline-flex items-center gap-2">
                <StatusDot tone={runTone(r.status)} live={r.status === "running"} />
                <span className="font-mono text-[11.5px]">{r.status}</span>
              </span>
            ) },
            { key: "name", header: "Name", width: "1.6fr", render: (r) => (
              <div>
                <div className="text-paper">{r.id}</div>
                <div className="text-paper-fade text-[11px]">{r.workflow_id.replace("wf_", "")}</div>
              </div>
            ) },
            { key: "by", header: "Triggered by", width: "1fr", render: (r) => <span className="font-mono text-paper-dim text-[11.5px]">{r.triggered_by}</span> },
            { key: "when", header: "When", width: "120px", render: (r) => <Timestamp ts={r.triggered_at} /> }
          ]}
        />
      </Section>

      <Section number="03" eyebrow="Supervision" title="Open findings">
        <ul className="grid gap-3 lg:grid-cols-2">
          {openFindings.slice(0, 4).map((f) => (
            <li key={f.id}>
              <Link href={`/findings/${f.id}`} className="block group">
                <div className="border border-rule p-4 group-hover:border-rule-bright transition-colors">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <Badge tone={severTone(f.severity)}>{f.severity}</Badge>
                        <Urn urn={f.urn} />
                      </div>
                      <h3 className="mt-2 ed-h3 text-paper truncate">{f.title}</h3>
                      <p className="mt-1 text-[12px] text-paper-fade leading-snug line-clamp-2">{f.description}</p>
                    </div>
                    <Confidence value={f.confidence} showNumeric />
                  </div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      </Section>

      <Section number="04" eyebrow="Audit" title="Packets in motion">
        <DataTable
          rows={packets}
          rowHref={(p) => `/evidence?packet=${p.id}`}
          columns={[
            { key: "status", header: "Status", width: "120px", render: (p) => <Badge tone={p.status === "ready" ? "ok" : p.status === "generating" ? "gold" : "warn"}>{p.status}</Badge> },
            { key: "label", header: "Scope", width: "1.6fr", render: (p) => <span className="text-paper">{p.scope.label ?? "—"}</span> },
            { key: "period", header: "Period", width: "1.2fr", render: (p) => <span className="font-mono text-[11.5px] text-paper-dim">{p.period_start.slice(0, 10)} → {p.period_end.slice(0, 10)}</span> },
            { key: "gen", header: "Generated", width: "120px", render: (p) => p.generated_at ? <Timestamp ts={p.generated_at} /> : <span className="text-paper-fade text-[11px]">— pending —</span> }
          ]}
        />
      </Section>

      <Hairline tone="display" className="mt-16" />
      <p className="mt-4 text-center text-[11px] text-paper-fade italic">
        Everything on this page is derived from the same hash-chained event
        log that produces the audit packet. <Link href="/evidence" className="text-paper-dim hover:text-paper underline-offset-4 hover:underline">Generate one →</Link>
      </p>
    </div>
  );
}

function Stat({ label, v, suffix }: { label: string; v: number; suffix?: string }) {
  return (
    <div>
      <div className="smallcaps mb-1">{label}</div>
      <div
        className="ed-display text-paper text-[44px] leading-none tabular-nums"
        style={{ fontVariationSettings: '"opsz" 144, "wght" 320' }}
      >
        {v}
      </div>
      {suffix && <div className="mt-1.5 text-[11px] text-paper-fade font-mono">{suffix}</div>}
    </div>
  );
}

function runTone(s: string): "ok" | "warn" | "crit" | "gold" | "neutral" {
  if (s === "running") return "gold";
  if (s === "awaiting_approval") return "warn";
  if (s === "succeeded") return "ok";
  if (s === "failed" || s === "cancelled") return "crit";
  return "neutral";
}

function severTone(s: string): "ok" | "warn" | "crit" | "info" | "muted" {
  if (s === "critical" || s === "high") return "crit";
  if (s === "medium") return "warn";
  if (s === "low") return "info";
  return "muted";
}
