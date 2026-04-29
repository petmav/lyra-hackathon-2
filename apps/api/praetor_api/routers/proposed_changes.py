from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from praetor_api.db import AsyncSessionLocal
from praetor_api.services.demo_state import (
    PROPOSED_CHANGES,
    create_sandbox_run,
    ensure_demo_state,
    now,
)
from praetor_api.services import production_reviews
from praetor_api.settings import get_settings

router = APIRouter(tags=["proposed-changes"])


class ApplyChangeRequest(BaseModel):
    hook_id: str | None = None
    operation: str | None = None
    inputs: dict = Field(default_factory=dict)
    dry_run: bool = True


@router.get("/proposed-changes")
async def proposed_changes() -> list[dict]:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            return await production_reviews.list_proposed_changes(session)
    ensure_demo_state()
    return list(PROPOSED_CHANGES.values())


@router.get("/proposed-changes/{change_id}")
async def proposed_change(change_id: str) -> dict:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            found = await production_reviews.get_proposed_change(session, change_id)
        if found is None:
            raise HTTPException(status_code=404, detail="proposed change not found")
        return found

    ensure_demo_state()
    found = PROPOSED_CHANGES.get(change_id)
    if found is None:
        raise HTTPException(status_code=404, detail="proposed change not found")
    return found


@router.post("/proposed-changes/{change_id}:sandbox-run")
@router.post("/proposed-changes/{change_id}/sandbox-run")
async def sandbox_run(change_id: str) -> dict:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            sandbox = await production_reviews.create_sandbox_run(session, change_id)
        if sandbox is None:
            raise HTTPException(status_code=404, detail="proposed change not found")
        return sandbox

    ensure_demo_state()
    if change_id not in PROPOSED_CHANGES:
        raise HTTPException(status_code=404, detail="proposed change not found")
    return create_sandbox_run(change_id)


@router.post("/proposed-changes/{change_id}:approve")
@router.post("/proposed-changes/{change_id}/approve")
async def approve(change_id: str) -> dict:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            found = await production_reviews.approve_change(session, change_id)
        if not found:
            raise HTTPException(status_code=404, detail="proposed change not found")
        return {"ok": True}

    ensure_demo_state()
    if change_id not in PROPOSED_CHANGES:
        raise HTTPException(status_code=404, detail="proposed change not found")
    PROPOSED_CHANGES[change_id]["status"] = "approved"
    PROPOSED_CHANGES[change_id]["approver"] = "demo-analyst"
    return {"ok": True}


@router.post("/proposed-changes/{change_id}:apply")
@router.post("/proposed-changes/{change_id}/apply")
async def apply(change_id: str, request: ApplyChangeRequest | None = None) -> dict:
    request = request or ApplyChangeRequest()
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            result = await production_reviews.apply_change(
                session,
                change_id,
                hook_id=request.hook_id,
                operation=request.operation,
                inputs=request.inputs,
                dry_run=request.dry_run,
            )
        if result is None:
            raise HTTPException(status_code=404, detail="proposed change not found")
        if result.get("ok") is False:
            raise HTTPException(status_code=409, detail=result)
        return result

    ensure_demo_state()
    if change_id not in PROPOSED_CHANGES:
        raise HTTPException(status_code=404, detail="proposed change not found")
    PROPOSED_CHANGES[change_id]["status"] = "applied"
    PROPOSED_CHANGES[change_id]["applied_at"] = now()
    return {"ok": True, "pr_url": "https://github.example/northwind/support-bot/pull/42"}
