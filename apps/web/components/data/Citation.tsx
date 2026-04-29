import { cn } from "@/lib/utils/cn";
import { Badge } from "@/components/primitives/Badge";

/**
 * Citation chip — used in Findings, EvidenceRecords, and corpus search results.
 *
 *   [GDPR] Article 5 / Paragraph 1 / Point (c)
 *   [ISO 42001] Clause 8 / 8.3 Operational planning and control
 *
 * The framework lives in a small uppercase badge; the citation path is in
 * Fraunces italic to read as a printed-citation reference.
 */
export function Citation({
  framework,
  path,
  excerpt,
  className
}: {
  framework: string;
  path: string;
  excerpt?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <div className="flex items-baseline gap-2">
        <Badge tone="gold" className="shrink-0">{framework}</Badge>
        <span className="ed-display-italic text-paper text-[14px]">{path}</span>
      </div>
      {excerpt && (
        <blockquote className="border-l border-rule-bright pl-3 text-[12.5px] leading-snug text-paper-dim italic">
          “{excerpt}”
        </blockquote>
      )}
    </div>
  );
}
