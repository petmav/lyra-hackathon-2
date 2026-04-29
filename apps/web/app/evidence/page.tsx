"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { AuditPacket, EvidenceRecord } from "@/lib/api/types";
import { PageHeader } from "@/components/shell/PageHeader";
import { Section } from "@/components/primitives/Section";
import { Hairline } from "@/components/primitives/Hairline";
import { Badge } from "@/components/primitives/Badge";
import { DataTable } from "@/components/primitives/DataTable";
import { Hash } from "@/components/data/Hash";
import { Timestamp } from "@/components/data/Timestamp";
import { AuditPacketBuilder } from "@/components/audit-packet/AuditPacketBuilder";
import { AuditPacketPreview } from "@/components/audit-packet/AuditPacketPreview";

/**
 * Evidence page — the audit packet builder + ledger + a live "PDF preview"
 * of the most recently ready packet. The preview renders on warm paper to
 * make the artefact feel printable; that's the demo's tangible-output beat.
 */
export default function EvidencePage() {
  const [packets, setPackets] = useState<AuditPacket[]>([]);
  const [evidence, setEvidence] = useState<EvidenceRecord[]>([]);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    api.auditPackets.list().then(setPackets);
    api.evidence.list().then(setEvidence);
  }, [refresh]);

  const ready = packets.find((p) => p.status === "ready");

  return (
    <div>
      <PageHeader
        number="08"
        kicker="Audit · evidence"
        title={<>The <span className="ed-display-italic">tangible</span> artefact.</>}
        subtitle="Continuously assembled EvidenceRecords linking events ↔ controls ↔ obligations ↔ assets across both surfaces. On demand, produce an ed25519-signed audit packet PDF an external auditor can verify offline."
      />

      <Section number="08·1" eyebrow="Builder" title="Generate audit packet">
        <AuditPacketBuilder onCreated={() => setRefresh((r) => r + 1)} />
      </Section>

      <Section number="08·2" eyebrow="Ledger" title="Recent packets">
        <DataTable
          rows={packets}
          columns={[
            { key: "status", header: "Status", width: "120px", render: (p) => <Badge tone={p.status === "ready" ? "ok" : p.status === "generating" ? "gold" : p.status === "failed" ? "crit" : "muted"}>{p.status}</Badge> },
            { key: "label", header: "Scope", width: "1.4fr", render: (p) => <span className="text-paper">{p.scope.label ?? "—"}</span> },
            { key: "period", header: "Period", width: "1.2fr", render: (p) => (
              <span className="font-mono text-[11.5px] text-paper-dim">
                {p.period_start.slice(0, 10)} → {p.period_end.slice(0, 10)}
              </span>
            ) },
            { key: "hash", header: "Packet hash", width: "180px", render: (p) => p.packet_hash ? <Hash value={p.packet_hash} /> : <span className="text-paper-fade text-[11px]">—</span> },
            { key: "gen", header: "Generated", width: "120px", render: (p) => p.generated_at ? <Timestamp ts={p.generated_at} /> : <span className="text-paper-fade text-[11px]">— pending —</span> }
          ]}
        />
      </Section>

      {ready && (
        <>
          <Hairline tone="display" className="my-10" />
          <Section number="08·3" eyebrow="Preview" title="What the auditor reads">
            <AuditPacketPreview packet={ready} />
            <p className="mt-4 text-[11.5px] text-paper-fade italic max-w-2xl">
              The PDF is rendered server-side via ReportLab; the JSON sidecar is
              ed25519-signed so an auditor can verify the artefact offline using{" "}
              <span className="font-mono text-paper-dim">scripts/verify_audit_packet.py</span>.
            </p>
          </Section>
        </>
      )}

      <Section number="08·4" eyebrow="Records" title="Evidence ledger">
        <DataTable
          rows={evidence}
          columns={[
            { key: "ts", header: "When", width: "120px", render: (e) => <Timestamp ts={e.ts} /> },
            { key: "summary", header: "Summary", width: "2fr", render: (e) => <span className="text-[12.5px] text-paper">{e.summary}</span> },
            { key: "hash", header: "Hash", width: "180px", render: (e) => <Hash value={e.hash} /> },
            { key: "obligations", header: "Obligations", width: "100px", align: "right", render: (e) => <span className="font-mono text-[11.5px] text-paper-dim">{e.obligation_ids.length}</span> }
          ]}
        />
      </Section>
    </div>
  );
}
