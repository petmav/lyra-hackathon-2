"use client";

import { use, useEffect, useState } from "react";
import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import type { Finding, ProposedChange } from "@/lib/api/types";
import { PageHeader } from "@/components/shell/PageHeader";
import { Section } from "@/components/primitives/Section";
import { FindingCard } from "@/components/finding-card/FindingCard";
import { ProposedChangeView } from "@/components/proposed-change/ProposedChangeView";

/**
 * Finding detail. Renders the FindingCard at full width, then the attached
 * proposed-change view beneath it. This is the page that anchors the
 * approve-the-patch beat in the demo flow.
 */
export default function FindingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [finding, setFinding] = useState<Finding | null>(null);
  const [proposals, setProposals] = useState<ProposedChange[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    Promise.all([api.findings.get(id), api.proposedChanges.list()]).then(async ([f, all]) => {
      if (!alive) return;
      setFinding(f);
      const attached = all.filter((p) => p.finding_id === id || (f && p.finding_id === f.id));
      if (attached.length === 0 && f?.proposed_change_ids.length) {
        const fetched = await Promise.all(f.proposed_change_ids.map((proposalId) => api.proposedChanges.get(proposalId)));
        if (alive) setProposals(fetched.filter((p): p is ProposedChange => Boolean(p)));
      } else {
        setProposals(attached);
      }
      setLoading(false);
    });
    return () => { alive = false; };
  }, [id]);

  if (loading) return <div className="pt-20 text-center text-paper-fade text-[12px] italic">loading finding…</div>;
  if (!finding) return notFound();

  return (
    <div>
      <PageHeader
        number="03·f"
        kicker={`Finding · ${finding.severity}`}
        title={finding.title}
      />
      <Section number="α" eyebrow="Case file" title="Finding">
        <FindingCard finding={finding} />
      </Section>
      {proposals.map((p) => (
        <Section key={p.id} number="β" eyebrow="Remediation" title="Proposed change">
          <ProposedChangeView change={p} />
        </Section>
      ))}
    </div>
  );
}
