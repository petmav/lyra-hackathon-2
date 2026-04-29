"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Corpus } from "@/lib/api/types";
import { PageHeader } from "@/components/shell/PageHeader";
import { Section } from "@/components/primitives/Section";
import { Drawer } from "@/components/primitives/Drawer";
import { Button } from "@/components/primitives/Button";
import { Input } from "@/components/primitives/Input";
import { Badge } from "@/components/primitives/Badge";
import { Hairline } from "@/components/primitives/Hairline";
import { Timestamp } from "@/components/data/Timestamp";
import { Urn } from "@/components/data/Urn";
import { CorpusSearch } from "@/components/corpus-search/CorpusSearch";
import { Plus, Trash2 } from "lucide-react";

const KINDS = [
  { value: "regulation", label: "Regulation" },
  { value: "standard", label: "Standard" },
  { value: "internal_policy", label: "Internal policy" },
  { value: "code_repo", label: "Code repository" },
  { value: "process_artefact", label: "Process artefact" },
  { value: "evidence_reference", label: "Evidence reference" }
];

export function CorpusManager() {
  const [corpora, setCorpora] = useState<Corpus[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);

  const reload = async () => {
    setLoading(true);
    try {
      setCorpora(await api.corpora.list());
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

  const onDelete = async (corpus: Corpus) => {
    if (!confirm(`Delete corpus "${corpus.name}" and all its documents?`)) return;
    try {
      await api.corpora.remove(corpus.id);
      await reload();
    } catch (e) {
      alert(`Delete failed: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  return (
    <div>
      <PageHeader
        number="05"
        kicker="Knowledge · corpora"
        title={<>Citable.</>}
        subtitle="Versioned, attributable corpora — regulations, standards, internal policies, code repos, process artefacts. Every retrieval emits a corpus.query event; every Finding cites obligations and document chunks by exact citation path."
        aside={
          <Button onClick={() => setCreating(true)} variant="primary" size="sm">
            <Plus size={12} strokeWidth={1.75} />
            New corpus
          </Button>
        }
      />

      {pageError && (
        <div className="mt-3 border border-crit/40 bg-crit/5 text-crit px-4 py-2 text-[12px] rounded-sm">
          {pageError}
        </div>
      )}

      <Section number="05·1" eyebrow="Catalogue" title="Indexed corpora">
        {loading ? (
          <div className="py-10 text-center text-[12px] text-paper-fade">loading…</div>
        ) : corpora.length === 0 ? (
          <div className="py-10 text-center text-[13px] text-paper-fade border border-rule rounded-sm">
            No corpora yet. <button onClick={() => setCreating(true)} className="underline underline-offset-4 hover:text-paper">Create the first one →</button>
          </div>
        ) : (
          <ul className="grid gap-px bg-rule lg:grid-cols-2">
            {corpora.map((c, i) => (
              <li key={c.id} className="bg-ink p-5 hover:bg-ink-2 transition-colors group relative">
                <Link href={`/corpora/${c.id}`}>
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[10.5px] text-paper-fade tabular-nums">§05·c·{String(i + 1).padStart(2, "0")}</span>
                        <Badge tone={kindTone(c.kind)}>{c.kind.replace("_", " ")}</Badge>
                        {c.framework && <Badge tone="gold">{c.framework}</Badge>}
                      </div>
                      <h3 className="mt-2 ed-h2 text-paper text-[19px]">{c.name}</h3>
                      <p className="mt-1 text-[12.5px] text-paper-dim leading-snug">{c.description}</p>
                      <div className="mt-3"><Urn urn={c.urn} /></div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="font-mono text-[18px] text-paper tabular-nums">{c.document_count}</div>
                      <div className="smallcaps text-paper-fade">documents</div>
                      <div className="mt-2 text-[10.5px] text-paper-fade">
                        v{c.version} · indexed <Timestamp ts={c.indexed_at} className="inline" />
                      </div>
                    </div>
                  </div>
                </Link>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); void onDelete(c); }}
                  aria-label={`Delete ${c.name}`}
                  className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity text-paper-fade hover:text-crit p-1.5 rounded-sm hover:bg-ink-3"
                >
                  <Trash2 size={13} strokeWidth={1.75} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Hairline tone="display" className="my-10" />

      <Section number="05·2" eyebrow="Hybrid retrieval" title="Search across corpora">
        <CorpusSearch corpora={corpora} />
      </Section>

      <Drawer
        open={creating}
        onClose={() => setCreating(false)}
        title="New corpus"
        subtitle="Indexed knowledge"
        width="wide"
      >
        <CorpusForm
          onClose={() => setCreating(false)}
          onSaved={() => { setCreating(false); void reload(); }}
        />
      </Drawer>
    </div>
  );
}

function CorpusForm({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState("");
  const [kind, setKind] = useState("internal_policy");
  const [description, setDescription] = useState("");
  const [framework, setFramework] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [retention, setRetention] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null);
    setBusy(true);
    try {
      await api.corpora.create({
        name,
        kind,
        description: description || undefined,
        framework: framework || undefined,
        jurisdiction: jurisdiction || undefined,
        retention: retention || undefined,
        source_url: sourceUrl || undefined
      });
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="px-6 py-5 space-y-5">
      <Field label="Name" hint="Human-readable corpus title">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Internal escalation policy" />
      </Field>

      <Field label="Kind" hint="Determines default badges and retention defaults">
        <select
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          className="w-full bg-transparent border-b border-rule h-9 text-[14px] font-mono text-paper focus:border-gold outline-none"
        >
          {KINDS.map((k) => <option key={k.value} value={k.value} className="bg-ink">{k.label}</option>)}
        </select>
      </Field>

      <Field label="Description">
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          className="w-full bg-transparent text-paper placeholder:text-paper-fade border border-rule rounded-sm px-3 py-2 text-[13px] focus:border-gold outline-none resize-y"
          placeholder="What this corpus covers, who owns it, how it should be cited."
        />
      </Field>

      <div className="grid grid-cols-2 gap-5">
        <Field label="Framework" hint="iso_42001, gdpr, internal_policy, …">
          <Input value={framework} onChange={(e) => setFramework(e.target.value)} placeholder="iso_42001" />
        </Field>
        <Field label="Jurisdiction">
          <Input value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value)} placeholder="EU" />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-5">
        <Field label="Retention">
          <Input value={retention} onChange={(e) => setRetention(e.target.value)} placeholder="7 years" />
        </Field>
        <Field label="Source URL">
          <Input value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder="https://…" />
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
        <Button onClick={submit} variant="primary" disabled={busy || !name}>
          {busy ? "Creating…" : "Create corpus"}
        </Button>
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

function kindTone(k: string) {
  if (k === "regulation") return "gold" as const;
  if (k === "standard") return "info" as const;
  if (k === "internal_policy") return "warn" as const;
  return "muted" as const;
}
