import { cn } from "@/lib/utils/cn";

/**
 * A flat, no-shadow badge. Variants encode meaning, not decoration.
 *
 * Default rendering: small-caps label inside a 1px hairline rectangle.
 * The padding is deliberately tighter on top/bottom than left/right —
 * that ratio reads as "metadata" rather than "button".
 */
export function Badge({
  children,
  tone = "neutral",
  className
}: {
  children: React.ReactNode;
  tone?: "neutral" | "gold" | "ok" | "warn" | "crit" | "info" | "muted";
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-1.5 py-0.5 text-[10.5px] font-medium uppercase tracking-[0.14em]",
        "border",
        toneClass(tone),
        className
      )}
    >
      {children}
    </span>
  );
}

function toneClass(t: "neutral" | "gold" | "ok" | "warn" | "crit" | "info" | "muted"): string {
  switch (t) {
    case "gold":
      return "border-gold/60 text-gold-bright";
    case "ok":
      return "border-ok/60 text-ok";
    case "warn":
      return "border-warn/60 text-warn";
    case "crit":
      return "border-crit/60 text-crit";
    case "info":
      return "border-info/60 text-info";
    case "muted":
      return "border-rule text-paper-fade";
    default:
      return "border-rule text-paper-dim";
  }
}
