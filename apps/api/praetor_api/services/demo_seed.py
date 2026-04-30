"""Boot-time demo seed.

Populates the in-memory state with a handful of completed historical runs
across the six prefab workflows so the dashboard isn't empty when a viewer
opens `npm run demo`. Idempotent — safe to call multiple times.

Companion `_emit_history_events` (Task 7) emits the per-step trace into
EVENTS so opening any seeded run shows a populated activity log.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from praetor_api.services import demo_state, demo_workflows
from praetor_api.services.demo_simulator import SCRIPTS

logger = logging.getLogger(__name__)

_SEEDED_RUN_IDS = (
    "wfr_seed_ccscan_001",
    "wfr_seed_ccfull_002",
    "wfr_seed_vendor_003",
    "wfr_seed_policy_004",
    "wfr_seed_evidence_005",
    "wfr_seed_intake_006",
)

_SEED_PLAN: tuple[tuple[str, str, int], ...] = (
    # (run_id, workflow_id, hours_ago)
    ("wfr_seed_ccscan_001", "code_compliance_scan", 6),
    ("wfr_seed_ccfull_002", "code_compliance_scan_full", 18),
    ("wfr_seed_vendor_003", "vendor_risk_review", 30),
    ("wfr_seed_policy_004", "policy_gap_analysis", 54),
    ("wfr_seed_evidence_005", "evidence_collection", 78),
    ("wfr_seed_intake_006", "ai_system_intake", 102),
)


async def seed_all() -> None:
    """Populate RUNS, FINDINGS, PROPOSED_CHANGES for the seeded historical
    runs. Idempotent.
    """
    if all(rid in demo_workflows.RUNS for rid in _SEEDED_RUN_IDS):
        return

    for run_id, workflow_id, hours_ago in _SEED_PLAN:
        if run_id in demo_workflows.RUNS:
            continue
        script = SCRIPTS.get(workflow_id)
        if script is None:
            logger.warning("no script for seed workflow %s", workflow_id)
            continue
        triggered_at = datetime.now(UTC) - timedelta(hours=hours_ago)
        run = _build_succeeded_run(run_id, script, triggered_at)
        demo_workflows.RUNS[run_id] = run

        for step in script.steps:
            for finding in step.findings:
                demo_state.FINDINGS.setdefault(
                    finding["id"],
                    {
                        **finding,
                        "workflow_run_id": run_id,
                        "asset_id": script.asset_id,
                        "created_at": run["finished_at"],
                        "proposed_change_ids": [p["id"] for p in step.proposals],
                    },
                )
            for proposal in step.proposals:
                demo_state.PROPOSED_CHANGES.setdefault(
                    proposal["id"],
                    {
                        **proposal,
                        "target_asset_id": script.asset_id,
                        "created_at": run["finished_at"],
                    },
                )

        await _emit_history_events(run, script)


async def _emit_history_events(run: dict[str, Any], script) -> None:
    """Append the full per-step event trace for a seeded run into EVENTS.

    Events go through `make_event` so the per-asset hash chain extends
    correctly. Timestamps are overwritten in place so the seeded events
    appear at the historical run's wall-clock times rather than 'now'."""
    from praetor_api.services.event_stream import EVENTS, append_event, make_event

    asset_id = script.asset_id
    run_id = run["id"]

    cursor = datetime.fromisoformat(run["triggered_at"])

    started = make_event(
        asset_id=asset_id,
        workflow_run_id=run_id,
        event_type="workflow.run.started",
        actor="workflow_runtime",
        payload={"workflow_id": script.workflow_id, "inputs": run["inputs"]},
    )
    started["ts"] = cursor.isoformat()
    EVENTS.append(started)

    for step in script.steps:
        cursor += timedelta(milliseconds=400)
        step_started = make_event(
            asset_id=asset_id,
            workflow_run_id=run_id,
            workflow_step_id=step.step_id,
            event_type="workflow.step.started",
            actor="workflow_runtime",
            payload={
                "step": step.step_id,
                "step_id": step.step_id,
                "type": step.step_type,
                "step_type": step.step_type,
                "status": "running",
            },
        )
        step_started["ts"] = cursor.isoformat()
        EVENTS.append(step_started)

        for scripted in step.events:
            cursor += timedelta(milliseconds=600)
            event_asset_id = (
                f"asset_wfa_{run_id}_{step.step_id}"
                if step.step_type == "agent"
                and scripted.type.startswith(("agent.", "sandbox."))
                else asset_id
            )
            ev = make_event(
                asset_id=event_asset_id,
                workflow_run_id=run_id,
                workflow_step_id=step.step_id,
                event_type=scripted.type,
                actor=scripted.actor,
                payload=dict(scripted.payload)
                | {"step_id": step.step_id, "step_type": step.step_type},
            )
            ev["ts"] = cursor.isoformat()
            EVENTS.append(ev)

        cursor += timedelta(milliseconds=400)
        step_finished = make_event(
            asset_id=asset_id,
            workflow_run_id=run_id,
            workflow_step_id=step.step_id,
            event_type="workflow.step.finished",
            actor="workflow_runtime",
            payload={
                "step": step.step_id,
                "step_id": step.step_id,
                "step_type": step.step_type,
                "status": "succeeded",
                "outputs_redacted": dict(step.final_outputs),
            },
        )
        step_finished["ts"] = cursor.isoformat()
        EVENTS.append(step_finished)

    cursor += timedelta(milliseconds=400)
    finished = make_event(
        asset_id=asset_id,
        workflow_run_id=run_id,
        event_type="workflow.run.finished",
        actor="workflow_runtime",
        payload={"status": "succeeded"},
    )
    finished["ts"] = cursor.isoformat()
    EVENTS.append(finished)

    _ = append_event  # kept for symmetry with the simulator's emit path


def _build_succeeded_run(
    run_id: str,
    script,  # ScriptedRun
    triggered_at: datetime,
) -> dict[str, Any]:
    cursor = triggered_at
    step_runs: list[dict[str, Any]] = []
    for i, step in enumerate(script.steps):
        step_started = cursor
        cursor = cursor + timedelta(seconds=2)
        outputs_redacted = dict(step.final_outputs)
        if step.step_type == "agent":
            outputs_redacted["workflow_agent_asset_id"] = f"asset_wfa_{run_id}_{step.step_id}"
            outputs_redacted["workflow_agent_asset_urn"] = (
                f"urn:praetor:asset:workflow_agent:{run_id}:{step.step_id}"
            )
        step_runs.append(
            {
                "step_id": step.step_id,
                "step_type": step.step_type,
                "status": "succeeded",
                "outputs_redacted": outputs_redacted,
                "depends_on": [script.steps[i - 1].step_id] if i > 0 else [],
                "started_at": step_started.isoformat(),
                "finished_at": cursor.isoformat(),
                "model_provider": "openai" if step.step_type == "agent" else None,
                "model": "gpt-4o-mini" if step.step_type == "agent" else None,
            }
        )
    findings: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    for step in script.steps:
        findings.extend(step.findings)
        proposals.extend(step.proposals)

    return {
        "id": run_id,
        "urn": f"urn:praetor:workflow-run:{run_id}",
        "workflow_id": script.workflow_id,
        "asset_id": script.asset_id,
        "status": "succeeded",
        "triggered_by": "demo:seed",
        "triggered_at": triggered_at.isoformat(),
        "created_at": triggered_at.isoformat(),
        "started_at": triggered_at.isoformat(),
        "finished_at": cursor.isoformat(),
        "updated_at": cursor.isoformat(),
        "inputs": {"seeded": True},
        "model_provider": "openai",
        "model": "gpt-4o-mini",
        "outputs": {
            "findings": list(findings),
            "proposed_changes": list(proposals),
        },
        "step_runs": step_runs,
    }
