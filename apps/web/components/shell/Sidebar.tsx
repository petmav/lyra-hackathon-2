"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Boxes,
  Files,
  Gavel,
  GitBranch,
  Layers,
  LayoutGrid,
  Network,
  Plug,
  ShieldCheck,
  Workflow
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils/cn";

const NAV: { href: string; label: string; group: "instrumentation" | "workflows" | "knowledge" | "audit"; icon: LucideIcon }[] = [
  { href: "/", label: "Dashboard", group: "instrumentation", icon: LayoutGrid },
  { href: "/inventory", label: "Inventory", group: "instrumentation", icon: Boxes },
  { href: "/workflows", label: "Workflows", group: "workflows", icon: Workflow },
  { href: "/sandbox", label: "Sandbox", group: "workflows", icon: Layers },
  { href: "/corpora", label: "Corpora", group: "knowledge", icon: Files },
  { href: "/obligations", label: "Obligations", group: "knowledge", icon: Network },
  { href: "/hooks", label: "Hooks", group: "knowledge", icon: Plug },
  { href: "/evidence", label: "Evidence", group: "audit", icon: ShieldCheck }
];

const GROUP_LABELS: Record<typeof NAV[number]["group"], string> = {
  instrumentation: "Overview",
  workflows: "Workflows",
  knowledge: "Knowledge",
  audit: "Audit"
};

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="sticky top-0 z-30 flex w-full flex-col border-b border-rule bg-ink md:fixed md:left-0 md:top-0 md:h-screen md:w-[224px] md:border-b-0 md:border-r">
      <div className="flex items-center gap-2.5 border-b border-rule px-4 py-3 md:px-5 md:py-5">
        <Link href="/" aria-label="Praetor home" className="flex items-center gap-2.5">
          <span aria-hidden className="block h-2.5 w-2.5 bg-gold" />
          <span className="text-[15px] font-semibold tracking-tight text-paper">Praetor</span>
        </Link>
      </div>

      <nav className="flex gap-3 overflow-x-auto px-3 py-2 md:flex-1 md:flex-col md:gap-0 md:overflow-x-visible md:overflow-y-auto md:py-5">
        <NavGroup group="instrumentation" pathname={pathname} />
        <NavGroup group="workflows" pathname={pathname} />
        <NavGroup group="knowledge" pathname={pathname} />
        <NavGroup group="audit" pathname={pathname} />
      </nav>

      <div className="hidden border-t border-rule px-5 py-3 text-[11px] md:block">
        <div className="flex items-center justify-between text-paper-fade">
          <span>Tenant</span>
          <span className="font-mono text-paper-dim">demo</span>
        </div>
        <div className="mt-1 flex items-center justify-between text-paper-fade">
          <span>Build</span>
          <span className="font-mono text-paper-dim">2026.04.28-α</span>
        </div>
      </div>
    </aside>
  );
}

function NavGroup({ group, pathname }: { group: typeof NAV[number]["group"]; pathname: string }) {
  const items = NAV.filter((n) => n.group === group);
  return (
    <div className="shrink-0 md:mb-5">
      <div className="hidden px-2 mb-1.5 text-[10.5px] font-medium uppercase tracking-[0.08em] text-paper-fade md:block">
        {GROUP_LABELS[group]}
      </div>
      <ul className="flex gap-1 md:block">
        {items.map((item) => {
          const active = item.href === "/"
            ? pathname === "/"
            : pathname === item.href || pathname.startsWith(item.href + "/");
          const Icon = item.icon;
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                className={cn(
                  "group flex items-center gap-2.5 px-2 py-1.5 text-[13px] transition-colors rounded-sm",
                  active
                    ? "bg-ink-2 text-paper"
                    : "text-paper-dim hover:text-paper hover:bg-ink-2"
                )}
              >
                <Icon
                  size={14}
                  strokeWidth={1.75}
                  className={cn(active ? "text-gold" : "text-paper-fade group-hover:text-paper-dim")}
                />
                <span>{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
