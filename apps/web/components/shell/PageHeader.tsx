import { cn } from "@/lib/utils/cn";

/**
 * Page header. Title + optional subtitle, kicker, and right-side action.
 * The `number` prop is accepted for API compatibility but no longer rendered.
 */
export function PageHeader({
  number: _number,
  kicker,
  title,
  subtitle,
  aside,
  children,
  className
}: {
  number?: string;
  kicker?: string;
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  aside?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <header className={cn("pb-6 mb-6 border-b border-rule", className)}>
      {kicker && (
        <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-paper-fade mb-2">
          {kicker}
        </div>
      )}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
        <div className="min-w-0 flex-1">
          <h1 className="text-[22px] font-semibold tracking-tight text-paper leading-tight">
            {title}
          </h1>
          {subtitle && (
            <div className="mt-2 text-[13.5px] text-paper-dim leading-relaxed max-w-3xl">
              {subtitle}
            </div>
          )}
        </div>
        {aside && <div className="shrink-0 self-start">{aside}</div>}
      </div>
      {children && <div className="mt-5">{children}</div>}
    </header>
  );
}
