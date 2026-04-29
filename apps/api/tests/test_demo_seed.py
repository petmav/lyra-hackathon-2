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
