/**
 * Formatting helpers — small, pure, no React.
 */

/** Truncate a hash for display: "0xa1b2…7c8d". Always renders the chain visible. */
export function shortHash(h: string, head = 6, tail = 4): string {
  if (!h) return "";
  if (h.length <= head + tail + 1) return h;
  return `${h.slice(0, head)}…${h.slice(-tail)}`;
}

/**
 * Render a URN as an editorial "call number".
 * `urn:praetor:asset:demo:northwind-support-bot`
 * → ["asset", "demo", "northwind-support-bot"]
 */
export function urnParts(urn: string): { kind: string; tenant: string; slug: string } {
  const parts = urn.split(":");
  return {
    kind: parts[2] ?? "",
    tenant: parts[3] ?? "",
    slug: parts.slice(4).join(":")
  };
}

export function pct(n: number): string {
  return `${Math.round(n * 100)}%`;
}

export function num(n: number): string {
  return n.toLocaleString("en-US");
}

export function ms(n: number): string {
  if (n < 1000) return `${n}ms`;
  if (n < 60_000) return `${(n / 1000).toFixed(1)}s`;
  return `${(n / 60_000).toFixed(1)}m`;
}

export function severityWeight(s: string): number {
  return { critical: 5, high: 4, medium: 3, low: 2, info: 1 }[s] ?? 0;
}

/** Returns a stable pseudo-random number in [0, 1) given a string seed. */
export function seededRandom(seed: string): number {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return ((h >>> 0) % 10000) / 10000;
}
