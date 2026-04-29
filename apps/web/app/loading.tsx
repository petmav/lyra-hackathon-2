/** Default route loading state. Quiet — a small mark, never a spinner. */
export default function Loading() {
  return (
    <div className="pt-24 pb-32 flex flex-col items-start gap-3">
      <span className="smallcaps text-paper-fade">retrieving…</span>
      <div className="flex gap-1.5">
        <span className="h-1.5 w-1.5 bg-gold animate-step-pulse" />
        <span className="h-1.5 w-1.5 bg-gold animate-step-pulse" style={{ animationDelay: "150ms" }} />
        <span className="h-1.5 w-1.5 bg-gold animate-step-pulse" style={{ animationDelay: "300ms" }} />
      </div>
    </div>
  );
}
