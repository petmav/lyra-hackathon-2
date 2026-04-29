from fastapi import APIRouter, HTTPException

from praetor_api.db import AsyncSessionLocal
from praetor_api.services.demo_state import FINDINGS, create_demo_finding, ensure_demo_state
from praetor_api.services import production_reviews
from praetor_api.settings import get_settings

router = APIRouter(tags=["findings"])


@router.get("/findings")
async def findings() -> list[dict]:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            return await production_reviews.list_findings(session)
    ensure_demo_state()
    return list(FINDINGS.values())


@router.get("/findings/{finding_id}")
async def finding(finding_id: str) -> dict:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            found = await production_reviews.get_finding(session, finding_id)
        if found is None:
            raise HTTPException(status_code=404, detail="finding not found")
        return found

    ensure_demo_state()
    found = FINDINGS.get(finding_id)
    if found is None:
        raise HTTPException(status_code=404, detail="finding not found")
    return found


@router.post("/findings/{finding_id}:accept")
@router.post("/findings/{finding_id}/accept")
async def accept(finding_id: str) -> dict:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            found = await production_reviews.set_finding_status(session, finding_id, "accepted")
        if not found:
            raise HTTPException(status_code=404, detail="finding not found")
        return {"ok": True}

    ensure_demo_state()
    if finding_id not in FINDINGS:
        raise HTTPException(status_code=404, detail="finding not found")
    FINDINGS[finding_id]["status"] = "accepted"
    return {"ok": True}


@router.post("/findings/{finding_id}:reject")
@router.post("/findings/{finding_id}/reject")
async def reject(finding_id: str) -> dict:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            found = await production_reviews.set_finding_status(session, finding_id, "rejected")
        if not found:
            raise HTTPException(status_code=404, detail="finding not found")
        return {"ok": True}

    ensure_demo_state()
    if finding_id not in FINDINGS:
        raise HTTPException(status_code=404, detail="finding not found")
    FINDINGS[finding_id]["status"] = "rejected"
    return {"ok": True}
