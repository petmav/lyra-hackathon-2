"use client";

import { useState } from "react";
import { Button } from "@/components/primitives/Button";
import { Hairline } from "@/components/primitives/Hairline";
import { api } from "@/lib/api";
import type { AuditPacket } from "@/lib/api/types";

/**
 * Audit packet builder — pick a period and a scope, hit Generate, watch the
 * row appear in the packet ledger as `generating` then `ready`.
 *
 * In hackathon scope the generation is mocked at the API layer. The visual
 * intent is to make the act of producing an auditable artefact feel
 * deliberate: the form is laid out like a court-filing cover sheet rather
 * than a SaaS modal.
 */
export function AuditPacketBuilder({ onCreated }: { onCreated?: (p: { packet_id: string; status: AuditPacket["status"] }) => void }) {
  const [period, setPeriod] = useState<"7d" | "14d" | "30d" | "90d">("7d");
  const [scope, setScope] = useState<"all" | "workflow_only" | "supervision_only">("all");
  const [busy, setBusy] = useState(false);

  const onGenerate = async () => {
    setBusy(true);
    const r = await api.auditPackets.generate({ label: scope === "all" ? `${period} · all surfaces` : `${period} · ${scope}` });
    setBusy(false);
    onCreated?.(r);
  };

  return (
    <div className="border border-rule">
      <header className="border-b border-rule px-5 py-3 flex items-end justify-between gap-4">
        <div>
          <div className="smallcaps">Filing · cover sheet</div>
          <h3 className="mt-1 ed-h2 text-paper text-[18px]">Generate Audit Packet</h3>
        </div>
        <span className="font-mono text-[10.5px] text-paper-fade">
          ed25519-signed · JSON sidecar · server-rendered PDF
        </span>
      </header>
      <div className="grid gap-6 px-5 py-5 md:grid-cols-2">
        <Field label="Period">
          <div className="grid grid-cols-4 gap-1">
            {(["7d", "14d", "30d", "90d"] as const).map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`border py-1.5 text-[11.5px] uppercase tracking-[0.14em] ${
                  period === p ? "border-gold text-gold" : "border-rule text-paper-dim hover:text-paper"
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        </Field>
        <Field label="Scope">
          <div className="grid grid-cols-3 gap-1">
            {(
              [
                ["all", "Both surfaces"],
                ["workflow_only", "Workflows"],
                ["supervision_only", "Supervision"]
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                onClick={() => setScope(id)}
                className={`border py-1.5 text-[11.5px] uppercase tracking-[0.14em] ${
                  scope === id ? "border-gold text-gold" : "border-rule text-paper-dim hover:text-paper"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </Field>
      </div>
      <Hairline />
      <div className="flex items-center justify-between gap-4 px-5 py-4">
        <div className="text-[11.5px] text-paper-fade italic max-w-md">
          The packet covers workflow runs, findings, proposed changes, supervision
          evidence, hook activity, the approval chain, and the obligation graph
          for the selected window — both surfaces, one document.
        </div>
        <Button variant="primary" onClick={onGenerate} disabled={busy}>
          {busy ? "queuing…" : "generate packet"}
        </Button>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="smallcaps mb-2">{label}</div>
      {children}
    </div>
  );
}
