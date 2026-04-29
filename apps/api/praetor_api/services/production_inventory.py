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
    seed_rows = [dict(row) for row in _load_obligation_seed_rows()]
    user_rows = [dict(row) for row in _DEMO_USER_OBLIGATIONS]
    by_urn = {row["urn"]: row for row in seed_rows}
    for row in user_rows:
        by_urn[row["urn"]] = row
    return list(by_urn.values())


def get_static_obligation(urn: str) -> dict[str, Any] | None:
    for row in _DEMO_USER_OBLIGATIONS:
        if row["urn"] == urn or row["id"] == urn:
            return dict(row)
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


_DEMO_USER_OBLIGATIONS: list[dict[str, Any]] = []


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "untitled"


def _build_obligation_urn(framework: str, citation: str, urn: str | None = None) -> str:
    if urn:
        return urn
    return f"urn:praetor:obligation:custom:{_slugify(framework)}-{_slugify(citation)}"


def _build_obligation_external_id(urn: str) -> str:
    return f"obl_{_slugify(urn.rsplit(':', 1)[-1])[:64]}"


def _normalize_obligation_payload(payload: dict[str, Any]) -> dict[str, Any]:
    framework = str(payload.get("framework") or "").strip()
    citation = str(payload.get("citation") or "").strip()
    text = str(payload.get("text") or "").strip()
    if not framework or not citation or not text:
        raise ValueError("framework, citation, and text are required")
    applicability = payload.get("applicability") or {}
    if not isinstance(applicability, dict):
        raise ValueError("applicability must be an object")
    severity_default = str(payload.get("severity_default") or "warn")
    if severity_default not in {"info", "warn", "block"}:
        raise ValueError("severity_default must be one of info|warn|block")
    urn_value = payload.get("urn")
    urn = _build_obligation_urn(framework, citation, urn_value if isinstance(urn_value, str) else None)
    return {
        "urn": urn,
        "framework": framework,
        "citation": citation,
        "text": text,
        "applicability": dict(applicability),
        "severity_default": severity_default,
        "version": str(payload.get("version") or "2026.04"),
    }


def add_demo_obligation(payload: dict[str, Any]) -> dict[str, Any]:
    data = _normalize_obligation_payload(payload)
    data["id"] = _build_obligation_external_id(data["urn"])
    for index, existing in enumerate(_DEMO_USER_OBLIGATIONS):
        if existing["urn"] == data["urn"]:
            _DEMO_USER_OBLIGATIONS[index] = data
            return data
    _DEMO_USER_OBLIGATIONS.append(data)
    return data


def update_demo_obligation(urn: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    for index, existing in enumerate(_DEMO_USER_OBLIGATIONS):
        if existing["urn"] == urn or existing["id"] == urn:
            merged = {**existing, **{k: v for k, v in patch.items() if v is not None}}
            normalized = _normalize_obligation_payload(merged)
            normalized["id"] = existing["id"]
            normalized["urn"] = existing["urn"]
            _DEMO_USER_OBLIGATIONS[index] = normalized
            return normalized
    return None


def delete_demo_obligation(urn: str) -> bool:
    before = len(_DEMO_USER_OBLIGATIONS)
    _DEMO_USER_OBLIGATIONS[:] = [o for o in _DEMO_USER_OBLIGATIONS if o["urn"] != urn and o["id"] != urn]
    return len(_DEMO_USER_OBLIGATIONS) != before


def import_demo_obligations_yaml(text: str) -> dict[str, Any]:
    payload = yaml.safe_load(text) or {}
    framework_default = str(payload.get("framework") or "")
    items = payload.get("obligations") or []
    if not isinstance(items, list):
        raise ValueError("YAML must contain an 'obligations' list")
    created: list[dict[str, Any]] = []
    updated: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        merged = {**raw, "framework": raw.get("framework") or framework_default}
        try:
            data = _normalize_obligation_payload(merged)
        except ValueError:
            continue
        data["id"] = _build_obligation_external_id(data["urn"])
        existing = next((o for o in _DEMO_USER_OBLIGATIONS if o["urn"] == data["urn"]), None)
        if existing is not None:
            existing.update(data)
            updated.append(data)
        else:
            _DEMO_USER_OBLIGATIONS.append(data)
            created.append(data)
    return {"created": created, "updated": updated, "skipped": max(0, len(items) - len(created) - len(updated))}


async def create_obligation(session: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    data = _normalize_obligation_payload(payload)
    existing = await session.execute(select(Obligation).where(Obligation.urn == data["urn"]))
    row = existing.scalar_one_or_none()
    if row is not None:
        row.framework = data["framework"]
        row.citation = data["citation"]
        row.text = data["text"]
        row.applicability = {**data["applicability"], "version": data["version"]}
        row.severity_default = data["severity_default"]
    else:
        row = Obligation(
            urn=data["urn"],
            framework=data["framework"],
            citation=data["citation"],
            text=data["text"],
            applicability={**data["applicability"], "version": data["version"]},
            severity_default=data["severity_default"],
        )
        session.add(row)
    await session.commit()
    await session.refresh(row)
    return _obligation_to_api(row)


async def update_obligation(
    session: AsyncSession, urn: str, patch: dict[str, Any]
) -> dict[str, Any] | None:
    row = await _resolve_obligation_row(session, urn)
    if row is None:
        return None
    merged: dict[str, Any] = {
        "framework": patch.get("framework") if patch.get("framework") is not None else row.framework,
        "citation": patch.get("citation") if patch.get("citation") is not None else row.citation,
        "text": patch.get("text") if patch.get("text") is not None else row.text,
        "severity_default": patch.get("severity_default") if patch.get("severity_default") is not None else row.severity_default,
        "applicability": patch.get("applicability") if patch.get("applicability") is not None else {k: v for k, v in (row.applicability or {}).items() if k != "version"},
        "version": patch.get("version") or (row.applicability or {}).get("version") or "2026.04",
        "urn": row.urn,
    }
    data = _normalize_obligation_payload(merged)
    row.framework = data["framework"]
    row.citation = data["citation"]
    row.text = data["text"]
    row.applicability = {**data["applicability"], "version": data["version"]}
    row.severity_default = data["severity_default"]
    await session.commit()
    await session.refresh(row)
    return _obligation_to_api(row)


async def delete_obligation(session: AsyncSession, urn: str) -> bool:
    row = await _resolve_obligation_row(session, urn)
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True


async def import_obligations_yaml(session: AsyncSession, text: str) -> dict[str, Any]:
    payload = yaml.safe_load(text) or {}
    framework_default = str(payload.get("framework") or "")
    items = payload.get("obligations") or []
    if not isinstance(items, list):
        raise ValueError("YAML must contain an 'obligations' list")
    created: list[dict[str, Any]] = []
    updated: list[dict[str, Any]] = []
    skipped = 0
    for raw in items:
        if not isinstance(raw, dict):
            skipped += 1
            continue
        merged = {**raw, "framework": raw.get("framework") or framework_default}
        try:
            data = _normalize_obligation_payload(merged)
        except ValueError:
            skipped += 1
            continue
        existing = await session.execute(select(Obligation).where(Obligation.urn == data["urn"]))
        row = existing.scalar_one_or_none()
        if row is None:
            row = Obligation(
                urn=data["urn"],
                framework=data["framework"],
                citation=data["citation"],
                text=data["text"],
                applicability={**data["applicability"], "version": data["version"]},
                severity_default=data["severity_default"],
            )
            session.add(row)
            created.append(data)
        else:
            row.framework = data["framework"]
            row.citation = data["citation"]
            row.text = data["text"]
            row.applicability = {**data["applicability"], "version": data["version"]}
            row.severity_default = data["severity_default"]
            updated.append(data)
    await session.commit()
    return {"created": created, "updated": updated, "skipped": skipped}


async def _resolve_obligation_row(session: AsyncSession, urn: str) -> Obligation | None:
    filters = [Obligation.urn == urn]
    try:
        filters.append(Obligation.id == UUID(urn))
    except ValueError:
        pass
    result = await session.execute(select(Obligation).where(or_(*filters)))
    return result.scalar_one_or_none()


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
