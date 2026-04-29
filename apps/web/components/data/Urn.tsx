import { cn } from "@/lib/utils/cn";
import { urnParts } from "@/lib/utils/format";

/**
 * URN renderer styled as an archival "call number" — distinctive Praetor element.
 *
 * `urn:praetor:asset:demo:northwind-support-bot`
 *
 *  →  ┌─ asset ─┐    Pen-stroke separators between the parts:
 *     │  demo   │     a hairline drawn between segments rather than the
 *     └─ slug ──┘     conventional colon. Reads as a shelf-mark.
 *
 * Compact mode renders inline as `kind · tenant · slug` mono with hairline
 * separators (the form used in tables).
 */
export function Urn({
  urn,
  variant = "compact",
  truncate = true,
  className
}: {
  urn: string;
  variant?: "compact" | "stamp";
  truncate?: boolean;
  className?: string;
}) {
  const { kind, tenant, slug } = urnParts(urn);
  if (variant === "stamp") {
    return (
      <div
        className={cn(
          "inline-flex items-stretch border border-rule font-mono text-[11px] leading-none",
          className
        )}
        title={urn}
      >
        <Cell label="kind">{kind}</Cell>
        <div className="w-px bg-rule" />
        <Cell label="tenant">{tenant}</Cell>
        <div className="w-px bg-rule" />
        <Cell label="slug">{truncate ? truncateSlug(slug) : slug}</Cell>
      </div>
    );
  }
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 font-mono text-[11.5px] text-paper-dim",
        className
      )}
      title={urn}
    >
      <span className="text-paper-fade">{kind}</span>
      <span aria-hidden className="h-2.5 w-px bg-rule-bright" />
      <span className="text-paper-fade">{tenant}</span>
      <span aria-hidden className="h-2.5 w-px bg-rule-bright" />
      <span className="text-paper">{truncate ? truncateSlug(slug) : slug}</span>
    </span>
  );
}

function Cell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="px-2 py-1.5">
      <div className="text-[8.5px] uppercase tracking-[0.18em] text-paper-fade leading-none mb-1">
        {label}
      </div>
      <div className="text-paper">{children}</div>
    </div>
  );
}

function truncateSlug(s: string, max = 28) {
  if (s.length <= max) return s;
  return s.slice(0, max - 1) + "…";
}
