from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from praetor_api.services.event_stream import append_event, make_event

RUNS: dict[str, dict[str, Any]] = {}

CODE_COMPLIANCE_SCAN = {
    "id": "code_compliance_scan",
    "urn": "urn:praetor:workflow:demo:code-compliance-scan",
    "name": "code_compliance_scan",
    "description": "Pull a repository, scan send_email controls, and emit a finding.",
    "definition": "pull -> scan -> emit",
    "trigger": "manual",
    "required_hooks": ["github_stub"],
    "required_corpora": ["iso_42001", "internal_data_min"],
}


def list_workflows() -> list[dict[str, Any]]:
    return [CODE_COMPLIANCE_SCAN]


def get_workflow(workflow_id: str) -> dict[str, Any] | None:
    if workflow_id in {CODE_COMPLIANCE_SCAN["id"], CODE_COMPLIANCE_SCAN["urn"]}:
        return CODE_COMPLIANCE_SCAN
    return None


async def run_code_compliance_scan(
    inputs: dict[str, Any],
    *,
    model_provider: str = "openai",
    model: str = "gpt-4.1-mini",
) -> dict[str, Any]:
    run_id = f"wfr_{uuid4().hex[:12]}"
    now = datetime.now(UTC).isoformat()
    finding = {
        "id": f"fnd_{uuid4().hex[:12]}",
        "title": "send_email lacks recipient domain validation",
        "description": "The Northwind support-bot can send email to arbitrary recipient domains.",
        "severity": "high",
        "confidence": 0.92,
        "obligations_cited": [
            "urn:praetor:obligation:demo:iso-42001-8-3",
            "urn:praetor:obligation:demo:internal-data-min",
        ],
        "documents_cited": [],
        "status": "open",
    }
    run = {
        "id": run_id,
        "workflow_id": CODE_COMPLIANCE_SCAN["id"],
        "status": "succeeded",
        "triggered_by": "api",
        "triggered_at": now,
        "inputs": inputs,
        "model_provider": model_provider,
        "model": model,
        "outputs": {"findings": [finding]},
        "step_runs": [
            {
                "step_id": "pull",
                "step_type": "hook.in",
                "status": "succeeded",
                "outputs_redacted": {"repo_url": inputs.get("repo_url", "stub://support-bot")},
            },
            {
                "step_id": "scan",
                "step_type": "agent",
                "status": "succeeded",
                "model_provider": model_provider,
                "model": model,
                "outputs_redacted": {"findings": [finding]},
            },
            {
                "step_id": "emit",
                "step_type": "finding.emit",
                "status": "succeeded",
                "outputs_redacted": {"count": 1},
            },
        ],
    }
    RUNS[run_id] = run
    asset_id = "asset_northwind_support_bot"
    await append_event(
        make_event(
            asset_id=asset_id,
            workflow_run_id=run_id,
            event_type="workflow.run.started",
            actor="workflow_runtime",
            payload={"workflow_id": CODE_COMPLIANCE_SCAN["id"], "inputs": inputs},
        )
    )
    for step in run["step_runs"]:
        await append_event(
            make_event(
                asset_id=asset_id,
                workflow_run_id=run_id,
                workflow_step_id=step["step_id"],
                event_type="workflow.step.finished",
                actor="workflow_runtime",
                payload={
                    "step_id": step["step_id"],
                    "step_type": step["step_type"],
                    "status": step["status"],
                    "outputs_redacted": step["outputs_redacted"],
                },
            )
        )
    await append_event(
        make_event(
            asset_id=asset_id,
            workflow_run_id=run_id,
            event_type="finding.emitted",
            actor="workflow_runtime",
            payload={"finding": finding},
        )
    )
    await append_event(
        make_event(
            asset_id=asset_id,
            workflow_run_id=run_id,
            event_type="workflow.run.finished",
            actor="workflow_runtime",
            payload={"status": run["status"]},
        )
    )
    return run
