import { cn } from "@/lib/utils/cn";

/**
 * Confidence renderer — small horizontal meter + numeric.
 *
 *   ▌▌▌▌▌▌▌▌▌░░  0.92
 *
 * Eleven cells (0..10) so the boundary at the conventional "needs-review"
 * threshold (0.6) lines up cleanly. Cells past the value are hairline-only;
 * cells up to the value are filled in gold (high), warn (medium), or
 * paper-fade (low).
 */
export function Confidence({
  value,
  showNumeric = true,
  className
}: {
  value: number;
  showNumeric?: boolean;
  className?: string;
}) {
  const filled = Math.round(Math.min(1, Math.max(0, value)) * 10);
  const tone = value >= 0.85 ? "bg-gold" : value >= 0.6 ? "bg-warn" : "bg-paper-fade";
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <span aria-hidden className="flex h-2.5 items-stretch gap-[2px]">
        {Array.from({ length: 11 }).map((_, i) => (
          <span
            key={i}
            className={cn(
              "w-[3px]",
              i < filled ? tone : "border border-rule-bright bg-transparent"
            )}
          />
        ))}
      </span>
      {showNumeric && (
        <span className="font-mono text-[11px] tabular-nums text-paper-dim">
          {value.toFixed(2)}
        </span>
      )}
    </span>
  );
}
