import { cn } from "@/lib/utils/cn";

/**
 * A 6px square — not a dot — used as a status indicator throughout.
 * Squares feel auditable; circles feel social. Praetor wants auditable.
 *
 * `live` adds a subtle 1.6s pulse animation for "currently emitting events".
 */
export function StatusDot({
  tone,
  live,
  className
}: {
  tone: "ok" | "warn" | "crit" | "info" | "neutral" | "gold";
  live?: boolean;
  className?: string;
}) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-block h-1.5 w-1.5",
        live && "animate-step-pulse",
        toneBg(tone),
        className
      )}
    />
  );
}

function toneBg(t: "ok" | "warn" | "crit" | "info" | "neutral" | "gold"): string {
  switch (t) {
    case "ok": return "bg-ok";
    case "warn": return "bg-warn";
    case "crit": return "bg-crit";
    case "info": return "bg-info";
    case "gold": return "bg-gold";
    default: return "bg-paper-fade";
  }
}
