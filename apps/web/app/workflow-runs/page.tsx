import { api } from "@/lib/api";
import { PageHeader } from "@/components/shell/PageHeader";
import { Section } from "@/components/primitives/Section";
import { DataTable } from "@/components/primitives/DataTable";
import { Badge } from "@/components/primitives/Badge";
import { StatusDot } from "@/components/primitives/StatusDot";
import { Urn } from "@/components/data/Urn";
import { Timestamp } from "@/components/data/Timestamp";
import { ms } from "@/lib/utils/format";

export const dynamic = "force-dynamic";

/** Workflow runs index — list of every run, navigable to the live view. */
export default async function WorkflowRunsPage() {
  const runs = await api.workflowRuns.list();

  return (
    <div>
      <PageHeader
        number="03·r"
        kicker="Workflow runs"
        title={<>Every run, on file.</>}
        subtitle="Each run is itself an Asset and writes its own hash chain."
      />
      <Section number="03·r·1" eyebrow="Ledger" title="Runs">
        <DataTable
          rows={runs}
          rowHref={(r) => `/workflow-runs/${r.id}`}
          columns={[
            { key: "status", header: "Status", width: "150px", render: (r) => (
              <span className="inline-flex items-center gap-2">
                <StatusDot
                  tone={r.status === "running" ? "gold" : r.status === "succeeded" ? "ok" : r.status === "failed" ? "crit" : "neutral"}
                  live={r.status === "running"}
                />
                <Badge tone={r.status === "running" ? "gold" : r.status === "succeeded" ? "ok" : r.status === "failed" ? "crit" : "muted"}>
                  {r.status}
                </Badge>
              </span>
            ) },
            { key: "id", header: "Run", width: "1.4fr", render: (r) => (
              <div>
                <div className="text-paper">{r.id}</div>
                <div className="mt-0.5"><Urn urn={r.urn} /></div>
              </div>
            ) },
            { key: "by", header: "Triggered by", width: "1fr", render: (r) => <span className="font-mono text-[11.5px] text-paper-dim">{r.triggered_by}</span> },
            { key: "started", header: "Started", width: "120px", render: (r) => <Timestamp ts={r.triggered_at} /> },
            { key: "dur", header: "Duration", width: "100px", align: "right", render: (r) => (
              <span className="font-mono text-[11.5px] text-paper-dim">
                {r.finished_at ? ms(new Date(r.finished_at).getTime() - new Date(r.triggered_at).getTime()) : "in flight"}
              </span>
            ) }
          ]}
        />
      </Section>
    </div>
  );
}
