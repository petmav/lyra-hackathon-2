from fastapi import APIRouter

from praetor_api.db import AsyncSessionLocal
from praetor_api.services.event_stream import (
    events_for_asset,
    events_for_asset_db,
    events_for_workflow_run,
    events_for_workflow_run_db,
)
from praetor_api.settings import get_settings

router = APIRouter(tags=["events"])


@router.get("/events")
async def events(asset_id: str | None = None, workflow_run_id: str | None = None) -> list[dict]:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            if workflow_run_id:
                return await events_for_workflow_run_db(session, workflow_run_id)
            if asset_id:
                return await events_for_asset_db(session, asset_id)
            return []

    if workflow_run_id:
        return events_for_workflow_run(workflow_run_id)
    if asset_id:
        return events_for_asset(asset_id)
    return []
