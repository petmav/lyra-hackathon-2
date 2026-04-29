"""Derived alerts feed.

There is no canonical `alert` table — alerts are a UI projection of high-priority
findings and proposed changes that need human review. We derive them server-side
so the frontend can hit one endpoint instead of fanning out across resources
(and tripping over per-route CORS / latency).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from praetor_api.db import AsyncSessionLocal
from praetor_api.services import production_reviews
from praetor_api.settings import get_settings

router = APIRouter(tags=["alerts"])


@router.get("/alerts")
async def list_alerts() -> list[dict[str, Any]]:
    if get_settings().data_mode != "production":
        # Demo mode has no canonical alerts source; the demo dashboard reads
        # its tile counts from findings/runs directly. Returning [] keeps the
        # tray empty rather than emitting noise.
        return []

    async with AsyncSessionLocal() as session:
        findings = await production_reviews.list_findings(session)
        changes = await production_reviews.list_proposed_changes(session)

    findings_by_id = {f.get("id"): f for f in findings if isinstance(f, dict)}
    alerts: list[dict[str, Any]] = []

    for finding in findings:
        if not isinstance(finding, dict):
            continue
        if finding.get("status") != "open":
            continue
        severity = str(finding.get("severity") or "medium")
        if severity not in {"high", "critical"}:
            continue
        alerts.append({
            "id": f"al_finding_{finding.get('id')}",
            "kind": "finding",
            "ts": finding.get("created_at"),
            "title": f"Finding · {finding.get('title', '')}",
            "detail": (str(finding.get("description") or ""))[:160],
            "severity": severity,
            "href": f"/findings/{finding.get('id')}",
        })

    for change in changes:
        if not isinstance(change, dict):
            continue
        if change.get("status") not in {"awaiting_approval", "tested"}:
            continue
        finding = findings_by_id.get(change.get("finding_id"))
        residual = change.get("residual_risk_estimate")
        try:
            residual_pct = int(round(float(residual) * 100))
        except (TypeError, ValueError):
            residual_pct = 0
        severity = (finding or {}).get("severity") or ("high" if residual_pct >= 50 else "medium")
        alerts.append({
            "id": f"al_change_{change.get('id')}",
            "kind": "approval",
            "ts": (finding or {}).get("created_at"),
            "title": f"Approval pending — {change.get('kind', 'change')} change for {(finding or {}).get('title', change.get('finding_id', ''))}",
            "detail": f"Residual risk {residual_pct}%; sandbox awaiting human review.",
            "severity": severity,
            "href": f"/proposed-changes/{change.get('id')}",
        })

    alerts.sort(key=lambda a: a.get("ts") or "", reverse=True)
    return alerts[:12]
