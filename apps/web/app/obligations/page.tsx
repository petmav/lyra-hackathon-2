import { api } from "@/lib/api";
import { PageHeader } from "@/components/shell/PageHeader";
import { Section } from "@/components/primitives/Section";
import { ObligationGraph } from "@/components/obligation-graph/ObligationGraph";
import { DataTable } from "@/components/primitives/DataTable";
import { Badge } from "@/components/primitives/Badge";
import { Citation } from "@/components/data/Citation";

export const dynamic = "force-dynamic";

/**
 * Obligations page — the obligation/control/asset graph at the top, the
 * obligation ledger at the bottom. The graph is hand-rendered SVG so it
 * matches the audit-packet's printed obligation chain exactly.
 */
export default async function ObligationsPage() {
  const [obligations, controls, assets] = await Promise.all([
    api.obligations.list(),
    api.controls.list(),
    api.assets.list()
  ]);

  return (
    <div>
      <PageHeader
        number="07"
        kicker="Knowledge · obligations"
        title={<>From obligation to <span className="ed-display-italic">asset</span>.</>}
        subtitle="A graph of regulatory and internal obligations, the controls that implement them, and the assets that bear them. Same shape as the audit packet's printed obligation chain."
      />
      <Section number="07·1" eyebrow="Graph" title="Obligations · Controls · Assets">
        <ObligationGraph obligations={obligations} controls={controls} assets={assets} />
      </Section>
      <Section number="07·2" eyebrow="Ledger" title="Obligations">
        <DataTable
          rows={obligations}
          columns={[
            { key: "framework", header: "Framework", width: "150px", render: (o) => <Badge tone="gold">{o.framework}</Badge> },
            { key: "citation", header: "Citation", width: "1.4fr", render: (o) => (
              <Citation framework={o.framework.replace("_", " ").toUpperCase()} path={o.citation} excerpt={o.text} />
            ) },
            { key: "sev", header: "Default", width: "100px", render: (o) => <Badge tone={o.severity_default === "block" ? "crit" : o.severity_default === "warn" ? "warn" : "muted"}>{o.severity_default}</Badge> },
            { key: "ver", header: "Version", width: "90px", render: (o) => <span className="font-mono text-[11.5px] text-paper-dim">{o.version}</span> }
          ]}
        />
      </Section>
    </div>
  );
}
