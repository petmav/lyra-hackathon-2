import { cn } from "@/lib/utils/cn";

/**
 * Section wrapper. Plain title + optional eyebrow and right-side aside.
 * The `number` prop is accepted for API compatibility but no longer rendered.
 */
export function Section({
  eyebrow,
  number: _number,
  title,
  aside,
  children,
  className
}: {
  eyebrow?: React.ReactNode;
  number?: string;
  title?: React.ReactNode;
  aside?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("mt-10 first:mt-0", className)}>
      {(eyebrow || title || aside) && (
        <header className="mb-4 flex items-end justify-between gap-6">
          <div>
            {eyebrow && (
              <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-paper-fade mb-1.5">
                {eyebrow}
              </div>
            )}
            {title && (
              <h2 className="text-[16px] font-semibold tracking-tight text-paper">{title}</h2>
            )}
          </div>
          {aside && <div className="shrink-0 text-right text-[12px]">{aside}</div>}
        </header>
      )}
      {children}
    </section>
  );
}
