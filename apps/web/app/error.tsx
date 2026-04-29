"use client";

import Link from "next/link";

/** Error boundary. Same editorial treatment as 404. */
export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="praetor-stagger pt-32 max-w-2xl">
      <div className="smallcaps text-crit">500 · runtime fault</div>
      <h1
        className="ed-display mt-4 text-[80px] leading-none text-paper"
        style={{ fontVariationSettings: '"opsz" 144, "wght" 320' }}
      >
        Something hit the floor.
      </h1>
      <pre className="mt-6 border-l-2 border-crit/60 pl-3 font-mono text-[12px] text-paper-dim whitespace-pre-wrap">
        {error.message}
      </pre>
      <div className="mt-8 flex items-center gap-3">
        <button
          onClick={reset}
          className="border border-gold px-3 py-2 text-[11px] uppercase tracking-[0.16em] text-gold hover:bg-gold hover:text-ink"
        >
          retry
        </button>
        <Link
          href="/"
          className="border border-rule px-3 py-2 text-[11px] uppercase tracking-[0.16em] text-paper-dim hover:text-paper hover:border-rule-bright"
        >
          dashboard
        </Link>
      </div>
    </div>
  );
}
