"use client";

import Link from "next/link";
import { cn } from "@/lib/utils/cn";
import type { Finding } from "@/lib/api/types";
import { SeverityBadge } from "@/components/primitives/SeverityBadge";
import { Citation } from "@/components/data/Citation";
import { Confidence } from "@/components/data/Confidence";
import { Urn } from "@/components/data/Urn";
import { Timestamp } from "@/components/data/Timestamp";

/**
 * The Finding card — used on Workflow Run pages, on the Dashboard, and on
 * the Findings list. The visual structure is a "case file" inside a
 * hairline rectangle: title in display, description in body, citations
 * laid out as classical references (Citation component does the typographic
 * heavy lifting), and a residual-confidence meter.
 *
 * `compact` hides the citation list and is used in tight rails.
 */
export function FindingCard({
  finding,
  compact,
  className
}: {
  finding: Finding;
  compact?: boolean;
  className?: string;
}) {
  return (
    <article className={cn("border border-rule p-5", className)}>
      <header className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={finding.severity} confidence={finding.confidence} />
            <Urn urn={finding.urn} />
          </div>
          <h3 className="mt-3 ed-h2 text-paper text-[20px]">
            {finding.title}
          </h3>
        </div>
        <div className="text-right">
          <Confidence value={finding.confidence} />
          <Timestamp ts={finding.created_at} className="mt-2 block" />
        </div>
      </header>
      {!compact && (
        <p className="mt-3 text-[13px] text-paper-dim leading-snug max-w-3xl">
          {finding.description}
        </p>
      )}
      {!compact && finding.documents_cited.length > 0 && (
        <>
          <div className="my-4 h-px bg-rule" />
          <div className="smallcaps mb-3">Citations</div>
          <ol className="flex flex-col gap-3 list-decimal list-inside marker:text-paper-fade marker:font-mono marker:text-[10.5px]">
            {finding.documents_cited.map((raw, i) => {
              const c = normalizeCitation(raw, i);
              return (
              <li key={`${c.document_id}-${c.chunk_ord}`} className="pl-2">
                <Citation
                  framework={frameworkFromTitle(c.document_title)}
                  path={c.citation_path}
                  excerpt={c.excerpt}
                  className="inline-block ml-2"
                />
              </li>
            );})}
          </ol>
        </>
      )}
      {!compact && finding.proposed_change_ids.length > 0 && (
        <div className="mt-4">
          <Link
            href={`/proposed-changes/${finding.proposed_change_ids[0]}`}
            className="text-[12px] text-gold hover:text-gold-bright"
          >
            ↗ Proposed change attached
          </Link>
        </div>
      )}
    </article>
  );
}

function normalizeCitation(citation: unknown, index: number) {
  if (citation && typeof citation === "object") {
    const c = citation as Record<string, unknown>;
    const title = String(c.document_title ?? c.document_id ?? c.citation_path ?? "Document");
    return {
      document_id: String(c.document_id ?? title),
      document_title: title,
      chunk_ord: Number(c.chunk_ord ?? index + 1),
      citation_path: String(c.citation_path ?? title),
      excerpt: typeof c.excerpt === "string" ? c.excerpt : undefined
    };
  }
  const text = String(citation ?? "Document");
  return {
    document_id: text,
    document_title: text,
    chunk_ord: index + 1,
    citation_path: text,
    excerpt: undefined
  };
}

function frameworkFromTitle(value: unknown): string {
  const t = String(value ?? "");
  if (t.includes("GDPR") || t.includes("2016/679")) return "GDPR";
  if (t.includes("ISO")) return "ISO 42001";
  if (t.includes("EU AI") || t.includes("2024/1689")) return "EU AI ACT";
  if (t.includes("OWASP")) return "OWASP";
  if (t.toLowerCase().includes("northwind") || t.toLowerCase().includes("internal")) return "INTERNAL";
  return "DOC";
}
