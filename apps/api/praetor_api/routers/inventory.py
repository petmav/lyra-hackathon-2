from typing import Any

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

from praetor_api.db import AsyncSessionLocal
from praetor_api.services import demo_state, production_inventory
from praetor_api.settings import get_settings

router = APIRouter(tags=["inventory"])


class ObligationPayload(BaseModel):
    framework: str
    citation: str
    text: str
    severity_default: str = "warn"
    applicability: dict[str, Any] = Field(default_factory=dict)
    urn: str | None = None
    version: str | None = None


class ObligationPatch(BaseModel):
    framework: str | None = None
    citation: str | None = None
    text: str | None = None
    severity_default: str | None = None
    applicability: dict[str, Any] | None = None
    version: str | None = None


class ObligationYamlImport(BaseModel):
    yaml: str
    framework: str | None = None


@router.get("/assets")
async def assets() -> list[dict]:
    if get_settings().data_mode != "production":
        return list(demo_state.DEMO_ASSETS.values())
    async with AsyncSessionLocal() as session:
        return await production_inventory.list_assets(session)


@router.get("/assets/{asset_id}")
async def asset(asset_id: str) -> dict:
    if get_settings().data_mode != "production":
        found = demo_state.DEMO_ASSETS.get(asset_id)
        if found is None:
            raise HTTPException(status_code=404, detail="asset not found")
        return found
    async with AsyncSessionLocal() as session:
        found = await production_inventory.get_asset(session, asset_id)
    if found is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return found


@router.get("/assets/{asset_id}/children")
async def asset_children(asset_id: str) -> list[dict]:
    if get_settings().data_mode != "production":
        return []
    async with AsyncSessionLocal() as session:
        return await production_inventory.child_assets(session, asset_id)


@router.get("/obligations")
async def obligations() -> list[dict]:
    if get_settings().data_mode != "production":
        return production_inventory.static_obligations()
    async with AsyncSessionLocal() as session:
        return await production_inventory.list_obligations(session)


@router.get("/obligations/{obligation_id:path}")
async def obligation(obligation_id: str) -> dict:
    if get_settings().data_mode != "production":
        found = production_inventory.get_static_obligation(obligation_id)
    else:
        async with AsyncSessionLocal() as session:
            found = await production_inventory.get_obligation(session, obligation_id)
    if found is None:
        raise HTTPException(status_code=404, detail="obligation not found")
    return found


@router.get("/controls")
async def controls() -> list[dict]:
    return production_inventory.list_controls()


@router.post("/obligations", status_code=201)
async def create_obligation(payload: ObligationPayload) -> dict:
    try:
        if get_settings().data_mode != "production":
            return production_inventory.add_demo_obligation(payload.model_dump(exclude_none=True))
        async with AsyncSessionLocal() as session:
            return await production_inventory.create_obligation(session, payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.patch("/obligations/{obligation_id:path}")
async def patch_obligation(obligation_id: str, patch: ObligationPatch) -> dict:
    try:
        if get_settings().data_mode != "production":
            updated = production_inventory.update_demo_obligation(obligation_id, patch.model_dump(exclude_none=True))
        else:
            async with AsyncSessionLocal() as session:
                updated = await production_inventory.update_obligation(session, obligation_id, patch.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    if updated is None:
        raise HTTPException(status_code=404, detail="obligation not found")
    return updated


@router.delete("/obligations/{obligation_id:path}", status_code=204)
async def delete_obligation(obligation_id: str) -> None:
    if get_settings().data_mode != "production":
        ok = production_inventory.delete_demo_obligation(obligation_id)
    else:
        async with AsyncSessionLocal() as session:
            ok = await production_inventory.delete_obligation(session, obligation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="obligation not found")
    return None


@router.post("/obligations:import-yaml")
@router.post("/obligations/import-yaml")
async def import_obligations_yaml(payload: ObligationYamlImport = Body(...)) -> dict:
    text = payload.yaml or ""
    try:
        if get_settings().data_mode != "production":
            return production_inventory.import_demo_obligations_yaml(text)
        async with AsyncSessionLocal() as session:
            return await production_inventory.import_obligations_yaml(session, text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
