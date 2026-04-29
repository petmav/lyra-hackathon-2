"use client";

import { useMemo, useState } from "react";
import { cn } from "@/lib/utils/cn";
import type { Hook, JsonStackCatalogEntry, JsonStackCategory } from "@/lib/api/types";
import {
  CATEGORY_LABEL,
  CATEGORY_ORDER,
  categorizeHook
} from "@/lib/utils/hooks";
import { HookListRow } from "./HookListRow";

type KindFilter = "all" | "mcp" | "json_stack";

/**
 * Filterable, grouped directory of hooks. Combines configured hooks with
 * the JSON Stack catalog so the operation count can be shown per row.
 */
export function HooksDirectory({
  hooks,
  catalog
}: {
  hooks: Hook[];
  catalog: JsonStackCatalogEntry[];
}) {
  const [kind, setKind] = useState<KindFilter>("all");
  const [category, setCategory] = useState<JsonStackCategory | "all">("all");

  const opCounts = useMemo(() => {
    const m = new Map<string, number>();
    for (const c of catalog) m.set(c.id, c.operations.length);
    return m;
  }, [catalog]);

  const filtered = useMemo(() => {
    return hooks.filter((h) => {
      if (kind !== "all" && h.kind !== kind) return false;
      if (category !== "all" && categorizeHook(h) !== category) return false;
      return true;
    });
  }, [hooks, kind, category]);

  const grouped = useMemo(() => {
    const map = new Map<JsonStackCategory, Hook[]>();
    for (const h of filtered) {
      const c = categorizeHook(h);
      if (!map.has(c)) map.set(c, []);
      map.get(c)!.push(h);
    }
    for (const list of map.values()) list.sort((a, b) => a.name.localeCompare(b.name));
    return CATEGORY_ORDER.filter((c) => map.has(c)).map((c) => ({
      category: c,
      hooks: map.get(c)!
    }));
  }, [filtered]);

  const counts = useMemo(() => {
    const total = hooks.length;
    const mcp = hooks.filter((h) => h.kind === "mcp").length;
    const json = hooks.filter((h) => h.kind === "json_stack").length;
    return { total, mcp, json };
  }, [hooks]);

  const categoryCounts = useMemo(() => {
    const m = new Map<JsonStackCategory, number>();
    for (const h of hooks) {
      const c = categorizeHook(h);
      m.set(c, (m.get(c) ?? 0) + 1);
    }
    return m;
  }, [hooks]);

  return (
    <div>
      <div className="mb-5 flex flex-col gap-3">
        <FilterRow label="Kind">
          <Chip active={kind === "all"} onClick={() => setKind("all")}>
            All <Count>{counts.total}</Count>
          </Chip>
          <Chip active={kind === "mcp"} onClick={() => setKind("mcp")}>
            MCP <Count>{counts.mcp}</Count>
          </Chip>
          <Chip active={kind === "json_stack"} onClick={() => setKind("json_stack")}>
            JSON Stack <Count>{counts.json}</Count>
          </Chip>
        </FilterRow>

        <FilterRow label="Category">
          <Chip active={category === "all"} onClick={() => setCategory("all")}>
            All
          </Chip>
          {CATEGORY_ORDER.map((c) => {
            const n = categoryCounts.get(c) ?? 0;
            if (n === 0) return null;
            return (
              <Chip
                key={c}
                active={category === c}
                onClick={() => setCategory(c)}
              >
                {CATEGORY_LABEL[c]} <Count>{n}</Count>
              </Chip>
            );
          })}
        </FilterRow>
      </div>

      {grouped.length === 0 ? (
        <div className="border border-rule rounded-sm p-8 text-center text-[12px] text-paper-fade">
          No hooks match the current filters.
        </div>
      ) : (
        <div className="space-y-6">
          {grouped.map(({ category: c, hooks: items }) => (
            <div key={c}>
              <div className="mb-2 flex items-baseline gap-2">
                <h3 className="text-[12px] font-medium uppercase tracking-[0.08em] text-paper-fade">
                  {CATEGORY_LABEL[c]}
                </h3>
                <span className="font-mono text-[11px] text-paper-fade">
                  {items.length}
                </span>
              </div>
              <ul className="space-y-1.5">
                {items.map((h) => (
                  <li key={h.id}>
                    <HookListRow hook={h} opCount={opCounts.get(h.id)} />
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function FilterRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 flex-wrap">
      <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-paper-fade min-w-[68px]">
        {label}
      </span>
      <div className="flex items-center gap-1.5 flex-wrap">{children}</div>
    </div>
  );
}

function Chip({
  active,
  onClick,
  children
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "h-7 px-2.5 inline-flex items-center gap-1.5 rounded-sm border text-[12px] transition-colors",
        active
          ? "border-gold text-gold bg-gold/5"
          : "border-rule text-paper-dim hover:text-paper hover:border-rule-bright"
      )}
    >
      {children}
    </button>
  );
}

function Count({ children }: { children: React.ReactNode }) {
  return <span className="font-mono text-[11px] text-paper-fade">{children}</span>;
}
