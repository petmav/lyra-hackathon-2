from fastapi.testclient import TestClient

from praetor_api.main import app
from praetor_api.services.event_stream import reset_events

HEADERS = {"Authorization": "Bearer dev"}


def test_workflow_run_publishes_hash_chained_events() -> None:
    reset_events()
    client = TestClient(app)
    response = client.post(
        "/workflows/code_compliance_scan:run",
        headers=HEADERS,
        json={"inputs": {"repo_url": "stub://support-bot"}},
    )
    run_id = response.json()["workflow_run_id"]

    events = client.get(f"/events?workflow_run_id={run_id}", headers=HEADERS).json()

    assert [event["type"] for event in events][0] == "workflow.run.started"
    assert events[-1]["type"] == "workflow.run.finished"
    assert events[1]["hash_chain_prev"] == events[0]["hash_chain_self"]


def test_workflow_run_websocket_streams_events() -> None:
    reset_events()
    client = TestClient(app)
    response = client.post(
        "/workflows/code_compliance_scan:run",
        headers=HEADERS,
        json={"inputs": {"repo_url": "stub://support-bot"}},
    )
    run_id = response.json()["workflow_run_id"]

    with client.websocket_connect(f"/ws/v1/workflow-runs/{run_id}/stream?token=dev") as websocket:
        event = websocket.receive_json()

    assert event["workflow_run_id"] == run_id
    assert event["type"] == "workflow.run.started"


def test_asset_websocket_requires_token() -> None:
    client = TestClient(app)

    try:
        with client.websocket_connect("/ws/v1/assets/asset_northwind_support_bot/stream"):
            raise AssertionError("connection should not be accepted")
    except Exception as exc:
        assert "1008" in str(exc) or "missing or invalid bearer token" in str(exc)
