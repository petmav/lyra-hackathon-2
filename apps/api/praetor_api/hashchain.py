import hashlib
import json
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from praetor_api.models.agent_event import AgentEvent

ZERO_HASH = "0" * 64


def compute(prev_hash: str | None, payload: dict[str, Any]) -> tuple[str, str]:
    prev = prev_hash or ZERO_HASH
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    self_hash = hashlib.sha256(prev.encode("utf-8") + body).hexdigest()
    return prev, self_hash


def latest_hash_query(asset_id: str) -> Select[tuple[str]]:
    return (
        select(AgentEvent.hash_chain_self)
        .where(AgentEvent.asset_id == asset_id)
        .order_by(AgentEvent.ts.desc())
        .limit(1)
    )


async def append(session: AsyncSession, asset_id: str, payload: dict[str, Any]) -> tuple[str, str]:
    last = await session.scalar(latest_hash_query(asset_id))
    return compute(last, payload)
