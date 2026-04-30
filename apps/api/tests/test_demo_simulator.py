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


import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from praetor_api.services import demo_workflows
from praetor_api.services.demo_simulator import tick_run
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
    outputs = run["step_runs"][0]["outputs_redacted"]
    assert outputs["organized"] == 6
    # agent steps also stamp workflow_agent identifiers
    assert outputs["workflow_agent_asset_id"].startswith("asset_wfa_")


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
    step_events = [
        e for e in EVENTS
        if e["workflow_run_id"] == run_id
        and e["type"] not in {"workflow.run.started", "workflow.run.finished"}
    ]
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


import json
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
