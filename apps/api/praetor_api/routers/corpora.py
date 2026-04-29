from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from praetor_api.db import AsyncSessionLocal
from praetor_api.services.corpus_index import (
    CORPORA,
    create_demo_corpus,
    delete_demo_corpus,
    ingest_document,
    search,
    upload_demo_document,
)
from praetor_api.services import production_corpus
from praetor_api.settings import get_settings

router = APIRouter(tags=["corpora"])


class IngestDocumentRequest(BaseModel):
    title: str
    source_uri: str
    text: str


class SearchRequest(BaseModel):
    query: str
    k: int = Field(default=8, ge=1, le=50)


class CorpusCreateRequest(BaseModel):
    name: str
    kind: str = "internal_policy"
    description: str | None = None
    framework: str | None = None
    jurisdiction: str | None = None
    retention: str | None = None
    source_url: str | None = None
    id: str | None = None


@router.get("/corpora")
async def list_corpora() -> list[dict]:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            return await production_corpus.list_corpora(session)
    return [_demo_corpus_to_api(corpus_id, row) for corpus_id, row in CORPORA.items()]


@router.get("/corpora/{corpus_id}")
async def get_corpus(corpus_id: str) -> dict:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            found = await production_corpus.get_corpus(session, corpus_id)
        if found is None:
            raise HTTPException(status_code=404, detail="corpus not found")
        return found

    found = CORPORA.get(corpus_id)
    if found is None:
        raise HTTPException(status_code=404, detail="corpus not found")
    return _demo_corpus_to_api(corpus_id, found)


@router.get("/corpora/{corpus_id}/documents")
async def list_documents(corpus_id: str) -> list[dict]:
    if get_settings().data_mode == "production":
        try:
            async with AsyncSessionLocal() as session:
                return await production_corpus.list_documents(session, corpus_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="corpus not found") from None

    if corpus_id not in CORPORA:
        raise HTTPException(status_code=404, detail="corpus not found")
    return []


@router.post("/corpora/{corpus_id}/documents:ingest")
@router.post("/corpora/{corpus_id}/documents/ingest")
async def ingest(corpus_id: str, request: IngestDocumentRequest) -> dict:
    try:
        if get_settings().data_mode == "production":
            async with AsyncSessionLocal() as session:
                return await production_corpus.ingest_document(
                    session,
                    corpus_id,
                    request.title,
                    request.source_uri,
                    request.text,
                )
        return ingest_document(corpus_id, request.title, request.source_uri, request.text)
    except KeyError:
        raise HTTPException(status_code=404, detail="corpus not found") from None


@router.post("/corpora/{corpus_id}:search")
@router.post("/corpora/{corpus_id}/search")
async def search_corpus(corpus_id: str, request: SearchRequest) -> list[dict]:
    if get_settings().data_mode == "production":
        try:
            async with AsyncSessionLocal() as session:
                return await production_corpus.search(session, corpus_id, request.query, request.k)
        except KeyError:
            raise HTTPException(status_code=404, detail="corpus not found") from None

    if corpus_id not in CORPORA:
        raise HTTPException(status_code=404, detail="corpus not found")
    return search(corpus_id, request.query, request.k)


def _demo_corpus_to_api(corpus_id: str, row: dict) -> dict:
    return {
        "id": corpus_id,
        "urn": f"urn:praetor:corpus:{corpus_id}",
        "name": row["name"],
        "description": row.get("description") or f"{row['name']} corpus for governed retrieval.",
        "kind": row["kind"],
        "framework": row.get("framework"),
        "jurisdiction": row.get("jurisdiction"),
        "retention": row.get("retention"),
        "source_url": row.get("source_url"),
        "version": row.get("version", "2026.04"),
        "document_count": row.get("document_count", 0),
        "indexed_at": row.get("indexed_at"),
    }


@router.post("/corpora", status_code=201)
async def create_corpus(request: CorpusCreateRequest) -> dict:
    payload = request.model_dump(exclude_none=True)
    try:
        if get_settings().data_mode == "production":
            async with AsyncSessionLocal() as session:
                return await production_corpus.create_corpus(session, payload)
        record = create_demo_corpus(payload)
        return _demo_corpus_to_api(record["id"], record)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.delete("/corpora/{corpus_id}", status_code=204)
async def delete_corpus(corpus_id: str) -> None:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            ok = await production_corpus.delete_corpus(session, corpus_id)
    else:
        ok = delete_demo_corpus(corpus_id)
    if not ok:
        raise HTTPException(status_code=404, detail="corpus not found")
    return None


@router.post("/corpora/{corpus_id}/documents:upload")
@router.post("/corpora/{corpus_id}/documents/upload")
async def upload_document(corpus_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    binary = await file.read()
    if not binary:
        raise HTTPException(status_code=422, detail="uploaded file is empty")
    try:
        if get_settings().data_mode == "production":
            async with AsyncSessionLocal() as session:
                return await production_corpus.upload_document(
                    session,
                    corpus_id,
                    filename=file.filename or "uploaded",
                    media_type=file.content_type,
                    binary=binary,
                )
        return upload_demo_document(
            corpus_id,
            filename=file.filename or "uploaded",
            media_type=file.content_type,
            binary=binary,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="corpus not found") from None
