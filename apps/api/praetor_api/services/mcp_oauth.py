from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from praetor_api.models.hook import Hook
from praetor_api.models.mcp_oauth_connection import McpOAuthConnection
from praetor_api.services import mcp_client

HOOK_URN_PREFIX = "urn:praetor:hook:"
MCP_OAUTH_URN_PREFIX = "urn:praetor:mcp_oauth_connection:"


class McpOAuthError(RuntimeError):
    pass


async def start_authorization(
    session: AsyncSession,
    *,
    hook_id: str,
    redirect_uri: str | None = None,
    scopes: list[str] | None = None,
) -> dict[str, Any]:
    hook = await _find_hook(session, hook_id)
    if hook is None:
        raise KeyError(hook_id)
    redirect_uri = redirect_uri or mcp_client.DEFAULT_REDIRECT_URI
    registration = await mcp_client.discover_and_register_oauth_client(
        hook.endpoint,
        redirect_uris=[redirect_uri],
    )
    if not registration.ok:
        raise McpOAuthError(registration.error or "oauth registration failed")
    metadata = registration.metadata
    auth_server = metadata["authorization_server"]
    client = metadata["client"]
    authorization_endpoint = auth_server.get("authorization_endpoint")
    token_endpoint = auth_server.get("token_endpoint")
    if not isinstance(authorization_endpoint, str) or not isinstance(token_endpoint, str):
        raise McpOAuthError("authorization server metadata missing authorization_endpoint or token_endpoint")

    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    selected_scopes = scopes or _scopes_from_registration(client, hook)
    connection = await _connection_for_hook(session, hook)
    if connection is None:
        connection = McpOAuthConnection(
            urn=f"{MCP_OAUTH_URN_PREFIX}{secrets.token_hex(12)}",
            hook_id=hook.id,
            endpoint=hook.endpoint,
            status="authorization_pending",
            issuer=auth_server.get("issuer"),
            authorization_endpoint=authorization_endpoint,
            token_endpoint=token_endpoint,
            registration_endpoint=auth_server.get("registration_endpoint"),
            client_id=str(client["client_id"]),
            client_secret=client.get("client_secret") if isinstance(client.get("client_secret"), str) else None,
            redirect_uri=redirect_uri,
            scopes=selected_scopes,
            state=state,
            code_verifier=verifier,
            registration=_redact_client_secret(metadata),
            token_set=None,
            created_by="api",
            version=1,
        )
        session.add(connection)
    else:
        connection.status = "authorization_pending"
        connection.endpoint = hook.endpoint
        connection.issuer = auth_server.get("issuer")
        connection.authorization_endpoint = authorization_endpoint
        connection.token_endpoint = token_endpoint
        connection.registration_endpoint = auth_server.get("registration_endpoint")
        connection.client_id = str(client["client_id"])
        connection.client_secret = client.get("client_secret") if isinstance(client.get("client_secret"), str) else None
        connection.redirect_uri = redirect_uri
        connection.scopes = selected_scopes
        connection.state = state
        connection.code_verifier = verifier
        connection.registration = _redact_client_secret(metadata)
    config = hook.config if isinstance(hook.config, dict) else {}
    hook.config = {**config, "mcp_oauth_connection_urn": connection.urn}
    await session.commit()
    await session.refresh(connection)
    return _connection_to_api(connection) | {
        "authorization_url": _authorization_url(connection),
    }


async def complete_authorization(
    session: AsyncSession,
    *,
    state: str,
    code: str,
) -> dict[str, Any]:
    connection = await session.scalar(select(McpOAuthConnection).where(McpOAuthConnection.state == state).limit(1))
    if connection is None:
        raise KeyError(state)
    payload = await _token_request(
        connection.token_endpoint,
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": connection.redirect_uri,
            "client_id": connection.client_id,
            "code_verifier": connection.code_verifier or "",
            **({"client_secret": connection.client_secret} if connection.client_secret else {}),
        },
    )
    _store_token_set(connection, payload)
    connection.status = "authorized"
    connection.state = None
    connection.code_verifier = None
    await session.commit()
    await session.refresh(connection)
    return _connection_to_api(connection)


async def refresh_connection(session: AsyncSession, connection_id: str) -> dict[str, Any]:
    connection = await _find_connection(session, connection_id)
    if connection is None:
        raise KeyError(connection_id)
    await refresh_if_needed(session, connection, force=True)
    return _connection_to_api(connection)


async def oauth_token_for_hook(session: AsyncSession, hook: Hook) -> str | None:
    connection = await _connection_for_hook(session, hook)
    if connection is None or connection.status != "authorized":
        return None
    await refresh_if_needed(session, connection)
    token_set = connection.token_set if isinstance(connection.token_set, dict) else {}
    token = token_set.get("access_token")
    return token if isinstance(token, str) else None


async def refresh_if_needed(
    session: AsyncSession,
    connection: McpOAuthConnection,
    *,
    force: bool = False,
) -> None:
    if not force and connection.token_expires_at and connection.token_expires_at > datetime.now(UTC) + timedelta(seconds=60):
        return
    token_set = connection.token_set if isinstance(connection.token_set, dict) else {}
    refresh_token = token_set.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        return
    payload = await _token_request(
        connection.token_endpoint,
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": connection.client_id,
            **({"client_secret": connection.client_secret} if connection.client_secret else {}),
        },
    )
    _store_token_set(connection, {**token_set, **payload})
    await session.commit()
    await session.refresh(connection)


async def list_connections(session: AsyncSession) -> list[dict[str, Any]]:
    result = await session.execute(select(McpOAuthConnection).order_by(McpOAuthConnection.created_at))
    return [_connection_to_api(row) for row in result.scalars().all()]


async def _token_request(token_endpoint: str, form: dict[str, str]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            token_endpoint,
            data=form,
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("access_token"), str):
        raise McpOAuthError("token response missing access_token")
    return payload


def _authorization_url(connection: McpOAuthConnection) -> str:
    params = {
        "response_type": "code",
        "client_id": connection.client_id,
        "redirect_uri": connection.redirect_uri,
        "scope": " ".join(connection.scopes or []),
        "state": connection.state or "",
        "code_challenge": _code_challenge(connection.code_verifier or ""),
        "code_challenge_method": "S256",
        "resource": connection.endpoint,
    }
    return f"{connection.authorization_endpoint}?{urlencode(params)}"


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _store_token_set(connection: McpOAuthConnection, payload: dict[str, Any]) -> None:
    expires_in = payload.get("expires_in")
    connection.token_expires_at = (
        datetime.now(UTC) + timedelta(seconds=int(expires_in))
        if isinstance(expires_in, int | float) or (isinstance(expires_in, str) and expires_in.isdigit())
        else None
    )
    connection.token_set = payload


def _scopes_from_registration(client: dict[str, Any], hook: Hook) -> list[str]:
    scope = client.get("scope")
    if isinstance(scope, str) and scope:
        return scope.split()
    if hook.scopes:
        return list(hook.scopes)
    return ["mcp:tools", "mcp:resources"]


async def _connection_for_hook(session: AsyncSession, hook: Hook) -> McpOAuthConnection | None:
    result = await session.execute(
        select(McpOAuthConnection)
        .where(McpOAuthConnection.hook_id == hook.id)
        .order_by(McpOAuthConnection.updated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _find_hook(session: AsyncSession, hook_id: str) -> Hook | None:
    filters = [Hook.urn == f"{HOOK_URN_PREFIX}{hook_id}"]
    try:
        filters.append(Hook.id == UUID(hook_id))
    except ValueError:
        pass
    result = await session.execute(select(Hook).where(or_(*filters)))
    return result.scalar_one_or_none()


async def _find_connection(session: AsyncSession, connection_id: str) -> McpOAuthConnection | None:
    filters = [McpOAuthConnection.urn == f"{MCP_OAUTH_URN_PREFIX}{connection_id}", McpOAuthConnection.urn == connection_id]
    try:
        filters.append(McpOAuthConnection.id == UUID(connection_id))
    except ValueError:
        pass
    result = await session.execute(select(McpOAuthConnection).where(or_(*filters)).limit(1))
    return result.scalar_one_or_none()


def _connection_to_api(row: McpOAuthConnection) -> dict[str, Any]:
    token_set = row.token_set if isinstance(row.token_set, dict) else {}
    return {
        "id": row.urn.removeprefix(MCP_OAUTH_URN_PREFIX),
        "urn": row.urn,
        "hook_id": str(row.hook_id) if row.hook_id else None,
        "endpoint": row.endpoint,
        "status": row.status,
        "issuer": row.issuer,
        "authorization_endpoint": row.authorization_endpoint,
        "token_endpoint": row.token_endpoint,
        "registration_endpoint": row.registration_endpoint,
        "client_id": row.client_id,
        "client_secret_configured": bool(row.client_secret),
        "redirect_uri": row.redirect_uri,
        "scopes": row.scopes,
        "token_configured": bool(token_set.get("access_token")),
        "refresh_token_configured": bool(token_set.get("refresh_token")),
        "token_expires_at": row.token_expires_at.isoformat() if row.token_expires_at else None,
    }


def _redact_client_secret(metadata: dict[str, Any]) -> dict[str, Any]:
    copied = {
        "protected_resource": metadata.get("protected_resource", {}),
        "authorization_server": metadata.get("authorization_server", {}),
        "client": dict(metadata.get("client", {})) if isinstance(metadata.get("client"), dict) else {},
    }
    if "client_secret" in copied["client"]:
        copied["client"]["client_secret"] = "[redacted]"
    return copied
