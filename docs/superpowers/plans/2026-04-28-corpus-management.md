# Corpus Management — Sub-Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Parent plan:** `2026-04-28-praetor-hackathon-build.md` — primarily Phase 2 Task 2.4 and Phase 3 Task 3.8.

**Goal:** Make regulations, standards, internal policies, code repos, and process artefacts queryable as versioned, attributable, citable corpora. Every retrieval emits a `corpus.query` event with the chunks returned, and every Finding cites obligations and document chunks by exact citation path.

**Architecture:** A `Corpus` is a versioned snapshot of `Document`s. Each Document is split into `DocumentChunk`s indexed by both pgvector (dense) and Postgres `tsvector` (keyword). Hybrid retrieval merges both via reciprocal rank fusion. Citation paths are first-class strings like `Article 5 / paragraph 1 / point c` so Findings can quote them faithfully.

**Tech Stack:** Python 3.12, async SQLAlchemy, pgvector, Postgres `tsvector`/`ts_query`, MinIO (raw text storage), Anthropic embeddings (with OpenAI fallback), `markdown-it-py` for structured markdown, `lxml` for BPMN/XML if encountered.

**Interface this sub-plan exposes:**

```python
class CorpusIndex:
    async def hybrid_search(self, corpus_id: str, query: str,
                            filters: dict | None = None, k: int = 8) -> list[Chunk]: ...
    async def get_document(self, document_id: str) -> Document: ...
    async def snapshot(self, corpus_id: str) -> str: ...   # returns new versioned corpus_id

class Ingester:
    async def ingest_markdown(self, corpus_id: str, source_uri: str, text: str,
                              citation_root: str | None = None) -> str: ...
    async def ingest_via_hook(self, corpus_id: str, hook_id: str,
                              scope: str, args: dict) -> list[str]: ...
```

HTTP: `GET/POST /corpora`, `POST /corpora/{id}/documents:ingest`, `GET /corpora/{id}/documents`, `POST /corpora/{id}:search`, `POST /corpora/{id}:snapshot`.

---

## File map

```
apps/api/praetor_api/
├── routers/corpora.py
├── services/
│   ├── corpus_index.py        # hybrid_search, RRF, embedding cache
│   ├── corpus_ingest.py       # markdown/PDF/BPMN/code ingestion
│   ├── corpus_snapshot.py     # versioning + parent_corpus_id chains
│   └── embeddings.py          # Anthropic-first, OpenAI fallback, on-disk cache
└── models/
    ├── corpus.py
    ├── document.py
    └── chunk.py

content/corpora_seed/                    # the five seed docs
├── eu_ai_act_excerpt.md
├── iso_42001_excerpt.md
├── gdpr_article_5.md
├── internal_data_min_policy.md
└── owasp_agent_top_10.md

content/obligations/                     # obligation YAML hydrated alongside ingestion
├── eu_ai_act.yaml
├── iso_42001.yaml
├── gdpr.yaml
├── nist_ai_rmf.yaml
├── owasp_agent.yaml
└── mitre_atlas.yaml

tests/corpus/
├── test_chunking.py
├── test_embeddings.py
├── test_hybrid_search.py
├── test_snapshot.py
└── fixtures/
    ├── gdpr_article_5.md
    └── tiny_policy.md
```

---

## Task 1: Schema + migrations (additions)

**Files:** alembic migration `0002_corpus.py` if not already in 0001; SQLAlchemy models.

- [ ] `corpus`, `document`, `document_chunk` per master plan §2.1.
- [ ] Indexes: `document_chunk` ivfflat on `embedding vector_cosine_ops`, GIN on `keyword_tokens` (tsvector), btree on `(document_id, ord)`.
- [ ] Test: insert + retrieve a chunk, vector and tsvector both query-able. Commit.

## Task 2: Embeddings service

**Files:** `apps/api/praetor_api/services/embeddings.py`.

- [ ] **Step 1: failing test** mocks Anthropic embeddings endpoint; asserts `embed("hello")` returns a 1536-vec; second call hits cache and doesn't call the API.

- [ ] **Step 2: implement**

```python
class Embedder:
    def __init__(self, anthropic_client, openai_client, cache_dir):
        self.a, self.o, self.cache = anthropic_client, openai_client, Path(cache_dir)
    async def embed(self, text: str) -> list[float]:
        h = sha256(text.encode()).hexdigest()
        cached = self.cache / f"{h}.npy"
        if cached.exists(): return np.load(cached).tolist()
        try:
            v = await self._anthropic_embed(text)
        except Exception:
            v = await self._openai_embed(text)   # fallback
        np.save(cached, np.asarray(v, dtype=np.float32))
        return v
```

Anthropic embeddings via Voyage (the partner model); fallback to OpenAI text-embedding-3-small if env var present, else fail loud.

- [ ] **Step 3: tests pass.** Commit.

## Task 3: Markdown chunking with citation paths

**Files:** `apps/api/praetor_api/services/corpus_ingest.py`.

- [ ] **Step 1: failing test** — feed `gdpr_article_5.md` (a fixture with `## Article 5\n### Paragraph 1\n#### Point (a)`); assert chunks emitted with `citation_path="Article 5 / Paragraph 1 / Point (a)"` and `text` ≤ 800 chars, no chunk crosses a heading.

- [ ] **Step 2: implement**

```python
def chunk_markdown(text: str, target_chars=800) -> list[ChunkRecord]:
    md = markdown_it.MarkdownIt().parse(text)
    stack: list[str] = []   # heading hierarchy
    chunks = []; buf = ""; current_path = []
    for tok in md:
        if tok.type == "heading_open":
            level = int(tok.tag[1])
            if buf.strip():
                chunks.append(ChunkRecord(text=buf.strip(),
                                          citation_path=" / ".join(current_path)))
                buf = ""
            stack = stack[:level-1]
        elif tok.type == "inline" and stack and stack[-1] == "PENDING":
            stack[-1] = tok.content
            current_path = list(stack)
        elif tok.type == "heading_close":
            pass
        elif hasattr(tok, "content"):
            buf += tok.content + "\n"
            if len(buf) > target_chars:
                chunks.append(ChunkRecord(text=buf.strip(),
                                          citation_path=" / ".join(current_path)))
                buf = ""
    if buf.strip():
        chunks.append(ChunkRecord(text=buf.strip(),
                                  citation_path=" / ".join(current_path)))
    return chunks
```

(Adjust the heading-name capture loop to match the exact `markdown-it-py` token API; tests cover.)

- [ ] **Step 3: tests pass.** Commit.

## Task 4: Document ingestion pipeline

**Files:** `apps/api/praetor_api/services/corpus_ingest.py`, `apps/api/praetor_api/routers/corpora.py`.

- [ ] **Step 1: failing test** — `POST /corpora/{id}/documents:ingest` with a markdown file → response includes `document_id` + `chunk_count`; DB has chunks with embeddings + tsvector populated; raw text stored in MinIO under `corpora/{corpus_id}/{document_id}.md`.

- [ ] **Step 2: implement**

```python
async def ingest_markdown(corpus_id, source_uri, text, citation_root=None):
    content_hash = sha256(text.encode()).hexdigest()
    text_path = f"corpora/{corpus_id}/{uuid()}.md"
    await s3.put_object(Bucket=BUCKET, Key=text_path, Body=text.encode())
    doc = Document(corpus_id=corpus_id, source_uri=source_uri,
                   content_hash=content_hash, title=_extract_title(text),
                   citation=citation_root, text_path=text_path)
    await session.add_and_flush(doc)
    chunks = chunk_markdown(text)
    for ord, c in enumerate(chunks):
        emb = await embedder.embed(c.text)
        await session.add(DocumentChunk(document_id=doc.id, ord=ord, text=c.text,
                                        embedding=emb,
                                        keyword_tokens=func.to_tsvector("english", c.text),
                                        citation_path=c.citation_path))
    return doc.id
```

- [ ] **Step 3: tests pass.** Commit.

## Task 5: Ingestion via hook

**Files:** `apps/api/praetor_api/services/corpus_ingest.py` (additions).

- [ ] `ingest_via_hook(corpus_id, hook_id, scope, args)` calls `hooks.call_in`, iterates returned files (each with `path` + `content`), routes to `ingest_markdown` or future PDF/BPMN ingester per file extension.
- [ ] Used to pull a vendor SOC 2 PDF into a corpus, or a customer's BPM XML.
- [ ] At hackathon scope: only markdown is reliable. PDF ingestion stubbed (raises `UnsupportedDocumentType`).
- [ ] Commit.

## Task 6: Hybrid search

**Files:** `apps/api/praetor_api/services/corpus_index.py`.

- [ ] **Step 1: failing test** — ingest 3 documents, query for a phrase that appears verbatim in doc B and is semantically close to doc A; assert RRF returns A, B, C in that order with non-zero scores; emits `corpus.query` event.

- [ ] **Step 2: implement** matching the snippet in PDF §6.4:

```python
async def hybrid_search(corpus_id, query, filters=None, k=8):
    embedding = await embedder.embed(query)
    dense = await session.execute(text("""
        SELECT id, document_id, ord, text, citation_path,
               1 - (embedding <=> :emb) AS score
        FROM document_chunk c
        JOIN document d ON d.id = c.document_id
        WHERE d.corpus_id = :corpus_id
        ORDER BY embedding <=> :emb LIMIT :n
    """), {"emb": embedding, "corpus_id": corpus_id, "n": k*2})
    keyword = await session.execute(text("""
        SELECT id, document_id, ord, text, citation_path,
               ts_rank(keyword_tokens, plainto_tsquery('english', :q)) AS score
        FROM document_chunk c
        JOIN document d ON d.id = c.document_id
        WHERE d.corpus_id = :corpus_id
          AND keyword_tokens @@ plainto_tsquery('english', :q)
        ORDER BY score DESC LIMIT :n
    """), {"q": query, "corpus_id": corpus_id, "n": k*2})
    merged = rrf_merge(list(dense), list(keyword), k=k)
    chunks = [hydrate(r) for r in merged]
    await bus.publish("events", {
        "type": "corpus.query", "corpus_id": corpus_id, "query": query,
        "chunks_returned": [c.summary() for c in chunks],
        "top_score": merged[0]["score"] if merged else 0.0,
    })
    return chunks

def rrf_merge(a, b, k=8, c=60):
    ranks = {}
    for i, r in enumerate(a): ranks[r.id] = ranks.get(r.id, 0) + 1.0/(c+i+1)
    for i, r in enumerate(b): ranks[r.id] = ranks.get(r.id, 0) + 1.0/(c+i+1)
    return sorted([{"id":k_,"score":v_} for k_,v_ in ranks.items()],
                  key=lambda x: -x["score"])[:k]
```

- [ ] **Step 3: tests pass.** Commit.

## Task 7: Versioned snapshots

**Files:** `apps/api/praetor_api/services/corpus_snapshot.py`.

- [ ] **Step 1: failing test** — ingest doc into corpus v1, snapshot, ingest a new doc into v2 (the new corpus_id), assert v1 still has only the original doc and v1's `parent_corpus_id` chain works.

- [ ] **Step 2: implement** — snapshot creates a new `corpus` row, copies all `document` rows pointing at it (chunks remain shared via `document_id` … or duplicated, decision below), sets `parent_corpus_id`, increments `version`.

  - **Decision:** at hackathon scope, copy document rows but share chunks (chunks key off document_id; documents are versioned, chunks are not). A snapshot is essentially "freeze which documents were in this corpus at this moment." This means re-embedding is not required.

- [ ] **Step 3: tests pass.** Commit.

## Task 8: Seed five corpora

**Files:** `content/corpora_seed/*.md`, `scripts/seed_demo.py` (additions).

- [ ] Curate the five demo seed files (the EU AI Act excerpt covers Annex III + Art 14; ISO 42001 §7–10; GDPR Article 5 verbatim; internal_data_min_policy section 3.2 describes recipient-domain validation requirements; OWASP Agent Top 10 from the public reference).
- [ ] `seed_demo.py` creates 5 corpora and ingests each file with a `citation_root` matching the framework name.
- [ ] Manual verification: `POST /corpora/<id>:search` with "data minimisation recipient" returns the internal policy chunk that the demo Finding will cite.
- [ ] Commit.

## Task 9: Obligation hydration from YAML

**Files:** `apps/api/praetor_api/services/obligation_loader.py`, `content/obligations/*.yaml`.

Obligations are first-class rows separate from corpus chunks but linked by citation. They're what Findings cite by URN.

- [ ] **Step 1: failing test** — load `eu_ai_act.yaml` (per PDF §8.2 format), assert each obligation's URN, framework, citation, applicability, severity_default match the YAML.

- [ ] **Step 2: implement** loader called at startup; idempotent (uses URN as primary key); supports `version` field so re-runs detect new versions.

- [ ] **Step 3: seed** all six obligation files (eu_ai_act, iso_42001, nist_ai_rmf, gdpr, owasp_agent, mitre_atlas) with at least 5 obligations each. Demo only needs ~10 to be richly cited; the rest provide "depth" in the obligation graph view.

- [ ] Commit.

## Task 10: Corpora UI

**Files:** `apps/web/app/corpora/page.tsx`, `apps/web/components/corpus-search/CorpusSearch.tsx`.

- [ ] List: name, kind, version, document_count, indexed_at, version chain.
- [ ] Click a corpus → document list + search box. Search calls `POST /corpora/{id}:search`, renders top chunks with citation_path highlighted.
- [ ] "Snapshot" button calls `POST /corpora/{id}:snapshot`.
- [ ] Commit.

---

## Self-review

- Hybrid retrieval (Task 6) covers both lexical-precise (e.g. citation lookups) and semantic queries.
- Citation paths preserved end-to-end (Task 3): chunking → DB → search → Finding `documents_cited[]` field with `citation_path`. The demo Finding "GDPR 5(1)(c)" works because chunks carry the path.
- Versioned snapshots (Task 7) ensure a workflow run can be replayed against the exact corpus state used at the time. Critical for audit reproducibility.
- Five seed corpora + six obligation files (Tasks 8, 9) populate the demo without live PDF ingestion (cut for hackathon scope).

## Out of scope for this sub-plan

- PDF ingestion (raises `UnsupportedDocumentType`; stub only).
- BPMN/XML structured parsing beyond a placeholder.
- Code repo AST indexing — handled inside the sandbox via `ast_parse` tool, not at corpus level (tradeoff: avoids re-indexing every commit).
- Multi-jurisdiction overlay logic (post-hackathon).
