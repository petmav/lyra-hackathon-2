"use client";

import { useMemo, useState } from "react";
import { cn } from "@/lib/utils/cn";
import type {
  JsonStackManifest,
  JsonStackOperation,
  JsonStackPreviewResult
} from "@/lib/api/types";
import { Badge } from "@/components/primitives/Badge";
import { Button } from "@/components/primitives/Button";
import { Drawer } from "@/components/primitives/Drawer";
import { api } from "@/lib/api";
import { directionLabel, effectRadiusTone } from "@/lib/utils/hooks";
import { Play, ArrowDown, ArrowUp, ArrowLeftRight } from "lucide-react";

/**
 * Renders each operation in a JSON Stack manifest as a row, with a "Preview"
 * button that opens a drawer rendering the dry-run request.
 */
export function JsonStackOperations({
  stackId,
  manifest
}: {
  stackId: string;
  manifest: JsonStackManifest;
}) {
  const ops = useMemo(() => Object.entries(manifest.operations), [manifest]);
  const [previewName, setPreviewName] = useState<string | null>(null);

  const previewing = previewName
    ? { name: previewName, op: manifest.operations[previewName] }
    : null;

  return (
    <>
      <div className="border border-rule rounded-sm overflow-hidden">
        <div className="grid grid-cols-[28px_1.4fr_70px_2fr_140px_92px] gap-3 px-4 py-2.5 border-b border-rule bg-ink text-[10.5px] font-medium uppercase tracking-[0.08em] text-paper-fade">
          <span></span>
          <span>Operation</span>
          <span>Method</span>
          <span>Path</span>
          <span>Effect radius</span>
          <span></span>
        </div>
        <ul>
          {ops.map(([name, op], i) => (
            <li key={name} className={cn(i > 0 && "border-t border-rule")}>
              <div className="grid grid-cols-[28px_1.4fr_70px_2fr_140px_92px] gap-3 items-center px-4 py-3">
                <DirectionIcon direction={op.direction} />
                <div className="min-w-0">
                  <div className="text-[13.5px] font-medium text-paper truncate">{name}</div>
                  <div className="font-mono text-[11px] text-paper-fade truncate">
                    {directionLabel(op.direction)}
                  </div>
                </div>
                <Badge tone={methodTone(op.method)}>{op.method}</Badge>
                <span className="font-mono text-[11.5px] text-paper-dim truncate">
                  {op.path}
                </span>
                <Badge tone={effectRadiusTone(op.effect_radius)}>
                  {op.effect_radius.replace("_", " ")}
                </Badge>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setPreviewName(name)}
                >
                  <Play size={11} strokeWidth={1.75} className="mr-1" />
                  Preview
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </div>

      <PreviewDrawer
        open={previewing !== null}
        onClose={() => setPreviewName(null)}
        stackId={stackId}
        opName={previewing?.name ?? ""}
        op={previewing?.op}
      />
    </>
  );
}

function methodTone(m: string): "ok" | "warn" | "crit" | "info" | "muted" {
  switch (m.toUpperCase()) {
    case "GET":
      return "ok";
    case "POST":
      return "info";
    case "PUT":
    case "PATCH":
      return "warn";
    case "DELETE":
      return "crit";
    default:
      return "muted";
  }
}

function DirectionIcon({ direction }: { direction: string }) {
  if (direction === "in") return <ArrowDown size={14} strokeWidth={1.75} className="text-info" />;
  if (direction === "out") return <ArrowUp size={14} strokeWidth={1.75} className="text-warn" />;
  return <ArrowLeftRight size={14} strokeWidth={1.75} className="text-paper-dim" />;
}

// ─── preview drawer ─────────────────────────────────────────────────────

function PreviewDrawer({
  open,
  onClose,
  stackId,
  opName,
  op
}: {
  open: boolean;
  onClose: () => void;
  stackId: string;
  opName: string;
  op?: JsonStackOperation;
}) {
  return (
    <Drawer
      open={open}
      onClose={onClose}
      subtitle={`Preview · ${stackId}`}
      title={opName}
      width="xl"
    >
      {op && open && (
        <PreviewBody stackId={stackId} opName={opName} op={op} />
      )}
    </Drawer>
  );
}

function PreviewBody({
  stackId,
  opName,
  op
}: {
  stackId: string;
  opName: string;
  op: JsonStackOperation;
}) {
  const inputSchema = op.input_schema ?? {};
  const inputKeys = Object.keys(inputSchema);

  const initialValues = useMemo(() => {
    const out: Record<string, string> = {};
    for (const key of inputKeys) out[key] = sampleForType(key, inputSchema[key]);
    return out;
  }, [inputKeys.join("|")]);

  const [values, setValues] = useState<Record<string, string>>(initialValues);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<JsonStackPreviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onRun = async () => {
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const inputs: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(values)) {
        const t = inputSchema[k];
        inputs[k] = parseValue(v, t);
      }
      const r = await api.hooks.preview({ stack_id: stackId, operation: opName, inputs });
      setResult(r);
      if (!r.ok) setError(r.error ?? "Preview returned ok=false.");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="px-6 py-5 space-y-6">
      <Meta op={op} />

      {inputKeys.length > 0 && (
        <div>
          <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-paper-fade mb-2">
            Inputs
          </div>
          <div className="space-y-3">
            {inputKeys.map((k) => (
              <InputField
                key={k}
                name={k}
                type={inputSchema[k]}
                value={values[k] ?? ""}
                onChange={(v) => setValues((prev) => ({ ...prev, [k]: v }))}
              />
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center gap-3">
        <Button onClick={onRun} disabled={loading}>
          {loading ? "Rendering…" : "Run preview"}
        </Button>
        <span className="text-[11.5px] text-paper-fade">
          Dry run only — no live request is sent. Auth header is redacted.
        </span>
      </div>

      {error && (
        <div className="border border-crit/60 bg-crit/5 px-4 py-3 text-[12.5px] text-crit rounded-sm">
          {error}
        </div>
      )}

      {result && <PreviewResult result={result} op={op} />}
    </div>
  );
}

function Meta({ op }: { op: JsonStackOperation }) {
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-[12.5px]">
      <Cell label="Method">
        <Badge tone={methodTone(op.method)}>{op.method}</Badge>
      </Cell>
      <Cell label="Direction">
        <Badge tone="muted">{directionLabel(op.direction)}</Badge>
      </Cell>
      <Cell label="Effect radius">
        <Badge tone={effectRadiusTone(op.effect_radius)}>
          {op.effect_radius.replace("_", " ")}
        </Badge>
      </Cell>
      <Cell label="Path">
        <span className="font-mono text-[11.5px] text-paper-dim break-all">{op.path}</span>
      </Cell>
    </dl>
  );
}

function Cell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-[10.5px] font-medium uppercase tracking-[0.08em] text-paper-fade mb-1">
        {label}
      </dt>
      <dd>{children}</dd>
    </div>
  );
}

function InputField({
  name,
  type,
  value,
  onChange
}: {
  name: string;
  type: string;
  value: string;
  onChange: (v: string) => void;
}) {
  const isMultiline = type === "object" || type === "array";
  return (
    <div>
      <label className="flex items-baseline justify-between mb-1">
        <span className="font-mono text-[12px] text-paper">{name}</span>
        <span className="text-[10.5px] text-paper-fade">{type}</span>
      </label>
      {isMultiline ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={4}
          spellCheck={false}
          className="w-full font-mono text-[12px] bg-ink border border-rule rounded-sm px-3 py-2 text-paper focus:border-gold outline-none resize-y"
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          spellCheck={false}
          className="w-full font-mono text-[12px] bg-ink border border-rule rounded-sm px-3 py-2 text-paper focus:border-gold outline-none"
        />
      )}
    </div>
  );
}

function PreviewResult({ result, op }: { result: JsonStackPreviewResult; op: JsonStackOperation }) {
  const req = result.outputs.request;
  return (
    <div className="space-y-5">
      <div className="border-t border-rule pt-5">
        <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-paper-fade mb-2 flex items-center justify-between">
          <span>Rendered request</span>
          <span className="font-mono text-paper-dim normal-case tracking-tight">
            {result.latency_ms}ms
          </span>
        </div>
        <div className="border border-rule rounded-sm overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-2.5 bg-ink border-b border-rule">
            <Badge tone={methodTone(req.method)}>{req.method}</Badge>
            <span className="font-mono text-[12px] text-paper truncate">{req.url}</span>
          </div>
          <div className="px-4 py-3">
            <SubLabel>Headers</SubLabel>
            <pre className="font-mono text-[11.5px] text-paper-dim whitespace-pre-wrap break-words">
              {Object.entries(req.headers)
                .map(([k, v]) => `${k}: ${v}`)
                .join("\n")}
            </pre>
            {req.json !== undefined && (
              <>
                <SubLabel className="mt-3">Body (JSON)</SubLabel>
                <pre className="font-mono text-[11.5px] text-paper-dim whitespace-pre-wrap break-words">
                  {JSON.stringify(req.json, null, 2)}
                </pre>
              </>
            )}
            {req.body !== undefined && req.json === undefined && (
              <>
                <SubLabel className="mt-3">Body</SubLabel>
                <pre className="font-mono text-[11.5px] text-paper-dim whitespace-pre-wrap break-words">
                  {String(req.body)}
                </pre>
              </>
            )}
          </div>
        </div>
      </div>

      {op.output_map && Object.keys(op.output_map).length > 0 && (
        <div>
          <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-paper-fade mb-2">
            Output map
          </div>
          <div className="border border-rule rounded-sm">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-rule bg-ink">
                  <th className="text-left px-4 py-2 font-medium text-paper-fade text-[11px] uppercase tracking-[0.08em]">
                    Key
                  </th>
                  <th className="text-left px-4 py-2 font-medium text-paper-fade text-[11px] uppercase tracking-[0.08em]">
                    JSONPath
                  </th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(op.output_map).map(([k, v], i) => (
                  <tr key={k} className={i > 0 ? "border-t border-rule" : ""}>
                    <td className="px-4 py-2 font-mono text-paper">{k}</td>
                    <td className="px-4 py-2 font-mono text-paper-dim">{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function SubLabel({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("text-[10.5px] font-medium uppercase tracking-[0.08em] text-paper-fade mb-1.5", className)}>
      {children}
    </div>
  );
}

// ─── value parsing helpers ───────────────────────────────────────────────

function sampleForType(name: string, type: string | undefined): string {
  if (type === "object") {
    if (name === "record") return JSON.stringify({ Subject: "Review Praetor finding" }, null, 2);
    return "{}";
  }
  if (type === "array") return "[]";
  if (type === "boolean") return "false";
  if (type === "number" || type === "integer") return "0";
  // string-ish defaults — sensible per common manifest field name
  if (name === "instance_url") return "https://example.my.salesforce.com";
  if (name === "api_version") return "v66.0";
  if (name === "object_name") return "Task";
  if (name === "table_name") return "incident";
  if (name === "folder_path") return "Documents";
  if (name === "filename") return "report.pdf";
  return "";
}

function parseValue(raw: string, type: string | undefined): unknown {
  if (type === "object" || type === "array") {
    try {
      return JSON.parse(raw);
    } catch {
      return raw;
    }
  }
  if (type === "boolean") return raw === "true";
  if (type === "number" || type === "integer") {
    const n = Number(raw);
    return Number.isFinite(n) ? n : raw;
  }
  return raw;
}
