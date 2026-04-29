from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
import asyncio
import json
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from praetor_api.bus import EVENTS_STREAM, get_redis_client, publish
from praetor_api.hashchain import compute
from praetor_api.models.agent_event import AgentEvent
from praetor_api.models.asset import Asset
from praetor_api.models.workflow_run import WorkflowRun
from praetor_api.settings import get_settings

EVENTS: list[dict[str, Any]] = []
_asset_hashes: dict[str, str] = {}
WORKFLOW_RUN_URN_PREFIX = "urn:praetor:workflow-run:"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def make_event(
    *,
    asset_id: str,
    event_type: str,
    actor: str,
    payload: dict[str, Any],
    workflow_run_id: str | None = None,
    workflow_step_id: str | None = None,
) -> dict[str, Any]:
    prev, self_hash = compute(_asset_hashes.get(asset_id), payload)
    _asset_hashes[asset_id] = self_hash
    return {
        "id": f"evt_{uuid4().hex[:12]}",
        "ts": _now(),
        "asset_id": asset_id,
        "workflow_run_id": workflow_run_id,
        "workflow_step_id": workflow_step_id,
        "type": event_type,
        "actor": actor,
        "payload": payload,
        "payload_redacted": payload,
        "hash_chain_prev": prev,
        "hash_chain_self": self_hash,
    }


async def append_event(event: dict[str, Any]) -> dict[str, Any]:
    if get_settings().data_mode == "production":
        await publish(EVENTS_STREAM, event)
    EVENTS.append(event)
    return event


async def append_persisted_event(
    session: AsyncSession,
    *,
    asset_record_id: UUID,
    asset_id: str,
    event_type: str,
    actor: str,
    payload: dict[str, Any],
    workflow_run_record_id: UUID | None = None,
    workflow_run_id: str | None = None,
    workflow_step_id: str | None = None,
) -> dict[str, Any]:
    event_uuid = uuid4()
    external_id = f"evt_{event_uuid.hex[:12]}"
    last_hash = await session.scalar(
        select(AgentEvent.hash_chain_self)
        .where(AgentEvent.asset_id == asset_record_id)
        .order_by(AgentEvent.ts.desc())
        .limit(1)
    )
    prev, self_hash = compute(last_hash, payload)
    row = AgentEvent(
        id=event_uuid,
        asset_id=asset_record_id,
        run_id=external_id,
        workflow_run_id=workflow_run_record_id,
        workflow_step_id=workflow_step_id,
        type=event_type,
        actor=actor,
        payload=payload,
        payload_redacted=payload,
        hash_chain_prev=prev,
        hash_chain_self=self_hash,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    event = _row_to_event(row, asset_id=asset_id, workflow_run_id=workflow_run_id)
    try:
        await publish(EVENTS_STREAM, event)
    except Exception:
        event["publish_warning"] = "redis unavailable"
    EVENTS.append(event)
    return event


def events_for_asset(asset_id: str, limit: int = 200) -> list[dict[str, Any]]:
    return [event for event in EVENTS if event.get("asset_id") == asset_id][-limit:]


def events_for_workflow_run(run_id: str, limit: int = 200) -> list[dict[str, Any]]:
    return [event for event in EVENTS if event.get("workflow_run_id") == run_id][-limit:]


async def events_for_asset_db(
    session: AsyncSession,
    asset_id: str,
    limit: int = 200,
) -> list[dict[str, Any]]:
    asset = await _find_asset(session, asset_id)
    if asset is None:
        return []

    result = await session.execute(
        select(AgentEvent).where(AgentEvent.asset_id == asset.id).order_by(AgentEvent.ts).limit(limit)
    )
    rows = list(result.scalars().all())
    return [_row_to_event(row, asset_id=_external_asset_id(asset)) for row in rows]


async def events_for_workflow_run_db(
    session: AsyncSession,
    run_id: str,
    limit: int = 200,
) -> list[dict[str, Any]]:
    workflow_run = await _find_workflow_run(session, run_id)
    if workflow_run is None:
        return []

    asset = await session.get(Asset, workflow_run.asset_id)
    asset_external_id = _external_asset_id(asset) if asset else str(workflow_run.asset_id)
    external_run_id = _external_workflow_run_id(workflow_run)
    result = await session.execute(
        select(AgentEvent)
        .where(AgentEvent.workflow_run_id == workflow_run.id)
        .order_by(AgentEvent.ts)
        .limit(limit)
    )
    rows = list(result.scalars().all())
    return [
        _row_to_event(row, asset_id=asset_external_id, workflow_run_id=external_run_id)
        for row in rows
    ]


async def stream_demo_events(
    *,
    asset_id: str | None = None,
    workflow_run_id: str | None = None,
    after_index: int = 0,
) -> AsyncIterator[dict[str, Any]]:
    index = after_index
    while True:
        while index < len(EVENTS):
            event = EVENTS[index]
            index += 1
            if asset_id and event.get("asset_id") != asset_id:
                continue
            if workflow_run_id and event.get("workflow_run_id") != workflow_run_id:
                continue
            yield event
        await asyncio.sleep(0.25)


async def stream_redis_events(
    *,
    asset_id: str | None = None,
    workflow_run_id: str | None = None,
    last_id: str = "$",
) -> AsyncIterator[dict[str, Any]]:
    client = get_redis_client()
    try:
        current_id = last_id
        while True:
            response = await client.xread({EVENTS_STREAM: current_id}, count=10, block=5000)
            for _, messages in response:
                for message_id, fields in messages:
                    current_id = message_id
                    event = json.loads(fields["event"])
                    if asset_id and event.get("asset_id") != asset_id:
                        continue
                    if workflow_run_id and event.get("workflow_run_id") != workflow_run_id:
                        continue
                    yield event
    finally:
        await client.aclose()


def reset_events() -> None:
    EVENTS.clear()
    _asset_hashes.clear()


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


async def _find_workflow_run(session: AsyncSession, run_id: str) -> WorkflowRun | None:
    filters = [WorkflowRun.urn == f"{WORKFLOW_RUN_URN_PREFIX}{run_id}"]
    try:
        filters.append(WorkflowRun.id == UUID(run_id))
    except ValueError:
        pass
    result = await session.execute(select(WorkflowRun).where(or_(*filters)))
    return result.scalar_one_or_none()


def _external_asset_id(asset: Asset) -> str:
    external_id = (asset.config or {}).get("external_id")
    return external_id if isinstance(external_id, str) else str(asset.id)


def _external_workflow_run_id(workflow_run: WorkflowRun) -> str:
    if workflow_run.urn.startswith(WORKFLOW_RUN_URN_PREFIX):
        return workflow_run.urn.removeprefix(WORKFLOW_RUN_URN_PREFIX)
    return str(workflow_run.id)


def _row_to_event(
    row: AgentEvent,
    *,
    asset_id: str,
    workflow_run_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": row.run_id or f"evt_{row.id.hex[:12]}",
        "ts": row.ts.isoformat(),
        "asset_id": asset_id,
        "workflow_run_id": workflow_run_id,
        "workflow_step_id": row.workflow_step_id,
        "type": row.type,
        "actor": row.actor,
        "payload": row.payload,
        "payload_redacted": row.payload_redacted,
        "hash_chain_prev": row.hash_chain_prev,
        "hash_chain_self": row.hash_chain_self,
    }
