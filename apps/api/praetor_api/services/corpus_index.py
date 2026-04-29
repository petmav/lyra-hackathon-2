from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class Chunk:
    id: str
    document_id: str
    ord: int
    text: str
    citation_path: str
    score: float = 0.0


@dataclass
class Document:
    id: str
    corpus_id: str
    title: str
    source_uri: str
    text: str
    chunks: list[Chunk] = field(default_factory=list)


CORPORA: dict[str, dict[str, Any]] = {
    "internal_data_min": {
        "id": "internal_data_min",
        "name": "Internal data minimisation policy",
        "kind": "internal_policy",
        "version": "2026.04",
        "document_count": 0,
    },
    "iso_42001": {
        "id": "iso_42001",
        "name": "ISO 42001 excerpt",
        "kind": "standard",
        "version": "2026.04",
        "document_count": 0,
    },
}
DOCUMENTS: dict[str, Document] = {}


def chunk_markdown(document_id: str, text: str) -> list[Chunk]:
    blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
    return [
        Chunk(
            id=f"chk_{uuid4().hex[:12]}",
            document_id=document_id,
            ord=index,
            text=block,
            citation_path=f"paragraph {index + 1}",
        )
        for index, block in enumerate(blocks)
    ]


def ingest_document(corpus_id: str, title: str, source_uri: str, text: str) -> dict[str, Any]:
    if corpus_id not in CORPORA:
        raise KeyError(corpus_id)

    document = Document(
        id=f"doc_{uuid4().hex[:12]}",
        corpus_id=corpus_id,
        title=title,
        source_uri=source_uri,
        text=text,
    )
    document.chunks = chunk_markdown(document.id, text)
    DOCUMENTS[document.id] = document
    CORPORA[corpus_id]["document_count"] = sum(
        1 for candidate in DOCUMENTS.values() if candidate.corpus_id == corpus_id
    )
    return serialize_document(document)


def search(corpus_id: str, query: str, k: int = 8) -> list[dict[str, Any]]:
    terms = {term.lower() for term in query.split() if term.strip()}
    chunks = [
        chunk
        for document in DOCUMENTS.values()
        if document.corpus_id == corpus_id
        for chunk in document.chunks
    ]
    for chunk in chunks:
        text = chunk.text.lower()
        chunk.score = sum(1 for term in terms if term in text) / max(len(terms), 1)
    return [serialize_chunk(chunk) for chunk in sorted(chunks, key=lambda item: item.score, reverse=True)[:k]]


def serialize_document(document: Document) -> dict[str, Any]:
    return {
        "id": document.id,
        "corpus_id": document.corpus_id,
        "title": document.title,
        "source_uri": document.source_uri,
        "chunk_count": len(document.chunks),
    }


def serialize_chunk(chunk: Chunk) -> dict[str, Any]:
    return {
        "id": chunk.id,
        "document_id": chunk.document_id,
        "ord": chunk.ord,
        "text": chunk.text,
        "citation_path": chunk.citation_path,
        "score": chunk.score,
    }
