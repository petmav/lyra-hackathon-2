from __future__ import annotations

from dataclasses import dataclass
import json
from time import perf_counter
from typing import Any

import httpx


@dataclass(frozen=True)
class McpCallResult:
    ok: bool
    outputs: dict[str, Any]
    latency_ms: int
    error: str | None = None


async def health(endpoint: str) -> McpCallResult:
    started = perf_counter()
    mcp = await _mcp_request(endpoint, "initialize", {})
    if mcp.get("ok"):
        tools = await _mcp_request(endpoint, "tools/list", {})
        resources = await _mcp_request(endpoint, "resources/list", {})
        tool_rows = tools.get("result", {}).get("tools", []) if isinstance(tools.get("result"), dict) else []
        resource_rows = resources.get("result", {}).get("resources", []) if isinstance(resources.get("result"), dict) else []
        return McpCallResult(
            True,
            {
                "mode": "mcp-json-rpc",
                "tools": tool_rows,
                "resources": resource_rows,
                "resources_count": len(resource_rows),
            },
            _elapsed_ms(started),
        )

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{endpoint.rstrip('/')}/resources")
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return McpCallResult(False, {}, _elapsed_ms(started), exc.__class__.__name__)

    resources = payload.get("resources", []) if isinstance(payload, dict) else []
    return McpCallResult(
        True,
        {"resources": resources, "resources_count": len(resources)},
        _elapsed_ms(started),
    )


async def call(
    endpoint: str,
    operation: str,
    inputs: dict[str, Any],
    dry_run: bool,
) -> McpCallResult:
    started = perf_counter()
    mcp = await _mcp_request(
        endpoint,
        "tools/call",
        {"name": operation, "arguments": {**inputs, "dry_run": dry_run}},
    )
    if mcp.get("ok"):
        result = mcp.get("result", {})
        outputs = _extract_mcp_tool_output(result)
        return McpCallResult(True, outputs, _elapsed_ms(started))

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{endpoint.rstrip('/')}/call",
                json={"operation": operation, "inputs": inputs, "dry_run": dry_run},
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return McpCallResult(False, {}, _elapsed_ms(started), exc.__class__.__name__)

    outputs = payload.get("outputs", payload) if isinstance(payload, dict) else {}
    return McpCallResult(True, outputs if isinstance(outputs, dict) else {}, _elapsed_ms(started))


async def _mcp_request(endpoint: str, method: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(
                f"{endpoint.rstrip('/')}/mcp",
                json={"jsonrpc": "2.0", "id": f"praetor-{method}", "method": method, "params": params},
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return {"ok": False}
    if not isinstance(payload, dict) or "error" in payload:
        return {"ok": False}
    payload["ok"] = True
    return payload


def _elapsed_ms(started: float) -> int:
    return max(1, int((perf_counter() - started) * 1000))


def _extract_mcp_tool_output(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    for item in result.get("content", []):
        if not isinstance(item, dict) or item.get("type") != "text":
            continue
        text = item.get("text")
        if not isinstance(text, str):
            continue
        try:
            parsed = json.loads(text)
        except ValueError:
            return {"text": text}
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    return {}
