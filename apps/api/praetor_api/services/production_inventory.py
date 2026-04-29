from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
import yaml

from praetor_api.models.asset import Asset
from praetor_api.models.obligation import Obligation


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


def _root_content_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "content"
        if candidate.exists():
            return candidate
    return Path.cwd() / "content"


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
OBLIGATION_SEED_DIRS = [
    _root_content_dir() / "obligations",
    PACKAGE_ROOT / "seed_content" / "obligations",
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


async def ensure_obligations(session: AsyncSession) -> list[Obligation]:
    seed_rows = _load_obligation_seed_rows()
    rows: list[Obligation] = []
    for data in seed_rows:
        result = await session.execute(select(Obligation).where(Obligation.urn == data["urn"]))
        row = result.scalar_one_or_none()
        applicability = dict(data.get("applicability") or {})
        applicability["version"] = data.get("version", "2026.04")
        if row is None:
            row = Obligation(
                urn=data["urn"],
                framework=data["framework"],
                citation=data["citation"],
                text=data["text"],
                applicability=applicability,
                severity_default=data["severity_default"],
            )
            session.add(row)
            await session.flush()
        else:
            row.framework = data["framework"]
            row.citation = data["citation"]
            row.text = data["text"]
            row.applicability = applicability
            row.severity_default = data["severity_default"]
        rows.append(row)
    return rows


async def list_obligations(session: AsyncSession) -> list[dict[str, Any]]:
    await ensure_obligations(session)
    await session.commit()
    result = await session.execute(select(Obligation).order_by(Obligation.framework, Obligation.citation))
    return [_obligation_to_api(row) for row in result.scalars().all()]


async def get_obligation(session: AsyncSession, urn: str) -> dict[str, Any] | None:
    await ensure_obligations(session)
    await session.commit()
    filters = [Obligation.urn == urn]
    for seed in _load_obligation_seed_rows():
        if seed["id"] == urn:
            filters.append(Obligation.urn == seed["urn"])
            break
    try:
        filters.append(Obligation.id == UUID(urn))
    except ValueError:
        pass
    result = await session.execute(select(Obligation).where(or_(*filters)))
    row = result.scalar_one_or_none()
    return _obligation_to_api(row) if row else None


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


def static_obligations() -> list[dict[str, Any]]:
    return [dict(row) for row in _load_obligation_seed_rows()]


def get_static_obligation(urn: str) -> dict[str, Any] | None:
    return next((dict(row) for row in _load_obligation_seed_rows() if row["urn"] == urn or row["id"] == urn), None)


def _load_obligation_seed_rows() -> list[dict[str, Any]]:
    by_urn = {row["urn"]: dict(row) for row in OBLIGATIONS}
    for path in _obligation_seed_files():
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        framework = str(payload.get("framework") or path.stem)
        version = str(payload.get("version") or "2026.04")
        obligations = payload.get("obligations") or []
        if not isinstance(obligations, list):
            continue
        for item in obligations:
            if not isinstance(item, dict):
                continue
            urn = str(item.get("urn") or "")
            if not urn:
                continue
            by_urn[urn] = {
                "id": str(item.get("id") or urn.rsplit(":", 1)[-1]),
                "urn": urn,
                "framework": str(item.get("framework") or framework),
                "citation": str(item.get("citation") or ""),
                "text": str(item.get("text") or ""),
                "applicability": dict(item.get("applicability") or {}),
                "severity_default": str(item.get("severity_default") or "warn"),
                "version": str(item.get("version") or version),
            }
    return list(by_urn.values())


def _obligation_seed_files() -> list[Path]:
    files: dict[str, Path] = {}
    for directory in OBLIGATION_SEED_DIRS:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.yaml")):
            files[path.name] = path
    return list(files.values())


def _obligation_to_api(row: Obligation) -> dict[str, Any]:
    applicability = row.applicability or {}
    external_id = next(
        (
            seed["id"]
            for seed in _load_obligation_seed_rows()
            if seed["urn"] == row.urn
        ),
        row.urn.rsplit(":", 1)[-1],
    )
    return {
        "id": external_id,
        "urn": row.urn,
        "framework": row.framework,
        "citation": row.citation,
        "text": row.text,
        "applicability": {key: value for key, value in applicability.items() if key != "version"},
        "severity_default": row.severity_default,
        "version": str(applicability.get("version") or row.version),
    }
