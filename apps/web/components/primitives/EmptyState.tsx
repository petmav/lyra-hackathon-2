/**
 * Used sparingly — the demo seeds enough data that empty states are rare.
 * When shown, the tone is institutional and quiet, not encouraging.
 */
export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="border border-rule px-8 py-16 text-center">
      <div className="ed-h2 text-paper-dim mb-2">{title}</div>
      {hint && <div className="text-[12px] text-paper-fade max-w-md mx-auto">{hint}</div>}
    </div>
  );
}
