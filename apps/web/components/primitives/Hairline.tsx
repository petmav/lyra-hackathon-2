import { cn } from "@/lib/utils/cn";

/**
 * The visual rule-of-the-house. Praetor uses hairlines, not cards or shadows,
 * to delimit data — same logic as a typeset ledger or a printed legal brief.
 *
 * `<Hairline />` — horizontal rule (default 1px var(--rule)).
 * `<Hairline tone="bright" />` — slightly more visible, used to demarcate
 * major sections.
 * `<Hairline tone="display" />` — the gradient rule used as section break,
 * fading at the ends like a printed ornament.
 */
export function Hairline({
  tone = "default",
  className
}: {
  tone?: "default" | "bright" | "display";
  className?: string;
}) {
  if (tone === "display") {
    return <div className={cn("display-rule", className)} role="separator" aria-orientation="horizontal" />;
  }
  return (
    <div
      role="separator"
      aria-orientation="horizontal"
      className={cn("h-px w-full", tone === "bright" ? "bg-rule-bright" : "bg-rule", className)}
    />
  );
}
