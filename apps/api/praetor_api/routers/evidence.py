import json
import random
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import FileResponse
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

DEMO_ARTIFACT_ROOT = Path("artifacts/demo_audit_packets")

router = APIRouter(tags=["evidence"])


def _randomised_packet_counts(period_days: int, surfaces: list[str]) -> dict[str, int]:
    """Plausible per-period activity counts so each generated packet looks
    different but stays internally consistent — findings track workflow runs,
    proposed changes track findings, supervision-only packets zero workflow
    counts, etc.
    """
    rng = random.Random()  # entropy from os, varies per generation
    span = max(1, period_days)
    has_workflow = "workflow" in surfaces
    has_supervision = "supervision" in surfaces

    if has_workflow:
        runs_per_day = rng.uniform(2.4, 3.6)
        workflow_runs = max(3, int(runs_per_day * span + rng.gauss(0, span * 0.4)))
    else:
        workflow_runs = 0
    findings = int(workflow_runs * rng.uniform(0.18, 0.32))
    proposed_changes = int(findings * rng.uniform(0.55, 0.78))
    if has_supervision:
        supervision_events = max(2, int(rng.uniform(4.0, 6.5) * span + rng.gauss(0, span * 0.3)))
    else:
        supervision_events = 0
    evidence_records = int(
        (workflow_runs * rng.uniform(1.4, 2.1))
        + (supervision_events * rng.uniform(0.6, 0.9))
    ) + rng.randint(0, 6)
    return {
        "workflow_runs": workflow_runs,
        "findings": findings,
        "proposed_changes": proposed_changes,
        "supervision_events": supervision_events,
        "evidence_records": max(1, evidence_records),
    }


def _write_demo_packet_artifacts(packet_id: str, sidecar: dict[str, Any]) -> tuple[str, str, str, str]:
    """Hash + sign + write the PDF/JSON pair to disk. Returns (pdf_path, sidecar_path, hash, signature)."""
    packet_hash = production_reviews._hash(sidecar)
    signature = production_reviews._sign(packet_hash)
    DEMO_ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = DEMO_ARTIFACT_ROOT / f"{packet_id}.json"
    pdf_path = DEMO_ARTIFACT_ROOT / f"{packet_id}.pdf"
    json_path.write_text(
        json.dumps({**sidecar, "packet_hash": packet_hash}, indent=2, default=str),
        encoding="utf-8",
    )
    pdf_path.write_bytes(
        production_reviews._minimal_pdf(
            f"Praetor Audit Packet {packet_id}\nHash: {packet_hash}"
        )
    )
    return str(pdf_path.as_posix()), str(json_path.as_posix()), packet_hash, signature


def seed_demo_audit_packets() -> None:
    """Populate the audit-packet ledger with a multi-day history.

    Demonstrates: a 7-day workflow-only packet from yesterday, a 30-day
    full-surface packet from 9 days ago, a 90-day quarterly packet from 35
    days ago, and a queued one currently generating.
    """
    if AUDIT_PACKETS:
        return
    from datetime import UTC, datetime, timedelta

    now_dt = datetime.now(UTC)
    base_surfaces = ["workflow", "supervision"]

    history = [
        {
            "id": "pkt_2026q2_7d_workflow",
            "generated_offset_days": 1.0,
            "span_days": 7,
            "surfaces": ["workflow"],
            "label": "7d · workflow_only",
            "counts": {
                "workflow_runs": 18,
                "findings": 4,
                "proposed_changes": 3,
                "supervision_events": 0,
                "evidence_records": 22,
            },
        },
        {
            "id": "pkt_2026q2_30d_all",
            "generated_offset_days": 9.0,
            "span_days": 30,
            "surfaces": base_surfaces,
            "label": "30d · all surfaces",
            "counts": {
                "workflow_runs": 71,
                "findings": 19,
                "proposed_changes": 12,
                "supervision_events": 47,
                "evidence_records": 128,
            },
        },
        {
            "id": "pkt_2026q1_90d_quarterly",
            "generated_offset_days": 35.0,
            "span_days": 90,
            "surfaces": base_surfaces,
            "label": "90d · quarterly close",
            "counts": {
                "workflow_runs": 214,
                "findings": 58,
                "proposed_changes": 41,
                "supervision_events": 152,
                "evidence_records": 396,
            },
        },
        {
            "id": "pkt_2026q1_14d_supervision",
            "generated_offset_days": 18.0,
            "span_days": 14,
            "surfaces": ["supervision"],
            "label": "14d · supervision_only",
            "counts": {
                "workflow_runs": 0,
                "findings": 6,
                "proposed_changes": 2,
                "supervision_events": 41,
                "evidence_records": 33,
            },
        },
    ]

    for entry in history:
        end_dt = now_dt - timedelta(days=entry["generated_offset_days"])
        start_dt = end_dt - timedelta(days=entry["span_days"])
        sidecar = {
            "id": entry["id"],
            "period_start": start_dt.isoformat(),
            "period_end": end_dt.isoformat(),
            "scope": {"tenant": "demo", "surfaces": entry["surfaces"], "label": entry["label"]},
            "evidence_records": list(EVIDENCE_RECORDS.values()),
        }
        pdf_path, json_path, packet_hash, signature = _write_demo_packet_artifacts(entry["id"], sidecar)
        AUDIT_PACKETS[entry["id"]] = {
            "id": entry["id"],
            "period_start": start_dt.isoformat(),
            "period_end": end_dt.isoformat(),
            "scope": sidecar["scope"],
            "pdf_path": pdf_path,
            "json_sidecar_path": json_path,
            "packet_hash": packet_hash,
            "signature": signature,
            "status": "ready",
            "generated_at": end_dt.isoformat(),
            "counts": entry["counts"],
        }

    # A packet currently being generated, to make the ledger feel alive.
    queued_id = "pkt_2026q2_inflight"
    queued_end = now_dt
    queued_start = queued_end - timedelta(days=7)
    AUDIT_PACKETS[queued_id] = {
        "id": queued_id,
        "period_start": queued_start.isoformat(),
        "period_end": queued_end.isoformat(),
        "scope": {"tenant": "demo", "surfaces": base_surfaces, "label": "7d · all surfaces"},
        "status": "generating",
        "counts": {
            "workflow_runs": 11,
            "findings": 2,
            "proposed_changes": 1,
            "supervision_events": 12,
            "evidence_records": 7,
        },
    }


class AuditPacketGenerateRequest(BaseModel):
    label: str | None = None
    period_days: int | None = None
    surfaces: list[str] = Field(default_factory=list)
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
    seed_demo_audit_packets()
    rows = [_demo_packet(p) for p in AUDIT_PACKETS.values()]
    rows.sort(key=lambda r: r.get("generated_at") or r.get("period_end") or "", reverse=True)
    return rows


@router.get("/audit-packets/{packet_id}")
async def get_audit_packet(packet_id: str) -> dict:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            packet = await production_reviews.get_audit_packet(session, packet_id)
        if packet is None:
            raise HTTPException(status_code=404, detail="audit packet not found")
        return packet
    ensure_demo_state()
    seed_demo_audit_packets()
    packet = AUDIT_PACKETS.get(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="audit packet not found")
    return _demo_packet(packet)


@router.post("/audit-packets:generate")
@router.post("/audit-packets/generate")
async def generate_audit_packet(payload: AuditPacketGenerateRequest = Body(default=None)) -> dict:
    from datetime import UTC, datetime, timedelta

    scope: dict[str, Any] = {}
    period_days: int | None = None
    if payload is not None:
        if payload.label:
            scope["label"] = payload.label
        if payload.surfaces:
            scope["surfaces"] = payload.surfaces
        if payload.asset_ids:
            scope["asset_ids"] = payload.asset_ids
        if payload.workflow_run_ids:
            scope["workflow_run_ids"] = payload.workflow_run_ids
        if payload.obligation_urns:
            scope["obligation_urns"] = payload.obligation_urns
        period_days = payload.period_days

    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            return await production_reviews.generate_audit_packet(session, scope=scope)

    ensure_demo_state()
    seed_demo_audit_packets()
    if not EVIDENCE_RECORDS:
        generate_evidence()
    next_index = sum(1 for k in AUDIT_PACKETS if k.startswith("pkt_") and k[4:].isdigit()) + 1
    packet_id = f"pkt_{next_index:03d}"
    default_surfaces = ["workflow", "supervision"]
    base_scope = {"tenant": "demo", "surfaces": scope.get("surfaces") or default_surfaces}
    end_dt = datetime.now(UTC)
    span = max(1, int(period_days or 7))
    start_dt = end_dt - timedelta(days=span)
    period_start = start_dt.isoformat()
    period_end = end_dt.isoformat()
    merged_scope = {**base_scope, **scope}
    sidecar = {
        "id": packet_id,
        "period_start": period_start,
        "period_end": period_end,
        "scope": merged_scope,
        "evidence_records": list(EVIDENCE_RECORDS.values()),
    }
    pdf_path, json_path, packet_hash, signature = _write_demo_packet_artifacts(packet_id, sidecar)
    packet = {
        "id": packet_id,
        "period_start": period_start,
        "period_end": period_end,
        "scope": merged_scope,
        "pdf_path": pdf_path,
        "json_sidecar_path": json_path,
        "packet_hash": packet_hash,
        "signature": signature,
        "pubkey_fingerprint": packet_hash[:16],
        "status": "ready",
        "generated_at": period_end,
        "counts": _randomised_packet_counts(span, merged_scope.get("surfaces") or default_surfaces),
    }
    AUDIT_PACKETS[packet_id] = packet
    return packet


def _packet_artifact_path(packet: dict, kind: str) -> Path:
    key = "pdf_path" if kind == "pdf" else "json_sidecar_path"
    raw = packet.get(key)
    if not raw:
        raise HTTPException(status_code=404, detail=f"audit packet has no {kind}")
    path = Path(raw)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"audit packet {kind} not on disk")
    return path


@router.get("/audit-packets/{packet_id}/pdf")
async def download_audit_packet_pdf(packet_id: str) -> FileResponse:
    packet = await get_audit_packet(packet_id)
    path = _packet_artifact_path(packet, "pdf")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{packet_id}.pdf",
    )


@router.get("/audit-packets/{packet_id}/sidecar")
async def download_audit_packet_sidecar(packet_id: str) -> FileResponse:
    packet = await get_audit_packet(packet_id)
    path = _packet_artifact_path(packet, "sidecar")
    return FileResponse(
        path,
        media_type="application/json",
        filename=f"{packet_id}.json",
    )
