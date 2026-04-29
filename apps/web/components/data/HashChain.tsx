import { cn } from "@/lib/utils/cn";
import { shortHash } from "@/lib/utils/format";

/**
 * Hash-chain renderer — the design's signature element.
 *
 *   ┄┄┄┄┄ a3c5b8d2 ←(prev) → 7f1d8e5c (this)  ┄┄┄┄┄
 *
 * Used beneath each event in the live stream and beneath each row in the
 * audit packet evidence appendix to show that events form an unbroken chain
 * per asset. The chain is visible as 1px ornamental dashes flanking the
 * hash pair; on the very latest event the chain animates in (`live` prop)
 * to make the "chain just extended" moment legible without being noisy.
 */
export function HashChain({
  prev,
  self,
  live,
  className
}: {
  prev: string;
  self: string;
  live?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-2 font-mono text-[10.5px] text-paper-fade",
        className
      )}
      aria-label="hash chain segment"
    >
      <span aria-hidden className="h-px w-3 bg-rule-bright" />
      <span title={prev}>{shortHash(prev, 6, 4)}</span>
      <span aria-hidden className="text-paper-fade">→</span>
      <span title={self} className={cn("text-paper-dim", live && "text-gold")}>
        {shortHash(self, 6, 4)}
      </span>
      <span
        aria-hidden
        className={cn(
          "h-px w-12 bg-rule-bright",
          live && "origin-left animate-hash-pulse !bg-gold"
        )}
      />
    </div>
  );
}
