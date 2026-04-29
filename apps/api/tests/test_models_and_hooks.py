from fastapi.testclient import TestClient

from praetor_api.main import app
from praetor_api.services.json_stack import apply_output_map

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


def test_json_stack_catalog_includes_dispatch_destinations() -> None:
    client = TestClient(app)
    response = client.get("/hooks/json-stack/catalog", headers=HEADERS)

    assert response.status_code == 200
    stacks = {stack["id"]: stack for stack in response.json()}
    assert {"github_json", "jira_json", "linear_json", "microsoft_mail_json", "slack_json"} <= set(stacks)
    assert any(operation["name"] == "create_issue" for operation in stacks["linear_json"]["operations"])
    assert any(operation["name"] == "send_mail" for operation in stacks["microsoft_mail_json"]["operations"])


def test_json_stack_persist_validates_manifest_shape() -> None:
    client = TestClient(app)
    response = client.post(
        "/hooks/json-stack",
        headers=HEADERS,
        json={
            "spec": {
                "id": "demo_custom_hook",
                "name": "Demo Custom Hook",
                "provider": "internal",
                "version": "2026-04",
                "base_url": "https://internal.example",
                "auth": {"kind": "none", "auth_ref": None, "scopes": []},
                "operations": {
                    "ping": {
                        "direction": "in",
                        "effect_radius": "internal",
                        "method": "GET",
                        "path": "/ping",
                    }
                },
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_json_stack_output_map_extracts_provider_fields() -> None:
    payload = {
        "html_url": "https://github.com/acme/repo/pull/7",
        "number": 7,
        "data": {"issueCreate": {"success": True, "issue": {"url": "https://linear.app/issue/ENG-1"}}},
    }

    mapped = apply_output_map(
        payload,
        {
            "github_url": "$.html_url",
            "github_number": "$.number",
            "linear_url": "$.data.issueCreate.issue.url",
        },
    )

    assert mapped == {
        "github_url": "https://github.com/acme/repo/pull/7",
        "github_number": 7,
        "linear_url": "https://linear.app/issue/ENG-1",
    }
