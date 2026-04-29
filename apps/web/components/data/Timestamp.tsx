"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils/cn";
import { friendly, precise, relative, timecode } from "@/lib/utils/time";

type Mode = "relative" | "precise" | "timecode" | "friendly";

/**
 * Timestamp renderer that ticks. Defaults to relative ("23s ago") and
 * re-renders every 30s so the "freshness" of a row stays accurate without
 * the page noticeably moving. Hover reveals the precise timestamp.
 */
export function Timestamp({
  ts,
  mode = "relative",
  className
}: {
  ts: string;
  mode?: Mode;
  className?: string;
}) {
  const [, setTick] = useState(0);
  useEffect(() => {
    if (mode !== "relative") return;
    const id = setInterval(() => setTick((t) => t + 1), 30_000);
    return () => clearInterval(id);
  }, [mode]);
  const text =
    mode === "precise"
      ? precise(ts)
      : mode === "timecode"
        ? timecode(ts)
        : mode === "friendly"
          ? friendly(ts)
          : relative(ts);
  return (
    <time
      title={precise(ts)}
      dateTime={ts}
      className={cn("font-mono text-[11px] tabular-nums text-paper-fade", className)}
    >
      {text}
    </time>
  );
}
