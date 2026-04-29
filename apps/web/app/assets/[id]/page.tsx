"use client";

import { use, useEffect, useState } from "react";
import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import type { Asset, AgentEvent } from "@/lib/api/types";
import { PageHeader } from "@/components/shell/PageHeader";
import { Badge } from "@/components/primitives/Badge";
import { Hairline } from "@/components/primitives/Hairline";
import { Section } from "@/components/primitives/Section";
import { Urn } from "@/components/data/Urn";
import { useEventStream } from "@/lib/ws/stream";
import { AgentDetail } from "@/components/agent-detail/AgentDetail";

/**
 * Asset Detail page.
 *
 * For every Asset (production agents, workflow agents, tools, etc.), a
 * three-pane live view of its events. Workflow agents render with the same
 * component, the same layout, the same colour palette as production agents
 * — the parity is the architectural claim made visible.
 */
export default function AssetPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [asset, setAsset] = useState<Asset | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api.assets.get(id).then((a) => {
      if (!alive) return;
      setAsset(a);
      setLoading(false);
    });
    return () => { alive = false; };
  }, [id]);

  const { events } = useEventStream({ kind: "asset", id }, { live: !!asset });

  if (loading) {
    return (
      <div className="pt-20 text-center text-paper-fade text-[12px] italic">
        loading asset…
      </div>
    );
  }
  if (!asset) return notFound();

  return (
    <div>
      <PageHeader
        number={asset.type === "workflow_agent" ? "02·a" : "02"}
        kicker={`Asset · ${asset.type.replace("_", " ")}`}
        title={asset.name}
        subtitle={asset.description}
        aside={
          <div className="text-right">
            <div className="flex flex-wrap items-center justify-end gap-1.5">
              <Badge tone={asset.type === "workflow_agent" ? "gold" : "info"}>{asset.type.replace("_", " ")}</Badge>
              <Badge tone="muted">tier {asset.risk_tier}</Badge>
              <Badge tone="muted">{asset.lifecycle}</Badge>
            </div>
            <div className="mt-2"><Urn urn={asset.urn} variant="stamp" /></div>
          </div>
        }
      >
        {asset.type === "workflow_agent" && (
          <div className="mt-2 border-l-2 border-gold pl-3 text-[12px] italic text-paper-dim max-w-2xl">
            This is a workflow agent — created by Praetor to do compliance work
            on the customer's behalf. It is a first-class governed Asset under
            the same control plane that supervises production AI. Same hash
            chain. Same audit packet. Same view.
          </div>
        )}
      </PageHeader>

      <Hairline className="mt-8 mb-2" />

      <Section number="α" eyebrow="Three-pane live view" title={<>Thoughts <span className="text-paper-fade">·</span> Memory <span className="text-paper-fade">·</span> Policy</>}>
        <AgentDetail asset={asset} events={events} />
      </Section>

      <Section number="β" eyebrow="Identity" title="Configuration">
        <dl className="grid gap-x-8 gap-y-4 md:grid-cols-2 text-[12.5px]">
          <Field label="URN"><span className="font-mono text-paper-dim break-all">{asset.urn}</span></Field>
          <Field label="Owner"><span className="font-mono text-paper-dim">{asset.owner_id}</span></Field>
          <Field label="Fingerprint"><span className="font-mono text-paper-fade">{asset.fingerprint}</span></Field>
          <Field label="Data classifications">
            <div className="flex flex-wrap gap-1">
              {asset.data_classifications.length === 0 ? <span className="text-paper-fade">—</span> :
                asset.data_classifications.map((d) => <Badge tone="warn" key={d}>{d}</Badge>)}
            </div>
          </Field>
          <Field label="Sectors">
            <div className="flex flex-wrap gap-1">
              {asset.sectors.length === 0 ? <span className="text-paper-fade">—</span> :
                asset.sectors.map((s) => <Badge tone="muted" key={s}>{s}</Badge>)}
            </div>
          </Field>
          <Field label="Tags">
            <div className="flex flex-wrap gap-1">
              {asset.tags.length === 0 ? <span className="text-paper-fade">—</span> :
                asset.tags.map((t) => <Badge tone="muted" key={t}>{t}</Badge>)}
            </div>
          </Field>
        </dl>
      </Section>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="smallcaps mb-1">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
