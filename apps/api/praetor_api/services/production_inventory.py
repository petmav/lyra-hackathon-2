from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from praetor_api.models.asset import Asset


OBLIGATIONS: list[dict[str, Any]] = [
    {
        "id": "obl_iso_42001_8_3",
        "urn": "urn:praetor:obligation:demo:iso-42001-8-3",
        "framework": "iso_42001",
        "citation": "8.3",
        "text": "AI system changes and operational tools must be controlled, evaluated, and evidenced.",
        "applicability": {"asset_types": ["agent", "tool", "workflow_agent"], "jurisdictions": ["US", "EU"]},
        "severity_default": "warn",
        "version": "2026.04",
    },
    {
        "id": "obl_internal_data_min",
        "urn": "urn:praetor:obligation:demo:internal-data-min",
        "framework": "internal_policy",
        "citation": "Data Minimisation 3.2",
        "text": "Outbound communications must validate recipient domains before sending customer data.",
        "applicability": {"asset_types": ["agent", "tool"], "high_risk": True},
        "severity_default": "block",
        "version": "2026.04",
    },
    {
        "id": "obl_gdpr_5_1_c",
        "urn": "urn:praetor:obligation:demo:gdpr-5-1-c",
        "framework": "gdpr",
        "citation": "Art. 5(1)(c)",
        "text": "Personal data processing must be adequate, relevant, and limited to what is necessary.",
        "applicability": {"jurisdictions": ["EU"], "asset_types": ["agent", "dataset", "tool"]},
        "severity_default": "warn",
        "version": "2026.04",
    },
]

CONTROLS: list[dict[str, Any]] = [
    {
        "id": "ctrl_tool_permission",
        "urn": "urn:praetor:control:tool-permission",
        "name": "Tool permission hot gate",
        "package": "praetor.controls.tool_permission",
        "obligations_implemented": [
            "urn:praetor:obligation:demo:iso-42001-8-3",
            "urn:praetor:obligation:demo:internal-data-min",
        ],
        "description": "Evaluates effect radius, approval state, and recipient validation before tool calls.",
    },
    {
        "id": "ctrl_workflow_agent_step",
        "urn": "urn:praetor:control:workflow-agent-step",
        "name": "Workflow agent step supervision",
        "package": "praetor.controls.workflow_agent_step",
        "obligations_implemented": ["urn:praetor:obligation:demo:iso-42001-8-3"],
        "description": "Requires workflow agent steps to preserve model/provider, inputs, outputs, and event evidence.",
    },
]


async def list_assets(session: AsyncSession) -> list[dict[str, Any]]:
    result = await session.execute(select(Asset).order_by(Asset.created_at))
    return [_asset_to_api(row) for row in result.scalars().all()]


async def get_asset(session: AsyncSession, asset_id: str) -> dict[str, Any] | None:
    asset = await _find_asset(session, asset_id)
    return _asset_to_api(asset) if asset else None


async def child_assets(session: AsyncSession, parent_id: str) -> list[dict[str, Any]]:
    parent = await _find_asset(session, parent_id)
    if parent is None:
        return []
    result = await session.execute(select(Asset).where(Asset.parent_asset_id == parent.id).order_by(Asset.created_at))
    return [_asset_to_api(row) for row in result.scalars().all()]


def list_obligations() -> list[dict[str, Any]]:
    return [dict(row) for row in OBLIGATIONS]


def get_obligation(urn: str) -> dict[str, Any] | None:
    return next((dict(row) for row in OBLIGATIONS if row["urn"] == urn or row["id"] == urn), None)


def list_controls() -> list[dict[str, Any]]:
    return [dict(row) for row in CONTROLS]


async def _find_asset(session: AsyncSession, asset_id: str) -> Asset | None:
    filters = [
        Asset.urn == asset_id,
        Asset.config["external_id"].astext == asset_id,
    ]
    try:
        filters.append(Asset.id == UUID(asset_id))
    except ValueError:
        pass
    result = await session.execute(select(Asset).where(or_(*filters)))
    return result.scalar_one_or_none()


def _asset_to_api(row: Asset) -> dict[str, Any]:
    config = row.config or {}
    external_id = config.get("external_id")
    return {
        "id": external_id if isinstance(external_id, str) else str(row.id),
        "urn": row.urn,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "created_by": row.created_by,
        "version": row.version,
        "type": row.type,
        "name": row.name,
        "description": config.get("description"),
        "owner_id": row.owner_id,
        "risk_tier": row.risk_tier,
        "lifecycle": row.lifecycle,
        "parent_asset_id": str(row.parent_asset_id) if row.parent_asset_id else None,
        "jurisdictions": row.jurisdictions,
        "data_classifications": row.data_classifications,
        "sectors": row.sectors,
        "tags": config.get("tags", []),
        "fingerprint": row.fingerprint,
        "metadata": config.get("metadata", {}),
        "config": config,
    }
