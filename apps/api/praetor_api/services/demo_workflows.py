import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from praetor_api.settings import get_settings

RUNS: dict[str, dict[str, Any]] = {}

WORKFLOWS: list[dict[str, Any]] = [
    {
        "id": "code_compliance_scan",
        "urn": "urn:praetor:workflow:demo:code-compliance-scan",
        "name": "code_compliance_scan",
        "description": "Pull a repository, scan controls, and emit a finding.",
        "definition": "pull -> retrieve_controls -> scan -> emit",
        "trigger": "manual",
        "required_hooks": ["github_stub"],
        "required_corpora": ["iso_42001", "internal_data_min"],
    },
    {
        "id": "code_compliance_scan_full",
        "urn": "urn:praetor:workflow:demo:code-compliance-scan-full",
        "name": "code_compliance_scan_full",
        "description": "Full code compliance scan with sandboxed remediation PR.",
        "definition": "pull -> retrieve_controls -> scan -> emit -> propose -> policy_gate -> human_gate -> open_pr",
        "trigger": "manual",
        "required_hooks": ["github_stub"],
        "required_corpora": ["iso_42001", "internal_data_min"],
    },
    {
        "id": "vendor_risk_review",
        "urn": "urn:praetor:workflow:demo:vendor-risk-review",
        "name": "vendor_risk_review",
        "description": "SOC2/ISO gap analysis on a vendor attestation, with remediation proposal.",
        "definition": "load_attestation -> retrieve_obligations -> analyze -> emit -> propose_remediation",
        "trigger": "manual",
        "required_hooks": ["github_stub"],
        "required_corpora": ["iso_42001"],
    },
    {
        "id": "policy_gap_analysis",
        "urn": "urn:praetor:workflow:demo:policy-gap-analysis",
        "name": "policy_gap_analysis",
        "description": "Onboard a new regulation and propose new control text.",
        "definition": "load_regulation -> retrieve_existing_controls -> analyze_gaps -> emit -> propose_controls -> policy_gate -> human_gate",
        "trigger": "manual",
        "required_hooks": [],
        "required_corpora": ["iso_42001", "internal_data_min"],
    },
    {
        "id": "evidence_collection",
        "urn": "urn:praetor:workflow:demo:evidence-collection",
        "name": "evidence_collection",
        "description": "Sweep source systems, organise candidates, bind to obligations.",
        "definition": "read_files -> retrieve_obligations -> organize -> emit",
        "trigger": "manual",
        "required_hooks": ["github_stub"],
        "required_corpora": ["iso_42001"],
    },
    {
        "id": "ai_system_intake",
        "urn": "urn:praetor:workflow:demo:ai-system-intake",
        "name": "ai_system_intake",
        "description": "Classify a newly-registered AI system and gate the tier.",
        "definition": "intake_form -> retrieve_obligations -> classify -> policy_gate -> emit",
        "trigger": "manual",
        "required_hooks": [],
        "required_corpora": ["iso_42001"],
    },
]

CODE_COMPLIANCE_SCAN = WORKFLOWS[0]


def list_workflows() -> list[dict[str, Any]]:
    return list(WORKFLOWS)


def get_workflow(workflow_id: str) -> dict[str, Any] | None:
    for wf in WORKFLOWS:
        if workflow_id in {wf["id"], wf["urn"]}:
            return wf
    return None


async def run_workflow(
    workflow_id: str,
    inputs: dict[str, Any],
    *,
    model_provider: str = "openai",
    model: str = "gpt-4o-mini",
    sync: bool = False,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    """Create a demo run and schedule the simulator.

    Returns the initial run dict with `status="running"` immediately.
    Caller is the FastAPI route in `routers/workflows.py`. When `sync=True`,
    awaits the simulator inline and returns the terminal run (used by tests).
    """
    from praetor_api.services.demo_simulator import SCRIPTS, tick_run

    if workflow_id not in SCRIPTS:
        for wf in WORKFLOWS:
            if wf["urn"] == workflow_id:
                workflow_id = wf["id"]
                break

    script = SCRIPTS.get(workflow_id)
    if script is None:
        raise KeyError(workflow_id)

    run_id = f"wfr_{uuid4().hex[:12]}"
    now = datetime.now(UTC).isoformat()
    run = {
        "id": run_id,
        "urn": f"urn:praetor:workflow-run:{run_id}",
        "workflow_id": workflow_id,
        "asset_id": script.asset_id,
        "status": "running",
        "triggered_by": "api",
        "triggered_at": now,
        "created_at": now,
        "updated_at": now,
        "started_at": now,
        "finished_at": None,
        "inputs": dict(inputs),
        "model_provider": model_provider,
        "model": model,
        "outputs": {"findings": [], "proposed_changes": []},
        "step_runs": [
            {
                "step_id": step.step_id,
                "step_type": step.step_type,
                "status": "pending",
                "outputs_redacted": {},
                "depends_on": [script.steps[i - 1].step_id] if i > 0 else [],
                "model_provider": model_provider if step.step_type == "agent" else None,
                "model": model if step.step_type == "agent" else None,
            }
            for i, step in enumerate(script.steps)
        ],
    }
    RUNS[run_id] = run

    settings = get_settings()
    api_key = settings.openai_api_key

    if sync:
        await tick_run(
            run_id,
            script=script,
            sleep=sleep or asyncio.sleep,
            openai_api_key=api_key,
        )
        return RUNS[run_id]

    asyncio.create_task(
        tick_run(run_id, script=script, openai_api_key=api_key)
    )
    return run
