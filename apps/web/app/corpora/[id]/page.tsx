"use client";

import { use, useEffect, useState } from "react";
import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import type { Corpus, PraetorDocument } from "@/lib/api/types";
import { PageHeader } from "@/components/shell/PageHeader";
import { Section } from "@/components/primitives/Section";
import { Badge } from "@/components/primitives/Badge";
import { Hairline } from "@/components/primitives/Hairline";
import { Urn } from "@/components/data/Urn";
import { Timestamp } from "@/components/data/Timestamp";
import { Hash } from "@/components/data/Hash";
import { CorpusSearch } from "@/components/corpus-search/CorpusSearch";
import { DocumentUploader } from "@/components/corpus-search/DocumentUploader";

/**
 * Corpus detail — list of documents in the corpus + a scoped search box.
 */
export default function CorpusPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [corpus, setCorpus] = useState<Corpus | null>(null);
  const [docs, setDocs] = useState<PraetorDocument[]>([]);
  const [loading, setLoading] = useState(true);

  const reload = async () => {
    const [c, d] = await Promise.all([api.corpora.get(id), api.corpora.documents(id)]);
    setCorpus(c);
    setDocs(d);
    setLoading(false);
  };

  useEffect(() => {
    let alive = true;
    void (async () => {
      const [c, d] = await Promise.all([api.corpora.get(id), api.corpora.documents(id)]);
      if (!alive) return;
      setCorpus(c);
      setDocs(d);
      setLoading(false);
    })();
    return () => { alive = false; };
  }, [id]);

  if (loading) return <div className="pt-20 text-center text-paper-fade text-[12px] italic">loading corpus…</div>;
  if (!corpus) return notFound();

  return (
    <div>
      <PageHeader
        number="05·c"
        kicker={`Corpus · ${corpus.kind.replace("_", " ")}`}
        title={corpus.name}
        subtitle={corpus.description}
        aside={
          <div className="text-right">
            <div className="flex items-center justify-end gap-1.5">
              <Badge tone="gold">v{corpus.version}</Badge>
              <Badge tone="muted">{corpus.document_count} docs</Badge>
            </div>
            <div className="mt-2"><Urn urn={corpus.urn} variant="stamp" /></div>
          </div>
        }
      />

      <div className="mt-6">
        <DocumentUploader corpusId={corpus.id} onUploaded={() => void reload()} />
      </div>

      <Section number="α" eyebrow="Documents" title="Indexed">
        <ul className="border border-rule">
          {docs.length === 0 && (
            <li className="px-4 py-6 text-center text-[12px] text-paper-fade">
              No documents in this corpus yet — upload one above.
            </li>
          )}
          {docs.map((d, i) => (
            <li key={d.id} className={`grid gap-4 px-4 py-3 md:grid-cols-[1.4fr_1fr_120px] ${i < docs.length - 1 ? "border-b border-rule" : ""}`}>
              <div>
                <div className="text-[13px] text-paper">{d.title}</div>
                {d.citation && <div className="mt-0.5 ed-display-italic text-[12.5px] text-paper-dim">{d.citation}</div>}
              </div>
              <div className="font-mono text-[11.5px] text-paper-fade truncate">{d.source_uri}</div>
              <div className="text-right text-[11.5px]">
                <Hash value={d.content_hash} />
                <div className="text-paper-fade">{d.chunk_count} chunks</div>
              </div>
            </li>
          ))}
        </ul>
      </Section>

      <Hairline tone="display" className="my-10" />

      <Section number="β" eyebrow="Search" title={`Within ${corpus.name}`}>
        <CorpusSearch corpora={[corpus]} defaultCorpusId={corpus.id} />
      </Section>
    </div>
  );
}
