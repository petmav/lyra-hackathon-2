import { formatDistanceToNowStrict, format } from "date-fns";

/** "23s ago", "2m ago", "1h ago" — used in event streams and alerts. */
export function relative(ts: string | Date): string {
  return formatDistanceToNowStrict(new Date(ts), { addSuffix: true });
}

/** "2026-04-28 14:32:07 UTC" — used in audit packet contexts where precision matters. */
export function precise(ts: string | Date): string {
  return format(new Date(ts), "yyyy-MM-dd HH:mm:ss 'UTC'");
}

/** "14:32:07.421" — used in event logs where sub-second matters. */
export function timecode(ts: string | Date): string {
  return format(new Date(ts), "HH:mm:ss.SSS");
}

/** "Apr 28 · 14:32" — friendly mid-density timestamp. */
export function friendly(ts: string | Date): string {
  return format(new Date(ts), "MMM d · HH:mm");
}
