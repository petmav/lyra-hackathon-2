"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import type { Finding, ProposedChange } from "@/lib/api/types";
import { PageHeader } from "@/components/shell/PageHeader";
import { Section } from "@/components/primitives/Section";
import { ProposedChangeView } from "@/components/proposed-change/ProposedChangeView";
import { FindingCard } from "@/components/finding-card/FindingCard";

/**
 * Proposed change detail page.
 *
 * Shown when a user navigates from a finding card. Renders the diff +
 * sandbox replay battery + approve/reject controls; below it, the parent
 * finding for context. The visual hierarchy here matters: the change is
 * the destination, the finding is the citation.
 */
export default function ProposedChangePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [change, setChange] = useState<ProposedChange | null>(null);
  const [finding, setFinding] = useState<Finding | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api.proposedChanges.get(id).then(async (c) => {
      if (!alive) return;
      setChange(c);
      if (c) {
        const f = await api.findings.get(c.finding_id);
        if (alive) setFinding(f);
      }
      setLoading(false);
    });
    return () => { alive = false; };
  }, [id]);

  if (loading) return <div className="pt-20 text-center text-paper-fade text-[12px] italic">loading change…</div>;
  if (!change) return notFound();

  return (
    <div>
      <PageHeader
        number="03·p"
        kicker={`Proposed change · ${change.kind}`}
        title={<>Apply, after evidence.</>}
        subtitle="Sandbox-tested before approval; applied via outbound hook only after a human (or an explicit policy) signs off."
      />
      <Section number="α" eyebrow="Change" title="Diff · sandbox replays · approval">
        <ProposedChangeView change={change} />
      </Section>
      {finding && (
        <Section number="β" eyebrow="Source" title="Originating finding">
          <Link href={`/findings/${finding.id}`}>
            <FindingCard finding={finding} compact />
          </Link>
        </Section>
      )}
    </div>
  );
}
