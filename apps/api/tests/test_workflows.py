from fastapi.testclient import TestClient

from praetor_api.main import app

HEADERS = {"Authorization": "Bearer dev"}


def test_code_compliance_scan_run_emits_finding() -> None:
    client = TestClient(app)
    response = client.post(
        "/workflows/code_compliance_scan:run",
        headers=HEADERS,
        json={
            "inputs": {"repo_url": "stub://support-bot"},
            "model_provider": "anthropic",
            "model": "claude-3-5-sonnet-latest",
        },
    )

    assert response.status_code == 200
    run_id = response.json()["workflow_run_id"]

    run_response = client.get(f"/workflow-runs/{run_id}", headers=HEADERS)
    assert run_response.status_code == 200

    run = run_response.json()
    assert run["status"] == "succeeded"
    assert run["model_provider"] == "anthropic"
    assert run["outputs"]["findings"][0]["severity"] == "high"
