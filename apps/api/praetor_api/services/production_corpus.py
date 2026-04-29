from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from praetor_api.models.corpus import Corpus
from praetor_api.models.document import Document
from praetor_api.models.document_chunk import DocumentChunk
from praetor_api.services.corpus_index import CORPORA

CORPUS_URN_PREFIX = "urn:praetor:corpus:"
DOCUMENT_URN_PREFIX = "urn:praetor:document:"
PACKAGE_ROOT = Path(__file__).resolve().parents[1]

CORPUS_KINDS = {
    "regulation",
    "standard",
    "internal_policy",
    "code_repo",
    "process_artefact",
    "evidence_reference",
}

ARTIFACT_ROOT = Path("artifacts/corpora")


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "corpus"


def _extract_text(filename: str, media_type: str | None, binary: bytes) -> str:
    """Best-effort text extraction. Decode UTF-8 for text-like files, return
    empty text for binary documents (PDFs, etc.) — the binary is still stored
    so the workflow runtime can mount it into the sandbox."""
    lower = filename.lower()
    if (media_type and media_type.startswith("text/")) or any(
        lower.endswith(ext) for ext in (".txt", ".md", ".markdown", ".csv", ".json", ".yaml", ".yml")
    ):
        try:
            return binary.decode("utf-8")
        except UnicodeDecodeError:
            return binary.decode("utf-8", errors="replace")
    return ""


def _corpus_urn(corpus_id: str) -> str:
    return f"{CORPUS_URN_PREFIX}{corpus_id}"


def _document_urn(document_id: str) -> str:
    return f"{DOCUMENT_URN_PREFIX}{document_id}"


def _external_id(urn: str, prefix: str) -> str:
    return urn.removeprefix(prefix)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _root_content_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "content"
        if candidate.exists():
            return candidate
    return Path.cwd() / "content"


SEED_DIRS = [
    _root_content_dir() / "corpora_seed",
    PACKAGE_ROOT / "seed_content" / "corpora_seed",
]


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
    seeded = await seed_corpora(session)
    seeded_urns = {row.urn for row in seeded}
    extra_result = await session.execute(
        select(Corpus).where(Corpus.urn.notin_(seeded_urns)).order_by(Corpus.created_at)
    )
    extras = list(extra_result.scalars().all())
    corpora = [*seeded, *extras]
    for corpus in corpora:
        corpus.document_count = await _document_count(session, corpus.id)
    await session.commit()
    return [_corpus_to_api(corpus) for corpus in corpora]


async def get_corpus(session: AsyncSession, corpus_id: str) -> dict[str, Any] | None:
    await seed_corpora(session)
    corpus = await _find_corpus(session, corpus_id)
    if corpus is None:
        return None
    corpus.document_count = await _document_count(session, corpus.id)
    await session.commit()
    return _corpus_to_api(corpus)


async def list_documents(session: AsyncSession, corpus_id: str) -> list[dict[str, Any]]:
    await seed_corpora(session)
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
    existing_result = await session.execute(
        select(Document)
        .where(Document.corpus_id == corpus.id, Document.source_uri == source_uri)
        .order_by(Document.created_at)
    )
    existing_documents = list(existing_result.scalars().all())
    existing = existing_documents[0] if existing_documents else None
    if existing is not None:
        for duplicate in existing_documents[1:]:
            await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == duplicate.id))
            await session.delete(duplicate)
        if existing.content_hash != digest:
            existing.content_hash = digest
            existing.title = title
            existing.parsed_structure = {"text": text}
            existing.framework = corpus.kind
            await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == existing.id))
            chunks = _chunk_text(existing.id, text)
            session.add_all(chunks)
        else:
            chunks_result = await session.execute(
                select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == existing.id)
            )
            chunk_count = int(chunks_result.scalar_one() or 0)
            return {
                "id": _external_id(existing.urn, DOCUMENT_URN_PREFIX),
                "corpus_id": corpus_id,
                "title": existing.title,
                "source_uri": existing.source_uri,
                "chunk_count": chunk_count,
            }
        corpus.document_count = await _document_count(session, corpus.id)
        corpus.indexed_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(existing)
        return {
            "id": _external_id(existing.urn, DOCUMENT_URN_PREFIX),
            "corpus_id": corpus_id,
            "title": existing.title,
            "source_uri": existing.source_uri,
            "chunk_count": len(chunks),
        }

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
    await seed_corpora(session)
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


async def seed_corpora(session: AsyncSession) -> list[Corpus]:
    corpora = await ensure_corpora(session)
    for seed_file in _seed_files():
        corpus_id = _corpus_id_for_seed(seed_file)
        if corpus_id not in CORPORA:
            continue
        text = seed_file.read_text(encoding="utf-8").strip()
        if not text:
            continue
        await ingest_document(
            session,
            corpus_id,
            _title_from_markdown(text, CORPORA[corpus_id]["name"]),
            f"seed://corpora/{seed_file.name}",
            text,
        )
    return corpora


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
    description = corpus.description or fixture.get("description") or f"{corpus.name} corpus for governed retrieval."
    return {
        "id": corpus_id,
        "urn": corpus.urn,
        "name": corpus.name,
        "description": description,
        "kind": corpus.kind,
        "framework": corpus.framework,
        "jurisdiction": corpus.jurisdiction,
        "retention": corpus.retention,
        "source_url": corpus.source_url,
        "version": "2026.04",
        "document_count": corpus.document_count,
        "indexed_at": corpus.indexed_at.isoformat() if corpus.indexed_at else None,
    }


async def create_corpus(session: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    kind = str(payload.get("kind") or "internal_policy")
    if kind not in CORPUS_KINDS:
        raise ValueError(f"kind must be one of {sorted(CORPUS_KINDS)}")
    explicit_id = payload.get("id")
    corpus_id = _slugify(str(explicit_id)) if explicit_id else _slugify(name)
    urn = _corpus_urn(corpus_id)
    existing = await session.execute(select(Corpus).where(Corpus.urn == urn))
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"corpus '{corpus_id}' already exists")
    corpus = Corpus(
        urn=urn,
        name=name,
        kind=kind,
        description=str(payload.get("description") or "").strip() or None,
        framework=(payload.get("framework") or None) and str(payload["framework"]),
        jurisdiction=(payload.get("jurisdiction") or None) and str(payload["jurisdiction"]),
        retention=(payload.get("retention") or None) and str(payload["retention"]),
        source_url=(payload.get("source_url") or None) and str(payload["source_url"]),
        document_count=0,
        indexed_at=None,
    )
    session.add(corpus)
    await session.commit()
    await session.refresh(corpus)
    return _corpus_to_api(corpus)


async def delete_corpus(session: AsyncSession, corpus_id: str) -> bool:
    corpus = await _find_corpus(session, corpus_id)
    if corpus is None:
        return False
    docs_result = await session.execute(select(Document.id).where(Document.corpus_id == corpus.id))
    document_ids = [row for row in docs_result.scalars().all()]
    if document_ids:
        await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id.in_(document_ids)))
        await session.execute(delete(Document).where(Document.id.in_(document_ids)))
    await session.delete(corpus)
    await session.commit()
    return True


async def upload_document(
    session: AsyncSession,
    corpus_id: str,
    *,
    filename: str,
    media_type: str | None,
    binary: bytes,
) -> dict[str, Any]:
    corpus = await _find_corpus(session, corpus_id)
    if corpus is None:
        raise KeyError(corpus_id)
    external_id = _external_id(corpus.urn, CORPUS_URN_PREFIX)
    document_id = f"doc_{uuid4().hex[:12]}"
    storage_dir = ARTIFACT_ROOT / external_id
    storage_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix or ""
    binary_path = storage_dir / f"{document_id}{suffix}"
    binary_path.write_bytes(binary)
    text = _extract_text(filename, media_type, binary)
    digest = _hash_text(f"upload://{filename}\n{len(binary)}\n{text}")
    document = Document(
        urn=_document_urn(document_id),
        corpus_id=corpus.id,
        source_uri=f"upload://{filename}",
        content_hash=digest,
        title=Path(filename).stem.replace("_", " ") or filename,
        citation=None,
        framework=corpus.framework or corpus.kind,
        jurisdiction=corpus.jurisdiction,
        sector=None,
        text_path=str(binary_path.as_posix()),
        binary_path=str(binary_path.as_posix()),
        media_type=media_type or "application/octet-stream",
        size_bytes=len(binary),
        parsed_structure={"text": text, "filename": filename},
    )
    session.add(document)
    await session.flush()
    chunks = _chunk_text(document.id, text) if text.strip() else []
    if chunks:
        session.add_all(chunks)
    corpus.document_count = await _document_count(session, corpus.id)
    corpus.indexed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(document)
    chunk_count = len(chunks)
    return _document_to_api(document, external_id, chunk_count)


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
        "binary_path": document.binary_path,
        "media_type": document.media_type,
        "size_bytes": document.size_bytes,
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


def _seed_files() -> list[Path]:
    files: dict[str, Path] = {}
    for directory in SEED_DIRS:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            files[path.name] = path
    return list(files.values())


def _title_from_markdown(text: str, fallback: str) -> str:
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if first.startswith("#"):
        return first.lstrip("#").strip() or fallback
    return fallback


def _corpus_id_for_seed(path: Path) -> str:
    if path.stem == "iso_42001_excerpt":
        return "iso_42001"
    return path.stem
