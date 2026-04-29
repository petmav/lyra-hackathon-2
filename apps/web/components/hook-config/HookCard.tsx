"use client";

import { useState } from "react";
import { cn } from "@/lib/utils/cn";
import type { Hook } from "@/lib/api/types";
import { Badge } from "@/components/primitives/Badge";
import { StatusDot } from "@/components/primitives/StatusDot";
import { Button } from "@/components/primitives/Button";
import { Urn } from "@/components/data/Urn";
import { Timestamp } from "@/components/data/Timestamp";
import { api } from "@/lib/api";
import { Check, X } from "lucide-react";

/**
 * Hook card — the registry display unit.
 *
 * Shows kind, direction, scopes, effect_radius. The "test" button hits
 * `POST /hooks/{id}:test` and surfaces a small inline result (resources
 * count + latency). Effect-radius is rendered as a typographic warning
 * when external_*: outbound calls without an upstream approval will be
 * gated by `praetor.controls.hook_out_gate`.
 */
export function HookCard({ hook }: { hook: Hook }) {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; resources_count: number; latency_ms: number } | null>(null);

  const onTest = async () => {
    setTesting(true);
    setTestResult(null);
    const r = await api.hooks.test(hook.id);
    setTestResult(r);
    setTesting(false);
  };

  return (
    <div className="border border-rule px-5 py-4">
      <div className="flex items-start justify-between gap-6">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <StatusDot tone={hookTone(hook)} live={hook.health_status === "ok" && hook.enabled} />
            <span className="ed-h3 text-paper">{hook.name}</span>
            <Badge tone="muted">{hook.kind}</Badge>
            <Badge tone="muted">{hook.direction}</Badge>
            {!hook.enabled && <Badge tone="warn">disabled</Badge>}
          </div>
          <div className="mt-2"><Urn urn={hook.urn} /></div>
        </div>
        <div className="text-right">
          <Button size="sm" variant="ghost" onClick={onTest} disabled={testing}>
            {testing ? "testing…" : "test"}
          </Button>
          {testResult && (
            <div className={cn(
              "mt-2 inline-flex items-center gap-1 font-mono text-[11px]",
              testResult.ok ? "text-ok" : "text-crit"
            )}>
              {testResult.ok ? <Check size={11} /> : <X size={11} />}
              {testResult.resources_count} resources · {testResult.latency_ms}ms
            </div>
          )}
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 text-[12px]">
        <Field label="Endpoint">
          <span className="font-mono text-paper-dim break-all">{hook.endpoint}</span>
        </Field>
        <Field label="Auth ref">
          <span className="font-mono text-paper-fade">{hook.auth_ref}</span>
        </Field>
        <Field label="Scopes">
          <div className="flex flex-wrap gap-1.5">
            {hook.scopes.map((s) => (
              <Badge tone="info" key={s}>{s}</Badge>
            ))}
          </div>
        </Field>
        <Field label="Effect radius">
          <span className={cn(
            "font-mono text-[12px]",
            hook.effect_radius === "internal" ? "text-paper-dim" :
            hook.effect_radius === "external_trusted" ? "text-warn" : "text-crit"
          )}>{hook.effect_radius}</span>
          {hook.effect_radius !== "internal" && (
            <span className="block mt-0.5 text-[10.5px] text-paper-fade italic">
              outbound calls require upstream gate.human approval
            </span>
          )}
        </Field>
        <Field label="Last health check">
          {hook.last_health_check ? <Timestamp ts={hook.last_health_check} /> : <span className="text-paper-fade">—</span>}
        </Field>
        <Field label="Status">
          <span className={cn(
            "font-mono text-[12px] uppercase tracking-[0.12em]",
            hook.health_status === "ok" ? "text-ok" :
            hook.health_status === "degraded" ? "text-warn" : "text-crit"
          )}>{hook.health_status ?? "unknown"}</span>
        </Field>
      </dl>
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

function hookTone(h: Hook): "ok" | "warn" | "crit" | "neutral" {
  if (!h.enabled) return "neutral";
  if (h.health_status === "ok") return "ok";
  if (h.health_status === "degraded") return "warn";
  if (h.health_status === "down") return "crit";
  return "neutral";
}
