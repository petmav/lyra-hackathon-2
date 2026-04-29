from typing import Any

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

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


class AuditPacketGenerateRequest(BaseModel):
    label: str | None = None
    asset_ids: list[str] = Field(default_factory=list)
    workflow_run_ids: list[str] = Field(default_factory=list)
    obligation_urns: list[str] = Field(default_factory=list)


def _demo_packet(packet: dict) -> dict:
    return {**packet, "status": packet.get("status", "ready"), "generated_at": packet.get("generated_at", packet.get("period_end"))}


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


@router.get("/audit-packets")
async def list_audit_packets() -> list[dict]:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            return await production_reviews.list_audit_packets(session)
    ensure_demo_state()
    return [_demo_packet(p) for p in AUDIT_PACKETS.values()]


@router.get("/audit-packets/{packet_id}")
async def get_audit_packet(packet_id: str) -> dict:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            packet = await production_reviews.get_audit_packet(session, packet_id)
        if packet is None:
            raise HTTPException(status_code=404, detail="audit packet not found")
        return packet
    ensure_demo_state()
    packet = AUDIT_PACKETS.get(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="audit packet not found")
    return _demo_packet(packet)


@router.post("/audit-packets:generate")
@router.post("/audit-packets/generate")
async def generate_audit_packet(payload: AuditPacketGenerateRequest = Body(default=None)) -> dict:
    scope: dict[str, Any] = {}
    if payload is not None:
        if payload.label:
            scope["label"] = payload.label
        if payload.asset_ids:
            scope["asset_ids"] = payload.asset_ids
        if payload.workflow_run_ids:
            scope["workflow_run_ids"] = payload.workflow_run_ids
        if payload.obligation_urns:
            scope["obligation_urns"] = payload.obligation_urns

    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            return await production_reviews.generate_audit_packet(session, scope=scope)

    ensure_demo_state()
    if not EVIDENCE_RECORDS:
        generate_evidence()
    packet_id = f"pkt_{len(AUDIT_PACKETS) + 1:03d}"
    base_scope = {"tenant": "demo", "surfaces": ["workflow", "supervision"]}
    packet = {
        "id": packet_id,
        "period_start": now(),
        "period_end": now(),
        "scope": {**base_scope, **scope},
        "pdf_path": f"memory://audit-packets/{packet_id}.pdf",
        "json_sidecar_path": f"memory://audit-packets/{packet_id}.json",
        "packet_hash": "a" * 64,
        "signature": "demo-signature",
    }
    AUDIT_PACKETS[packet_id] = packet
    return packet
