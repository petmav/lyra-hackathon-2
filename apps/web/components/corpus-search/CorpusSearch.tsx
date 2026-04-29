"use client";

import { useEffect, useState } from "react";
import { Input } from "@/components/primitives/Input";
import { api } from "@/lib/api";
import type { Corpus, DocumentChunk } from "@/lib/api/types";
import { Citation } from "@/components/data/Citation";
import { Search } from "lucide-react";
import { Confidence } from "@/components/data/Confidence";

/**
 * Corpus search box + results.
 *
 * Hybrid retrieval at the API layer (RRF over dense + keyword) is mocked by
 * a small token-overlap scorer in the API client. The UI surfaces the
 * citation_path, an excerpt, and a confidence-style meter for relevance —
 * relevance scores look like Finding confidences on purpose, since they live
 * in the same epistemic family.
 */
export function CorpusSearch({
  corpora,
  defaultCorpusId
}: {
  corpora: Corpus[];
  defaultCorpusId?: string;
}) {
  const [corpusId, setCorpusId] = useState(defaultCorpusId ?? corpora[0]?.id);
  const [query, setQuery] = useState("recipient validation");
  const [results, setResults] = useState<DocumentChunk[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!corpusId) return;
    setLoading(true);
    const id = setTimeout(() => {
      api.corpora.search(corpusId, query, 8).then((r) => {
        setResults(r);
        setLoading(false);
      });
    }, 180);
    return () => clearTimeout(id);
  }, [corpusId, query]);

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 md:grid-cols-[200px_1fr] items-end">
        <label className="block">
          <span className="smallcaps mb-1 block">Corpus</span>
          <select
            value={corpusId}
            onChange={(e) => setCorpusId(e.target.value)}
            className="w-full bg-transparent border-b border-rule h-9 text-[14px] text-paper-dim focus:border-gold focus:outline-none"
          >
            {corpora.map((c) => (
              <option key={c.id} value={c.id} className="bg-ink-2">
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="smallcaps mb-1 flex items-center gap-2"><Search size={11} strokeWidth={1.5} /> Hybrid query</span>
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. recipient validation; data minimisation"
          />
        </label>
      </div>
      <div>
        <div className="smallcaps mb-3 flex items-center justify-between">
          <span>Results · {results.length}</span>
          <span className="text-paper-fade">{loading ? "searching…" : "ranked by RRF · vector + keyword"}</span>
        </div>
        <ul className="flex flex-col">
          {results.map((c, i) => (
            <li key={c.id} className="border-t border-rule first:border-t-0 py-4">
              <div className="flex items-baseline justify-between gap-4 mb-2">
                <div className="font-mono text-[10.5px] text-paper-fade">
                  {String(i + 1).padStart(2, "0")} · chunk #{c.ord}
                </div>
                <Confidence value={c.score ?? 0} />
              </div>
              <Citation
                framework={frameworkFor(corpusId)}
                path={c.citation_path}
                excerpt={c.text}
              />
            </li>
          ))}
          {results.length === 0 && !loading && (
            <li className="text-[12.5px] text-paper-fade py-6 italic">No matches in this corpus.</li>
          )}
        </ul>
      </div>
    </div>
  );
}

function frameworkFor(corpusId: string | undefined): string {
  if (!corpusId) return "";
  if (corpusId.includes("eu_ai_act")) return "EU AI ACT";
  if (corpusId.includes("iso_42001")) return "ISO 42001";
  if (corpusId.includes("gdpr")) return "GDPR";
  if (corpusId.includes("internal")) return "INTERNAL";
  if (corpusId.includes("owasp")) return "OWASP";
  return "CORPUS";
}
