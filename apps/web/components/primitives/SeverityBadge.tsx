import { Badge } from "./Badge";
import { cn } from "@/lib/utils/cn";
import type { Severity } from "@/lib/api/types";

const TONE_BY_SEV: Record<Severity, "crit" | "warn" | "info" | "muted"> = {
  critical: "crit",
  high: "crit",
  medium: "warn",
  low: "info",
  info: "muted"
};

/** "high · 0.92 conf" badge — the canonical Praetor severity chip. */
export function SeverityBadge({ severity, confidence, className }: { severity: Severity; confidence?: number; className?: string }) {
  return (
    <Badge tone={TONE_BY_SEV[severity]} className={cn("gap-2", className)}>
      <span>{severity}</span>
      {typeof confidence === "number" && (
        <>
          <span aria-hidden className="opacity-50">·</span>
          <span className="font-mono normal-case tracking-normal">
            {confidence.toFixed(2)}
          </span>
        </>
      )}
    </Badge>
  );
}
