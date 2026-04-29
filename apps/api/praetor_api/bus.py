from collections.abc import Awaitable, Callable
import json
from typing import Any

try:
    import redis.asyncio as redis
except ModuleNotFoundError:
    redis = None

from praetor_api.settings import get_settings

EVENTS_STREAM = "events"
WORKFLOW_RUNS_STREAM = "workflow.runs"
SANDBOX_EVENTS_STREAM = "sandbox.events"

Handler = Callable[[str, dict[str, Any]], Awaitable[None]]


def get_redis_client():
    if redis is None:
        raise RuntimeError("redis package is not installed")
    return redis.from_url(get_settings().redis_url, decode_responses=True)


async def publish(stream: str, event: dict[str, Any]) -> str:
    client = get_redis_client()
    try:
        payload = {"event": json.dumps(event, sort_keys=True, separators=(",", ":"))}
        return await client.xadd(stream, payload)
    finally:
        await client.aclose()


async def consume(stream: str, group: str, name: str, handler: Handler) -> None:
    client = get_redis_client()
    try:
        try:
            await client.xgroup_create(stream, group, id="0", mkstream=True)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

        while True:
            response = await client.xreadgroup(group, name, {stream: ">"}, count=10, block=5000)
            for _, messages in response:
                for message_id, fields in messages:
                    event = json.loads(fields["event"])
                    await handler(message_id, event)
                    await client.xack(stream, group, message_id)
    finally:
        await client.aclose()
