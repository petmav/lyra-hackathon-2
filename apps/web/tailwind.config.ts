import type { Config } from "tailwindcss";

/**
 * Praetor design tokens.
 *
 * Bound to CSS variables in globals.css so the theme can be inspected at
 * runtime and overridden per surface (e.g. high-contrast audit-packet preview).
 *
 * The single accent is `gold` — Praetor's Roman-magistrate visual mark.
 * Severity colours are deliberately muted: this is a governance surface, not
 * a status page; we want a calm signal, not a fairground.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "var(--ink)",
        "ink-2": "var(--ink-2)",
        "ink-3": "var(--ink-3)",
        paper: "var(--paper)",
        "paper-dim": "var(--paper-dim)",
        "paper-fade": "var(--paper-fade)",
        rule: "var(--rule)",
        "rule-bright": "var(--rule-bright)",
        gold: "var(--gold)",
        "gold-bright": "var(--gold-bright)",
        "gold-dim": "var(--gold-dim)",
        crit: "var(--crit)",
        warn: "var(--warn)",
        ok: "var(--ok)",
        info: "var(--info)"
      },
      fontFamily: {
        display: ["Fraunces", "Georgia", "serif"],
        sans: ["General Sans", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "Menlo", "monospace"]
      },
      fontSize: {
        // a custom editorial scale; display sizes lean larger for "section-as-headline" feel
        "ed-xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.06em" }],
        "ed-sm": ["0.8125rem", { lineHeight: "1.15rem" }],
        "ed-base": ["0.9375rem", { lineHeight: "1.45rem" }],
        "ed-lg": ["1.0625rem", { lineHeight: "1.55rem" }],
        "ed-xl": ["1.375rem", { lineHeight: "1.65rem" }],
        "ed-2xl": ["1.875rem", { lineHeight: "2.1rem" }],
        "ed-3xl": ["2.625rem", { lineHeight: "2.85rem", letterSpacing: "-0.01em" }],
        "ed-display": ["3.75rem", { lineHeight: "1.02", letterSpacing: "-0.02em" }]
      },
      letterSpacing: {
        smallcaps: "0.14em"
      },
      borderColor: {
        DEFAULT: "var(--rule)"
      },
      boxShadow: {
        "ink-deep": "0 24px 64px -32px rgba(0,0,0,0.7)",
        "gold-focus": "0 0 0 1px var(--gold)",
        "rule-focus": "0 0 0 1px var(--rule-bright)"
      },
      keyframes: {
        "praetor-enter": {
          from: { opacity: "0", transform: "translateY(2px)" },
          to: { opacity: "1", transform: "translateY(0)" }
        },
        "event-flash": {
          "0%": { backgroundColor: "rgba(196,165,114,0.10)" },
          "100%": { backgroundColor: "transparent" }
        },
        "hash-pulse": {
          "0%": { transform: "scaleX(0)", opacity: "0" },
          "50%": { transform: "scaleX(1)", opacity: "1" },
          "100%": { transform: "scaleX(1)", opacity: "0.4" }
        },
        "step-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.55" }
        }
      },
      animation: {
        "praetor-enter": "praetor-enter 600ms cubic-bezier(0.2,0.8,0.2,1) both",
        "event-flash": "event-flash 800ms ease-out both",
        "hash-pulse": "hash-pulse 700ms ease-out both",
        "step-pulse": "step-pulse 1.6s ease-in-out infinite"
      }
    }
  },
  plugins: []
};

export default config;
