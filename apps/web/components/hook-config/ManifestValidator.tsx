"use client";

import { useState } from "react";
import { cn } from "@/lib/utils/cn";
import { api } from "@/lib/api";
import type { JsonStackValidateResult } from "@/lib/api/types";
import { Button } from "@/components/primitives/Button";
import { Check, X } from "lucide-react";

const SAMPLE = `{
  "id": "internal_grc_json",
  "name": "Internal GRC JSON stack",
  "provider": "internal_grc",
  "version": "2026-04",
  "base_url": "https://grc.internal.example",
  "auth": {
    "kind": "bearer",
    "auth_ref": "secret:internal_grc_token",
    "scopes": ["findings.read", "findings.write"]
  },
  "operations": {
    "create_finding": {
      "direction": "out",
      "effect_radius": "external_trusted",
      "method": "POST",
      "path": "/api/findings",
      "body_template": {
        "title": "{finding.title}",
        "severity": "{finding.severity}",
        "source": "praetor"
      },
      "input_schema": {
        "finding": "object"
      },
      "output_map": {
        "external_id": "$.id",
        "url": "$.url"
      }
    }
  }
}`;

export function ManifestValidator() {
  const [text, setText] = useState<string>(SAMPLE);
  const [busy, setBusy] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [result, setResult] = useState<JsonStackValidateResult | null>(null);

  const onValidate = async () => {
    setBusy(true);
    setResult(null);
    setParseError(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch (e) {
      setParseError(e instanceof Error ? e.message : String(e));
      setBusy(false);
      return;
    }
    try {
      const r = await api.hooks.validate(parsed);
      setResult(r);
    } catch (e) {
      setParseError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onReset = () => {
    setText(SAMPLE);
    setResult(null);
    setParseError(null);
  };

  return (
    <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
      <div>
        <label className="block text-[11px] font-medium uppercase tracking-[0.08em] text-paper-fade mb-1.5">
          Manifest JSON
        </label>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={28}
          spellCheck={false}
          className="w-full font-mono text-[12px] leading-[1.55] bg-ink border border-rule rounded-sm px-3 py-2 text-paper focus:border-gold outline-none resize-y"
        />
        <div className="mt-3 flex items-center gap-3">
          <Button onClick={onValidate} disabled={busy} variant="primary">
            {busy ? "Validating…" : "Validate"}
          </Button>
          <Button onClick={onReset} variant="ghost">
            Reset to sample
          </Button>
        </div>
      </div>

      <div className="space-y-4">
        <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-paper-fade">
          Result
        </div>

        {!result && !parseError && (
          <div className="border border-rule rounded-sm px-4 py-6 text-[12px] text-paper-fade">
            Paste a manifest and click Validate.
          </div>
        )}

        {parseError && (
          <ResultPanel ok={false}>
            <div className="text-[12px] text-crit">JSON parse error</div>
            <pre className="mt-1 font-mono text-[11.5px] text-paper-dim whitespace-pre-wrap">
              {parseError}
            </pre>
          </ResultPanel>
        )}

        {result && (
          <ResultPanel ok={result.ok}>
            <div className="flex items-center gap-2">
              {result.ok ? (
                <span className="inline-flex items-center gap-1.5 text-ok text-[13px]">
                  <Check size={14} strokeWidth={1.75} />
                  Manifest is valid
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 text-crit text-[13px]">
                  <X size={14} strokeWidth={1.75} />
                  Validation failed
                </span>
              )}
            </div>

            {result.errors.length > 0 && (
              <ul className="mt-3 space-y-1.5">
                {result.errors.map((err, i) => (
                  <li
                    key={i}
                    className="font-mono text-[11.5px] text-crit/90 leading-snug"
                  >
                    · {err}
                  </li>
                ))}
              </ul>
            )}

            {result.ok && (
              <p className="mt-2 text-[12px] text-paper-dim">
                Manifest passes structural checks. Inline secrets are absent;
                auth_ref is well-formed; operations declare direction, effect
                radius, method, and path.
              </p>
            )}
          </ResultPanel>
        )}
      </div>
    </div>
  );
}

function ResultPanel({
  ok,
  children
}: {
  ok: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "border rounded-sm px-4 py-3",
        ok ? "border-ok/40 bg-ok/5" : "border-crit/40 bg-crit/5"
      )}
    >
      {children}
    </div>
  );
}

