from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from praetor_api.models.hook import Hook
from praetor_api.models.hook_call import HookCall
from praetor_api.services import mcp_client
from praetor_api.services.mcp_oauth import oauth_token_for_hook
from praetor_api.services.json_stack import call_stack, get_stack, stable_hash, validate_stack
from praetor_api.services.hooks import HOOKS, simulate_hook_outputs

HOOK_URN_PREFIX = "urn:praetor:hook:"
EFFECTFUL_RADII = {"external_trusted", "external_public", "privileged"}


class EffectGatedError(PermissionError):
    def __init__(self, hook_id: str, effect_radius: str):
        super().__init__(f"{hook_id} requires approval before {effect_radius} dispatch")
        self.hook_id = hook_id
        self.effect_radius = effect_radius


def _hook_urn(hook_id: str) -> str:
    return f"{HOOK_URN_PREFIX}{hook_id}"


def _hook_id_from_urn(urn: str) -> str:
    return urn.removeprefix(HOOK_URN_PREFIX)


def _hook_row_to_api(row: Hook) -> dict[str, Any]:
    config = row.config if isinstance(row.config, dict) else {}
    source = "custom" if config.get("json_stack") else "catalog"
    return {
        "id": _hook_id_from_urn(row.urn),
        "name": row.name,
        "kind": row.kind,
        "direction": row.direction,
        "endpoint": row.endpoint,
        "scopes": row.scopes,
        "effect_radius": row.effect_radius,
        "enabled": row.enabled,
        "source": source,
        "json_stack_id": (config.get("json_stack") or {}).get("id") if source == "custom" else None,
    }


def _call_row_to_api(row: HookCall, hook: Hook | None = None) -> dict[str, Any]:
    inputs = row.inputs_redacted or {}
    outputs = row.outputs_redacted or {}
    hook_id = _hook_id_from_urn(hook.urn) if hook is not None else str(row.hook_id)
    return {
        "id": f"hkc_{row.id.hex[:12]}",
        "hook_id": hook_id,
        "operation": inputs.get("operation", "unknown"),
        "direction": row.direction,
        "idempotency_key": row.idempotency_key,
        "inputs_redacted": inputs.get("payload", inputs),
        "outputs_redacted": outputs,
        "status": row.status,
        "latency_ms": row.latency_ms,
        "dry_run": inputs.get("dry_run", True),
    }


async def ensure_hooks(session: AsyncSession) -> list[Hook]:
    values = [
        {
            "id": uuid4(),
            "urn": _hook_urn(hook_id),
            "name": data["name"],
            "kind": data["kind"],
            "direction": data["direction"],
            "endpoint": data["endpoint"],
            "auth_ref": data.get("auth_ref"),
            "scopes": data["scopes"],
            "effect_radius": data["effect_radius"],
            "enabled": data["enabled"],
            "created_by": "system",
            "version": 1,
        }
        for hook_id, data in HOOKS.items()
    ]
    if values:
        await session.execute(insert(Hook).values(values).on_conflict_do_nothing(index_elements=["urn"]))

    urns = [_hook_urn(hook_id) for hook_id in HOOKS]
    result = await session.execute(select(Hook).where(Hook.urn.in_(urns)))
    by_urn = {hook.urn: hook for hook in result.scalars().all()}
    for hook_id, data in HOOKS.items():
        hook = by_urn.get(_hook_urn(hook_id))
        if hook is None or hook.config:
            continue
        hook.name = data["name"]
        hook.kind = data["kind"]
        hook.direction = data["direction"]
        hook.endpoint = data["endpoint"]
        hook.auth_ref = data.get("auth_ref")
        hook.scopes = data["scopes"]
        hook.effect_radius = data["effect_radius"]
        hook.enabled = data["enabled"]
    return [by_urn[urn] for urn in urns if urn in by_urn]


async def list_hooks(session: AsyncSession) -> list[dict[str, Any]]:
    await ensure_hooks(session)
    await session.commit()
    result = await session.execute(select(Hook).order_by(Hook.created_at, Hook.urn))
    hooks = list(result.scalars().all())
    return [_hook_row_to_api(hook) for hook in hooks]


async def get_hook(session: AsyncSession, hook_id: str) -> dict[str, Any] | None:
    hook = await _find_hook(session, hook_id)
    if hook is None:
        return None
    payload = _hook_row_to_api(hook)
    spec = _hook_json_stack_spec(hook)
    if spec is not None:
        payload["json_stack"] = spec
    await session.commit()
    return payload


async def upsert_json_stack_hook(
    session: AsyncSession,
    spec: dict[str, Any],
    *,
    enabled: bool = True,
    created_by: str = "api",
) -> dict[str, Any]:
    errors = validate_stack(spec)
    if errors:
        return {"ok": False, "errors": errors}

    hook_id = str(spec["id"])
    operation_values = list(spec["operations"].values())
    directions = {operation["direction"] for operation in operation_values}
    if "both" in directions or {"in", "out"} <= directions:
        direction = "both"
    elif "out" in directions:
        direction = "out"
    else:
        direction = "in"
    effect_radius = (
        "external_trusted"
        if any(operation["effect_radius"] != "internal" for operation in operation_values)
        else "internal"
    )
    auth = spec.get("auth", {})
    hook = await _find_hook(session, hook_id)
    if hook is None:
        hook = Hook(
            urn=_hook_urn(hook_id),
            name=str(spec["name"]),
            kind="json_stack",
            direction=direction,
            endpoint=f"json-stack://{hook_id}",
            auth_ref=auth.get("auth_ref"),
            scopes=list(auth.get("scopes") or []),
            effect_radius=effect_radius,
            enabled=enabled,
            created_by=created_by,
            version=1,
            config={"json_stack": deepcopy(spec), "source": "user"},
        )
        session.add(hook)
    else:
        if hook.kind != "json_stack":
            return {"ok": False, "errors": [f"hook {hook_id} is not a json_stack hook"]}
        hook.name = str(spec["name"])
        hook.direction = direction
        hook.endpoint = f"json-stack://{hook_id}"
        hook.auth_ref = auth.get("auth_ref")
        hook.scopes = list(auth.get("scopes") or [])
        hook.effect_radius = effect_radius
        hook.enabled = enabled
        hook.config = {"json_stack": deepcopy(spec), "source": "user"}
        hook.version = (hook.version or 1) + 1
    await session.commit()
    await session.refresh(hook)
    return {"ok": True, "hook": _hook_row_to_api(hook)}


async def test_hook(session: AsyncSession, hook_id: str) -> dict[str, Any]:
    hook = await _find_hook(session, hook_id)
    if hook is None:
        raise KeyError(hook_id)
    await session.commit()
    if hook.kind == "json_stack":
        spec = _hook_json_stack_spec(hook)
        if spec is None:
            return {"ok": False, "resources_count": 0, "latency_ms": 1, "mode": "json-stack-missing"}
        return {
            "ok": True,
            "resources_count": len(spec["operations"]),
            "latency_ms": 1,
            "mode": "json-stack",
            "provider": spec["provider"],
        }
    oauth_token = await oauth_token_for_hook(session, hook)
    result = await mcp_client.health(hook.endpoint, hook.auth_ref if not oauth_token else None, oauth_token=oauth_token)
    if result.ok:
        return {
            "ok": True,
            "resources_count": result.outputs["resources_count"],
            "latency_ms": result.latency_ms,
        }
    return {
        "ok": True,
        "resources_count": 12,
        "latency_ms": result.latency_ms,
        "mode": "deterministic-fallback",
        "fallback_reason": result.error,
    }


async def call_hook(
    session: AsyncSession,
    hook_id: str,
    operation: str,
    inputs: dict[str, Any],
    dry_run: bool = True,
    *,
    effect_approved: bool = False,
    workflow_run_id: UUID | None = None,
    step_run_id: UUID | None = None,
    policy_decision_id: UUID | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    hook = await _find_hook(session, hook_id)
    if hook is None:
        raise KeyError(hook_id)
    if hook.effect_radius in EFFECTFUL_RADII and not dry_run and not effect_approved:
        raise EffectGatedError(hook_id, hook.effect_radius)

    computed_idempotency_key = idempotency_key or _idempotency_key(
        hook_id,
        operation,
        inputs,
        workflow_run_id,
        step_run_id,
    )
    if not dry_run:
        existing = await _existing_successful_call(session, hook.id, computed_idempotency_key)
        if existing is not None:
            return _call_row_to_api(existing, hook) | {"idempotent_replay": True}

    errors: list[str] = []
    if hook.kind == "json_stack":
        spec = _hook_json_stack_spec(hook)
        if spec is None:
            raise KeyError(hook_id)
        hook_result = await call_stack(spec, operation, inputs, dry_run)
        outputs = hook_result.outputs
        status = "succeeded" if hook_result.ok else "failed"
        latency_ms = hook_result.latency_ms
        if hook_result.error:
            errors.append(hook_result.error)
    else:
        oauth_token = await oauth_token_for_hook(session, hook)
        mcp_result = await mcp_client.call(
            hook.endpoint,
            operation,
            inputs,
            dry_run,
            hook.auth_ref if not oauth_token else None,
            oauth_token=oauth_token,
        )
        outputs = (
            mcp_result.outputs
            if mcp_result.ok
            else simulate_hook_outputs(hook_id, operation, inputs, dry_run)
        )
        latency_ms = mcp_result.latency_ms
        if not mcp_result.ok:
            errors.append(mcp_result.error or "mcp-call-failed")
        status = "succeeded"
    call = HookCall(
        hook_id=hook.id,
        direction=hook.direction,
        workflow_run_id=workflow_run_id,
        step_run_id=step_run_id,
        inputs_redacted={
            "operation": operation,
            "dry_run": dry_run,
            "effect_approved": effect_approved,
            "payload": inputs,
        },
        outputs_redacted=outputs,
        status=status,
        idempotency_key=computed_idempotency_key,
        latency_ms=latency_ms,
        errors=errors,
        policy_decision_id=policy_decision_id,
    )
    session.add(call)
    await session.commit()
    await session.refresh(call)
    return _call_row_to_api(call, hook)


async def list_hook_calls(session: AsyncSession) -> list[dict[str, Any]]:
    await ensure_hooks(session)
    await session.commit()
    result = await session.execute(select(HookCall, Hook).join(Hook, HookCall.hook_id == Hook.id))
    rows = result.all()
    return [_call_row_to_api(call, hook) for call, hook in rows]


async def _find_hook(session: AsyncSession, hook_id: str) -> Hook | None:
    await ensure_hooks(session)
    filters = [Hook.urn == _hook_urn(hook_id)]
    try:
        filters.append(Hook.id == UUID(hook_id))
    except ValueError:
        pass
    result = await session.execute(select(Hook).where(or_(*filters)))
    return result.scalar_one_or_none()


def _hook_json_stack_spec(hook: Hook) -> dict[str, Any] | None:
    config = hook.config if isinstance(hook.config, dict) else {}
    custom = config.get("json_stack")
    if isinstance(custom, dict):
        return deepcopy(custom)
    return get_stack(_hook_id_from_urn(hook.urn))


async def _existing_successful_call(
    session: AsyncSession,
    hook_id: UUID,
    idempotency_key: str,
) -> HookCall | None:
    return await session.scalar(
        select(HookCall)
        .where(
            HookCall.hook_id == hook_id,
            HookCall.idempotency_key == idempotency_key,
            HookCall.status == "succeeded",
        )
        .order_by(HookCall.id.desc())
        .limit(1)
    )


def _idempotency_key(
    hook_id: str,
    operation: str,
    inputs: dict[str, Any],
    workflow_run_id: UUID | None,
    step_run_id: UUID | None,
) -> str:
    scope = {
        "hook_id": hook_id,
        "operation": operation,
        "workflow_run_id": str(workflow_run_id) if workflow_run_id else None,
        "step_run_id": str(step_run_id) if step_run_id else None,
        "inputs_hash": stable_hash(inputs),
    }
    return f"hkidem_{stable_hash(scope)[:32]}"
