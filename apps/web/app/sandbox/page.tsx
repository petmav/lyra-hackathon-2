import { api } from "@/lib/api";
import { PageHeader } from "@/components/shell/PageHeader";
import { Section } from "@/components/primitives/Section";
import { DataTable } from "@/components/primitives/DataTable";
import { Badge } from "@/components/primitives/Badge";
import { Hash } from "@/components/data/Hash";
import { Timestamp } from "@/components/data/Timestamp";
import { ms } from "@/lib/utils/format";

export const dynamic = "force-dynamic";

/**
 * Sandbox page. Active and historical sandbox runs — every workflow agent
 * step and every remediation test is one of these. The page reads as a
 * forensic ledger: status, manifest hash, exit code, replay results.
 */
export default async function SandboxPage() {
  const runs = await api.sandboxRuns.list();
  return (
    <div>
      <PageHeader
        number="04"
        kicker="Workflow runtime · sandbox"
        title={<>Isolated. <span className="ed-display-italic">Replayable.</span></>}
        subtitle="Every workflow agent step runs in a short-lived Docker container with no internet egress except via the MCP bridge. Replay mode reads recorded events from disk for demo resilience."
      />
      <Section number="04·1" eyebrow="Runs" title="Active and historical">
        <DataTable
          rows={runs}
          columns={[
            { key: "status", header: "Status", width: "120px", render: (r) => <Badge tone={r.status === "running" ? "gold" : r.status === "succeeded" ? "ok" : r.status === "failed" || r.status === "timeout" || r.status === "oom" ? "crit" : "muted"}>{r.status}</Badge> },
            { key: "id", header: "Sandbox", width: "140px", render: (r) => <span className="font-mono text-[12px] text-paper">{r.id}</span> },
            { key: "owner", header: "Owner", width: "1fr", render: (r) => (
              <span className="font-mono text-[11.5px] text-paper-dim">
                {r.workflow_run_id ? `wf:${r.workflow_run_id}` : r.proposed_change_id ? `pc:${r.proposed_change_id}` : "—"}
              </span>
            ) },
            { key: "started", header: "Started", width: "120px", render: (r) => <Timestamp ts={r.started_at} /> },
            { key: "dur", header: "Duration", width: "100px", align: "right", render: (r) => (
              <span className="font-mono text-[11.5px] text-paper-dim">
                {r.finished_at ? ms(new Date(r.finished_at).getTime() - new Date(r.started_at).getTime()) : "—"}
              </span>
            ) },
            { key: "exit", header: "Exit", width: "60px", align: "center", render: (r) => <span className="font-mono text-[11.5px]">{r.exit_code ?? "—"}</span> }
          ]}
        />
      </Section>
      <Section number="04·2" eyebrow="Boundary" title="Sandbox runtime">
        <div className="border border-rule p-6 grid gap-6 md:grid-cols-3">
          <Pill label="Image"><span className="font-mono">praetor/sandbox-runtime:latest</span></Pill>
          <Pill label="Network">praetor-mocks bridge only</Pill>
          <Pill label="Filesystem">read-only root · overlay /sandbox/work</Pill>
          <Pill label="Resources">2 vCPU · 2 GB RAM · 300s wall</Pill>
          <Pill label="MCP bridge">enforces per-step scopes</Pill>
          <Pill label="Replay">PRAETOR_REPLAY=1 swaps to disk-backed runs</Pill>
        </div>
      </Section>
    </div>
  );
}

function Pill({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="smallcaps mb-1">{label}</div>
      <div className="text-[13px] text-paper-dim">{children}</div>
    </div>
  );
}
