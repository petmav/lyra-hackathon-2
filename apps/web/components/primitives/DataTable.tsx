import { cn } from "@/lib/utils/cn";
import Link from "next/link";

/**
 * A ledger-style data table.
 *
 * - 1px hairline rules between rows (no zebra striping).
 * - Column headers are small-caps, paper-fade, never bold.
 * - Numerics tabular-nums by default (set on the html root in globals.css).
 * - Each row can have an `href` to make the entire row a link.
 *
 * Columns are declared as `{ key, header, render?, align?, width? }`.
 */
export interface Column<T> {
  key: string;
  header: React.ReactNode;
  render: (row: T) => React.ReactNode;
  align?: "left" | "right" | "center";
  width?: string;
  className?: string;
}

export function DataTable<T extends { id?: string }>({
  rows,
  columns,
  rowHref,
  empty,
  className
}: {
  rows: T[];
  columns: Column<T>[];
  rowHref?: (row: T) => string | undefined;
  empty?: React.ReactNode;
  className?: string;
}) {
  if (rows.length === 0) {
    return (
      <div className="border border-rule px-6 py-12 text-center">
        <div className="smallcaps text-paper-fade">{empty ?? "No records."}</div>
      </div>
    );
  }
  return (
    <div className={cn("w-full", className)}>
      <ul className="md:hidden" role="rowgroup">
        {rows.map((row, i) => {
          const href = rowHref?.(row);
          const inner = (
            <div role="row" className="border-b border-rule px-2 py-3">
              {columns.map((c) => (
                <div key={c.key} className="grid grid-cols-[112px_1fr] gap-3 py-1">
                  <div className="smallcaps text-paper-fade">{c.header}</div>
                  <div className={cn("min-w-0 text-[12.5px]", c.align === "right" && "text-right")}>
                    {c.render(row)}
                  </div>
                </div>
              ))}
            </div>
          );
          return (
            <li key={row.id ?? i}>{href ? <Link href={href}>{inner}</Link> : inner}</li>
          );
        })}
      </ul>
      <div className="hidden overflow-x-auto md:block">
        <div className="min-w-[640px]">
        <div
          role="row"
          className="grid items-center gap-4 border-b border-rule px-2 py-2"
          style={{ gridTemplateColumns: columns.map((c) => c.width ?? "1fr").join(" ") }}
        >
          {columns.map((c) => (
            <div
              key={c.key}
              className={cn(
                "smallcaps text-paper-fade",
                c.align === "right" && "text-right",
                c.align === "center" && "text-center",
                c.className
              )}
            >
              {c.header}
            </div>
          ))}
        </div>
        <ul role="rowgroup">
          {rows.map((row, i) => {
            const href = rowHref?.(row);
            const inner = (
              <div
                role="row"
                className={cn(
                  "grid items-center gap-4 border-b border-rule px-2 py-3 transition-colors",
                  href && "hover:bg-ink-2 cursor-pointer"
                )}
                style={{ gridTemplateColumns: columns.map((c) => c.width ?? "1fr").join(" ") }}
              >
                {columns.map((c) => (
                  <div
                    key={c.key}
                    className={cn(
                      "min-w-0 text-[13px]",
                      c.align === "right" && "text-right",
                      c.align === "center" && "text-center",
                      c.className
                    )}
                  >
                    {c.render(row)}
                  </div>
                ))}
              </div>
            );
            return (
              <li key={row.id ?? i}>{href ? <Link href={href}>{inner}</Link> : inner}</li>
            );
          })}
        </ul>
        </div>
      </div>
    </div>
  );
}
