"use client";

import { Bell, Search } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils/cn";
import { AlertsTray } from "./AlertsTray";

export function Header() {
  const [alertsOpen, setAlertsOpen] = useState(false);
  return (
    <header className="sticky top-0 z-20 flex h-12 items-center justify-between border-b border-rule bg-ink/85 backdrop-blur-md px-6">
      <div className="flex items-center gap-3 text-[12px] text-paper-dim">
        <span className="font-mono tabular-nums text-paper-fade">2026-04-28 · 14:32 UTC</span>
        <span aria-hidden className="h-3 w-px bg-rule" />
        <span>
          <span className="text-paper-fade">Governed assets</span>{" "}
          <span className="font-mono text-paper">11</span>
        </span>
        <span aria-hidden className="h-3 w-px bg-rule" />
        <span>
          <span className="text-paper-fade">Live workflows</span>{" "}
          <span className="font-mono text-paper">1</span>
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
          <span aria-hidden className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-gold" />
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
