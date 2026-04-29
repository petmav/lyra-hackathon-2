"use client";

import { useState } from "react";
import Link from "next/link";
import type { Hook } from "@/lib/api/types";
import { api } from "@/lib/api";
import { Badge } from "@/components/primitives/Badge";
import { StatusDot } from "@/components/primitives/StatusDot";
import { ArrowRight, Loader2, PlayCircle } from "lucide-react";
import { directionLabel, effectRadiusTone } from "@/lib/utils/hooks";

/**
 * Compact row in the hooks directory. Click → /hooks/[id] for full detail.
 * The Test button bypasses the row link and runs `/hooks/{id}:test` inline.
 */
export function HookListRow({ hook, opCount }: { hook: Hook; opCount?: number }) {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; latency_ms: number; resources_count: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onTest = async (event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    if (testing) return;
    setTesting(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.hooks.test(hook.id);
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setTesting(false);
    }
  };

  return (
    <Link
      href={`/hooks/${encodeURIComponent(hook.id)}`}
      className="group block border border-rule hover:border-rule-bright bg-ink-2 hover:bg-ink-3 transition-colors rounded-sm"
    >
      <div className="grid grid-cols-[18px_1.5fr_120px_140px_1fr_92px_24px] items-center gap-3 px-4 py-3">
        <StatusDot
          tone={hookTone(hook)}
          live={hook.health_status === "ok" && hook.enabled}
        />

        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[14px] font-medium text-paper truncate">
              {hook.name}
            </span>
            {!hook.enabled && <Badge tone="warn">disabled</Badge>}
          </div>
          <div className="mt-0.5 font-mono text-[11px] text-paper-fade truncate">
            {hook.id}
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <Badge tone={hook.kind === "mcp" ? "info" : "gold"}>
            {hook.kind === "json_stack" ? "JSON Stack" : hook.kind.toUpperCase()}
          </Badge>
        </div>

        <div className="flex items-center gap-1.5">
          <Badge tone="muted">{directionLabel(hook.direction)}</Badge>
          <Badge tone={effectRadiusTone(hook.effect_radius)}>
            {hook.effect_radius.replace("_", " ")}
          </Badge>
        </div>

        <div className="text-[11.5px] text-paper-fade truncate">
          {opCount !== undefined ? (
            <span><span className="font-mono text-paper-dim">{opCount}</span> operations</span>
          ) : (
            <span className="font-mono text-paper-dim">{hook.scopes.length}</span>
          )}
          {opCount === undefined && <span> scope{hook.scopes.length === 1 ? "" : "s"}</span>}
        </div>

        <button
          type="button"
          onClick={onTest}
          disabled={testing}
          aria-label={`Test ${hook.name}`}
          title={error ?? (result ? `${result.ok ? "ok" : "failed"} · ${result.latency_ms}ms · ${result.resources_count} resources` : "Run /hooks/:id:test")}
          className="inline-flex items-center justify-center gap-1.5 h-7 px-2 border border-rule rounded-sm text-[11.5px] text-paper-dim hover:text-paper hover:border-rule-bright disabled:opacity-50 transition-colors"
        >
          {testing ? (
            <Loader2 size={12} strokeWidth={1.75} className="animate-spin" />
          ) : (
            <PlayCircle size={12} strokeWidth={1.75} />
          )}
          {result ? (
            <span className={result.ok ? "text-ok" : "text-crit"}>
              {result.ok ? `${result.latency_ms}ms` : "fail"}
            </span>
          ) : error ? (
            <span className="text-crit">err</span>
          ) : (
            <span>Test</span>
          )}
        </button>

        <ArrowRight
          size={14}
          strokeWidth={1.75}
          className="text-paper-fade group-hover:text-paper transition-colors"
        />
      </div>
    </Link>
  );
}

function hookTone(h: Hook): "ok" | "warn" | "crit" | "neutral" {
  if (!h.enabled) return "neutral";
  if (h.health_status === "ok") return "ok";
  if (h.health_status === "degraded") return "warn";
  if (h.health_status === "down") return "crit";
  return "ok";
}
