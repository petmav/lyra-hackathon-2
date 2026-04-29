# Demo Live Simulator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `npm run demo` boot a populated Praetor stack where the dashboard shows scripted historical runs, the user can instantiate any of six prefab workflows and watch it tick live with thoughts/tool calls/findings, and `code_compliance_scan_full` makes a real OpenAI Responses API call when `OPENAI_API_KEY` is set — all activity-log paths (history fetch + WS stream) work for both seeded and instantiated runs.

**Architecture:** A new `demo_simulator` service ticks a run forward in an asyncio background task per instantiation, mutating in-memory `RUNS` state and emitting events into the shared `EVENTS` list (which the existing WS stream already polls). A new `demo_seed` writes 4-6 historical runs with their full event traces on API startup. `demo_workflows` is expanded to know all six prefabs. The frontend's demo default switches from `fixtures` to `hybrid` so the UI actually hits the API, and a new `ActivityFeed` component on the run page subscribes via the existing `useEventStream` hook.

**Tech Stack:** Python 3.12 / FastAPI / Pydantic / asyncio / Pytest / TestClient · TypeScript / React / Next.js / Tailwind. urllib for OpenAI (no new deps).

**Spec:** `docs/superpowers/specs/2026-04-30-demo-live-simulator-design.md`

---

## File map

**New (3):**
- `apps/api/praetor_api/services/demo_simulator.py` — ScriptedRun/ScriptedStep/ScriptedEvent dataclasses, per-workflow `SCRIPTS`, `tick_run`, OpenAI live caller
- `apps/api/praetor_api/services/demo_seed.py` — `seed_all()` boot-time historical runs + events
- `apps/web/components/workflow-run/ActivityFeed.tsx` — read-only ticker for the run page

**New tests (2):**
- `apps/api/tests/test_demo_simulator.py`
- `apps/api/tests/test_demo_seed.py`

**Modified (5):**
- `apps/api/praetor_api/services/demo_workflows.py` — metadata for all 6 prefabs; new `run_workflow` dispatches to simulator
- `apps/api/praetor_api/routers/workflows.py` — POST `:run` calls new `run_workflow`
- `apps/api/praetor_api/main.py` — startup hook calls `seed_all()` in demo mode
- `apps/api/tests/test_workflows.py` — update existing test for the new async-tick model
- `apps/api/tests/test_event_streams.py` — same
- `scripts/run-stack.mjs` — change demo `NEXT_PUBLIC_DATA_SOURCE` default to `hybrid`
- `apps/web/app/workflow-runs/[id]/page.tsx` — render `<ActivityFeed/>`

---

### Task 1: Add metadata for the five missing demo workflows

**Files:**
- Modify: `apps/api/praetor_api/services/demo_workflows.py`
- Test: `apps/api/tests/test_workflows.py` (add new test only — don't touch the existing one yet)

**Why:** Today only `code_compliance_scan` is exposed in demo mode. The dashboard / `/workflows` page should show all 6 prefabs.

- [ ] **Step 1: Write the failing test**

Append to `apps/api/tests/test_workflows.py`:

```python
def test_demo_lists_all_six_workflows() -> None:
    client = TestClient(app)
    response = client.get("/workflows", headers=HEADERS)
    assert response.status_code == 200

    ids = {w["id"] for w in response.json()}
    assert ids == {
        "code_compliance_scan",
        "code_compliance_scan_full",
        "vendor_risk_review",
        "policy_gap_analysis",
        "evidence_collection",
        "ai_system_intake",
    }


def test_demo_get_each_workflow_by_id() -> None:
    client = TestClient(app)
    for wf_id in [
        "code_compliance_scan",
        "code_compliance_scan_full",
        "vendor_risk_review",
        "policy_gap_analysis",
        "evidence_collection",
        "ai_system_intake",
    ]:
        response = client.get(f"/workflows/{wf_id}", headers=HEADERS)
        assert response.status_code == 200, f"missing workflow {wf_id}"
        body = response.json()
        assert body["id"] == wf_id
        assert isinstance(body.get("required_hooks"), list)
        assert isinstance(body.get("required_corpora"), list)
```

- [ ] **Step 2: Run the failing tests**

Run: `cd apps/api && python -m pytest tests/test_workflows.py::test_demo_lists_all_six_workflows tests/test_workflows.py::test_demo_get_each_workflow_by_id -v`
Expected: FAIL — only one workflow returned / 404 for the others.

- [ ] **Step 3: Replace `CODE_COMPLIANCE_SCAN` and helpers in `demo_workflows.py` with a 6-entry registry**

Replace the entire current contents of `apps/api/praetor_api/services/demo_workflows.py` from the top through (but not including) `async def run_code_compliance_scan(` with the following. Keep everything from `run_code_compliance_scan` downwards untouched for now (Task 5 replaces it).

```python
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
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_workflows.py::test_demo_lists_all_six_workflows tests/test_workflows.py::test_demo_get_each_workflow_by_id -v`
Expected: PASS (both).

- [ ] **Step 5: Run the full test_workflows.py to ensure nothing regressed**

Run: `cd apps/api && python -m pytest tests/test_workflows.py -v`
Expected: All tests in this file PASS (the existing `test_code_compliance_scan_run_emits_finding` should still pass since we kept the underlying `run_code_compliance_scan`).

- [ ] **Step 6: Commit**

```bash
git add apps/api/praetor_api/services/demo_workflows.py apps/api/tests/test_workflows.py
git commit -m "feat(api): expose all six demo workflows in metadata

GET /workflows now returns code_compliance_scan plus
code_compliance_scan_full, vendor_risk_review, policy_gap_analysis,
evidence_collection, ai_system_intake."
```

---

### Task 2: Define ScriptedEvent / ScriptedStep / ScriptedRun dataclasses

**Files:**
- Create: `apps/api/praetor_api/services/demo_simulator.py`
- Test: `apps/api/tests/test_demo_simulator.py`

**Why:** The simulator's data model. Pure types, no logic yet.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_demo_simulator.py`:

```python
from praetor_api.services.demo_simulator import (
    ScriptedEvent,
    ScriptedRun,
    ScriptedStep,
)


def test_scripted_event_holds_type_actor_and_payload() -> None:
    event = ScriptedEvent(
        type="agent.thought",
        actor="workflow_agent",
        payload={"text": "hello"},
        delay_before=0.5,
    )
    assert event.type == "agent.thought"
    assert event.actor == "workflow_agent"
    assert event.payload == {"text": "hello"}
    assert event.delay_before == 0.5


def test_scripted_step_carries_step_metadata_and_events() -> None:
    step = ScriptedStep(
        step_id="scan",
        step_type="agent",
        events=(
            ScriptedEvent(type="agent.thought", actor="workflow_agent", payload={"text": "thinking"}),
        ),
        final_outputs={"findings": []},
        is_live_agent=True,
    )
    assert step.step_id == "scan"
    assert step.step_type == "agent"
    assert step.is_live_agent is True
    assert len(step.events) == 1
    assert step.findings == ()
    assert step.proposals == ()


def test_scripted_run_assembles_workflow_metadata() -> None:
    script = ScriptedRun(
        workflow_id="vendor_risk_review",
        asset_id="asset_acme_vendor",
        steps=(
            ScriptedStep(
                step_id="load_attestation",
                step_type="hook.in",
                events=(),
                final_outputs={"loaded": True},
            ),
        ),
    )
    assert script.workflow_id == "vendor_risk_review"
    assert script.asset_id == "asset_acme_vendor"
    assert len(script.steps) == 1
```

- [ ] **Step 2: Run the failing tests**

Run: `cd apps/api && python -m pytest tests/test_demo_simulator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'praetor_api.services.demo_simulator'`.

- [ ] **Step 3: Create `demo_simulator.py` with the dataclasses only**

Create `apps/api/praetor_api/services/demo_simulator.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_demo_simulator.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/api/praetor_api/services/demo_simulator.py apps/api/tests/test_demo_simulator.py
git commit -m "feat(api): scaffold demo simulator dataclasses

ScriptedEvent / ScriptedStep / ScriptedRun describe the shape of a
demo-mode run — what events to emit, what outputs to materialise,
and which step (if any) should attempt a live model call."
```

---

### Task 3: Implement `tick_run` for scripted (no-OpenAI) workflows

**Files:**
- Modify: `apps/api/praetor_api/services/demo_simulator.py`
- Modify: `apps/api/tests/test_demo_simulator.py`

**Why:** The core tick engine. Walks through a scripted run, mutates `RUNS` state, emits events. No OpenAI yet (Task 4).

- [ ] **Step 1: Write the failing tests**

Append to `apps/api/tests/test_demo_simulator.py`:

```python
import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from praetor_api.services import demo_workflows
from praetor_api.services.demo_simulator import (
    ScriptedEvent,
    ScriptedRun,
    ScriptedStep,
    tick_run,
)
from praetor_api.services.event_stream import EVENTS, reset_events


async def _instant(seconds: float) -> None:
    return None


def _seed_run(script: ScriptedRun) -> str:
    run_id = f"wfr_{uuid4().hex[:12]}"
    now = datetime.now(UTC).isoformat()
    demo_workflows.RUNS[run_id] = {
        "id": run_id,
        "workflow_id": script.workflow_id,
        "status": "running",
        "asset_id": script.asset_id,
        "triggered_by": "test",
        "triggered_at": now,
        "created_at": now,
        "updated_at": now,
        "inputs": {},
        "outputs": {"findings": [], "proposed_changes": []},
        "step_runs": [
            {
                "step_id": step.step_id,
                "step_type": step.step_type,
                "status": "pending",
                "outputs_redacted": {},
            }
            for step in script.steps
        ],
        "model_provider": "openai",
        "model": "gpt-4o-mini",
    }
    return run_id


@pytest.fixture(autouse=True)
def _isolate_state():
    reset_events()
    demo_workflows.RUNS.clear()
    yield
    reset_events()
    demo_workflows.RUNS.clear()


@pytest.mark.asyncio
async def test_tick_run_advances_a_one_step_run_to_succeeded() -> None:
    script = ScriptedRun(
        workflow_id="evidence_collection",
        asset_id="asset_evidence",
        steps=(
            ScriptedStep(
                step_id="organize",
                step_type="agent",
                events=(
                    ScriptedEvent(
                        type="agent.thought",
                        actor="workflow_agent",
                        payload={"text": "Sorting candidate records."},
                    ),
                ),
                final_outputs={"organized": 6},
            ),
        ),
    )
    run_id = _seed_run(script)

    await tick_run(run_id, script=script, sleep=_instant)

    run = demo_workflows.RUNS[run_id]
    assert run["status"] == "succeeded"
    assert run["step_runs"][0]["status"] == "succeeded"
    assert run["step_runs"][0]["outputs_redacted"] == {"organized": 6}


@pytest.mark.asyncio
async def test_tick_run_emits_run_and_step_brackets_plus_scripted_events() -> None:
    script = ScriptedRun(
        workflow_id="evidence_collection",
        asset_id="asset_evidence",
        steps=(
            ScriptedStep(
                step_id="organize",
                step_type="agent",
                events=(
                    ScriptedEvent(
                        type="agent.thought",
                        actor="workflow_agent",
                        payload={"text": "thinking"},
                    ),
                    ScriptedEvent(
                        type="agent.tool.called",
                        actor="workflow_agent",
                        payload={"name": "emit_finding", "args": {"count": 0}},
                    ),
                ),
                final_outputs={"ok": True},
            ),
        ),
    )
    run_id = _seed_run(script)

    await tick_run(run_id, script=script, sleep=_instant)

    types = [e["type"] for e in EVENTS if e["workflow_run_id"] == run_id]
    assert types == [
        "workflow.run.started",
        "workflow.step.started",
        "agent.thought",
        "agent.tool.called",
        "workflow.step.finished",
        "workflow.run.finished",
    ]
    # all step events carry workflow_step_id == step.step_id so StepDrawer
    # filtering works:
    step_events = [e for e in EVENTS if e["workflow_run_id"] == run_id and e["type"] != "workflow.run.started" and e["type"] != "workflow.run.finished"]
    assert all(e["workflow_step_id"] == "organize" for e in step_events)


@pytest.mark.asyncio
async def test_tick_run_merges_findings_and_proposals_into_run_outputs() -> None:
    finding = {
        "id": "fnd_x",
        "title": "Sample",
        "severity": "high",
        "confidence": 0.8,
        "obligations_cited": [],
        "documents_cited": [],
        "status": "open",
    }
    proposal = {
        "id": "pc_x",
        "finding_id": "fnd_x",
        "kind": "code",
        "diff": "",
        "diff_format": "unified",
        "obligations_addressed": [],
        "residual_risk_estimate": "low",
        "status": "proposed",
    }
    script = ScriptedRun(
        workflow_id="vendor_risk_review",
        asset_id="asset_x",
        steps=(
            ScriptedStep(
                step_id="emit",
                step_type="finding.emit",
                events=(),
                final_outputs={"emitted": [finding]},
                findings=(finding,),
            ),
            ScriptedStep(
                step_id="propose_remediation",
                step_type="change.propose",
                events=(),
                final_outputs={"proposed": [proposal]},
                proposals=(proposal,),
            ),
        ),
    )
    run_id = _seed_run(script)

    await tick_run(run_id, script=script, sleep=_instant)

    run = demo_workflows.RUNS[run_id]
    assert run["outputs"]["findings"] == [finding]
    assert run["outputs"]["proposed_changes"] == [proposal]


@pytest.mark.asyncio
async def test_tick_run_marks_run_failed_when_a_step_raises() -> None:
    class BoomError(RuntimeError):
        pass

    async def boom(_seconds: float) -> None:
        raise BoomError("scripted failure")

    script = ScriptedRun(
        workflow_id="vendor_risk_review",
        asset_id="asset_x",
        steps=(
            ScriptedStep(
                step_id="analyze",
                step_type="agent",
                events=(ScriptedEvent(type="agent.thought", actor="workflow_agent", payload={"text": "x"}),),
                final_outputs={},
            ),
        ),
    )
    run_id = _seed_run(script)

    await tick_run(run_id, script=script, sleep=boom)

    run = demo_workflows.RUNS[run_id]
    assert run["status"] == "failed"
    assert any(e["type"] == "workflow.run.failed" for e in EVENTS if e["workflow_run_id"] == run_id)
```

Note the `pytest-asyncio` decorator. Confirm it's installed by running `cd apps/api && python -c "import pytest_asyncio"` — if it errors, install with `pip install pytest-asyncio` and add it to `pyproject.toml` test-deps.

- [ ] **Step 2: Run the failing tests**

Run: `cd apps/api && python -m pytest tests/test_demo_simulator.py -v`
Expected: FAIL — `ImportError: cannot import name 'tick_run' from 'praetor_api.services.demo_simulator'`.

- [ ] **Step 3: Implement `tick_run` in `demo_simulator.py`**

Append to `apps/api/praetor_api/services/demo_simulator.py`:

```python
import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_demo_simulator.py -v`
Expected: PASS (4 new tests + 3 from Task 2).

- [ ] **Step 5: Commit**

```bash
git add apps/api/praetor_api/services/demo_simulator.py apps/api/tests/test_demo_simulator.py
git commit -m "feat(api): demo simulator ticks scripted runs to terminal state

tick_run mutates RUNS[run_id] from pending->running->succeeded per
step, emits workflow.run.started/finished and workflow.step.*
brackets plus the scripted in-step events, and merges findings +
proposals into run outputs. Failure mode marks the run failed and
emits workflow.run.failed."
```

---

### Task 4: Add the OpenAI live-call branch to `tick_run`

**Files:**
- Modify: `apps/api/praetor_api/services/demo_simulator.py`
- Modify: `apps/api/tests/test_demo_simulator.py`

**Why:** Only the `code_compliance_scan_full` `scan` step is allowed to call OpenAI. Live response gets chunked into thoughts; on any error, fall back to scripted.

- [ ] **Step 1: Write the failing tests**

Append to `apps/api/tests/test_demo_simulator.py`:

```python
import json
from io import BytesIO
from urllib.error import URLError


@pytest.mark.asyncio
async def test_live_agent_step_uses_openai_findings_when_key_set(monkeypatch) -> None:
    captured_url: list[str] = []

    class FakeResponse:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self) -> bytes:
            return self._body

    def fake_urlopen(request, timeout=30):
        captured_url.append(request.full_url)
        body = json.dumps(
            {
                "output_text": "```json\n"
                + json.dumps(
                    {
                        "thinking": "Reviewed the repo. send_email lacks recipient validation.",
                        "findings": [
                            {
                                "id": "fnd_live_1",
                                "title": "Live: missing domain guard",
                                "description": "send_email accepts any recipient.",
                                "severity": "high",
                                "confidence": 0.9,
                                "obligations_cited": [],
                                "documents_cited": [],
                            }
                        ],
                    }
                )
                + "\n```",
            }
        ).encode()
        return FakeResponse(body)

    monkeypatch.setattr("praetor_api.services.demo_simulator.urlopen", fake_urlopen)

    fallback_finding = {
        "id": "fnd_scripted",
        "title": "Scripted",
        "severity": "low",
        "confidence": 0.5,
        "obligations_cited": [],
        "documents_cited": [],
        "status": "open",
    }
    script = ScriptedRun(
        workflow_id="code_compliance_scan_full",
        asset_id="asset_full",
        steps=(
            ScriptedStep(
                step_id="scan",
                step_type="agent",
                events=(
                    ScriptedEvent(type="agent.thought", actor="workflow_agent", payload={"text": "fallback"}),
                ),
                final_outputs={"findings": [fallback_finding]},
                findings=(fallback_finding,),
                is_live_agent=True,
            ),
        ),
    )
    run_id = _seed_run(script)

    await tick_run(run_id, script=script, sleep=_instant, openai_api_key="sk-test")

    assert "api.openai.com" in captured_url[0]
    run = demo_workflows.RUNS[run_id]
    titles = [f["title"] for f in run["outputs"]["findings"]]
    assert "Live: missing domain guard" in titles
    assert "Scripted" not in titles

    thoughts = [
        e for e in EVENTS
        if e["workflow_run_id"] == run_id and e["type"] == "agent.thought"
    ]
    assert any("Reviewed the repo" in str(t["payload"].get("text", "")) for t in thoughts)


@pytest.mark.asyncio
async def test_live_agent_step_falls_back_to_scripted_when_openai_errors(monkeypatch) -> None:
    def fake_urlopen(request, timeout=30):
        raise URLError("network down")

    monkeypatch.setattr("praetor_api.services.demo_simulator.urlopen", fake_urlopen)

    fallback_finding = {
        "id": "fnd_scripted",
        "title": "Scripted",
        "severity": "low",
        "confidence": 0.5,
        "obligations_cited": [],
        "documents_cited": [],
        "status": "open",
    }
    script = ScriptedRun(
        workflow_id="code_compliance_scan_full",
        asset_id="asset_full",
        steps=(
            ScriptedStep(
                step_id="scan",
                step_type="agent",
                events=(
                    ScriptedEvent(type="agent.thought", actor="workflow_agent", payload={"text": "scripted-thinking"}),
                ),
                final_outputs={"findings": [fallback_finding]},
                findings=(fallback_finding,),
                is_live_agent=True,
            ),
        ),
    )
    run_id = _seed_run(script)

    await tick_run(run_id, script=script, sleep=_instant, openai_api_key="sk-test")

    run = demo_workflows.RUNS[run_id]
    assert run["status"] == "succeeded"
    titles = [f["title"] for f in run["outputs"]["findings"]]
    assert titles == ["Scripted"]


@pytest.mark.asyncio
async def test_live_agent_step_skipped_when_no_key(monkeypatch) -> None:
    def must_not_call(request, timeout=30):
        raise AssertionError("openai must not be called when key is None")

    monkeypatch.setattr("praetor_api.services.demo_simulator.urlopen", must_not_call)

    fallback_finding = {
        "id": "fnd_scripted",
        "title": "Scripted",
        "severity": "low",
        "confidence": 0.5,
        "obligations_cited": [],
        "documents_cited": [],
        "status": "open",
    }
    script = ScriptedRun(
        workflow_id="code_compliance_scan_full",
        asset_id="asset_full",
        steps=(
            ScriptedStep(
                step_id="scan",
                step_type="agent",
                events=(
                    ScriptedEvent(type="agent.thought", actor="workflow_agent", payload={"text": "scripted-thinking"}),
                ),
                final_outputs={"findings": [fallback_finding]},
                findings=(fallback_finding,),
                is_live_agent=True,
            ),
        ),
    )
    run_id = _seed_run(script)

    await tick_run(run_id, script=script, sleep=_instant, openai_api_key=None)

    run = demo_workflows.RUNS[run_id]
    titles = [f["title"] for f in run["outputs"]["findings"]]
    assert titles == ["Scripted"]
```

- [ ] **Step 2: Run the failing tests**

Run: `cd apps/api && python -m pytest tests/test_demo_simulator.py -v -k live`
Expected: FAIL — `urlopen` symbol not yet imported by demo_simulator, `is_live_agent` not honoured.

- [ ] **Step 3: Add the OpenAI branch**

In `apps/api/praetor_api/services/demo_simulator.py`:

(a) Add at the top of the imports section:

```python
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
```

(b) Inside `tick_run`, replace the inner loop body that emits scripted events for the step with the version that detects a live step. Replace **only** this block:

```python
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
```

with:

```python
            live_findings: list[dict[str, Any]] | None = None
            if step.is_live_agent and openai_api_key:
                live_findings = await _emit_live_openai_thoughts(
                    asset_id=asset_id,
                    run_id=run_id,
                    step=step,
                    inputs=run.get("inputs", {}),
                    model=str(run.get("model") or "gpt-4o-mini"),
                    openai_api_key=openai_api_key,
                    sleep=sleep,
                )

            if live_findings is None:
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
            else:
                step_record["outputs_redacted"] = {"findings": list(live_findings), "live": True}
```

(c) Same patch for the findings-merge block. Replace:

```python
            if step.findings:
                run.setdefault("outputs", {}).setdefault("findings", []).extend(step.findings)
```

with:

```python
            if live_findings is not None:
                run.setdefault("outputs", {}).setdefault("findings", []).extend(live_findings)
            elif step.findings:
                run.setdefault("outputs", {}).setdefault("findings", []).extend(step.findings)
```

(d) Add the OpenAI helper functions at the bottom of the module (after `_iso_now`):

```python
_OPENAI_URL = "https://api.openai.com/v1/responses"
_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


async def _emit_live_openai_thoughts(
    *,
    asset_id: str,
    run_id: str,
    step: ScriptedStep,
    inputs: dict[str, Any],
    model: str,
    openai_api_key: str,
    sleep: SleepFn,
) -> list[dict[str, Any]] | None:
    """Make a real OpenAI call. Emit chunked agent.thought events with the
    rationale and a final agent.tool.called(emit_finding). Return parsed
    findings, or None if the call failed for any reason (caller falls
    back to scripted)."""
    prompt = _build_live_prompt(inputs)
    try:
        text = await asyncio.to_thread(_call_openai_responses, openai_api_key, model, prompt)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        logger.info("live OpenAI call failed for %s: %s", run_id, exc)
        return None

    parsed = _parse_response_text(text)
    if not parsed:
        return None

    rationale = str(parsed.get("thinking") or text).strip()
    findings = _normalise_findings(parsed.get("findings"))
    if not findings:
        return None

    chunks = _chunk_rationale(rationale, n=4)
    for chunk in chunks:
        await sleep(0.4)
        await append_event(
            make_event(
                asset_id=asset_id,
                workflow_run_id=run_id,
                workflow_step_id=step.step_id,
                event_type="agent.thought",
                actor="workflow_agent",
                payload={"text": chunk, "step_id": step.step_id, "step_type": step.step_type},
            )
        )

    await append_event(
        make_event(
            asset_id=asset_id,
            workflow_run_id=run_id,
            workflow_step_id=step.step_id,
            event_type="agent.tool.called",
            actor="workflow_agent",
            payload={
                "name": "emit_finding",
                "args": {"count": len(findings)},
                "step_id": step.step_id,
                "step_type": step.step_type,
            },
        )
    )

    return findings


def _build_live_prompt(inputs: dict[str, Any]) -> str:
    inputs_block = json.dumps(inputs, sort_keys=True, indent=2) if inputs else "{}"
    return (
        "You are Praetor's governed compliance workflow agent running a "
        "code compliance scan. Read the workflow inputs and produce "
        "structured findings.\n\n"
        "Respond with a single JSON object inside a ```json fenced block "
        "with this shape:\n"
        "{\n"
        '  "thinking": "short auditable rationale (one paragraph max)",\n'
        '  "findings": [\n'
        "    {\n"
        '      "title": "short title",\n'
        '      "description": "two or three sentences",\n'
        '      "severity": "low | medium | high | critical",\n'
        '      "confidence": 0.0-1.0,\n'
        '      "obligations_cited": []\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "If the repository looks clean, return findings: [].\n\n"
        f"Workflow inputs:\n{inputs_block}"
    )


def _call_openai_responses(api_key: str, model: str, prompt: str) -> str:
    body = json.dumps({"model": model, "input": prompt}).encode("utf-8")
    request = Request(
        _OPENAI_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed https host
        data = json.loads(response.read().decode("utf-8"))
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    parts: list[str] = []
    for item in data.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) or []:
            if isinstance(content, dict):
                text = content.get("text")
                if isinstance(text, str):
                    parts.append(text)
                elif isinstance(text, dict) and isinstance(text.get("value"), str):
                    parts.append(text["value"])
    return "".join(parts)


def _parse_response_text(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    match = _FENCE_RE.search(text)
    candidates: list[str] = []
    if match:
        candidates.append(match.group(1))
    candidates.append(text)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _normalise_findings(value: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return out
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            continue
        severity = str(raw.get("severity") or "medium").lower()
        if severity not in {"low", "medium", "high", "critical"}:
            severity = "medium"
        try:
            confidence = float(raw.get("confidence", 0.7))
        except (TypeError, ValueError):
            confidence = 0.7
        confidence = max(0.0, min(1.0, confidence))
        out.append(
            {
                "id": str(raw.get("id") or f"fnd_live_{index + 1}"),
                "title": str(raw.get("title") or "Compliance finding")[:240],
                "description": str(raw.get("description") or "")[:1200],
                "severity": severity,
                "confidence": confidence,
                "obligations_cited": [
                    str(urn) for urn in (raw.get("obligations_cited") or []) if isinstance(urn, str)
                ],
                "documents_cited": raw.get("documents_cited") if isinstance(raw.get("documents_cited"), list) else [],
                "status": "open",
            }
        )
    return out


def _chunk_rationale(text: str, *, n: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if n <= 1 or len(text) <= 120:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    if len(sentences) <= n:
        return [s for s in sentences if s]
    size = max(1, len(sentences) // n)
    chunks: list[str] = []
    for i in range(0, len(sentences), size):
        chunk = " ".join(sentences[i : i + size]).strip()
        if chunk:
            chunks.append(chunk)
    return chunks[:n] if len(chunks) > n else chunks
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_demo_simulator.py -v`
Expected: PASS (all 7).

- [ ] **Step 5: Commit**

```bash
git add apps/api/praetor_api/services/demo_simulator.py apps/api/tests/test_demo_simulator.py
git commit -m "feat(api): live OpenAI branch for code_compliance_scan_full

Marked agent steps with is_live_agent=True attempt a real OpenAI
Responses API call when an api key is supplied. Rationale is
chunked across ~4 agent.thought events; findings replace the
scripted ones. Any failure (HTTP, parse, network) silently falls
back to the scripted path so the run still ticks to succeeded."
```

---

### Task 5: Add scripted runs for all six workflows + replace `run_code_compliance_scan` with `run_workflow`

**Files:**
- Modify: `apps/api/praetor_api/services/demo_simulator.py` (add `SCRIPTS` dict)
- Modify: `apps/api/praetor_api/services/demo_workflows.py` (new `run_workflow`, drop the old single-workflow function)
- Modify: `apps/api/praetor_api/routers/workflows.py` (use `run_workflow`)
- Modify: `apps/api/tests/test_workflows.py` (update the existing test)
- Modify: `apps/api/tests/test_event_streams.py` (update existing tests)

**Why:** Wire the simulator into the API so any of the six workflows can be instantiated with live ticking.

- [ ] **Step 1: Write the failing test**

Append to `apps/api/tests/test_demo_simulator.py`:

```python
from praetor_api.services.demo_simulator import SCRIPTS


def test_scripts_cover_all_six_workflows() -> None:
    assert set(SCRIPTS.keys()) == {
        "code_compliance_scan",
        "code_compliance_scan_full",
        "vendor_risk_review",
        "policy_gap_analysis",
        "evidence_collection",
        "ai_system_intake",
    }


def test_only_full_scan_marks_a_step_as_live_agent() -> None:
    for wf_id, script in SCRIPTS.items():
        live_steps = [s.step_id for s in script.steps if s.is_live_agent]
        if wf_id == "code_compliance_scan_full":
            assert live_steps == ["scan"], f"{wf_id} should have exactly one live step"
        else:
            assert live_steps == [], f"{wf_id} must have no live steps"


def test_each_script_step_has_step_id_and_step_type() -> None:
    for script in SCRIPTS.values():
        for step in script.steps:
            assert step.step_id, f"empty step_id in {script.workflow_id}"
            assert step.step_type, f"empty step_type in {script.workflow_id}/{step.step_id}"
```

Replace the existing `test_code_compliance_scan_run_emits_finding` in `apps/api/tests/test_workflows.py` with:

```python
import asyncio


def test_demo_run_starts_running_and_returns_a_run_id() -> None:
    client = TestClient(app)
    response = client.post(
        "/workflows/vendor_risk_review:run",
        headers=HEADERS,
        json={"inputs": {"vendor": "Acme"}},
    )
    assert response.status_code == 200
    run_id = response.json()["workflow_run_id"]

    run = client.get(f"/workflow-runs/{run_id}", headers=HEADERS).json()
    assert run["id"] == run_id
    assert run["status"] in {"running", "succeeded"}
    assert run["workflow_id"] == "vendor_risk_review"
    assert isinstance(run["step_runs"], list) and len(run["step_runs"]) >= 1


def test_demo_run_completes_via_simulator_directly() -> None:
    """Bypass the router so we can deterministically wait for completion."""
    from praetor_api.services import demo_workflows

    async def go() -> str:
        run = await demo_workflows.run_workflow(
            "code_compliance_scan",
            inputs={"repo_url": "stub://support-bot"},
            model_provider="openai",
            model="gpt-4o-mini",
            sync=True,
            sleep=lambda _s: asyncio.sleep(0),
        )
        return run["id"]

    run_id = asyncio.run(go())
    from praetor_api.services.demo_workflows import RUNS

    run = RUNS[run_id]
    assert run["status"] == "succeeded"
    assert run["outputs"]["findings"], "scripted run should emit at least one finding"
```

Replace the contents of `apps/api/tests/test_event_streams.py` with:

```python
import asyncio

from fastapi.testclient import TestClient

from praetor_api.main import app
from praetor_api.services import demo_workflows
from praetor_api.services.event_stream import reset_events

HEADERS = {"Authorization": "Bearer dev"}


def test_completed_demo_run_publishes_hash_chained_events() -> None:
    reset_events()
    demo_workflows.RUNS.clear()

    async def go() -> str:
        run = await demo_workflows.run_workflow(
            "code_compliance_scan",
            inputs={"repo_url": "stub://support-bot"},
            model_provider="openai",
            model="gpt-4o-mini",
            sync=True,
            sleep=lambda _s: asyncio.sleep(0),
        )
        return run["id"]

    run_id = asyncio.run(go())

    client = TestClient(app)
    events = client.get(f"/events?workflow_run_id={run_id}", headers=HEADERS).json()

    assert events, "expected events for a completed scripted run"
    assert events[0]["type"] == "workflow.run.started"
    assert events[-1]["type"] == "workflow.run.finished"
    assert events[1]["hash_chain_prev"] == events[0]["hash_chain_self"]


def test_workflow_run_websocket_streams_initial_event() -> None:
    reset_events()
    demo_workflows.RUNS.clear()

    async def go() -> str:
        run = await demo_workflows.run_workflow(
            "code_compliance_scan",
            inputs={"repo_url": "stub://support-bot"},
            model_provider="openai",
            model="gpt-4o-mini",
            sync=True,
            sleep=lambda _s: asyncio.sleep(0),
        )
        return run["id"]

    run_id = asyncio.run(go())

    client = TestClient(app)
    with client.websocket_connect(f"/ws/v1/workflow-runs/{run_id}/stream?token=dev") as ws:
        first = ws.receive_json()
    assert first["workflow_run_id"] == run_id
    assert first["type"] == "workflow.run.started"


def test_asset_websocket_requires_token() -> None:
    client = TestClient(app)
    try:
        with client.websocket_connect("/ws/v1/assets/asset_northwind_support_bot/stream"):
            raise AssertionError("connection should not be accepted")
    except Exception as exc:
        assert "1008" in str(exc) or "missing or invalid bearer token" in str(exc)
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `cd apps/api && python -m pytest tests/test_demo_simulator.py tests/test_workflows.py tests/test_event_streams.py -v`
Expected: failures referencing `SCRIPTS`, `run_workflow`, etc. — these are the targets of the next two steps.

- [ ] **Step 3: Add the SCRIPTS table to `demo_simulator.py`**

Append to `apps/api/praetor_api/services/demo_simulator.py`:

```python
# ─── Scripted runs ────────────────────────────────────────────────────────


def _thought(text: str, *, actor: str = "workflow_agent", delay: float = 0.6) -> ScriptedEvent:
    return ScriptedEvent(type="agent.thought", actor=actor, payload={"text": text}, delay_before=delay)


def _tool(name: str, *, args: dict[str, Any] | None = None, delay: float = 0.4) -> ScriptedEvent:
    return ScriptedEvent(
        type="agent.tool.called",
        actor="workflow_agent",
        payload={"name": name, "args": args or {}},
        delay_before=delay,
    )


def _hook_in(repo: str, *, delay: float = 0.4) -> ScriptedEvent:
    return ScriptedEvent(
        type="hook.in.called",
        actor="praetor:hooks",
        payload={"repo_url": repo, "summary": f"Pulled artefacts from {repo}."},
        delay_before=delay,
    )


def _corpus_query(query: str, corpus_id: str, chunks: int, *, delay: float = 0.4) -> ScriptedEvent:
    return ScriptedEvent(
        type="corpus.query.called",
        actor="praetor:corpus",
        payload={"corpus_id": corpus_id, "query": query, "chunks_returned": chunks, "top_score": 0.78},
        delay_before=delay,
    )


def _policy_decision(package: str, outcome: str, *, delay: float = 0.3) -> ScriptedEvent:
    return ScriptedEvent(
        type="policy.decision.hot",
        actor="praetor:policy",
        payload={"package": package, "outcome": outcome, "latency_ms": 4},
        delay_before=delay,
    )


def _human_gate(*, delay: float = 0.4) -> ScriptedEvent:
    return ScriptedEvent(
        type="human.gate.opened",
        actor="praetor:runtime",
        payload={"reason": "awaiting reviewer approval"},
        delay_before=delay,
    )


def _human_resolve(approver: str = "demo:reviewer", *, delay: float = 5.0) -> ScriptedEvent:
    return ScriptedEvent(
        type="human.gate.resolved",
        actor=approver,
        payload={"approved": True, "approver": approver},
        delay_before=delay,
    )


def _hook_out(target: str, *, delay: float = 0.6) -> ScriptedEvent:
    return ScriptedEvent(
        type="hook.out.called",
        actor="praetor:hooks",
        payload={"target": target, "ok": True},
        delay_before=delay,
    )


def _finding_emitted(finding: dict[str, Any], *, delay: float = 0.3) -> ScriptedEvent:
    return ScriptedEvent(
        type="finding.emitted",
        actor="workflow_runtime",
        payload={"finding": finding},
        delay_before=delay,
    )


def _change_proposed(proposal: dict[str, Any], *, delay: float = 0.4) -> ScriptedEvent:
    return ScriptedEvent(
        type="change.proposed",
        actor="workflow_runtime",
        payload={"proposed_change": proposal},
        delay_before=delay,
    )


def _f(
    *,
    fid: str,
    title: str,
    description: str,
    severity: str = "high",
    confidence: float = 0.85,
    obligations: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "id": fid,
        "urn": f"urn:praetor:finding:demo:{fid}",
        "title": title,
        "description": description,
        "severity": severity,
        "confidence": confidence,
        "obligations_cited": list(obligations),
        "documents_cited": [],
        "status": "open",
    }


def _p(*, pid: str, finding_id: str, kind: str, diff: str, residual: str = "Low") -> dict[str, Any]:
    return {
        "id": pid,
        "urn": f"urn:praetor:proposed_change:demo:{pid}",
        "finding_id": finding_id,
        "kind": kind,
        "diff_format": "unified" if kind == "code" else "markdown",
        "diff": diff,
        "obligations_addressed": [],
        "residual_risk_estimate": residual,
        "status": "proposed",
    }


_SCAN_F = _f(
    fid="fnd_send_email_guard",
    title="send_email lacks recipient domain validation",
    description="The send_email path forwards messages without checking the recipient domain against an allowlist.",
    severity="high",
    confidence=0.9,
    obligations=("urn:praetor:obligation:demo:iso-42001-8-3",),
)
_SCAN_P = _p(
    pid="pc_send_email_validator",
    finding_id="fnd_send_email_guard",
    kind="code",
    diff=(
        "--- a/tools.py\n"
        "+++ b/tools.py\n"
        "@@\n"
        "+ALLOWED = {'northwind.test', 'customer.example'}\n"
        " def send_email(recipient, subject, body):\n"
        "+    assert recipient.rsplit('@', 1)[-1] in ALLOWED\n"
        "     return smtp.send(recipient, subject, body)\n"
    ),
)


SCRIPTS: dict[str, ScriptedRun] = {
    "code_compliance_scan": ScriptedRun(
        workflow_id="code_compliance_scan",
        asset_id="asset_northwind_support_bot",
        steps=(
            ScriptedStep(
                step_id="pull",
                step_type="hook.in",
                events=(_hook_in("stub://support-bot"),),
                final_outputs={"repo_url": "stub://support-bot"},
            ),
            ScriptedStep(
                step_id="retrieve_controls",
                step_type="corpus.query",
                events=(_corpus_query("recipient domain validation", "iso_42001", chunks=3),),
                final_outputs={"chunks_returned": 3},
            ),
            ScriptedStep(
                step_id="scan",
                step_type="agent",
                events=(
                    _thought("Reading source files for outbound email primitives."),
                    _thought("send_email accepts arbitrary recipients with no allowlist check."),
                    _tool("emit_finding", args={"count": 1}),
                ),
                final_outputs={"findings": [_SCAN_F]},
                findings=(_SCAN_F,),
            ),
            ScriptedStep(
                step_id="emit",
                step_type="finding.emit",
                events=(_finding_emitted(_SCAN_F),),
                final_outputs={"emitted": [_SCAN_F]},
            ),
        ),
    ),
    "code_compliance_scan_full": ScriptedRun(
        workflow_id="code_compliance_scan_full",
        asset_id="asset_northwind_support_bot",
        steps=(
            ScriptedStep(
                step_id="pull",
                step_type="hook.in",
                events=(_hook_in("stub://support-bot"),),
                final_outputs={"repo_url": "stub://support-bot"},
            ),
            ScriptedStep(
                step_id="retrieve_controls",
                step_type="corpus.query",
                events=(_corpus_query("recipient domain validation", "iso_42001", chunks=3),),
                final_outputs={"chunks_returned": 3},
            ),
            ScriptedStep(
                step_id="scan",
                step_type="agent",
                events=(
                    _thought("Inspecting outbound integrations and policy obligations."),
                    _thought("send_email is missing the recipient-domain guard required by ISO 42001 §8.3."),
                    _tool("emit_finding", args={"count": 1}),
                ),
                final_outputs={"findings": [_SCAN_F]},
                findings=(_SCAN_F,),
                is_live_agent=True,
            ),
            ScriptedStep(
                step_id="emit",
                step_type="finding.emit",
                events=(_finding_emitted(_SCAN_F),),
                final_outputs={"emitted": [_SCAN_F]},
            ),
            ScriptedStep(
                step_id="propose",
                step_type="change.propose",
                events=(_change_proposed(_SCAN_P),),
                final_outputs={"proposed": [_SCAN_P]},
                proposals=(_SCAN_P,),
            ),
            ScriptedStep(
                step_id="policy_gate",
                step_type="gate.policy",
                events=(_policy_decision("praetor.controls.workflow_findings_gate", "allow"),),
                final_outputs={"outcome": "allow"},
            ),
            ScriptedStep(
                step_id="human_gate",
                step_type="gate.human",
                events=(_human_gate(), _human_resolve(delay=4.0)),
                final_outputs={"approved": True},
            ),
            ScriptedStep(
                step_id="open_pr",
                step_type="hook.out",
                events=(_hook_out("github_stub#open_pr"),),
                final_outputs={"pr_url": "https://github.example/northwind/support-bot/pull/42"},
            ),
        ),
    ),
    "vendor_risk_review": ScriptedRun(
        workflow_id="vendor_risk_review",
        asset_id="asset_acme_vendor",
        steps=(
            ScriptedStep(
                step_id="load_attestation",
                step_type="hook.in",
                events=(_hook_in("stub://acme-soc2-attestation"),),
                final_outputs={"document": "soc2-2026-q1.pdf"},
            ),
            ScriptedStep(
                step_id="retrieve_obligations",
                step_type="corpus.query",
                events=(_corpus_query("SOC2 access control gaps", "iso_42001", chunks=4),),
                final_outputs={"chunks_returned": 4},
            ),
            ScriptedStep(
                step_id="analyze",
                step_type="agent",
                events=(
                    _thought("Cross-checking Acme's SOC2 controls against ISO 42001."),
                    _thought("CC6.1 access logging is partial; A.9.4.5 lacks segregation evidence."),
                    _tool("cite_obligation", args={"count": 2}),
                    _tool("emit_finding", args={"count": 2}),
                ),
                final_outputs={"findings_count": 2},
                findings=(
                    _f(
                        fid="fnd_acme_cc61",
                        title="Acme SOC2 CC6.1 — partial access logging",
                        description="Acme's evidence does not cover privileged user access. Request a remediation plan.",
                        severity="high",
                        confidence=0.82,
                        obligations=("urn:praetor:obligation:demo:soc2-cc6-1",),
                    ),
                    _f(
                        fid="fnd_acme_a945",
                        title="ISO 27001 A.9.4.5 segregation evidence missing",
                        description="No artefact demonstrates code-environment segregation for production releases.",
                        severity="medium",
                        confidence=0.74,
                        obligations=("urn:praetor:obligation:demo:iso-27001-a945",),
                    ),
                ),
            ),
            ScriptedStep(
                step_id="emit",
                step_type="finding.emit",
                events=(),
                final_outputs={"emitted_count": 2},
            ),
            ScriptedStep(
                step_id="propose_remediation",
                step_type="change.propose",
                events=(),
                final_outputs={"proposed_count": 1},
                proposals=(
                    _p(
                        pid="pc_acme_remediation",
                        finding_id="fnd_acme_cc61",
                        kind="process",
                        diff="Request a 30-day remediation plan covering CC6.1 access logging gaps; require evidence by next quarter's review.",
                        residual="Medium until evidence is supplied.",
                    ),
                ),
            ),
        ),
    ),
    "policy_gap_analysis": ScriptedRun(
        workflow_id="policy_gap_analysis",
        asset_id="asset_policy_corpus",
        steps=(
            ScriptedStep(
                step_id="load_regulation",
                step_type="hook.in",
                events=(_hook_in("stub://eu-ai-act-art10"),),
                final_outputs={"regulation": "eu_ai_act_art_10"},
            ),
            ScriptedStep(
                step_id="retrieve_existing_controls",
                step_type="corpus.query",
                events=(_corpus_query("data governance training data quality", "internal_data_min", chunks=5),),
                final_outputs={"chunks_returned": 5},
            ),
            ScriptedStep(
                step_id="analyze_gaps",
                step_type="agent",
                events=(
                    _thought("Mapping existing controls onto AI Act Article 10 obligations."),
                    _thought("Existing controls cover bias monitoring; data lineage attestation is missing."),
                    _tool("emit_finding", args={"count": 1}),
                ),
                final_outputs={"gaps": 1},
                findings=(
                    _f(
                        fid="fnd_eu_ai_act_lineage",
                        title="No data-lineage attestation for training datasets",
                        description="Article 10(2)(f) requires data lineage. Internal controls cover bias but not lineage attestation.",
                        severity="high",
                        confidence=0.81,
                        obligations=("urn:praetor:obligation:demo:eu-ai-act-art10",),
                    ),
                ),
            ),
            ScriptedStep(
                step_id="emit",
                step_type="finding.emit",
                events=(),
                final_outputs={"emitted_count": 1},
            ),
            ScriptedStep(
                step_id="propose_controls",
                step_type="change.propose",
                events=(),
                final_outputs={"proposed_count": 1},
                proposals=(
                    _p(
                        pid="pc_data_lineage_control",
                        finding_id="fnd_eu_ai_act_lineage",
                        kind="policy",
                        diff="## Control: Training-Data Lineage Attestation\n\nEvery training dataset MUST carry a signed lineage attestation linking source systems, transformation steps, and consent basis.",
                    ),
                ),
            ),
            ScriptedStep(
                step_id="policy_gate",
                step_type="gate.policy",
                events=(_policy_decision("praetor.controls.policy_gate", "allow"),),
                final_outputs={"outcome": "allow"},
            ),
            ScriptedStep(
                step_id="human_gate",
                step_type="gate.human",
                events=(_human_gate(), _human_resolve(delay=4.0)),
                final_outputs={"approved": True},
            ),
        ),
    ),
    "evidence_collection": ScriptedRun(
        workflow_id="evidence_collection",
        asset_id="asset_evidence_q1",
        steps=(
            ScriptedStep(
                step_id="read_files",
                step_type="hook.in",
                events=(_hook_in("stub://evidence-bundle-q1"),),
                final_outputs={"files": 14},
            ),
            ScriptedStep(
                step_id="retrieve_obligations",
                step_type="corpus.query",
                events=(_corpus_query("ISO 42001 evidence requirements", "iso_42001", chunks=4),),
                final_outputs={"chunks_returned": 4},
            ),
            ScriptedStep(
                step_id="organize",
                step_type="agent",
                events=(
                    _thought("Sorting raw artefacts by obligation URN."),
                    _thought("6 evidence records bound; 8 artefacts uncategorised — flagged for review."),
                    _tool("bind_evidence", args={"bound": 6, "unbound": 8}),
                ),
                final_outputs={"records_created": 6},
            ),
            ScriptedStep(
                step_id="emit",
                step_type="finding.emit",
                events=(),
                final_outputs={"emitted_count": 0},
            ),
        ),
    ),
    "ai_system_intake": ScriptedRun(
        workflow_id="ai_system_intake",
        asset_id="asset_chat_summary_v2",
        steps=(
            ScriptedStep(
                step_id="intake_form",
                step_type="hook.in",
                events=(_hook_in("stub://intake/chat-summary-v2"),),
                final_outputs={"form_id": "intake_chat_summary_v2"},
            ),
            ScriptedStep(
                step_id="retrieve_obligations",
                step_type="corpus.query",
                events=(_corpus_query("AI system risk classification", "iso_42001", chunks=3),),
                final_outputs={"chunks_returned": 3},
            ),
            ScriptedStep(
                step_id="classify",
                step_type="agent",
                events=(
                    _thought("Reviewing intake form against AI Act risk categories."),
                    _thought("Customer-facing summary tool with PII access — classified high-risk."),
                    _tool("emit_finding", args={"count": 1}),
                ),
                final_outputs={"classification": "high-risk"},
                findings=(
                    _f(
                        fid="fnd_chat_summary_classification",
                        title="Chat-summary v2 classified high-risk",
                        description="Customer-facing summarisation that accesses PII. Subject to AI Act high-risk obligations (Annex III).",
                        severity="high",
                        confidence=0.88,
                        obligations=("urn:praetor:obligation:demo:eu-ai-act-annex-iii",),
                    ),
                ),
            ),
            ScriptedStep(
                step_id="policy_gate",
                step_type="gate.policy",
                events=(_policy_decision("praetor.controls.intake_gate", "permit_with_conditions"),),
                final_outputs={"outcome": "permit_with_conditions"},
            ),
            ScriptedStep(
                step_id="emit",
                step_type="finding.emit",
                events=(),
                final_outputs={"emitted_count": 1},
            ),
        ),
    ),
}
```

- [ ] **Step 4: Replace `run_code_compliance_scan` with `run_workflow` in `demo_workflows.py`**

In `apps/api/praetor_api/services/demo_workflows.py`:

(a) Delete the now-unused `from praetor_api.services.event_stream import append_event, make_event` line at the top of the file (added in Task 1, no longer needed since the simulator owns event emission).

(b) Add these imports to the import block at the top of the file (merge with the existing ones from Task 1; keep imports sorted by stdlib → third-party → local):

```python
import asyncio
from collections.abc import Awaitable, Callable

from praetor_api.settings import get_settings
```

After this step the top of `demo_workflows.py` should look like:

```python
import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from praetor_api.settings import get_settings
```

(c) Replace the existing `run_code_compliance_scan`, `_append_step_trace`, and `_demo_step_trace_events` functions (everything below the `get_workflow` you set up in Task 1) with:

```python
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
                "model_provider": model_provider if step.step_type == "agent" else None,
                "model": model if step.step_type == "agent" else None,
            }
            for step in script.steps
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
```

- [ ] **Step 5: Update the router in `routers/workflows.py`**

Change the import (line 7-12) from:

```python
from praetor_api.services.demo_workflows import (
    get_workflow,
    list_workflows,
    run_code_compliance_scan,
    RUNS,
)
```

to:

```python
from praetor_api.services.demo_workflows import (
    get_workflow,
    list_workflows,
    run_workflow as run_demo_workflow,
    RUNS,
)
```

Replace the demo branch of `POST /workflows/{id}:run` (lines 180-188) — the `else` block currently containing `run = await run_code_compliance_scan(...)` — with:

```python
    else:
        if get_workflow(workflow_id) is None:
            raise HTTPException(status_code=404, detail="workflow not found")

        run = await run_demo_workflow(
            workflow_id,
            request.inputs,
            model_provider=request.model_provider or settings.default_model_provider,
            model=request.model or settings.default_model_name,
        )
```

- [ ] **Step 6: Run the test suite**

Run: `cd apps/api && python -m pytest tests/test_demo_simulator.py tests/test_workflows.py tests/test_event_streams.py -v`
Expected: PASS for all the new and updated tests.

- [ ] **Step 7: Run the full API test suite to catch regressions**

Run: `cd apps/api && python -m pytest -q`
Expected: PASS. If anything fails, fix before continuing — common culprits are imports of `run_code_compliance_scan` (now removed) elsewhere; grep with `cd apps/api && grep -rn run_code_compliance_scan praetor_api tests` and replace with `run_workflow("code_compliance_scan", …)` plus `sync=True` for any test that needs a terminal run.

- [ ] **Step 8: Commit**

```bash
git add apps/api/praetor_api/services/demo_simulator.py apps/api/praetor_api/services/demo_workflows.py apps/api/praetor_api/routers/workflows.py apps/api/tests/test_demo_simulator.py apps/api/tests/test_workflows.py apps/api/tests/test_event_streams.py
git commit -m "feat(api): generic run_workflow scheduling demo simulator

POST /workflows/{id}:run now creates a demo run for any of the six
prefab workflows, returns immediately with status=running, and
fires the simulator as an asyncio.create_task. The run ticks live
and lands in succeeded after ~15-25s. Tests use sync=True with
zero-delay sleep for deterministic assertions."
```

---

### Task 6: `demo_seed.seed_all()` — historical runs in `RUNS`

**Files:**
- Create: `apps/api/praetor_api/services/demo_seed.py`
- Test: `apps/api/tests/test_demo_seed.py`

**Why:** Populates the dashboard with completed runs the moment the API boots. Step 1 covers run records only; events come in Task 7.

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_demo_seed.py`:

```python
import pytest

from praetor_api.services import demo_seed, demo_state, demo_workflows
from praetor_api.services.event_stream import EVENTS, reset_events


@pytest.fixture(autouse=True)
def _isolate():
    reset_events()
    demo_workflows.RUNS.clear()
    demo_state.FINDINGS.clear()
    demo_state.PROPOSED_CHANGES.clear()
    demo_state.SANDBOX_RUNS.clear()
    demo_state.EVIDENCE_RECORDS.clear()
    yield
    reset_events()
    demo_workflows.RUNS.clear()
    demo_state.FINDINGS.clear()
    demo_state.PROPOSED_CHANGES.clear()
    demo_state.SANDBOX_RUNS.clear()
    demo_state.EVIDENCE_RECORDS.clear()


@pytest.mark.asyncio
async def test_seed_all_populates_runs_for_each_seed_workflow() -> None:
    await demo_seed.seed_all()

    seeded_workflow_ids = {run["workflow_id"] for run in demo_workflows.RUNS.values()}
    # at least 4 distinct workflows seeded; covers the dashboard
    assert len(seeded_workflow_ids) >= 4
    for run in demo_workflows.RUNS.values():
        assert run["status"] == "succeeded"
        assert run["step_runs"], f"run {run['id']} has no step_runs"
        for step in run["step_runs"]:
            assert step["status"] == "succeeded"


@pytest.mark.asyncio
async def test_seed_all_is_idempotent() -> None:
    await demo_seed.seed_all()
    snapshot = dict(demo_workflows.RUNS)
    await demo_seed.seed_all()
    assert demo_workflows.RUNS == snapshot


@pytest.mark.asyncio
async def test_seed_all_writes_findings_and_proposals() -> None:
    await demo_seed.seed_all()
    assert demo_state.FINDINGS, "expected at least one seeded finding"
    assert demo_state.PROPOSED_CHANGES, "expected at least one seeded proposal"
```

- [ ] **Step 2: Run the failing tests**

Run: `cd apps/api && python -m pytest tests/test_demo_seed.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Create `demo_seed.py`**

Create `apps/api/praetor_api/services/demo_seed.py`:

```python
"""Boot-time demo seed.

Populates the in-memory state with a handful of completed historical runs
across the six prefab workflows so the dashboard isn't empty when a viewer
opens `npm run demo`. Idempotent — safe to call multiple times.

Companion `seed_history_events` (Task 7) emits the per-step trace into
EVENTS so opening any seeded run shows a populated activity log.
"""

from __future__ import annotations

import asyncio
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
    """Populate RUNS, FINDINGS, PROPOSED_CHANGES, SANDBOX_RUNS for the
    seeded historical runs. Idempotent.
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


def _build_succeeded_run(
    run_id: str,
    script,  # ScriptedRun
    triggered_at: datetime,
) -> dict[str, Any]:
    cursor = triggered_at
    step_runs: list[dict[str, Any]] = []
    for step in script.steps:
        step_started = cursor
        # rough plausible step duration: 1-6s
        cursor = cursor + timedelta(seconds=2)
        step_runs.append(
            {
                "step_id": step.step_id,
                "step_type": step.step_type,
                "status": "succeeded",
                "outputs_redacted": dict(step.final_outputs),
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_demo_seed.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/api/praetor_api/services/demo_seed.py apps/api/tests/test_demo_seed.py
git commit -m "feat(api): demo_seed.seed_all populates historical runs

Six pre-completed runs across the six prefab workflows are written
into RUNS on boot, with realistic step timing spread over the past
~4 days. Findings and proposed changes from each scripted run are
mirrored into demo_state. Idempotent."
```

---

### Task 7: Seed historical events into `EVENTS`

**Files:**
- Modify: `apps/api/praetor_api/services/demo_seed.py`
- Modify: `apps/api/tests/test_demo_seed.py`

**Why:** Without per-step events the activity panel and `StepDrawer` are empty when a viewer clicks into a seeded run. This is the §4.2 / §4.7 correctness gate.

- [ ] **Step 1: Write the failing tests**

Append to `apps/api/tests/test_demo_seed.py`:

```python
@pytest.mark.asyncio
async def test_seed_all_emits_events_for_each_seeded_run() -> None:
    await demo_seed.seed_all()

    for run_id in demo_workflows.RUNS:
        run_events = [e for e in EVENTS if e["workflow_run_id"] == run_id]
        assert run_events, f"no events emitted for seeded run {run_id}"
        types = [e["type"] for e in run_events]
        assert types[0] == "workflow.run.started"
        assert types[-1] == "workflow.run.finished"


@pytest.mark.asyncio
async def test_seeded_step_events_carry_workflow_step_id() -> None:
    """StepDrawer filters by e.workflow_step_id === step.step_id, so every
    step event must carry that id."""
    await demo_seed.seed_all()

    for run_id, run in demo_workflows.RUNS.items():
        step_ids = {step["step_id"] for step in run["step_runs"]}
        step_events = [
            e
            for e in EVENTS
            if e["workflow_run_id"] == run_id
            and e["type"] not in {"workflow.run.started", "workflow.run.finished"}
        ]
        assert step_events, f"no step events for {run_id}"
        for ev in step_events:
            assert ev["workflow_step_id"] in step_ids, (
                f"event {ev['type']} for {run_id} has unknown step_id "
                f"{ev['workflow_step_id']}"
            )


@pytest.mark.asyncio
async def test_seed_event_hash_chain_is_valid_per_asset() -> None:
    await demo_seed.seed_all()

    by_asset: dict[str, list[dict]] = {}
    for ev in EVENTS:
        by_asset.setdefault(ev["asset_id"], []).append(ev)

    for asset_id, evs in by_asset.items():
        for prev_ev, this_ev in zip(evs, evs[1:]):
            assert this_ev["hash_chain_prev"] == prev_ev["hash_chain_self"], (
                f"hash chain broken for asset {asset_id}"
            )
```

- [ ] **Step 2: Run the failing tests**

Run: `cd apps/api && python -m pytest tests/test_demo_seed.py -v`
Expected: the three new tests FAIL (no events seeded yet).

- [ ] **Step 3: Implement event seeding**

In `apps/api/praetor_api/services/demo_seed.py`, add a new helper and call it from `seed_all`. Replace the body of `seed_all` with:

```python
async def seed_all() -> None:
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
```

Add at the bottom of the module:

```python
async def _emit_history_events(run: dict[str, Any], script) -> None:
    """Append the full per-step event trace for a seeded run into EVENTS.

    Events go through `make_event` / `append_event` so the per-asset hash
    chain extends correctly. Timestamps are overwritten in place so the
    seeded events appear at the historical run's wall-clock times rather
    than 'now'."""
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
            ev = make_event(
                asset_id=asset_id,
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

    # `append_event` would re-publish to redis; for in-memory demo we just
    # append directly above. Keep `append_event` import for completeness so
    # future tweaks land on the right helper.
    _ = append_event
```

Note: the helper appends directly to `EVENTS` (rather than `await append_event(ev)`) because `make_event` already updates `_asset_hashes`, and we want to override the synthetic `ts` field for backdating. The `append_event` import is kept for symmetry with the simulator path; the underscore assignment silences linting.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_demo_seed.py -v`
Expected: PASS (6 tests total in this file now).

- [ ] **Step 5: Run the full API test suite**

Run: `cd apps/api && python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/praetor_api/services/demo_seed.py apps/api/tests/test_demo_seed.py
git commit -m "feat(api): seed historical event traces into EVENTS

Each seeded run now writes its full workflow.run.started/finished
plus per-step started/finished + scripted in-step events into the
in-memory EVENTS list with backdated timestamps. The per-asset hash
chain stays valid. Closes the activity-log gap that left seeded
runs with empty timelines."
```

---

### Task 8: Wire `seed_all()` into FastAPI startup

**Files:**
- Modify: `apps/api/praetor_api/main.py`

**Why:** The seeder must run on boot (in demo mode only) before any request hits.

- [ ] **Step 1: Write the failing test**

Append to `apps/api/tests/test_demo_seed.py`:

```python
def test_main_app_seeds_demo_state_on_startup() -> None:
    """Booting the FastAPI app in demo mode must populate RUNS via the
    startup hook so the dashboard isn't empty."""
    from fastapi.testclient import TestClient

    from praetor_api.main import app
    from praetor_api.services import demo_workflows

    demo_workflows.RUNS.clear()
    reset_events()

    with TestClient(app) as _client:
        # entering the context fires startup hooks
        assert demo_workflows.RUNS, "startup did not populate demo runs"
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd apps/api && python -m pytest tests/test_demo_seed.py::test_main_app_seeds_demo_state_on_startup -v`
Expected: FAIL — RUNS empty after startup.

- [ ] **Step 3: Add the startup hook to `main.py`**

In `apps/api/praetor_api/main.py`, add after the existing `app = FastAPI(...)` block (before the middlewares):

```python
@app.on_event("startup")
async def _seed_demo_state() -> None:
    if settings.data_mode != "demo":
        return
    from praetor_api.services.demo_seed import seed_all

    try:
        await seed_all()
    except Exception:
        logger.exception("demo seed failed; continuing without seed data")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd apps/api && python -m pytest tests/test_demo_seed.py -v`
Expected: PASS (all tests in this file).

- [ ] **Step 5: Run the full API test suite**

Run: `cd apps/api && python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/praetor_api/main.py
git commit -m "feat(api): seed demo state on FastAPI startup

The startup hook calls demo_seed.seed_all() in demo mode so the
dashboard, findings, proposed changes, and activity log are all
populated the moment the API is reachable."
```

---

### Task 9: Switch demo `NEXT_PUBLIC_DATA_SOURCE` default to `hybrid`

**Files:**
- Modify: `scripts/run-stack.mjs`

**Why:** Default demo today renders the frontend from static fixtures and never hits the API, which means none of the work in Tasks 1-8 is visible. `hybrid` makes the API primary with fixture fallback only on outright failure.

- [ ] **Step 1: Make the change**

Edit `scripts/run-stack.mjs` line 46:

```js
NEXT_PUBLIC_DATA_SOURCE: process.env.NEXT_PUBLIC_DATA_SOURCE ?? (mode === "demo" ? "fixtures" : "api"),
```

to:

```js
NEXT_PUBLIC_DATA_SOURCE: process.env.NEXT_PUBLIC_DATA_SOURCE ?? (mode === "demo" ? "hybrid" : "api"),
```

- [ ] **Step 2: Verify the script is still valid**

Run: `node --check scripts/run-stack.mjs`
Expected: no output (success).

- [ ] **Step 3: Verify the help text still prints**

Run: `node scripts/run-stack.mjs help`
Expected: prints usage block; exits 0.

- [ ] **Step 4: Commit**

```bash
git add scripts/run-stack.mjs
git commit -m "chore(scripts): default demo to hybrid data source

Demo mode now sets NEXT_PUBLIC_DATA_SOURCE=hybrid by default so the
web app calls the API (with fixtures as fallback only). Without this
the live ticking simulator and seeded runs are invisible to the UI.
Override via NEXT_PUBLIC_DATA_SOURCE=fixtures if you specifically
need the legacy frontend-only mode."
```

---

### Task 10: `ActivityFeed` component

**Files:**
- Create: `apps/web/components/workflow-run/ActivityFeed.tsx`

**Why:** The run-page activity panel. Renders the live event stream from `useEventStream`.

- [ ] **Step 1: Create the component**

Create `apps/web/components/workflow-run/ActivityFeed.tsx`:

```tsx
"use client";

import { useEffect, useRef } from "react";
import type { AgentEvent, WorkflowRun } from "@/lib/api/types";
import { useEventStream } from "@/lib/ws/stream";
import { Timestamp } from "@/components/data/Timestamp";
import { Badge } from "@/components/primitives/Badge";

const FIXTURES_ONLY =
  (process.env.NEXT_PUBLIC_DATA_SOURCE ?? "").toLowerCase() === "fixtures";

const VISIBLE_TYPES = new Set([
  "workflow.run.started",
  "workflow.run.finished",
  "workflow.run.failed",
  "workflow.step.started",
  "workflow.step.finished",
  "agent.thought",
  "agent.tool.called",
  "agent.tool.refused",
  "corpus.query.called",
  "hook.in.called",
  "hook.out.called",
  "policy.decision.hot",
  "human.gate.opened",
  "human.gate.resolved",
  "finding.emitted",
  "change.proposed",
]);

const RUNNING_STATUSES = new Set(["running", "awaiting_approval"]);

export function ActivityFeed({ run }: { run: WorkflowRun }) {
  if (FIXTURES_ONLY) return null;

  const { events, connected } = useEventStream(
    { kind: "workflowRun", id: run.id },
    { live: true }
  );
  const visible = events.filter((e) => VISIBLE_TYPES.has(e.type));
  const tail = visible.slice(-30);

  const tailRef = useRef<HTMLLIElement | null>(null);
  useEffect(() => {
    if (RUNNING_STATUSES.has(run.status) && tailRef.current) {
      tailRef.current.scrollIntoView({ block: "end", behavior: "smooth" });
    }
  }, [tail.length, run.status]);

  return (
    <section className="border border-rule">
      <header className="flex items-center justify-between border-b border-rule px-4 py-2.5">
        <div className="smallcaps">Activity</div>
        <span className="font-mono text-[10.5px] text-paper-fade tabular-nums">
          {connected ? `${visible.length} live` : `${visible.length} ·`}
        </span>
      </header>
      <ul className="max-h-[420px] overflow-y-auto">
        {tail.length === 0 ? (
          <li className="px-4 py-8 text-center text-[12px] italic text-paper-fade">
            No events yet.
          </li>
        ) : (
          tail.map((e, i) => (
            <li
              key={e.id}
              ref={i === tail.length - 1 ? tailRef : undefined}
              className="border-b border-rule px-4 py-2"
            >
              <Row event={e} />
            </li>
          ))
        )}
      </ul>
    </section>
  );
}

function Row({ event }: { event: AgentEvent }) {
  return (
    <div>
      <div className="flex items-baseline gap-3">
        <Timestamp ts={event.ts} mode="timecode" />
        <Badge tone={toneFor(event.type)} className="shrink-0">
          {chipLabel(event.type)}
        </Badge>
        <span className="font-mono text-[11px] text-paper-fade truncate">{event.actor}</span>
      </div>
      <Body event={event} />
    </div>
  );
}

function Body({ event }: { event: AgentEvent }) {
  const p = (event.payload ?? {}) as Record<string, unknown>;
  switch (event.type) {
    case "agent.thought":
      return <p className="mt-1 text-[13px] leading-snug text-paper">{String(p.text ?? "")}</p>;
    case "agent.tool.called":
      return (
        <p className="mt-1 text-[12.5px] leading-snug">
          <span className="text-paper-fade">→ tool </span>
          <span className="font-mono text-paper">{String(p.name ?? "")}</span>
          <span className="text-paper-fade"> · </span>
          <span className="font-mono text-[11.5px] text-paper-dim">{summariseArgs(p.args)}</span>
        </p>
      );
    case "agent.tool.refused":
      return (
        <p className="mt-1 text-[12.5px] leading-snug text-crit">
          ↺ refused <span className="font-mono">{String(p.name ?? "")}</span>
          <span className="text-paper-dim"> — {String(p.reason ?? "")}</span>
        </p>
      );
    case "corpus.query.called":
      return (
        <p className="mt-1 text-[12.5px] leading-snug text-paper-dim">
          corpus <span className="font-mono">{String(p.corpus_id ?? "")}</span> — “{String(p.query ?? "")}” · {String(p.chunks_returned ?? "0")} chunks
        </p>
      );
    case "hook.in.called":
      return (
        <p className="mt-1 text-[12.5px] leading-snug text-paper-dim">
          ⤵ pulled <span className="font-mono">{String(p.repo_url ?? p.target ?? "")}</span>
        </p>
      );
    case "hook.out.called":
      return (
        <p className="mt-1 text-[12.5px] leading-snug text-paper-dim">
          ⤴ called <span className="font-mono">{String(p.target ?? "")}</span>
        </p>
      );
    case "policy.decision.hot":
      return (
        <p className="mt-1 text-[12.5px] leading-snug text-paper-dim">
          policy <span className="font-mono">{String(p.package ?? "")}</span> · {String(p.outcome ?? "")} ({String(p.latency_ms ?? "?")}ms)
        </p>
      );
    case "human.gate.opened":
      return (
        <p className="mt-1 text-[12.5px] leading-snug text-paper-dim">⏸ human gate · {String(p.reason ?? "awaiting approval")}</p>
      );
    case "human.gate.resolved":
      return (
        <p className="mt-1 text-[12.5px] leading-snug text-paper-dim">
          ▶ resolved by <span className="font-mono">{String(p.approver ?? "?")}</span> · approved={String(p.approved ?? "?")}
        </p>
      );
    case "finding.emitted": {
      const f = (p.finding ?? {}) as Record<string, unknown>;
      return (
        <p className="mt-1 text-[12.5px] leading-snug">
          <span className="text-paper-fade">finding </span>
          <span className="text-paper">{String(f.title ?? "")}</span>
          <span className="text-paper-fade"> · {String(f.severity ?? "")}</span>
        </p>
      );
    }
    case "change.proposed": {
      const c = (p.proposed_change ?? {}) as Record<string, unknown>;
      return (
        <p className="mt-1 text-[12.5px] leading-snug">
          <span className="text-paper-fade">proposed </span>
          <span className="font-mono text-paper">{String(c.kind ?? "")}</span>
          <span className="text-paper-fade"> change · {String(c.id ?? "")}</span>
        </p>
      );
    }
    case "workflow.step.started":
      return (
        <p className="mt-1 text-[12.5px] leading-snug text-paper-dim">
          ⊳ step <span className="font-mono text-paper">{String(p.step_id ?? p.step ?? "")}</span> · {String(p.step_type ?? p.type ?? "")}
        </p>
      );
    case "workflow.step.finished":
      return (
        <p className="mt-1 text-[12.5px] leading-snug text-paper-dim">
          ⊠ step <span className="font-mono text-paper">{String(p.step_id ?? p.step ?? "")}</span> · {String(p.status ?? "succeeded")}
        </p>
      );
    case "workflow.run.started":
      return <p className="mt-1 text-[12.5px] text-paper-dim">▶ run started</p>;
    case "workflow.run.finished":
      return <p className="mt-1 text-[12.5px] text-paper-dim">■ run finished · {String(p.status ?? "")}</p>;
    case "workflow.run.failed":
      return <p className="mt-1 text-[12.5px] text-crit">✖ run failed · {String(p.error ?? "")}</p>;
    default:
      return null;
  }
}

function summariseArgs(args: unknown): string {
  if (!args || typeof args !== "object") return "";
  return Object.entries(args as Record<string, unknown>)
    .slice(0, 3)
    .map(([k, v]) => `${k}=${typeof v === "string" ? v.slice(0, 32) : JSON.stringify(v).slice(0, 32)}`)
    .join(" · ");
}

function chipLabel(t: string): string {
  if (t === "agent.thought") return "thought";
  if (t === "agent.tool.called") return "tool";
  if (t === "agent.tool.refused") return "refused";
  if (t === "corpus.query.called") return "corpus";
  if (t.startsWith("hook.")) return "hook";
  if (t === "policy.decision.hot") return "policy";
  if (t.startsWith("human.gate.")) return "gate";
  if (t === "finding.emitted") return "finding";
  if (t === "change.proposed") return "change";
  if (t.startsWith("workflow.step.")) return "step";
  if (t.startsWith("workflow.run.")) return "run";
  return t;
}

function toneFor(t: string): "info" | "muted" | "crit" {
  if (t === "agent.tool.refused" || t === "workflow.run.failed") return "crit";
  if (t === "agent.tool.called" || t === "finding.emitted" || t === "change.proposed") return "info";
  return "muted";
}
```

- [ ] **Step 2: Type-check the web app**

Run: `cd apps/web && npm run typecheck`
Expected: PASS — no TypeScript errors.

- [ ] **Step 3: Commit**

```bash
git add apps/web/components/workflow-run/ActivityFeed.tsx
git commit -m "feat(web): ActivityFeed component for workflow run page

Renders the live workflow event stream — agent thoughts, tool
calls, corpus queries, hook calls, policy decisions, human gates,
findings, proposed changes — with auto-scroll while the run is
running. Subscribes via useEventStream(workflowRun, live=true);
returns null in fixtures-only mode so it's a no-op there."
```

---

### Task 11: Mount `ActivityFeed` on `/workflow-runs/[id]/page.tsx`

**Files:**
- Modify: `apps/web/app/workflow-runs/[id]/page.tsx`

- [ ] **Step 1: Add the import**

In `apps/web/app/workflow-runs/[id]/page.tsx`, add to the imports near the top (after the `ProposedChangeView` import):

```tsx
import { ActivityFeed } from "@/components/workflow-run/ActivityFeed";
```

- [ ] **Step 2: Render the panel**

Find the `<Section number="03·2" eyebrow="Outputs" title="Findings · Proposed changes" ...>` block and the surrounding `<div className="mt-8 grid gap-6 lg:grid-cols-[1.6fr_1fr]">`. Below that grid (after its closing `</div>`), insert:

```tsx
      <div className="mt-6">
        <ActivityFeed run={run} />
      </div>
```

The full insertion sits between the existing closing `</div>` of the two-column grid and the `<Hairline tone="display" className="my-12" />` line.

- [ ] **Step 3: Type-check**

Run: `cd apps/web && npm run typecheck`
Expected: PASS.

- [ ] **Step 4: Build**

Run: `cd apps/web && npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/app/workflow-runs/[id]/page.tsx
git commit -m "feat(web): render ActivityFeed on workflow run page

The run page now shows a live event ticker beneath the DAG /
findings columns, ticking thoughts and tool calls in real time
as the simulator advances the run."
```

---

### Task 12: End-to-end manual smoke + final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full Python test suite from the repo root**

Run: `npm test`
Expected: PASS.

- [ ] **Step 2: Boot the demo without an OpenAI key**

In one shell: `unset OPENAI_API_KEY; npm run demo`

In a browser:

- Open `http://localhost:3000/` — confirm the dashboard shows ≥4 recent runs and ≥3 open findings.
- Open `http://localhost:3000/workflows` — confirm 6 prefab cards.
- Click any seeded run from the dashboard table. On `/workflow-runs/{id}`:
  - Activity panel populated immediately with events spanning the run.
  - Click a step row in the DAG → `StepDrawer` shows step-scoped events for that step.

- [ ] **Step 3: Instantiate a non-OpenAI workflow (e.g. `vendor_risk_review`)**

- Click `vendor_risk_review` → click *instantiate run*.
- On the run page, confirm:
  - The DAG ticks: each node moves `pending → running → succeeded` over ~12-18s.
  - The Activity panel scrolls events live (`hook.in.called`, `corpus.query.called`, `agent.thought`, `agent.tool.called`, `finding.emitted`, …).
  - On completion, status is `succeeded`; findings list shows the two scripted findings.

- [ ] **Step 4: Instantiate `code_compliance_scan_full` *with* an OpenAI key**

In a fresh shell: `export OPENAI_API_KEY=sk-…; npm run demo`

- Click `code_compliance_scan_full` → instantiate.
- On the run page, during the `scan` step the Activity panel should show 3-5 `agent.thought` events whose text is the model's rationale (recognisable as model-written prose, not the scripted strings).
- The run completes ~25-35s in. Findings come from the model.

- [ ] **Step 5: Same workflow, no OpenAI key**

- `unset OPENAI_API_KEY; npm run demo`
- Instantiate `code_compliance_scan_full`. Activity panel shows the scripted thought lines (`Inspecting outbound integrations and policy obligations.` / `send_email is missing the recipient-domain guard…`). Run completes in ~18-22s.

- [ ] **Step 6: If everything passes, mark the plan done with a final commit**

```bash
git commit --allow-empty -m "test(demo): manual e2e smoke verified

Confirmed:
- npm test passes
- Dashboard populated on boot
- Six prefab workflows visible
- Seeded runs render activity events on first paint
- Instantiated runs tick live (DAG + activity panel)
- code_compliance_scan_full uses live OpenAI when key set
- Same workflow falls back to scripted output without a key"
```
