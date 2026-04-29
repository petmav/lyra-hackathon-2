import { api } from "@/lib/api";
import { PageHeader } from "@/components/shell/PageHeader";
import { DataTable } from "@/components/primitives/DataTable";
import { Badge } from "@/components/primitives/Badge";
import { Urn } from "@/components/data/Urn";
import { Timestamp } from "@/components/data/Timestamp";

export const dynamic = "force-dynamic";

/**
 * Inventory page. Lists every Asset in one table — production agents,
 * workflow agents, tools, ai_systems, models. Workflow agents share the
 * list with production agents (distinguished only by a chip), reinforcing
 * that they are first-class governed entities.
 */
export default async function InventoryPage() {
  const assets = await api.assets.list();

  return (
    <div>
      <PageHeader
        number="02"
        kicker="Inventory · governed assets"
        title={<>Catalogue.</>}
        subtitle="Every governed entity. Production agents, workflow agents, tools, datasets, and models — all under the same supervision umbrella, all writing to the same hash chain."
      />
      <div className="mt-10">
        <DataTable
          rows={assets}
          rowHref={(a) => `/assets/${a.id}`}
          columns={[
            { key: "type", header: "Type", width: "150px", render: (a) => (
              <Badge tone={typeTone(a.type)}>
                {a.type.replace("_", " ")}
              </Badge>
            ) },
            { key: "name", header: "Name", width: "1.4fr", render: (a) => (
              <div>
                <div className="text-paper">{a.name}</div>
                <div className="mt-0.5"><Urn urn={a.urn} /></div>
              </div>
            ) },
            { key: "tier", header: "Risk", width: "60px", align: "center", render: (a) => <span className="font-mono text-paper-dim">{a.risk_tier}</span> },
            { key: "lifecycle", header: "Lifecycle", width: "120px", render: (a) => <span className="font-mono text-[11.5px] text-paper-fade">{a.lifecycle}</span> },
            { key: "juris", header: "Jurisdictions", width: "150px", render: (a) => (
              <div className="flex flex-wrap gap-1">
                {a.jurisdictions.length === 0 ? (
                  <span className="text-paper-fade">—</span>
                ) : a.jurisdictions.map((j) => <Badge tone="muted" key={j}>{j}</Badge>)}
              </div>
            ) },
            { key: "owner", header: "Owner", width: "1fr", render: (a) => <span className="font-mono text-[11.5px] text-paper-dim truncate inline-block max-w-full align-middle">{a.owner_id}</span> },
            { key: "updated", header: "Updated", width: "100px", render: (a) => <Timestamp ts={a.updated_at} /> }
          ]}
        />
      </div>
    </div>
  );
}

function typeTone(t: string) {
  if (t === "agent") return "info" as const;
  if (t === "workflow_agent") return "gold" as const;
  if (t === "workflow_run") return "gold" as const;
  if (t === "ai_system") return "info" as const;
  if (t === "tool") return "muted" as const;
  return "muted" as const;
}
