"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Hook, HookCall, JsonStackCatalogEntry } from "@/lib/api/types";
import { PageHeader } from "@/components/shell/PageHeader";
import { Section } from "@/components/primitives/Section";
import { HooksDirectory } from "@/components/hook-config/HooksDirectory";
import { HookCalls } from "@/components/hook-config/HookCalls";
import { ArrowUpRight } from "lucide-react";

export default function HooksPage() {
  const [hooks, setHooks] = useState<Hook[]>([]);
  const [calls, setCalls] = useState<HookCall[]>([]);
  const [catalog, setCatalog] = useState<JsonStackCatalogEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    Promise.all([
      api.hooks.list(),
      api.hooks.calls(),
      api.hooks.catalog()
    ]).then(([h, c, cat]) => {
      if (!alive) return;
      setHooks(h);
      setCalls(c);
      setCatalog(cat);
      setLoading(false);
    });
    return () => { alive = false; };
  }, []);

  return (
    <div>
      <PageHeader
        kicker="Knowledge · hooks"
        title="Boundary crossings."
        subtitle="Every hook is hash-chained. Outbound calls with a non-internal effect radius require an upstream gate.human approval. MCP servers and JSON Hook Stack templates share this control plane."
        aside={
          <Link
            href="/hooks/validate"
            className="inline-flex items-center gap-2 border border-rule px-3 py-2 text-[12px] text-paper-dim hover:text-paper hover:border-rule-bright transition-colors rounded-sm"
          >
            Validate manifest
            <ArrowUpRight size={13} strokeWidth={1.75} />
          </Link>
        }
      />

      <Section eyebrow="Registry" title="Configured hooks">
        {loading ? (
          <div className="border border-rule rounded-sm p-8 text-center text-[12px] text-paper-fade">
            Loading hooks…
          </div>
        ) : (
          <HooksDirectory hooks={hooks} catalog={catalog} />
        )}
      </Section>

      <Section eyebrow="Ledger" title="Recent calls">
        <HookCalls calls={calls} />
      </Section>
    </div>
  );
}
