import { forwardRef } from "react";
import { cn } from "@/lib/utils/cn";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

/**
 * A flat, slightly cramped button. No rounded corners (squared off matches
 * the editorial-archive aesthetic). Primary variant uses the gold accent
 * sparingly — only for the singular CTA on a page.
 */
export const Button = forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }>(function Button(
  { variant = "secondary", size = "md", className, children, ...rest },
  ref
) {
  return (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center gap-2 border px-3 font-medium uppercase tracking-[0.12em] transition-colors disabled:opacity-50 disabled:cursor-not-allowed",
        size === "sm" ? "h-7 text-[11px]" : "h-9 text-[12px]",
        variantClass(variant),
        className
      )}
      {...rest}
    >
      {children}
    </button>
  );
});

function variantClass(v: Variant) {
  switch (v) {
    case "primary":
      return "border-gold bg-gold text-ink hover:bg-gold-bright hover:border-gold-bright";
    case "danger":
      return "border-crit/70 text-crit hover:bg-crit/10";
    case "ghost":
      return "border-transparent text-paper-dim hover:text-paper hover:border-rule";
    default:
      return "border-rule text-paper hover:border-rule-bright hover:bg-ink-2";
  }
}
