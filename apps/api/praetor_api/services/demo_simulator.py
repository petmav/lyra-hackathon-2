"""Demo-mode workflow simulator.

Drives an in-memory workflow run forward over time, emitting realistic
agentic events as it goes. The shape mirrors what a real run produces so
the existing UI components render naturally.

The simulator is reached through `demo_workflows.run_workflow`. Tests can
call `tick_run` directly with a zero-delay sleep callable for instant
completion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScriptedEvent:
    """A single event the simulator emits during a step."""

    type: str
    actor: str
    payload: dict[str, Any]
    delay_before: float = 0.5


@dataclass(frozen=True)
class ScriptedStep:
    """One step of a scripted run.

    `events` are emitted in order between `workflow.step.started` and
    `workflow.step.finished`. `final_outputs` is written into the step's
    `outputs_redacted` once the step succeeds. `findings` and `proposals`
    are appended to the run's `outputs.findings` / `outputs.proposed_changes`.

    `is_live_agent=True` marks the step the simulator should attempt to
    drive with a real OpenAI call (used by `code_compliance_scan_full`'s
    `scan` step). When the call succeeds, the live findings and a chunked
    `agent.thought` rationale replace the scripted ones for that step.
    """

    step_id: str
    step_type: str
    events: tuple[ScriptedEvent, ...]
    final_outputs: dict[str, Any]
    findings: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    proposals: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    is_live_agent: bool = False


@dataclass(frozen=True)
class ScriptedRun:
    """A full scripted workflow run."""

    workflow_id: str
    asset_id: str
    steps: tuple[ScriptedStep, ...]


import asyncio
import logging
from collections.abc import Awaitable, Callable

from praetor_api.services.event_stream import append_event, make_event

logger = logging.getLogger(__name__)

SleepFn = Callable[[float], Awaitable[None]]


async def tick_run(
    run_id: str,
    *,
    script: ScriptedRun,
    sleep: SleepFn = asyncio.sleep,
    openai_api_key: str | None = None,
) -> None:
    """Drive the in-memory run forward, emitting events as it ticks.

    The run dict at `RUNS[run_id]` must already exist with all step_runs
    in `pending`. On return the run is in a terminal state
    (`succeeded` or `failed`) and `EVENTS` contains the full trace.
    """
    from praetor_api.services import demo_workflows  # local to avoid cycle

    run = demo_workflows.RUNS.get(run_id)
    if run is None:
        logger.warning("tick_run called for unknown run %s", run_id)
        return

    asset_id = script.asset_id

    try:
        await append_event(
            make_event(
                asset_id=asset_id,
                workflow_run_id=run_id,
                event_type="workflow.run.started",
                actor="workflow_runtime",
                payload={"workflow_id": script.workflow_id, "inputs": run.get("inputs", {})},
            )
        )

        for step in script.steps:
            step_record = _find_step_record(run, step.step_id)
            if step_record is None:
                continue
            step_record["status"] = "running"
            run["updated_at"] = _iso_now()

            await append_event(
                make_event(
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
            )

            for scripted in step.events:
                if scripted.delay_before > 0:
                    await sleep(scripted.delay_before)
                await append_event(
                    make_event(
                        asset_id=asset_id,
                        workflow_run_id=run_id,
                        workflow_step_id=step.step_id,
                        event_type=scripted.type,
                        actor=scripted.actor,
                        payload=dict(scripted.payload)
                        | {"step_id": step.step_id, "step_type": step.step_type},
                    )
                )

            step_record["outputs_redacted"] = dict(step.final_outputs)
            step_record["status"] = "succeeded"
            run["updated_at"] = _iso_now()

            if step.findings:
                run.setdefault("outputs", {}).setdefault("findings", []).extend(step.findings)
            if step.proposals:
                run.setdefault("outputs", {}).setdefault("proposed_changes", []).extend(step.proposals)

            await append_event(
                make_event(
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
                        "outputs_redacted": step_record["outputs_redacted"],
                    },
                )
            )

        run["status"] = "succeeded"
        run["finished_at"] = _iso_now()
        run["updated_at"] = run["finished_at"]
        await append_event(
            make_event(
                asset_id=asset_id,
                workflow_run_id=run_id,
                event_type="workflow.run.finished",
                actor="workflow_runtime",
                payload={"status": "succeeded"},
            )
        )

    except Exception as exc:  # noqa: BLE001 - record + surface, don't crash the loop
        logger.exception("tick_run failed for %s", run_id)
        run["status"] = "failed"
        run["finished_at"] = _iso_now()
        run["updated_at"] = run["finished_at"]
        await append_event(
            make_event(
                asset_id=asset_id,
                workflow_run_id=run_id,
                event_type="workflow.run.failed",
                actor="workflow_runtime",
                payload={"error": f"{exc.__class__.__name__}: {exc}"},
            )
        )


def _find_step_record(run: dict[str, Any], step_id: str) -> dict[str, Any] | None:
    for step in run.get("step_runs", []):
        if step.get("step_id") == step_id:
            return step
    return None


def _iso_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
