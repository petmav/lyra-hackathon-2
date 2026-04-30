import { formatDistanceToNowStrict, format } from "date-fns";

/**
 * Coerce an unknown timestamp into a Date. Returns null if the input is
 * missing or unparseable rather than letting `new Date(...)` produce an
 * Invalid Date that throws inside date-fns formatters.
 */
// Anything before this epoch threshold is treated as missing data. We surface
// these as em-dashes rather than rendering "55 years ago" for a row whose
// created_at came back as null and got coerced through new Date(0).
const MIN_VALID_EPOCH_MS = Date.UTC(2000, 0, 1);

function toDate(ts: unknown): Date | null {
  if (ts instanceof Date) {
    const t = ts.getTime();
    return Number.isNaN(t) || t < MIN_VALID_EPOCH_MS ? null : ts;
  }
  if (typeof ts !== "string" && typeof ts !== "number") return null;
  if (typeof ts === "string" && ts.trim() === "") return null;
  const parsed = new Date(ts as string | number);
  const t = parsed.getTime();
  if (Number.isNaN(t) || t < MIN_VALID_EPOCH_MS) return null;
  return parsed;
}

/** "23s ago", "2m ago", "1h ago" — used in event streams and alerts. */
export function relative(ts: string | Date | null | undefined): string {
  const date = toDate(ts);
  if (!date) return "—";
  return formatDistanceToNowStrict(date, { addSuffix: true });
}

/** "2026-04-28 14:32:07 UTC" — used in audit packet contexts where precision matters. */
export function precise(ts: string | Date | null | undefined): string {
  const date = toDate(ts);
  if (!date) return "—";
  return format(date, "yyyy-MM-dd HH:mm:ss 'UTC'");
}

/** "14:32:07.421" — used in event logs where sub-second matters. */
export function timecode(ts: string | Date | null | undefined): string {
  const date = toDate(ts);
  if (!date) return "—";
  return format(date, "HH:mm:ss.SSS");
}

/** "Apr 28 · 14:32" — friendly mid-density timestamp. */
export function friendly(ts: string | Date | null | undefined): string {
  const date = toDate(ts);
  if (!date) return "—";
  return format(date, "MMM d · HH:mm");
}
