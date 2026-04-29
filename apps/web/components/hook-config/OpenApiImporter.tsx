"use client";

import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { EffectRadius, HookDirection, JsonStackManifest, JsonStackOperation } from "@/lib/api/types";
import { Button } from "@/components/primitives/Button";
import { Badge } from "@/components/primitives/Badge";
import { Check, FileJson, Save, X } from "lucide-react";

const SAMPLE_OPENAPI = `{
  "openapi": "3.1.0",
  "info": { "title": "Internal Ticketing", "version": "2026-04" },
  "servers": [{ "url": "https://tickets.internal.example" }],
  "paths": {
    "/api/tickets": {
      "post": {
        "operationId": "create_ticket",
        "summary": "Create ticket",
        "parameters": [
          { "name": "workspace", "in": "query", "schema": { "type": "string" } }
        ],
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "title": { "type": "string" },
                  "body": { "type": "string" }
                }
              }
            }
          }
        },
        "responses": {
          "201": {
            "description": "Created",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "id": { "type": "string" },
                    "url": { "type": "string" }
                  }
                }
              }
            }
          }
        }
      }
    },
    "/api/tickets/{id}": {
      "get": {
        "operationId": "get_ticket",
        "parameters": [
          { "name": "id", "in": "path", "required": true, "schema": { "type": "string" } }
        ],
        "responses": { "200": { "description": "OK" } }
      }
    }
  }
}`;

type OpenApiOperation = {
  key: string;
  name: string;
  method: string;
  path: string;
  summary: string;
  direction: HookDirection;
  effect_radius: EffectRadius;
  input_schema: Record<string, string>;
  body_template?: unknown;
  output_map?: Record<string, string>;
};

export function OpenApiImporter() {
  const [text, setText] = useState(SAMPLE_OPENAPI);
  const [stackId, setStackId] = useState("internal_ticketing_json");
  const [provider, setProvider] = useState("internal_ticketing");
  const [authRef, setAuthRef] = useState("secret:internal_ticketing_token");
  const [selected, setSelected] = useState<Set<string>>(new Set(["POST /api/tickets"]));
  const [parseError, setParseError] = useState<string | null>(null);
  const [manifest, setManifest] = useState<JsonStackManifest | null>(null);
  const [saveState, setSaveState] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const parsed = useMemo(() => {
    setParseError(null);
    try {
      return JSON.parse(text) as Record<string, unknown>;
    } catch (e) {
      setParseError(e instanceof Error ? e.message : String(e));
      return null;
    }
  }, [text]);

  const operations = useMemo(() => parsed ? extractOperations(parsed) : [], [parsed]);

  const toggle = (key: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const build = async () => {
    if (!parsed) return;
    const next = buildManifest(parsed, operations.filter((op) => selected.has(op.key)), stackId, provider, authRef);
    setManifest(next);
    setSaveState(null);
  };

  const persist = async () => {
    if (!manifest) return;
    setBusy(true);
    setSaveState(null);
    try {
      const validation = await api.hooks.validate(manifest);
      if (!validation.ok) {
        setSaveState(`Validation failed: ${validation.errors.join("; ")}`);
        return;
      }
      const result = await api.hooks.persist(manifest);
      setSaveState(result.ok ? `Persisted hook ${result.hook?.id ?? manifest.id}` : `Save failed: ${(result.errors ?? []).join("; ")}`);
    } catch (e) {
      setSaveState(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid gap-5 xl:grid-cols-[1.1fr_1fr]">
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Stack id" value={stackId} onChange={setStackId} />
          <Field label="Provider" value={provider} onChange={setProvider} />
          <Field label="Auth ref" value={authRef} onChange={setAuthRef} />
        </div>

        <div>
          <label className="block text-[11px] font-medium uppercase tracking-[0.08em] text-paper-fade mb-1.5">
            OpenAPI JSON
          </label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={24}
            spellCheck={false}
            className="w-full font-mono text-[12px] leading-[1.55] bg-ink border border-rule rounded-sm px-3 py-2 text-paper focus:border-gold outline-none resize-y"
          />
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-paper-fade">
            Operations
          </div>
          <Button size="sm" onClick={build} disabled={!parsed || selected.size === 0}>
            <FileJson size={12} strokeWidth={1.75} />
            Convert
          </Button>
        </div>

        {parseError ? (
          <Status tone="crit" icon={<X size={14} strokeWidth={1.75} />}>
            {parseError}
          </Status>
        ) : (
          <div className="border border-rule rounded-sm overflow-hidden">
            {operations.length === 0 ? (
              <div className="px-4 py-6 text-[12px] text-paper-fade">
                No OpenAPI operations found.
              </div>
            ) : operations.map((op, index) => (
              <label
                key={op.key}
                className={`grid grid-cols-[24px_1fr_64px_120px] items-center gap-3 px-4 py-3 cursor-pointer hover:bg-ink-2 ${index > 0 ? "border-t border-rule" : ""}`}
              >
                <input
                  type="checkbox"
                  checked={selected.has(op.key)}
                  onChange={() => toggle(op.key)}
                  className="accent-gold"
                />
                <span className="min-w-0">
                  <span className="block text-[13px] text-paper truncate">{op.name}</span>
                  <span className="block font-mono text-[11px] text-paper-fade truncate">{op.path}</span>
                </span>
                <Badge tone={op.method === "GET" ? "ok" : "info"}>{op.method}</Badge>
                <Badge tone={op.effect_radius === "internal" ? "ok" : "warn"}>
                  {op.effect_radius.replace("_", " ")}
                </Badge>
              </label>
            ))}
          </div>
        )}

        {manifest && (
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-paper-fade">
                Generated manifest
              </div>
              <Button size="sm" variant="primary" onClick={persist} disabled={busy}>
                <Save size={12} strokeWidth={1.75} />
                {busy ? "Saving..." : "Save hook"}
              </Button>
            </div>
            {saveState && (
              <Status tone={saveState.startsWith("Persisted") ? "ok" : "crit"} icon={saveState.startsWith("Persisted") ? <Check size={14} strokeWidth={1.75} /> : <X size={14} strokeWidth={1.75} />}>
                {saveState}
              </Status>
            )}
            <pre className="max-h-[420px] overflow-auto border border-rule rounded-sm bg-ink px-3 py-2 font-mono text-[11.5px] leading-[1.5] text-paper-dim">
              {JSON.stringify(manifest, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label>
      <span className="block text-[10.5px] font-medium uppercase tracking-[0.08em] text-paper-fade mb-1">
        {label}
      </span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        spellCheck={false}
        className="w-full font-mono text-[12px] bg-ink border border-rule rounded-sm px-3 py-2 text-paper focus:border-gold outline-none"
      />
    </label>
  );
}

function Status({ tone, icon, children }: { tone: "ok" | "crit"; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className={`flex items-start gap-2 border rounded-sm px-4 py-3 text-[12px] ${tone === "ok" ? "border-ok/40 bg-ok/5 text-ok" : "border-crit/40 bg-crit/5 text-crit"}`}>
      <span className="mt-0.5">{icon}</span>
      <span>{children}</span>
    </div>
  );
}

function buildManifest(
  doc: Record<string, unknown>,
  operations: OpenApiOperation[],
  id: string,
  provider: string,
  authRef: string
): JsonStackManifest {
  return {
    id,
    name: stringAt(doc, ["info", "title"]) || id,
    provider,
    version: stringAt(doc, ["info", "version"]) || "2026-04",
    base_url: firstServerUrl(doc),
    auth: {
      kind: authRef ? "bearer" : "none",
      auth_ref: authRef || null,
      scopes: operations.some((op) => op.direction === "out") ? ["write"] : ["read"]
    },
    operations: Object.fromEntries(operations.map((op) => [
      op.name,
      {
        direction: op.direction,
        effect_radius: op.effect_radius,
        method: op.method,
        path: op.path,
        input_schema: op.input_schema,
        ...(op.body_template ? { body_template: op.body_template } : {}),
        ...(op.output_map ? { output_map: op.output_map } : {})
      } satisfies JsonStackOperation
    ]))
  };
}

function extractOperations(doc: Record<string, unknown>): OpenApiOperation[] {
  const paths = objectAt(doc, ["paths"]);
  if (!paths) return [];
  const out: OpenApiOperation[] = [];
  for (const [path, item] of Object.entries(paths)) {
    if (!isRecord(item)) continue;
    for (const method of ["get", "post", "put", "patch", "delete"]) {
      const operation = item[method];
      if (!isRecord(operation)) continue;
      const methodUpper = method.toUpperCase();
      const name = sanitizeName(String(operation.operationId || `${method}_${path}`));
      const input_schema = collectInputSchema(item, operation);
      const hasBody = Boolean(objectAt(operation, ["requestBody", "content", "application/json"]));
      if (hasBody) input_schema.body = "object";
      out.push({
        key: `${methodUpper} ${path}`,
        name,
        method: methodUpper,
        path,
        summary: String(operation.summary || operation.description || name),
        direction: methodUpper === "GET" ? "in" : "out",
        effect_radius: methodUpper === "GET" ? "internal" : "external_trusted",
        input_schema,
        body_template: hasBody ? "{body}" : undefined,
        output_map: guessOutputMap(operation)
      });
    }
  }
  return out;
}

function collectInputSchema(pathItem: Record<string, unknown>, operation: Record<string, unknown>): Record<string, string> {
  const schema: Record<string, string> = {};
  const params = [...arrayAt(pathItem, ["parameters"]), ...arrayAt(operation, ["parameters"])];
  for (const param of params) {
    if (!isRecord(param)) continue;
    const name = String(param.name || "");
    if (!name) continue;
    schema[name] = String(objectAt(param, ["schema"])?.type || "string");
  }
  return schema;
}

function guessOutputMap(operation: Record<string, unknown>): Record<string, string> | undefined {
  const schema =
    objectAt(operation, ["responses", "200", "content", "application/json", "schema"]) ??
    objectAt(operation, ["responses", "201", "content", "application/json", "schema"]);
  const properties = isRecord(schema) ? objectAt(schema, ["properties"]) : null;
  if (!properties) return undefined;
  const mapped: Record<string, string> = {};
  for (const key of ["id", "key", "url", "web_url", "html_url", "number", "status"]) {
    if (key in properties) mapped[key] = `$.${key}`;
  }
  return Object.keys(mapped).length ? mapped : undefined;
}

function firstServerUrl(doc: Record<string, unknown>): string {
  const server = arrayAt(doc, ["servers"])[0];
  return isRecord(server) && typeof server.url === "string" ? server.url : "https://api.example.com";
}

function stringAt(value: unknown, path: string[]): string | null {
  const found = path.reduce<unknown>((acc, key) => isRecord(acc) ? acc[key] : undefined, value);
  return typeof found === "string" ? found : null;
}

function objectAt(value: unknown, path: string[]): Record<string, unknown> | null {
  const found = path.reduce<unknown>((acc, key) => isRecord(acc) ? acc[key] : undefined, value);
  return isRecord(found) ? found : null;
}

function arrayAt(value: unknown, path: string[]): unknown[] {
  const found = path.reduce<unknown>((acc, key) => isRecord(acc) ? acc[key] : undefined, value);
  return Array.isArray(found) ? found : [];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function sanitizeName(value: string): string {
  return value.replace(/[^a-zA-Z0-9_]+/g, "_").replace(/^_+|_+$/g, "").toLowerCase() || "operation";
}
