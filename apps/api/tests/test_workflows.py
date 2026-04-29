from fastapi.testclient import TestClient

from praetor_api.main import app

HEADERS = {"Authorization": "Bearer dev"}


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
