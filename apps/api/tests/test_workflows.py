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
