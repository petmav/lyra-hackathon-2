"use client";

import { cn } from "@/lib/utils/cn";
import { useState } from "react";

interface TabSpec {
  id: string;
  label: string;
  badge?: React.ReactNode;
}

/**
 * Editorial-style tabs: a row of small-caps labels with a 1px gold underline
 * marking the active tab. Lives uncontrolled by default; pass `value` and
 * `onChange` to control externally.
 */
export function Tabs({
  tabs,
  value,
  onChange,
  defaultValue,
  className,
  children
}: {
  tabs: TabSpec[];
  value?: string;
  onChange?: (id: string) => void;
  defaultValue?: string;
  className?: string;
  children?: (active: string) => React.ReactNode;
}) {
  const [internal, setInternal] = useState(defaultValue ?? tabs[0]?.id);
  const active = value ?? internal;
  const setActive = (id: string) => {
    setInternal(id);
    onChange?.(id);
  };

  return (
    <div className={cn("flex flex-col", className)}>
      <div role="tablist" className="flex items-end gap-6 border-b border-rule">
        {tabs.map((t) => {
          const isActive = t.id === active;
          return (
            <button
              key={t.id}
              role="tab"
              aria-selected={isActive}
              onClick={() => setActive(t.id)}
              className={cn(
                "relative -mb-px py-2 text-[11px] uppercase tracking-[0.14em] transition-colors",
                isActive ? "text-paper" : "text-paper-fade hover:text-paper-dim"
              )}
            >
              <span className="flex items-center gap-2">
                {t.label}
                {t.badge}
              </span>
              {isActive && (
                <span aria-hidden className="absolute inset-x-0 -bottom-px h-px bg-gold" />
              )}
            </button>
          );
        })}
      </div>
      {children && <div className="pt-4">{children(active)}</div>}
    </div>
  );
}
