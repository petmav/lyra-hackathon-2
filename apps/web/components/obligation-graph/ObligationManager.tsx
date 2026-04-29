"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Obligation, AssetType } from "@/lib/api/types";
import { PageHeader } from "@/components/shell/PageHeader";
import { Section } from "@/components/primitives/Section";
import { Drawer } from "@/components/primitives/Drawer";
import { Button } from "@/components/primitives/Button";
import { Input } from "@/components/primitives/Input";
import { Badge } from "@/components/primitives/Badge";
import { Citation } from "@/components/data/Citation";
import { DataTable } from "@/components/primitives/DataTable";
import { ObligationGraph } from "@/components/obligation-graph/ObligationGraph";
import { Hairline } from "@/components/primitives/Hairline";
import { ArrowUpRight, Pencil, Plus, Trash2, Upload } from "lucide-react";

type Severity = "info" | "warn" | "block";
type Mode = { kind: "closed" } | { kind: "create" } | { kind: "edit"; obligation: Obligation } | { kind: "import" };

const SEVERITIES: Severity[] = ["info", "warn", "block"];

const SAMPLE_YAML = `framework: internal_policy
version: "2026.04"
obligations:
  - urn: urn:praetor:obligation:custom:internal-tool-egress
    citation: Tool Egress 4.1
    text: Tools that send data outside the tenant must require human approval.
    severity_default: block
    applicability:
      asset_types: [tool, agent]
      jurisdictions: [US, EU]
`;

export function ObligationManager() {
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [controls, setControls] = useState<Awaited<ReturnType<typeof api.controls.list>>>([]);
  const [assets, setAssets] = useState<Awaited<ReturnType<typeof api.assets.list>>>([]);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<Mode>({ kind: "closed" });
  const [pageError, setPageError] = useState<string | null>(null);

  const reload = async () => {
    setLoading(true);
    try {
      const [o, c, a] = await Promise.all([api.obligations.list(), api.controls.list(), api.assets.list()]);
      setObligations(o);
      setControls(c);
      setAssets(a);
      setPageError(null);
    } catch (e) {
      setPageError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void reload();
  }, []);

  const onDelete = async (obligation: Obligation) => {
    if (!confirm(`Delete obligation "${obligation.framework} ${obligation.citation}"?`)) return;
    try {
      await api.obligations.remove(obligation.urn);
      await reload();
    } catch (e) {
      alert(`Delete failed: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  return (
    <div>
      <PageHeader
        number="07"
        kicker="Knowledge · obligations"
        title={<>From obligation to <span className="ed-display-italic">asset</span>.</>}
        subtitle="A graph of regulatory and internal obligations, the controls that implement them, and the assets that bear them. Same shape as the audit packet's printed obligation chain."
        aside={
          <div className="flex items-center gap-2">
            <Button onClick={() => setMode({ kind: "import" })} size="sm">
              <Upload size={12} strokeWidth={1.75} />
              Import YAML
            </Button>
            <Button onClick={() => setMode({ kind: "create" })} variant="primary" size="sm">
              <Plus size={12} strokeWidth={1.75} />
              New obligation
            </Button>
          </div>
        }
      />

      {pageError && (
        <div className="mt-3 border border-crit/40 bg-crit/5 text-crit px-4 py-2 text-[12px] rounded-sm">
          {pageError}
        </div>
      )}

      <Section number="07·1" eyebrow="Graph" title="Obligations · Controls · Assets">
        {loading ? (
          <div className="py-10 text-center text-[12px] text-paper-fade">loading…</div>
        ) : (
          <ObligationGraph obligations={obligations} controls={controls} assets={assets} />
        )}
      </Section>

      <Section number="07·2" eyebrow="Ledger" title="Obligations">
        <DataTable
          rows={obligations}
          columns={[
            { key: "framework", header: "Framework", width: "150px", render: (o) => <Badge tone="gold">{o.framework}</Badge> },
            {
              key: "citation",
              header: "Citation",
              width: "1.4fr",
              render: (o) => (
                <Citation framework={o.framework.replace("_", " ").toUpperCase()} path={o.citation} excerpt={o.text} />
              )
            },
            {
              key: "sev",
              header: "Default",
              width: "100px",
              render: (o) => (
                <Badge tone={o.severity_default === "block" ? "crit" : o.severity_default === "warn" ? "warn" : "muted"}>
                  {o.severity_default}
                </Badge>
              )
            },
            { key: "ver", header: "Version", width: "90px", render: (o) => <span className="font-mono text-[11.5px] text-paper-dim">{o.version}</span> },
            {
              key: "actions",
              header: "",
              width: "92px",
              render: (o) => (
                <div className="flex items-center gap-1.5 justify-end">
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); setMode({ kind: "edit", obligation: o }); }}
                    aria-label={`Edit ${o.framework} ${o.citation}`}
                    className="text-paper-fade hover:text-paper p-1.5 rounded-sm hover:bg-ink-2"
                  >
                    <Pencil size={13} strokeWidth={1.75} />
                  </button>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); void onDelete(o); }}
                    aria-label={`Delete ${o.framework} ${o.citation}`}
                    className="text-paper-fade hover:text-crit p-1.5 rounded-sm hover:bg-ink-2"
                  >
                    <Trash2 size={13} strokeWidth={1.75} />
                  </button>
                </div>
              )
            }
          ]}
        />
      </Section>

      <ObligationDrawer
        mode={mode}
        onClose={() => setMode({ kind: "closed" })}
        onSaved={() => { setMode({ kind: "closed" }); void reload(); }}
      />
    </div>
  );
}

function ObligationDrawer({
  mode,
  onClose,
  onSaved
}: {
  mode: Mode;
  onClose: () => void;
  onSaved: () => void;
}) {
  if (mode.kind === "import") {
    return (
      <Drawer open onClose={onClose} title="Import obligations from YAML" subtitle="Bulk import" width="wide">
        <YamlImportForm onClose={onClose} onSaved={onSaved} />
      </Drawer>
    );
  }
  if (mode.kind === "create" || mode.kind === "edit") {
    const initial = mode.kind === "edit" ? mode.obligation : null;
    return (
      <Drawer
        open
        onClose={onClose}
        title={initial ? `Edit · ${initial.framework} ${initial.citation}` : "New obligation"}
        subtitle={initial ? "Update existing record" : "Create new"}
        width="wide"
      >
        <ObligationForm initial={initial} onClose={onClose} onSaved={onSaved} />
      </Drawer>
    );
  }
  return <Drawer open={false} onClose={onClose} />;
}

function ObligationForm({
  initial,
  onClose,
  onSaved
}: {
  initial: Obligation | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [framework, setFramework] = useState(initial?.framework ?? "");
  const [citation, setCitation] = useState(initial?.citation ?? "");
  const [text, setText] = useState(initial?.text ?? "");
  const [severity, setSeverity] = useState<Severity>((initial?.severity_default as Severity | undefined) ?? "warn");
  const [jurisdictions, setJurisdictions] = useState((initial?.applicability.jurisdictions ?? []).join(", "));
  const [assetTypes, setAssetTypes] = useState((initial?.applicability.asset_types ?? []).join(", "));
  const [highRisk, setHighRisk] = useState<boolean>(Boolean(initial?.applicability.high_risk));
  const [version, setVersion] = useState(initial?.version ?? "2026.04");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null);
    setBusy(true);
    const applicability = {
      jurisdictions: jurisdictions.split(",").map((s) => s.trim()).filter(Boolean),
      asset_types: (assetTypes.split(",").map((s) => s.trim()).filter(Boolean) as AssetType[]),
      high_risk: highRisk || undefined
    };
    try {
      if (initial) {
        await api.obligations.update(initial.urn, {
          framework,
          citation,
          text,
          severity_default: severity,
          applicability,
          version
        });
      } else {
        await api.obligations.create({
          framework,
          citation,
          text,
          severity_default: severity,
          applicability,
          version
        });
      }
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="px-6 py-5 space-y-5">
      <div className="grid grid-cols-2 gap-5">
        <Field label="Framework" hint="e.g. iso_42001, gdpr, internal_policy">
          <Input value={framework} onChange={(e) => setFramework(e.target.value)} placeholder="iso_42001" />
        </Field>
        <Field label="Citation" hint="e.g. 8.3, Annex III(5)(a)">
          <Input value={citation} onChange={(e) => setCitation(e.target.value)} placeholder="8.3" />
        </Field>
      </div>

      <Field label="Text" hint="The exact obligation text — used as evidence in findings">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={4}
          className="w-full bg-transparent text-paper placeholder:text-paper-fade border border-rule rounded-sm px-3 py-2 text-[13px] focus:border-gold outline-none resize-y"
          placeholder="The obligation text…"
        />
      </Field>

      <div className="grid grid-cols-3 gap-5">
        <Field label="Default severity" hint="Triggered by violation">
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value as Severity)}
            className="w-full bg-transparent border-b border-rule h-9 text-[14px] font-mono text-paper focus:border-gold outline-none"
          >
            {SEVERITIES.map((s) => <option key={s} value={s} className="bg-ink">{s}</option>)}
          </select>
        </Field>
        <Field label="Version">
          <Input value={version} onChange={(e) => setVersion(e.target.value)} placeholder="2026.04" />
        </Field>
        <Field label="High risk" hint="Marks for elevated scrutiny">
          <label className="inline-flex items-center gap-2 text-[13px] text-paper-dim mt-2">
            <input type="checkbox" checked={highRisk} onChange={(e) => setHighRisk(e.target.checked)} className="accent-gold" />
            High-risk obligation
          </label>
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-5">
        <Field label="Jurisdictions" hint="Comma-separated, e.g. US, EU, UK">
          <Input value={jurisdictions} onChange={(e) => setJurisdictions(e.target.value)} placeholder="US, EU" />
        </Field>
        <Field label="Asset types" hint="Comma-separated, e.g. agent, tool, dataset">
          <Input value={assetTypes} onChange={(e) => setAssetTypes(e.target.value)} placeholder="agent, tool" />
        </Field>
      </div>

      {error && (
        <div className="border border-crit/40 bg-crit/5 text-crit px-4 py-2 text-[12px] rounded-sm">
          {error}
        </div>
      )}

      <Hairline />
      <div className="flex items-center justify-end gap-2">
        <Button onClick={onClose} variant="ghost">Cancel</Button>
        <Button onClick={submit} variant="primary" disabled={busy || !framework || !citation || !text}>
          {busy ? "Saving…" : (initial ? "Save changes" : "Create obligation")}
        </Button>
      </div>
    </div>
  );
}

function YamlImportForm({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [text, setText] = useState(SAMPLE_YAML);
  const [framework, setFramework] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ created: number; updated: number; skipped: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null);
    setBusy(true);
    setResult(null);
    try {
      const r = await api.obligations.importYaml(text, framework || undefined);
      setResult({ created: r.created.length, updated: r.updated.length, skipped: r.skipped });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="px-6 py-5 space-y-5">
      <Field label="Default framework" hint="Optional — used when an obligation in the YAML omits its framework">
        <Input value={framework} onChange={(e) => setFramework(e.target.value)} placeholder="iso_42001" />
      </Field>

      <Field label="YAML" hint="Schema: framework + obligations: [{urn, citation, text, severity_default, applicability}]">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={20}
          spellCheck={false}
          className="w-full font-mono text-[12px] leading-[1.55] bg-ink border border-rule rounded-sm px-3 py-2 text-paper focus:border-gold outline-none resize-y"
        />
      </Field>

      {error && (
        <div className="border border-crit/40 bg-crit/5 text-crit px-4 py-2 text-[12px] rounded-sm">
          {error}
        </div>
      )}

      {result && (
        <div className="border border-ok/40 bg-ok/5 text-ok px-4 py-2 text-[12px] rounded-sm">
          Imported · {result.created} created, {result.updated} updated, {result.skipped} skipped.
        </div>
      )}

      <Hairline />
      <div className="flex items-center justify-end gap-2">
        <Button onClick={onClose} variant="ghost">Cancel</Button>
        {result ? (
          <Button onClick={onSaved} variant="primary">
            Done
            <ArrowUpRight size={11} strokeWidth={1.5} />
          </Button>
        ) : (
          <Button onClick={submit} variant="primary" disabled={busy || !text.trim()}>
            {busy ? "Importing…" : "Import"}
          </Button>
        )}
      </div>
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="text-[10.5px] font-medium uppercase tracking-[0.08em] text-paper-fade mb-1">
        {label}
      </div>
      {children}
      {hint && <div className="mt-1 text-[11px] text-paper-fade">{hint}</div>}
    </label>
  );
}
