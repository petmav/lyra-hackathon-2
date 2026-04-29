from fastapi import APIRouter, HTTPException

from praetor_api.db import AsyncSessionLocal
from praetor_api.services import production_inventory

router = APIRouter(tags=["inventory"])


@router.get("/assets")
async def assets() -> list[dict]:
    async with AsyncSessionLocal() as session:
        return await production_inventory.list_assets(session)


@router.get("/assets/{asset_id}")
async def asset(asset_id: str) -> dict:
    async with AsyncSessionLocal() as session:
        found = await production_inventory.get_asset(session, asset_id)
    if found is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return found


@router.get("/assets/{asset_id}/children")
async def asset_children(asset_id: str) -> list[dict]:
    async with AsyncSessionLocal() as session:
        return await production_inventory.child_assets(session, asset_id)


@router.get("/obligations")
async def obligations() -> list[dict]:
    return production_inventory.list_obligations()


@router.get("/obligations/{obligation_id:path}")
async def obligation(obligation_id: str) -> dict:
    found = production_inventory.get_obligation(obligation_id)
    if found is None:
        raise HTTPException(status_code=404, detail="obligation not found")
    return found


@router.get("/controls")
async def controls() -> list[dict]:
    return production_inventory.list_controls()
