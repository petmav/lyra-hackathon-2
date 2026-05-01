from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import json

from praetor_api.db import AsyncSessionLocal
from praetor_api.services.demo_state import SANDBOX_RUNS, ensure_demo_state
from praetor_api.services import production_reviews
from praetor_api.settings import get_settings

router = APIRouter(tags=["sandbox"])


@router.get("/sandbox-runs")
async def sandbox_runs() -> list[dict]:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            return await production_reviews.list_sandbox_runs(session)
    ensure_demo_state()
    return list(SANDBOX_RUNS.values())


@router.get("/sandbox-runs/{sandbox_id}")
async def sandbox_run(sandbox_id: str) -> dict:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            found = await production_reviews.get_sandbox_run(session, sandbox_id)
        if found is None:
            raise HTTPException(status_code=404, detail="sandbox run not found")
        return found

    ensure_demo_state()
    found = SANDBOX_RUNS.get(sandbox_id)
    if found is None:
        raise HTTPException(status_code=404, detail="sandbox run not found")
    return found


@router.get("/sandbox-runs/{sandbox_id}/logs")
async def sandbox_run_logs(sandbox_id: str) -> StreamingResponse:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            chunks = await production_reviews.sandbox_logs(session, sandbox_id)
        if chunks is None:
            raise HTTPException(status_code=404, detail="sandbox run not found")
    else:
        ensure_demo_state()
        found = SANDBOX_RUNS.get(sandbox_id)
        if found is None:
            raise HTTPException(status_code=404, detail="sandbox run not found")
        result = found.get("result", {})
        logs = result.get("logs", {}) if isinstance(result, dict) else {}
        chunks = [
            {"stream": stream, "index": index, "line": line}
            for stream, text in (logs if isinstance(logs, dict) else {}).items()
            if isinstance(text, str)
            for index, line in enumerate(text.splitlines())
        ]

    async def stream():
        for chunk in chunks:
            yield json.dumps(chunk) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")
