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
