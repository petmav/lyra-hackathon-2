from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from praetor_api.models.corpus import Corpus
from praetor_api.models.document import Document
from praetor_api.models.document_chunk import DocumentChunk
from praetor_api.services.corpus_index import CORPORA

CORPUS_URN_PREFIX = "urn:praetor:corpus:"
DOCUMENT_URN_PREFIX = "urn:praetor:document:"


def _corpus_urn(corpus_id: str) -> str:
    return f"{CORPUS_URN_PREFIX}{corpus_id}"


def _document_urn(document_id: str) -> str:
    return f"{DOCUMENT_URN_PREFIX}{document_id}"


def _external_id(urn: str, prefix: str) -> str:
    return urn.removeprefix(prefix)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def ensure_corpora(session: AsyncSession) -> list[Corpus]:
    rows: list[Corpus] = []
    for corpus_id, data in CORPORA.items():
        result = await session.execute(select(Corpus).where(Corpus.urn == _corpus_urn(corpus_id)))
        corpus = result.scalar_one_or_none()
        if corpus is None:
            corpus = Corpus(
                urn=_corpus_urn(corpus_id),
                name=data["name"],
                kind=data["kind"],
                document_count=0,
                indexed_at=None,
            )
            session.add(corpus)
            await session.flush()
        rows.append(corpus)
    return rows


async def list_corpora(session: AsyncSession) -> list[dict[str, Any]]:
    corpora = await ensure_corpora(session)
    for corpus in corpora:
        corpus.document_count = await _document_count(session, corpus.id)
    await session.commit()
    return [_corpus_to_api(corpus) for corpus in corpora]


async def get_corpus(session: AsyncSession, corpus_id: str) -> dict[str, Any] | None:
    corpus = await _find_corpus(session, corpus_id)
    if corpus is None:
        return None
    corpus.document_count = await _document_count(session, corpus.id)
    await session.commit()
    return _corpus_to_api(corpus)


async def list_documents(session: AsyncSession, corpus_id: str) -> list[dict[str, Any]]:
    corpus = await _find_corpus(session, corpus_id)
    if corpus is None:
        raise KeyError(corpus_id)

    result = await session.execute(
        select(Document).where(Document.corpus_id == corpus.id).order_by(Document.created_at)
    )
    documents = list(result.scalars().all())
    rows: list[dict[str, Any]] = []
    for document in documents:
        chunk_count = (
            await session.scalar(select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document.id))
        ) or 0
        rows.append(_document_to_api(document, _external_id(corpus.urn, CORPUS_URN_PREFIX), chunk_count))
    return rows


async def ingest_document(
    session: AsyncSession,
    corpus_id: str,
    title: str,
    source_uri: str,
    text: str,
) -> dict[str, Any]:
    corpus = await _find_corpus(session, corpus_id)
    if corpus is None:
        raise KeyError(corpus_id)

    digest = _hash_text(f"{source_uri}\n{text}")
    document_id = f"doc_{uuid4().hex[:12]}"
    document = Document(
        urn=_document_urn(document_id),
        corpus_id=corpus.id,
        source_uri=source_uri,
        content_hash=digest,
        title=title,
        citation=None,
        framework=corpus.kind,
        jurisdiction=None,
        sector=None,
        text_path=f"db://document/{document_id}",
        parsed_structure={"text": text},
    )
    session.add(document)
    await session.flush()

    chunks = _chunk_text(document.id, text)
    session.add_all(chunks)
    corpus.document_count = await _document_count(session, corpus.id)
    corpus.indexed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(document)
    return {
        "id": document_id,
        "corpus_id": corpus_id,
        "title": document.title,
        "source_uri": document.source_uri,
        "chunk_count": len(chunks),
    }


async def search(session: AsyncSession, corpus_id: str, query: str, k: int = 8) -> list[dict[str, Any]]:
    corpus = await _find_corpus(session, corpus_id)
    if corpus is None:
        raise KeyError(corpus_id)

    result = await session.execute(
        select(DocumentChunk, Document)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(Document.corpus_id == corpus.id)
    )
    terms = {term.lower() for term in query.split() if term.strip()}
    scored = []
    for chunk, document in result.all():
        text = chunk.text.lower()
        score = sum(1 for term in terms if term in text) / max(len(terms), 1)
        scored.append(
            {
                "id": f"chk_{chunk.id.hex[:12]}",
                "document_id": _external_id(document.urn, DOCUMENT_URN_PREFIX),
                "ord": chunk.ord,
                "text": chunk.text,
                "citation_path": chunk.citation_path,
                "score": score,
            }
        )
    return sorted(scored, key=lambda item: item["score"], reverse=True)[:k]


async def _find_corpus(session: AsyncSession, corpus_id: str) -> Corpus | None:
    await ensure_corpora(session)
    filters = [Corpus.urn == _corpus_urn(corpus_id)]
    try:
        filters.append(Corpus.id == UUID(corpus_id))
    except ValueError:
        pass
    result = await session.execute(select(Corpus).where(or_(*filters)))
    return result.scalar_one_or_none()


async def _document_count(session: AsyncSession, corpus_id: UUID) -> int:
    return (
        await session.scalar(select(func.count(Document.id)).where(Document.corpus_id == corpus_id))
    ) or 0


def _corpus_to_api(corpus: Corpus) -> dict[str, Any]:
    corpus_id = _external_id(corpus.urn, CORPUS_URN_PREFIX)
    fixture = CORPORA.get(corpus_id, {})
    return {
        "id": corpus_id,
        "urn": corpus.urn,
        "name": corpus.name,
        "description": fixture.get("description", f"{corpus.name} corpus for governed retrieval."),
        "kind": corpus.kind,
        "version": "2026.04",
        "document_count": corpus.document_count,
        "indexed_at": corpus.indexed_at.isoformat() if corpus.indexed_at else None,
    }


def _document_to_api(document: Document, corpus_id: str, chunk_count: int) -> dict[str, Any]:
    return {
        "id": _external_id(document.urn, DOCUMENT_URN_PREFIX),
        "corpus_id": corpus_id,
        "source_uri": document.source_uri,
        "content_hash": document.content_hash,
        "title": document.title,
        "citation": document.citation,
        "framework": document.framework,
        "jurisdiction": document.jurisdiction,
        "sector": document.sector,
        "text_path": document.text_path,
        "parsed_structure": document.parsed_structure,
        "chunk_count": chunk_count,
    }


def _chunk_text(document_id: UUID, text: str) -> list[DocumentChunk]:
    blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
    return [
        DocumentChunk(
            document_id=document_id,
            ord=index,
            text=block,
            keyword_tokens=sorted({term.lower() for term in block.split() if term.strip()}),
            citation_path=f"paragraph {index + 1}",
        )
        for index, block in enumerate(blocks)
    ]
