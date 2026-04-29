from __future__ import annotations

from dataclasses import dataclass
import json
from time import perf_counter
from typing import Any

import httpx

from praetor_api.services.secrets import resolve_secret

MCP_PROTOCOL_VERSION = "2025-06-18"
MCP_SESSION_HEADER = "MCP-Session-Id"


@dataclass(frozen=True)
class McpCallResult:
    ok: bool
    outputs: dict[str, Any]
    latency_ms: int
    error: str | None = None


@dataclass
class McpSession:
    endpoint: str
    auth_ref: str | None = None
    session_id: str | None = None
    protocol_version: str = MCP_PROTOCOL_VERSION
    server_info: dict[str, Any] | None = None
    capabilities: dict[str, Any] | None = None

    def headers(self, method: str, params: dict[str, Any]) -> dict[str, str]:
        headers = {
            "MCP-Protocol-Version": self.protocol_version,
            "Mcp-Method": method,
        }
        name = _request_name(method, params)
        if name:
            headers["Mcp-Name"] = name
        if self.session_id:
            headers[MCP_SESSION_HEADER] = self.session_id
        token = resolve_secret(self.auth_ref)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers


async def health(endpoint: str, auth_ref: str | None = None) -> McpCallResult:
    started = perf_counter()
    session = McpSession(endpoint=endpoint, auth_ref=auth_ref)
    mcp = await _mcp_request(session, "initialize", _initialize_params())
    if mcp.get("ok"):
        tools = await _mcp_request(session, "tools/list", {})
        resources = await _mcp_request(session, "resources/list", {})
        prompts = await _mcp_request(session, "prompts/list", {})
        tool_rows = tools.get("result", {}).get("tools", []) if isinstance(tools.get("result"), dict) else []
        resource_rows = resources.get("result", {}).get("resources", []) if isinstance(resources.get("result"), dict) else []
        prompt_rows = prompts.get("result", {}).get("prompts", []) if isinstance(prompts.get("result"), dict) else []
        return McpCallResult(
            True,
            {
                "mode": "mcp-streamable-http",
                "protocol_version": session.protocol_version,
                "session_id": _redact_session(session.session_id),
                "server_info": session.server_info or {},
                "capabilities": session.capabilities or {},
                "tools": tool_rows,
                "resources": resource_rows,
                "prompts": prompt_rows,
                "resources_count": len(resource_rows),
                "tools_count": len(tool_rows),
                "prompts_count": len(prompt_rows),
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
    auth_ref: str | None = None,
) -> McpCallResult:
    started = perf_counter()
    session = McpSession(endpoint=endpoint, auth_ref=auth_ref)
    initialized = await _mcp_request(session, "initialize", _initialize_params())
    if not initialized.get("ok"):
        return await _legacy_call(endpoint, operation, inputs, dry_run, started)
    mcp = await _mcp_request(
        session,
        "tools/call",
        {"name": operation, "arguments": {**inputs, "dry_run": dry_run}},
    )
    if mcp.get("ok"):
        result = mcp.get("result", {})
        outputs = _extract_mcp_tool_output(result)
        return McpCallResult(
            True,
            {
                **outputs,
                "_mcp": {
                    "mode": "mcp-streamable-http",
                    "protocol_version": session.protocol_version,
                    "session_id": _redact_session(session.session_id),
                },
            },
            _elapsed_ms(started),
        )

    return await _legacy_call(endpoint, operation, inputs, dry_run, started)


async def _legacy_call(
    endpoint: str,
    operation: str,
    inputs: dict[str, Any],
    dry_run: bool,
    started: float,
) -> McpCallResult:
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


async def _mcp_request(session: McpSession, method: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(
                f"{session.endpoint.rstrip('/')}/mcp",
                headers=session.headers(method, params),
                json={"jsonrpc": "2.0", "id": f"praetor-{method}", "method": method, "params": params},
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return {"ok": False}
    if not isinstance(payload, dict) or "error" in payload:
        return {"ok": False}
    if method == "initialize" and isinstance(payload.get("result"), dict):
        result = payload["result"]
        session.session_id = response.headers.get(MCP_SESSION_HEADER) or response.headers.get("Mcp-Session-Id")
        if isinstance(result.get("protocolVersion"), str):
            session.protocol_version = result["protocolVersion"]
        session.server_info = result.get("serverInfo") if isinstance(result.get("serverInfo"), dict) else {}
        session.capabilities = result.get("capabilities") if isinstance(result.get("capabilities"), dict) else {}
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


def _initialize_params() -> dict[str, Any]:
    return {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "capabilities": {
            "roots": {"listChanged": False},
            "sampling": {},
        },
        "clientInfo": {
            "name": "praetor-api",
            "version": "0.1.0",
            "title": "Praetor API",
        },
    }


def _request_name(method: str, params: dict[str, Any]) -> str | None:
    if method == "tools/call" and isinstance(params.get("name"), str):
        return params["name"]
    if method == "resources/read" and isinstance(params.get("uri"), str):
        return params["uri"]
    if method == "prompts/get" and isinstance(params.get("name"), str):
        return params["name"]
    return None


def _redact_session(session_id: str | None) -> str | None:
    if not session_id:
        return None
    if len(session_id) <= 8:
        return "[redacted]"
    return f"{session_id[:4]}...{session_id[-4:]}"
