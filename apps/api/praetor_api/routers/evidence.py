from fastapi import APIRouter

from praetor_api.db import AsyncSessionLocal
from praetor_api.services.demo_state import (
    AUDIT_PACKETS,
    EVIDENCE_RECORDS,
    ensure_demo_state,
    generate_evidence,
    now,
)
from praetor_api.services import production_reviews
from praetor_api.settings import get_settings

router = APIRouter(tags=["evidence"])


@router.get("/evidence-records")
async def evidence_records() -> list[dict]:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            await production_reviews.consume_evidence_events(session)
            return await production_reviews.list_evidence_records(session)

    ensure_demo_state()
    if not EVIDENCE_RECORDS:
        generate_evidence()
    return list(EVIDENCE_RECORDS.values())


@router.post("/evidence-records:sweep")
@router.post("/evidence-records/sweep")
async def sweep_evidence_records() -> dict:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            result = await production_reviews.consume_evidence_events(session)
        return {"ok": True, "created": result["count"], "checkpoint": result["checkpoint"]}

    ensure_demo_state()
    before = len(EVIDENCE_RECORDS)
    if not EVIDENCE_RECORDS:
        generate_evidence()
    return {"ok": True, "created": len(EVIDENCE_RECORDS) - before}


@router.post("/evidence-records:consume")
@router.post("/evidence-records/consume")
async def consume_evidence_records() -> dict:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            result = await production_reviews.consume_evidence_events(session)
        return {"ok": True, **result}

    ensure_demo_state()
    before = len(EVIDENCE_RECORDS)
    if not EVIDENCE_RECORDS:
        generate_evidence()
    return {"ok": True, "created": len(EVIDENCE_RECORDS) - before, "count": len(EVIDENCE_RECORDS) - before}


@router.post("/audit-packets:generate")
@router.post("/audit-packets/generate")
async def generate_audit_packet() -> dict:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            return await production_reviews.generate_audit_packet(session)

    ensure_demo_state()
    if not EVIDENCE_RECORDS:
        generate_evidence()
    packet_id = f"pkt_{len(AUDIT_PACKETS) + 1:03d}"
    packet = {
        "id": packet_id,
        "period_start": now(),
        "period_end": now(),
        "scope": {"tenant": "demo", "surfaces": ["workflow", "supervision"]},
        "pdf_path": f"memory://audit-packets/{packet_id}.pdf",
        "json_sidecar_path": f"memory://audit-packets/{packet_id}.json",
        "packet_hash": "a" * 64,
        "signature": "demo-signature",
    }
    AUDIT_PACKETS[packet_id] = packet
    return packet
