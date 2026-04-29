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
