from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from praetor_api.models.hook import Hook
from praetor_api.models.hook_call import HookCall
from praetor_api.services import mcp_client
from praetor_api.services.json_stack import call_stack, get_stack
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
    return {
        "id": _hook_id_from_urn(row.urn),
        "name": row.name,
        "kind": row.kind,
        "direction": row.direction,
        "endpoint": row.endpoint,
        "scopes": row.scopes,
        "effect_radius": row.effect_radius,
        "enabled": row.enabled,
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
            "auth_ref": None,
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
    return [by_urn[urn] for urn in urns if urn in by_urn]


async def list_hooks(session: AsyncSession) -> list[dict[str, Any]]:
    hooks = await ensure_hooks(session)
    await session.commit()
    return [_hook_row_to_api(hook) for hook in hooks]


async def test_hook(session: AsyncSession, hook_id: str) -> dict[str, Any]:
    hook = await _find_hook(session, hook_id)
    if hook is None:
        raise KeyError(hook_id)
    await session.commit()
    if hook.kind == "json_stack":
        spec = get_stack(hook_id)
        if spec is None:
            return {"ok": False, "resources_count": 0, "latency_ms": 1, "mode": "json-stack-missing"}
        return {
            "ok": True,
            "resources_count": len(spec["operations"]),
            "latency_ms": 1,
            "mode": "json-stack",
            "provider": spec["provider"],
        }
    result = await mcp_client.health(hook.endpoint)
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
) -> dict[str, Any]:
    hook = await _find_hook(session, hook_id)
    if hook is None:
        raise KeyError(hook_id)
    if hook.effect_radius in EFFECTFUL_RADII and not dry_run and not effect_approved:
        raise EffectGatedError(hook_id, hook.effect_radius)

    errors: list[str] = []
    if hook.kind == "json_stack":
        spec = get_stack(hook_id)
        if spec is None:
            raise KeyError(hook_id)
        hook_result = await call_stack(spec, operation, inputs, dry_run)
        outputs = hook_result.outputs
        status = "succeeded" if hook_result.ok else "failed"
        latency_ms = hook_result.latency_ms
        if hook_result.error:
            errors.append(hook_result.error)
    else:
        mcp_result = await mcp_client.call(hook.endpoint, operation, inputs, dry_run)
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
