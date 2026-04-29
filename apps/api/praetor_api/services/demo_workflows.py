from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from praetor_api.services.event_stream import append_event, make_event

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
        await _append_step_trace(asset_id, run_id, step)
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


async def _append_step_trace(asset_id: str, run_id: str, step: dict[str, Any]) -> None:
    await append_event(
        make_event(
            asset_id=asset_id,
            workflow_run_id=run_id,
            workflow_step_id=step["step_id"],
            event_type="workflow.step.started",
            actor="workflow_runtime",
            payload={
                "step_id": step["step_id"],
                "step_type": step["step_type"],
                "status": "running",
            },
        )
    )
    for event_type, actor, payload in _demo_step_trace_events(step):
        await append_event(
            make_event(
                asset_id=asset_id,
                workflow_run_id=run_id,
                workflow_step_id=step["step_id"],
                event_type=event_type,
                actor=actor,
                payload=payload | {"step_id": step["step_id"], "step_type": step["step_type"]},
            )
        )
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


def _demo_step_trace_events(step: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    outputs = step.get("outputs_redacted") or {}
    if step["step_type"] == "hook.in":
        return [
            (
                "hook.in.called",
                "praetor:hooks",
                {"repo_url": outputs.get("repo_url"), "summary": "Loaded source artefacts through the inbound hook."},
            )
        ]
    if step["step_type"] == "agent":
        findings = outputs.get("findings", [])
        return [
            (
                "agent.thought",
                "workflow_agent",
                {
                    "text": "Reviewed source artefacts and policy obligations; produced structured findings.",
                    "findings_count": len(findings) if isinstance(findings, list) else 0,
                },
            ),
            (
                "agent.tool.called",
                "workflow_agent",
                {"name": "emit_finding", "status": "ok", "items": len(findings) if isinstance(findings, list) else 0},
            ),
        ]
    if step["step_type"] == "finding.emit":
        emitted = outputs.get("emitted") or []
        if not emitted and "count" in outputs:
            emitted = [{"count": outputs["count"]}]
        return [
            ("finding.emitted", "workflow_runtime", {"finding": item})
            for item in emitted
            if isinstance(item, dict)
        ]
    return []
