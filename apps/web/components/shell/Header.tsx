"use client";

import { Bell, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils/cn";
import { api } from "@/lib/api";
import { AlertsTray } from "./AlertsTray";

const REFRESH_MS = 30_000;
const CLOCK_MS = 1_000;

function formatClock(date: Date): string {
  const yyyy = date.getUTCFullYear();
  const mm = String(date.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(date.getUTCDate()).padStart(2, "0");
  const hh = String(date.getUTCHours()).padStart(2, "0");
  const min = String(date.getUTCMinutes()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd} · ${hh}:${min} UTC`;
}

export function Header() {
  const [alertsOpen, setAlertsOpen] = useState(false);
  const [now, setNow] = useState<string | null>(null);
  const [stats, setStats] = useState<{ assets: number; live: number; alerts: number } | null>(null);

  // Tick the clock every second after mount (avoids SSR/CSR mismatch).
  useEffect(() => {
    setNow(formatClock(new Date()));
    const interval = setInterval(() => setNow(formatClock(new Date())), CLOCK_MS);
    return () => clearInterval(interval);
  }, []);

  // Pull live counts from the API. Refresh on a slow interval so navigations
  // don't spam the backend; pages that change these counts (e.g. running a
  // workflow) will see the change within REFRESH_MS or after a hard nav.
  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const [assets, runs, alerts] = await Promise.all([
          api.assets.list().catch(() => []),
          api.workflowRuns.list().catch(() => []),
          api.alerts.list().catch(() => [])
        ]);
        if (!alive) return;
        const live = runs.filter((r) => r.status === "running" || r.status === "awaiting_approval").length;
        setStats({ assets: assets.length, live, alerts: alerts.length });
      } catch {
        // ignore — stats stay null and the chips render as em-dashes
      }
    };
    void load();
    const interval = setInterval(load, REFRESH_MS);
    return () => {
      alive = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <header className="sticky top-0 z-20 flex h-12 items-center justify-between border-b border-rule bg-ink/85 backdrop-blur-md px-6">
      <div className="flex items-center gap-3 text-[12px] text-paper-dim">
        <span className="font-mono tabular-nums text-paper-fade min-w-[160px]" suppressHydrationWarning>
          {now ?? "—"}
        </span>
        <span aria-hidden className="h-3 w-px bg-rule" />
        <span>
          <span className="text-paper-fade">Governed assets</span>{" "}
          <span className="font-mono text-paper tabular-nums">{stats ? stats.assets : "—"}</span>
        </span>
        <span aria-hidden className="h-3 w-px bg-rule" />
        <span>
          <span className="text-paper-fade">Live workflows</span>{" "}
          <span className="font-mono text-paper tabular-nums">{stats ? stats.live : "—"}</span>
        </span>
      </div>
      <div className="flex items-center gap-2">
        <button
          aria-label="Search"
          className="flex h-8 items-center gap-2 border border-rule px-2.5 text-[12px] text-paper-fade hover:text-paper hover:border-rule-bright transition-colors rounded-sm"
        >
          <Search size={13} strokeWidth={1.75} />
          <span className="hidden sm:inline">Search</span>
          <span className="hidden sm:inline font-mono text-paper-fade ml-2">⌘K</span>
        </button>
        <button
          aria-label="Open alerts"
          onClick={() => setAlertsOpen((v) => !v)}
          className={cn(
            "relative flex h-8 w-8 items-center justify-center border transition-colors rounded-sm",
            alertsOpen
              ? "border-gold text-gold"
              : "border-rule text-paper-dim hover:text-paper hover:border-rule-bright"
          )}
        >
          <Bell size={14} strokeWidth={1.75} />
          {stats && stats.alerts > 0 && (
            <span aria-hidden className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-gold" />
          )}
        </button>
        <div className="ml-1 flex items-center gap-2 text-[12px]">
          <span aria-hidden className="h-7 w-7 border border-rule grid place-items-center text-paper-dim font-mono text-[11px] rounded-sm">
            CL
          </span>
          <span className="hidden md:inline text-paper-dim">compliance.lead@northwind.health</span>
        </div>
      </div>
      <AlertsTray open={alertsOpen} onClose={() => setAlertsOpen(false)} />
    </header>
  );
}
