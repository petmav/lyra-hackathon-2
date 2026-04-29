"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { shortHash } from "@/lib/utils/format";

/**
 * Truncated SHA-256 with click-to-copy. Hover surfaces the full hash in a
 * mono-positioned tooltip; that the truncation is visible in the UI is a
 * deliberate feature — auditors can spot when chains have actually been
 * computed vs. zeroed out.
 */
export function Hash({
  value,
  className,
  variant = "default"
}: {
  value: string;
  className?: string;
  variant?: "default" | "muted";
}) {
  const [copied, setCopied] = useState(false);
  const onCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard?.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };
  return (
    <button
      onClick={onCopy}
      title={value}
      className={cn(
        "group inline-flex items-center gap-1 font-mono text-[11px] tabular-nums",
        variant === "muted" ? "text-paper-fade" : "text-paper-dim",
        "hover:text-paper",
        className
      )}
    >
      <span>{shortHash(value, 8, 6)}</span>
      {copied ? (
        <Check size={11} strokeWidth={1.5} className="text-ok" />
      ) : (
        <Copy size={11} strokeWidth={1.5} className="opacity-0 group-hover:opacity-60 transition-opacity" />
      )}
    </button>
  );
}
