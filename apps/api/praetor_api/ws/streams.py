import contextlib
from collections.abc import AsyncIterator

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from praetor_api.services.event_stream import (
    stream_demo_events,
    stream_redis_events,
)
from praetor_api.services.auth import authorize_websocket
from praetor_api.settings import get_settings

router = APIRouter()


async def _authorize(websocket: WebSocket) -> bool:
    return authorize_websocket(websocket).ok


def _stream(
    *,
    asset_id: str | None = None,
    workflow_run_id: str | None = None,
) -> AsyncIterator[dict]:
    if get_settings().data_mode == "production":
        return stream_redis_events(asset_id=asset_id, workflow_run_id=workflow_run_id)
    return stream_demo_events(asset_id=asset_id, workflow_run_id=workflow_run_id)


async def _serve(websocket: WebSocket, events: AsyncIterator[dict]) -> None:
    if not await _authorize(websocket):
        await websocket.close(code=1008, reason="missing or invalid bearer token")
        return

    await websocket.accept()
    try:
        async for event in events:
            await websocket.send_json(event)
    except WebSocketDisconnect:
        return
    finally:
        with contextlib.suppress(Exception):
            await events.aclose()


@router.websocket("/ws/v1/assets/{asset_id}/stream")
async def asset_stream(websocket: WebSocket, asset_id: str) -> None:
    await _serve(websocket, _stream(asset_id=asset_id))


@router.websocket("/ws/v1/workflow-runs/{run_id}/stream")
async def workflow_run_stream(websocket: WebSocket, run_id: str) -> None:
    await _serve(websocket, _stream(workflow_run_id=run_id))
