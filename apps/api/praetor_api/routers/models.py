import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from praetor_api.services.model_providers import (
    ModelProviderError,
    check_provider,
    complete,
    list_providers,
    stream_complete,
)

router = APIRouter(tags=["models"])


class CompletionRequest(BaseModel):
    prompt: str
    system: str | None = None
    provider: str | None = None
    model: str | None = None
    dry_run: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelCheckRequest(BaseModel):
    provider: str | None = None
    model: str | None = None
    live: bool = False


@router.get("/models/providers")
async def providers() -> list[dict[str, Any]]:
    return list_providers()


@router.get("/models/readiness")
async def model_readiness() -> dict[str, Any]:
    return {"providers": list_providers()}


@router.post("/models:check")
@router.post("/models/check")
async def model_check(request: ModelCheckRequest) -> dict[str, Any]:
    try:
        return await check_provider(
            provider=request.provider,
            model=request.model,
            live=request.live,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown provider: {exc.args[0]}") from None


@router.post("/models:complete")
@router.post("/models/complete")
async def model_complete(request: CompletionRequest) -> dict[str, Any]:
    try:
        return await complete(
            request.prompt,
            provider=request.provider,
            model=request.model,
            system=request.system,
            dry_run=request.dry_run,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown provider: {exc.args[0]}") from None
    except ModelProviderError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.post("/models:stream")
@router.post("/models/stream")
async def model_stream(request: CompletionRequest) -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        try:
            async for event in stream_complete(
                request.prompt,
                provider=request.provider,
                model=request.model,
                system=request.system,
                dry_run=request.dry_run,
            ):
                yield _sse(event["type"], event)
        except ModelProviderError as exc:
            yield _sse(
                "error",
                {
                    "type": "error",
                    "provider": exc.provider,
                    "model": exc.model,
                    "error": str(exc),
                    "status_code": exc.status_code or 502,
                },
            )
        except KeyError as exc:
            yield _sse("error", {"type": "error", "error": f"unknown provider: {exc.args[0]}"})
        except RuntimeError as exc:
            yield _sse("error", {"type": "error", "error": str(exc)})

    return StreamingResponse(events(), media_type="text/event-stream")


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"
