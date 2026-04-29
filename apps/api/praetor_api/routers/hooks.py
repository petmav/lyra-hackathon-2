from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from praetor_api.db import AsyncSessionLocal
from praetor_api.services.hooks import CALLS, HOOKS, call_hook, test_hook
from praetor_api.services import production_hooks
from praetor_api.services.json_stack import call_stack, catalog_summary, get_stack, validate_stack
from praetor_api.settings import get_settings

router = APIRouter(tags=["hooks"])


class HookCallRequest(BaseModel):
    operation: str
    inputs: dict = Field(default_factory=dict)
    dry_run: bool = True
    effect_approved: bool = False


class JsonStackValidateRequest(BaseModel):
    spec: dict = Field(default_factory=dict)


class JsonStackPersistRequest(BaseModel):
    spec: dict = Field(default_factory=dict)
    enabled: bool = True


class JsonStackPreviewRequest(BaseModel):
    spec: dict | None = None
    stack_id: str | None = None
    operation: str
    inputs: dict = Field(default_factory=dict)


@router.get("/hooks/json-stack/catalog")
async def json_stack_catalog() -> list[dict]:
    return catalog_summary()


@router.get("/hooks/json-stack/catalog/{stack_id}")
async def json_stack_catalog_item(stack_id: str) -> dict:
    spec = get_stack(stack_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="json stack not found")
    return spec


@router.post("/hooks/json-stack:validate")
@router.post("/hooks/json-stack/validate")
async def json_stack_validate(request: JsonStackValidateRequest) -> dict:
    errors = validate_stack(request.spec)
    return {"ok": not errors, "errors": errors}


@router.post("/hooks/json-stack:preview")
@router.post("/hooks/json-stack/preview")
async def json_stack_preview(request: JsonStackPreviewRequest) -> dict:
    spec = request.spec or (get_stack(request.stack_id) if request.stack_id else None)
    if spec is None and request.stack_id and get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            hook = await production_hooks.get_hook(session, request.stack_id)
        if hook is not None:
            spec = hook.get("json_stack")
    if spec is None:
        raise HTTPException(status_code=404, detail="json stack not found")
    result = await call_stack(spec, request.operation, request.inputs, dry_run=True)
    return {
        "ok": result.ok,
        "outputs": result.outputs,
        "latency_ms": result.latency_ms,
        "error": result.error,
    }


@router.post("/hooks/json-stack")
async def json_stack_persist(request: JsonStackPersistRequest) -> dict:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            result = await production_hooks.upsert_json_stack_hook(
                session,
                request.spec,
                enabled=request.enabled,
            )
        if not result["ok"]:
            raise HTTPException(status_code=422, detail=result)
        return result
    errors = validate_stack(request.spec)
    if errors:
        raise HTTPException(status_code=422, detail={"ok": False, "errors": errors})
    return {"ok": True, "hook": {"id": request.spec["id"], "source": "validated-demo-only"}}


@router.get("/hooks")
async def list_hooks() -> list[dict]:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            return await production_hooks.list_hooks(session)
    return list(HOOKS.values())


@router.get("/hooks/{hook_id}")
async def get_hook(hook_id: str) -> dict:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            hook = await production_hooks.get_hook(session, hook_id)
        if hook is None:
            raise HTTPException(status_code=404, detail="hook not found")
        return hook
    hook = HOOKS.get(hook_id)
    if hook is None:
        raise HTTPException(status_code=404, detail="hook not found")
    return hook


@router.post("/hooks/{hook_id}:test")
@router.post("/hooks/{hook_id}/test")
async def test(hook_id: str) -> dict:
    try:
        if get_settings().data_mode == "production":
            async with AsyncSessionLocal() as session:
                return await production_hooks.test_hook(session, hook_id)
        return test_hook(hook_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="hook not found") from None


@router.get("/hook-calls")
async def hook_calls() -> list[dict]:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            return await production_hooks.list_hook_calls(session)
    return CALLS


@router.post("/hooks/{hook_id}:call")
@router.post("/hooks/{hook_id}/call")
async def call(hook_id: str, request: HookCallRequest) -> dict:
    try:
        if get_settings().data_mode == "production":
            async with AsyncSessionLocal() as session:
                return await production_hooks.call_hook(
                    session,
                    hook_id,
                    request.operation,
                    request.inputs,
                    request.dry_run,
                    effect_approved=request.effect_approved,
                )
        return call_hook(hook_id, request.operation, request.inputs, request.dry_run)
    except KeyError:
        raise HTTPException(status_code=404, detail="hook not found") from None
    except production_hooks.EffectGatedError as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "effect-gated",
                "hook_id": exc.hook_id,
                "effect_radius": exc.effect_radius,
            },
        ) from None
