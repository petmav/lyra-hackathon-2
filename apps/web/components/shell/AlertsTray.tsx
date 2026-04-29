"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils/cn";
import { api } from "@/lib/api";
import type { Alert } from "@/lib/api/types";
import { StatusDot } from "@/components/primitives/StatusDot";
import { Timestamp } from "@/components/data/Timestamp";

/**
 * The alerts tray is a slide-out from the top header. Renders findings,
 * supervision violations, pending approvals, and system events — all
 * surfaced from the same shared `events` stream behind the scenes.
 */
export function AlertsTray({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  useEffect(() => {
    api.alerts.list().then(setAlerts);
  }, []);
  return (
    <>
      <div
        aria-hidden={!open}
        onClick={onClose}
        className={cn(
          "fixed inset-0 z-30 bg-black/40 transition-opacity",
          open ? "opacity-100" : "pointer-events-none opacity-0"
        )}
      />
      <aside
        className={cn(
          "fixed right-0 top-12 z-40 w-[420px] max-w-[100vw] border-l border-b border-rule bg-ink-2",
          "transition-transform duration-300 ease-[cubic-bezier(0.2,0.8,0.2,1)] origin-top",
          open ? "translate-y-0" : "-translate-y-2 opacity-0 pointer-events-none"
        )}
      >
        <header className="flex items-center justify-between border-b border-rule px-5 py-3">
          <div>
            <div className="smallcaps">Live tray</div>
            <div className="ed-h2 text-paper text-[18px] mt-0.5">Findings · Approvals · Events</div>
          </div>
          <span className="font-mono text-[11px] text-paper-fade">{alerts.length}</span>
        </header>
        <ul className="max-h-[60vh] overflow-y-auto">
          {alerts.map((a) => (
            <li key={a.id} className="border-b border-rule">
              <Link
                href={a.href ?? "#"}
                onClick={onClose}
                className="block px-5 py-4 transition-colors hover:bg-ink-3"
              >
                <div className="flex items-start gap-3">
                  <StatusDot tone={toneFor(a)} live={a.kind === "approval"} className="mt-1.5" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="text-[13px] text-paper truncate">{a.title}</span>
                      <Timestamp ts={a.ts} />
                    </div>
                    <div className="mt-1 text-[12px] text-paper-fade leading-snug">{a.detail}</div>
                  </div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      </aside>
    </>
  );
}

function toneFor(a: Alert): "ok" | "warn" | "crit" | "info" | "gold" {
  if (a.kind === "approval") return "gold";
  if (a.severity === "critical" || a.severity === "high") return "crit";
  if (a.severity === "medium") return "warn";
  if (a.severity === "info") return "info";
  return "info";
}
