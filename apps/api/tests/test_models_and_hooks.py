from fastapi.testclient import TestClient

from praetor_api.main import app

HEADERS = {"Authorization": "Bearer dev"}


def test_model_provider_registry_and_dry_run_completion() -> None:
    client = TestClient(app)
    providers = client.get("/models/providers", headers=HEADERS)

    assert providers.status_code == 200
    assert {provider["id"] for provider in providers.json()} >= {"openai", "anthropic", "google"}

    completion = client.post(
        "/models:complete",
        headers=HEADERS,
        json={
            "provider": "google",
            "model": "gemini-1.5-flash",
            "prompt": "Summarize a control gap",
            "dry_run": True,
        },
    )

    assert completion.status_code == 200
    assert completion.json()["provider"] == "google"
    assert completion.json()["model"] == "gemini-1.5-flash"


def test_model_readiness_and_offline_check() -> None:
    client = TestClient(app)

    readiness = client.get("/models/readiness", headers=HEADERS)
    assert readiness.status_code == 200
    assert "providers" in readiness.json()

    check = client.post(
        "/models:check",
        headers=HEADERS,
        json={"provider": "openai", "model": "gpt-5.4-mini", "live": False},
    )
    assert check.status_code == 200
    assert check.json()["provider"] == "openai"
    assert check.json()["live_checked"] is False


def test_hook_call_records_external_operation() -> None:
    response = TestClient(app).post(
        "/hooks/github_stub:call",
        headers=HEADERS,
        json={
            "operation": "open_pr",
            "inputs": {"branch": "praetor/test"},
            "dry_run": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["outputs_redacted"]["pr_url"].endswith("/pull/42")
