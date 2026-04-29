from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from praetor_api.db import AsyncSessionLocal
from praetor_api.services.corpus_index import CORPORA, ingest_document, search
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
        "description": row.get("description", f"{row['name']} corpus for governed retrieval."),
        "kind": row["kind"],
        "version": row.get("version", "2026.04"),
        "document_count": row.get("document_count", 0),
        "indexed_at": row.get("indexed_at"),
    }
