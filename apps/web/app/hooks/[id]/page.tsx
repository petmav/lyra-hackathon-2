"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { notFound, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import type { Hook, JsonStackManifest } from "@/lib/api/types";
import { PageHeader } from "@/components/shell/PageHeader";
import { Section } from "@/components/primitives/Section";
import { Badge } from "@/components/primitives/Badge";
import { StatusDot } from "@/components/primitives/StatusDot";
import { JsonStackOperations } from "@/components/hook-config/JsonStackOperations";
import { CATEGORY_LABEL, categorizeHook, directionLabel, effectRadiusTone } from "@/lib/utils/hooks";
import { ArrowLeft, Check, Loader2, X } from "lucide-react";

type TestState =
  | { kind: "idle" }
  | { kind: "running" }
  | { kind: "ok"; latency_ms: number; resources_count: number }
  | { kind: "error"; message: string };

export default function HookDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const searchParams = useSearchParams();
  const autoTest = searchParams.get("test") === "1";
  const [hook, setHook] = useState<Hook | null | undefined>(undefined);
  const [manifest, setManifest] = useState<JsonStackManifest | null>(null);
  const [testState, setTestState] = useState<TestState>({ kind: "idle" });

  useEffect(() => {
    let alive = true;
    (async () => {
      const hooks = await api.hooks.list();
      if (!alive) return;
      const found = hooks.find((h) => h.id === id) ?? null;
      setHook(found);
      if (found?.kind === "json_stack") {
        const m = await api.hooks.manifest(found.id);
        if (alive) setManifest(m);
      }
    })();
    return () => { alive = false; };
  }, [id]);

  useEffect(() => {
    if (!autoTest || !hook) return;
    let alive = true;
    (async () => {
      setTestState({ kind: "running" });
      try {
        const r = await api.hooks.test(hook.id);
        if (!alive) return;
        setTestState(r.ok
          ? { kind: "ok", latency_ms: r.latency_ms, resources_count: r.resources_count }
          : { kind: "error", message: "Test reported not-ok" });
      } catch (e) {
        if (!alive) return;
        setTestState({ kind: "error", message: e instanceof Error ? e.message : String(e) });
      }
    })();
    return () => { alive = false; };
  }, [autoTest, hook]);

  if (hook === undefined) {
    return (
      <div className="pt-12 text-center text-[12px] text-paper-fade">Loading hook…</div>
    );
  }
  if (hook === null) return notFound();

  const category = categorizeHook(hook);

  return (
    <div>
      <Link
        href="/hooks"
        className="inline-flex items-center gap-1.5 text-[12px] text-paper-fade hover:text-paper transition-colors mb-3"
      >
        <ArrowLeft size={13} strokeWidth={1.75} />
        Back to hooks
      </Link>

      <PageHeader
        kicker={`${CATEGORY_LABEL[category]} · ${hook.kind === "json_stack" ? "JSON Stack" : hook.kind.toUpperCase()}`}
        title={hook.name}
        subtitle={<span className="font-mono text-paper-dim">{hook.id}</span>}
        aside={
          <div className="flex flex-col items-end gap-2">
            <span className="inline-flex items-center gap-2">
              <StatusDot
                tone={hook.health_status === "ok" ? "ok" : hook.health_status === "degraded" ? "warn" : "neutral"}
                live={hook.enabled && hook.health_status === "ok"}
              />
              <span className="font-mono text-[12px] text-paper">
                {hook.health_status ?? "unknown"}
              </span>
            </span>
            <div className="flex gap-1.5">
              <Badge tone="muted">{directionLabel(hook.direction)}</Badge>
              <Badge tone={effectRadiusTone(hook.effect_radius)}>
                {hook.effect_radius.replace("_", " ")}
              </Badge>
            </div>
          </div>
        }
      />

      {testState.kind !== "idle" && (
        <div
          role="status"
          className={`mt-2 mb-4 flex items-center gap-2 border rounded-sm px-4 py-2 text-[12.5px] ${
            testState.kind === "ok"
              ? "border-ok/40 bg-ok/5 text-ok"
              : testState.kind === "error"
                ? "border-crit/40 bg-crit/5 text-crit"
                : "border-rule bg-ink-2 text-paper-dim"
          }`}
        >
          {testState.kind === "running" && <Loader2 size={13} strokeWidth={1.75} className="animate-spin" />}
          {testState.kind === "ok" && <Check size={13} strokeWidth={1.75} />}
          {testState.kind === "error" && <X size={13} strokeWidth={1.75} />}
          {testState.kind === "running" && <span>Running connectivity test…</span>}
          {testState.kind === "ok" && (
            <span>
              Hook is healthy — <span className="font-mono">{testState.latency_ms}ms</span>, {testState.resources_count} resources reachable.
            </span>
          )}
          {testState.kind === "error" && <span className="font-mono">{testState.message}</span>}
        </div>
      )}

      <Section eyebrow="Configuration" title="Connection">
        <ConnectionPanel hook={hook} manifest={manifest} />
      </Section>

      {hook.kind === "json_stack" && manifest && (
        <Section eyebrow="Operations" title={`${Object.keys(manifest.operations).length} operations`}>
          <JsonStackOperations stackId={hook.id} manifest={manifest} />
        </Section>
      )}

      {hook.kind !== "json_stack" && (
        <Section eyebrow="Capabilities" title="Scopes">
          <div className="flex flex-wrap gap-1.5">
            {hook.scopes.length === 0 ? (
              <span className="text-[12px] text-paper-fade">No scopes declared.</span>
            ) : (
              hook.scopes.map((s) => (
                <Badge key={s} tone="info">{s}</Badge>
              ))
            )}
          </div>
        </Section>
      )}
    </div>
  );
}

function ConnectionPanel({ hook, manifest }: { hook: Hook; manifest: JsonStackManifest | null }) {
  return (
    <div className="border border-rule bg-ink-2 rounded-sm">
      <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4 p-5 text-[13px]">
        <Field label="Endpoint">
          <span className="font-mono text-paper-dim break-all">{hook.endpoint}</span>
        </Field>
        <Field label="Auth ref">
          <span className="font-mono text-paper-fade">{hook.auth_ref || "—"}</span>
        </Field>
        {manifest && (
          <>
            <Field label="Provider">
              <span className="text-paper">{manifest.provider}</span>
            </Field>
            <Field label="Manifest version">
              <span className="font-mono text-paper-dim">{manifest.version}</span>
            </Field>
            <Field label="Base URL">
              <span className="font-mono text-paper-dim break-all">{manifest.base_url}</span>
            </Field>
            <Field label="Auth kind">
              <span className="font-mono text-paper-dim">{manifest.auth.kind}</span>
            </Field>
          </>
        )}
        <Field label="Effect radius">
          <Badge tone={effectRadiusTone(hook.effect_radius)}>
            {hook.effect_radius.replace("_", " ")}
          </Badge>
          {hook.effect_radius !== "internal" && (
            <span className="block mt-1 text-[11.5px] text-paper-fade">
              Outbound calls require upstream <span className="font-mono">gate.human</span> approval.
            </span>
          )}
        </Field>
        <Field label="Direction">
          <Badge tone="muted">{directionLabel(hook.direction)}</Badge>
        </Field>
        {hook.scopes.length > 0 && (
          <Field label="Scopes" wide>
            <div className="flex flex-wrap gap-1.5">
              {hook.scopes.map((s) => (
                <Badge key={s} tone="info">{s}</Badge>
              ))}
            </div>
          </Field>
        )}
      </dl>
    </div>
  );
}

function Field({
  label,
  children,
  wide
}: {
  label: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <div className={wide ? "md:col-span-2" : undefined}>
      <dt className="text-[10.5px] font-medium uppercase tracking-[0.08em] text-paper-fade mb-1">
        {label}
      </dt>
      <dd>{children}</dd>
    </div>
  );
}
