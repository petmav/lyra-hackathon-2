from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from praetor_api.db import AsyncSessionLocal
from praetor_api.services.demo_workflows import (
    get_workflow,
    list_workflows,
    run_code_compliance_scan,
    RUNS,
)
from praetor_api.services import production_workflows
from praetor_api.settings import get_settings

router = APIRouter(tags=["workflows"])


class RunWorkflowRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    inputs: dict[str, Any] = Field(default_factory=dict)
    model_provider: str | None = None
    model: str | None = None


class ResumeWorkflowRequest(BaseModel):
    approved: bool = True
    approver: str = "api"


class DrainWorkflowRequest(BaseModel):
    limit: int = 1
    worker_id: str | None = None
    lease_seconds: int = Field(default=300, ge=30, le=3600)


class WorkflowGraphPayload(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class WorkflowCreatePayload(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    name: str
    id: str | None = None
    description: str | None = None
    trigger: str = "manual"
    trigger_config: dict[str, Any] | None = None
    inputs_schema: dict[str, Any] | None = None
    outputs_schema: dict[str, Any] | None = None
    required_hooks: list[str] = Field(default_factory=list)
    required_corpora: list[str] = Field(default_factory=list)
    default_policy_set: str = "praetor-demo"
    graph: WorkflowGraphPayload


class WorkflowPatchPayload(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    name: str | None = None
    description: str | None = None
    trigger: str | None = None
    required_hooks: list[str] | None = None
    required_corpora: list[str] | None = None
    graph: WorkflowGraphPayload | None = None


@router.get("/workflows")
async def workflows() -> list[dict[str, Any]]:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            return await production_workflows.list_workflows(session)
    return list_workflows()


@router.get("/workflows/nodes/catalog")
async def workflow_node_catalog() -> list[dict[str, Any]]:
    return production_workflows.list_node_catalog()


@router.post("/workflows", status_code=201)
async def create_workflow(payload: WorkflowCreatePayload) -> dict[str, Any]:
    if get_settings().data_mode != "production":
        raise HTTPException(status_code=400, detail="creating workflows requires production data mode")
    try:
        async with AsyncSessionLocal() as session:
            return await production_workflows.create_custom_workflow(
                session,
                payload.model_dump(exclude_none=True),
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.patch("/workflows/{workflow_id}")
async def patch_workflow(workflow_id: str, payload: WorkflowPatchPayload) -> dict[str, Any]:
    if get_settings().data_mode != "production":
        raise HTTPException(status_code=400, detail="editing workflows requires production data mode")
    try:
        async with AsyncSessionLocal() as session:
            updated = await production_workflows.update_custom_workflow(
                session, workflow_id, payload.model_dump(exclude_none=True)
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    if updated is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return updated


@router.delete("/workflows/{workflow_id}", status_code=204)
async def delete_workflow(workflow_id: str) -> None:
    if get_settings().data_mode != "production":
        raise HTTPException(status_code=400, detail="deleting workflows requires production data mode")
    async with AsyncSessionLocal() as session:
        ok = await production_workflows.delete_custom_workflow(session, workflow_id)
    if not ok:
        raise HTTPException(status_code=404, detail="workflow not found or is a template")
    return None


@router.get("/workflows/{workflow_id}")
async def workflow(workflow_id: str) -> dict[str, Any]:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            found = await production_workflows.get_workflow(session, workflow_id)
        if found is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        return found

    found = get_workflow(workflow_id)
    if found is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return found


@router.post("/workflows/{workflow_id}:run")
@router.post("/workflows/{workflow_id}/run")
async def run_workflow(workflow_id: str, request: RunWorkflowRequest) -> dict[str, str]:
    settings = get_settings()
    if settings.data_mode == "production":
        async with AsyncSessionLocal() as session:
            if await production_workflows.get_workflow(session, workflow_id) is None:
                raise HTTPException(status_code=404, detail="workflow not found")
            if settings.workflow_execution_mode == "queued":
                run = await production_workflows.enqueue_workflow_run(
                    session,
                    workflow_id,
                    request.inputs,
                    model_provider=request.model_provider or settings.default_model_provider,
                    model=request.model or settings.default_model_name,
                )
            else:
                run = await production_workflows.run_workflow(
                    session,
                    workflow_id,
                    request.inputs,
                    model_provider=request.model_provider or settings.default_model_provider,
                    model=request.model or settings.default_model_name,
                )
    else:
        if get_workflow(workflow_id) is None:
            raise HTTPException(status_code=404, detail="workflow not found")

        run = await run_code_compliance_scan(
            request.inputs,
            model_provider=request.model_provider or settings.default_model_provider,
            model=request.model or settings.default_model_name,
        )
    return {"workflow_run_id": run["id"]}


@router.post("/workflow-runs:drain")
async def drain_workflow_runs(request: DrainWorkflowRequest) -> dict[str, Any]:
    if get_settings().data_mode != "production":
        return {"processed": [], "count": 0}
    async with AsyncSessionLocal() as session:
        processed = await production_workflows.drain_queued_workflows(
            session,
            limit=request.limit,
            worker_id=request.worker_id,
            lease_seconds=request.lease_seconds,
        )
    return {"processed": processed, "count": len(processed)}


@router.get("/workflow-runs")
async def workflow_runs() -> list[dict[str, Any]]:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            return await production_workflows.list_workflow_runs(session)
    return list(RUNS.values())


@router.post("/workflow-runs/{run_id}:resume")
@router.post("/workflow-runs/{run_id}/resume")
async def resume_workflow(run_id: str, request: ResumeWorkflowRequest) -> dict[str, Any]:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            run = await production_workflows.resume_workflow_run(
                session,
                run_id,
                approved=request.approved,
                approver=request.approver,
            )
        if run is None:
            raise HTTPException(status_code=404, detail="workflow run not found")
        return run

    try:
        run = RUNS[run_id]
    except KeyError:
        raise HTTPException(status_code=404, detail="workflow run not found") from None
    run["status"] = "succeeded" if request.approved else "cancelled"
    return run


@router.post("/workflow-runs/{run_id}:cancel")
@router.post("/workflow-runs/{run_id}/cancel")
async def cancel_workflow(run_id: str) -> dict[str, bool]:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            found = await production_workflows.cancel_workflow_run(session, run_id)
        if not found:
            raise HTTPException(status_code=404, detail="workflow run not found")
        return {"ok": True}

    try:
        RUNS[run_id]["status"] = "cancelled"
    except KeyError:
        raise HTTPException(status_code=404, detail="workflow run not found") from None
    return {"ok": True}


@router.get("/workflow-runs/{run_id}")
async def workflow_run(run_id: str) -> dict[str, Any]:
    if get_settings().data_mode == "production":
        async with AsyncSessionLocal() as session:
            run = await production_workflows.workflow_run_by_id(session, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="workflow run not found")
        return run

    try:
        return RUNS[run_id]
    except KeyError:
        raise HTTPException(status_code=404, detail="workflow run not found") from None
