import Link from "next/link";

/** 404. Set into the editorial type system rather than as an apology. */
export default function NotFound() {
  return (
    <div className="praetor-stagger pt-32 max-w-2xl">
      <div className="smallcaps">404 · not on file</div>
      <h1
        className="ed-display mt-4 text-[112px] leading-none tabular-nums text-paper"
        style={{ fontVariationSettings: '"opsz" 144, "wght" 320' }}
      >
        404
      </h1>
      <p className="ed-display-italic mt-2 text-[28px] text-paper-dim">
        No record matches that URN.
      </p>
      <p className="mt-6 max-w-lg text-[14px] text-paper-fade leading-relaxed">
        Praetor only displays entities that exist in its catalogue. If you
        followed a link from an audit packet, this slug may have been
        archived or never existed.
      </p>
      <div className="mt-8 flex items-center gap-3 text-[12px]">
        <Link
          href="/"
          className="inline-flex items-center gap-2 border border-rule px-3 py-2 uppercase tracking-[0.16em] text-paper-dim hover:text-paper hover:border-rule-bright"
        >
          ← Dashboard
        </Link>
        <Link
          href="/inventory"
          className="inline-flex items-center gap-2 border border-rule px-3 py-2 uppercase tracking-[0.16em] text-paper-dim hover:text-paper hover:border-rule-bright"
        >
          Inventory
        </Link>
      </div>
    </div>
  );
}
