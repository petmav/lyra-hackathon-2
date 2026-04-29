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
