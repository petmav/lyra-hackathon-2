"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { cn } from "@/lib/utils/cn";
import { api } from "@/lib/api";
import type { JsonStackManifest, JsonStackValidateResult } from "@/lib/api/types";
import { Button } from "@/components/primitives/Button";
import { Check, Save, X } from "lucide-react";

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

const NEW_SCAFFOLD = `{
  "id": "my_custom_hook",
  "name": "My custom hook",
  "provider": "internal",
  "version": "2026-04",
  "base_url": "https://api.example.com",
  "auth": {
    "kind": "bearer",
    "auth_ref": "secret:my_custom_hook_token",
    "scopes": ["read"]
  },
  "operations": {
    "list_items": {
      "direction": "in",
      "effect_radius": "internal",
      "method": "GET",
      "path": "/api/items",
      "input_schema": {},
      "output_map": {
        "id": "$.id"
      }
    }
  }
}`;

export function ManifestValidator() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isNew = searchParams.get("new") === "1";
  const initialText = isNew ? NEW_SCAFFOLD : SAMPLE;

  const [text, setText] = useState<string>(initialText);
  const [busy, setBusy] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [result, setResult] = useState<JsonStackValidateResult | null>(null);
  const [lastSpec, setLastSpec] = useState<JsonStackManifest | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setText(isNew ? NEW_SCAFFOLD : SAMPLE);
  }, [isNew]);

  const onValidate = async () => {
    setBusy(true);
    setResult(null);
    setParseError(null);
    setSaveError(null);
    setLastSpec(null);
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
      if (r.ok) setLastSpec(parsed as JsonStackManifest);
    } catch (e) {
      setParseError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onReset = () => {
    setText(isNew ? NEW_SCAFFOLD : SAMPLE);
    setResult(null);
    setParseError(null);
    setSaveError(null);
    setLastSpec(null);
  };

  const onSave = async () => {
    if (!lastSpec) return;
    setSaving(true);
    setSaveError(null);
    try {
      const persisted = await api.hooks.persist(lastSpec, true);
      if (!persisted.ok) {
        setSaveError((persisted.errors ?? ["Save failed"]).join("; "));
        return;
      }
      const hookId = persisted.hook?.id ?? lastSpec.id;
      router.push(`/hooks/${encodeURIComponent(hookId)}?test=1`);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
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
              <>
                <p className="mt-2 text-[12px] text-paper-dim">
                  Manifest passes structural checks. Inline secrets are absent;
                  auth_ref is well-formed; operations declare direction, effect
                  radius, method, and path.
                </p>
                <div className="mt-3 flex items-center gap-3">
                  <Button onClick={onSave} disabled={saving || !lastSpec} variant="primary" size="sm">
                    <Save size={12} strokeWidth={1.75} />
                    {saving ? "Saving…" : "Save & enable"}
                  </Button>
                  {saveError && <span className="text-[11px] text-crit max-w-[260px] leading-snug">{saveError}</span>}
                </div>
              </>
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

