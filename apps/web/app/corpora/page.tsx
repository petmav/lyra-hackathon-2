import Link from "next/link";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/shell/PageHeader";
import { Section } from "@/components/primitives/Section";
import { Badge } from "@/components/primitives/Badge";
import { Hairline } from "@/components/primitives/Hairline";
import { Timestamp } from "@/components/data/Timestamp";
import { Urn } from "@/components/data/Urn";
import { CorpusSearch } from "@/components/corpus-search/CorpusSearch";

export const dynamic = "force-dynamic";

/**
 * Corpora page — list of regulations, standards, internal policies, code
 * repos, and process artefacts indexed for hybrid retrieval. The search
 * box at the bottom lets the audience demonstrate a citation lookup live.
 */
export default async function CorporaPage() {
  const corpora = await api.corpora.list();

  return (
    <div>
      <PageHeader
        number="05"
        kicker="Knowledge · corpora"
        title={<>Citable.</>}
        subtitle="Versioned, attributable corpora — regulations, standards, internal policies, code repos, process artefacts. Every retrieval emits a corpus.query event; every Finding cites obligations and document chunks by exact citation path."
      />
      <Section number="05·1" eyebrow="Catalogue" title="Indexed corpora">
        <ul className="grid gap-px bg-rule lg:grid-cols-2">
          {corpora.map((c, i) => (
            <li key={c.id} className="bg-ink p-5 hover:bg-ink-2 transition-colors group">
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
            </li>
          ))}
        </ul>
      </Section>

      <Hairline tone="display" className="my-10" />

      <Section number="05·2" eyebrow="Hybrid retrieval" title="Search across corpora">
        <CorpusSearch corpora={corpora} />
      </Section>
    </div>
  );
}

function kindTone(k: string) {
  if (k === "regulation") return "gold" as const;
  if (k === "standard") return "info" as const;
  if (k === "internal_policy") return "warn" as const;
  return "muted" as const;
}
