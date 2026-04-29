"use client";

import { Hairline } from "@/components/primitives/Hairline";
import type { AuditPacket } from "@/lib/api/types";
import { precise } from "@/lib/utils/time";
import { shortHash } from "@/lib/utils/format";

/**
 * On-screen preview of an audit packet's cover page.
 *
 * Rendered as if the screen were paper: warm paper background, ink type,
 * Fraunces wordmark, tabular numerals, period and scope laid out like a
 * court filing. This makes the demo's "tangible artefact" claim land —
 * the audience sees what the auditor will read, not just a download link.
 */
export function AuditPacketPreview({ packet }: { packet: AuditPacket }) {
  return (
    <div className="overflow-hidden border border-rule">
      <div className="grid lg:grid-cols-[1.1fr_1fr]">
        <div className="relative flex flex-col border-r border-rule bg-paper text-ink p-10 min-h-[560px]">
          {/* paper grain */}
          <div
            aria-hidden
            className="absolute inset-0 pointer-events-none opacity-30 mix-blend-multiply"
            style={{
              backgroundImage:
                "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='1.4' numOctaves='2'/%3E%3CfeColorMatrix values='0 0 0 0 0.16 0 0 0 0 0.14 0 0 0 0 0.10 0 0 0 0.18 0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")"
            }}
          />
          <div className="relative flex flex-1 flex-col">
            <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.22em] text-ink/60">
              <span>Praetor · Audit Packet</span>
              <span>v 1.0 · ed25519</span>
            </div>
            <div className="mt-10">
              <div
                className="ed-display text-[44px] leading-[1.02] tracking-tight text-ink"
                style={{ fontVariationSettings: '"opsz" 144, "wght" 380' }}
              >
                Audit Packet
              </div>
              <div className="ed-display-italic mt-2 text-[19px] text-ink/70">
                {packet.scope.label ?? "compliance evidence"}
              </div>
            </div>
            <div className="mt-12 grid grid-cols-2 gap-x-10 gap-y-4 text-[12px]">
              <Field label="Period">
                <span className="font-mono">{precise(packet.period_start)}</span>
                <span className="block font-mono">→ {precise(packet.period_end)}</span>
              </Field>
              <Field label="Generated">
                {packet.generated_at ? (
                  <span className="font-mono">{precise(packet.generated_at)}</span>
                ) : (
                  <span className="font-mono text-ink/50">— pending —</span>
                )}
              </Field>
              <Field label="Packet hash">
                <span className="font-mono">
                  {packet.packet_hash ? shortHash(packet.packet_hash, 14, 8) : "—"}
                </span>
              </Field>
              <Field label="Pubkey fingerprint">
                <span className="font-mono">{packet.pubkey_fingerprint ?? "—"}</span>
              </Field>
            </div>

            {packet.scope && Object.keys(packet.scope).filter((k) => k !== "label").length > 0 && (
              <div className="mt-8">
                <div className="text-[9.5px] uppercase tracking-[0.22em] text-ink/55 mb-2">Scope detail</div>
                <ul className="space-y-1 text-[11.5px] font-mono text-ink/70">
                  {Object.entries(packet.scope).map(([key, value]) => {
                    if (key === "label") return null;
                    const display = Array.isArray(value)
                      ? value.length === 0 ? "—" : value.join(", ")
                      : String(value ?? "—");
                    return (
                      <li key={key} className="flex gap-3">
                        <span className="text-ink/50 w-32 shrink-0">{key}</span>
                        <span className="text-ink break-all">{display}</span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}

            {packet.counts && (
              <>
                <hr className="my-10 border-ink/15" />
                <div className="grid grid-cols-5 gap-6 text-center">
                  <Stat label="workflow runs" v={packet.counts.workflow_runs} />
                  <Stat label="findings" v={packet.counts.findings} />
                  <Stat label="proposed changes" v={packet.counts.proposed_changes} />
                  <Stat label="supervision" v={packet.counts.supervision_events} />
                  <Stat label="evidence records" v={packet.counts.evidence_records} />
                </div>
              </>
            )}

            <div className="mt-auto pt-12 flex items-end justify-between text-[10px] uppercase tracking-[0.22em] text-ink/60">
              <span>Confidential · Praetor signed</span>
              <span>Page 1 / —</span>
            </div>
          </div>
        </div>

        <aside className="px-6 py-6">
          <div className="smallcaps">Sections in this packet</div>
          <ul className="mt-3 flex flex-col">
            {[
              "Executive summary",
              "Obligation chain — graph",
              "Workflow runs · per-run timeline",
              "Supervision evidence",
              "Hook activity ledger (redacted)",
              "Approval chain",
              "Evidence appendix · hash-chained samples",
              "Signing block"
            ].map((label, i) => (
              <li
                key={label}
                className="grid grid-cols-[36px_1fr] items-baseline gap-2 border-b border-rule py-2"
              >
                <span className="font-mono text-[11px] text-paper-fade tabular-nums">
                  §{String(i + 1).padStart(2, "0")}
                </span>
                <span className="text-[13px] text-paper">{label}</span>
              </li>
            ))}
          </ul>
          <Hairline className="my-5" />
          <p className="text-[11.5px] text-paper-fade italic leading-snug">
            The JSON sidecar accompanying this PDF is signed with ed25519. An
            external verifier can validate the signature without contacting
            Praetor — see <span className="font-mono">scripts/verify_audit_packet.py</span>.
          </p>
        </aside>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[9.5px] uppercase tracking-[0.22em] text-ink/55 mb-1">{label}</div>
      <div className="text-ink">{children}</div>
    </div>
  );
}

function Stat({ label, v }: { label: string; v: number }) {
  return (
    <div>
      <div className="ed-display text-[26px] tabular-nums" style={{ fontVariationSettings: '"opsz" 96, "wght" 360' }}>
        {v}
      </div>
      <div className="text-[9.5px] uppercase tracking-[0.18em] text-ink/55 mt-0.5">{label}</div>
    </div>
  );
}
