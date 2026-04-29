import asyncio

from fastapi.testclient import TestClient

from praetor_api.main import app
from praetor_api.services.json_stack import build_request, call_stack, get_stack, validate_stack

HEADERS = {"Authorization": "Bearer dev"}


def test_json_stack_catalog_and_preview() -> None:
    client = TestClient(app)
    catalog = client.get("/hooks/json-stack/catalog", headers=HEADERS)
    assert catalog.status_code == 200
    assert {item["id"] for item in catalog.json()} >= {
        "onedrive_json",
        "power_platform_json",
        "salesforce_json",
        "servicenow_grc_json",
        "onetrust_grc_json",
        "github_json",
        "gitlab_json",
        "jira_json",
        "confluence_json",
        "google_drive_json",
        "slack_json",
        "teams_json",
        "notion_json",
        "linear_json",
        "okta_json",
        "datadog_json",
        "splunk_hec_json",
        "zendesk_json",
        "azure_devops_json",
        "s3_presigned_json",
    }

    preview = client.post(
        "/hooks/json-stack:preview",
        headers=HEADERS,
        json={
            "stack_id": "salesforce_json",
            "operation": "create_sobject",
            "inputs": {
                "instance_url": "https://example.my.salesforce.com",
                "api_version": "v66.0",
                "object_name": "Task",
                "record": {"Subject": "Review Praetor finding"},
            },
        },
    )

    assert preview.status_code == 200
    outputs = preview.json()["outputs"]
    assert outputs["mode"] == "json-stack-preview"
    assert outputs["request"]["method"] == "POST"
    assert "/services/data/v66.0/sobjects/Task" in outputs["request"]["url"]
    assert outputs["request"]["headers"]["Authorization"] == "[redacted auth_ref]"

    hooks = client.get("/hooks", headers=HEADERS)
    assert hooks.status_code == 200
    assert "jira_json" in {hook["id"] for hook in hooks.json()}


def test_json_stack_validation_rejects_inline_secrets() -> None:
    spec = {
        "id": "internal_grc",
        "name": "Internal GRC",
        "provider": "internal",
        "version": "1",
        "base_url": "https://grc.internal",
        "auth": {"kind": "bearer", "auth_ref": "secret:internal_grc"},
        "operations": {
            "create_finding": {
                "direction": "out",
                "effect_radius": "external_trusted",
                "method": "POST",
                "path": "/findings",
                "secret": "do-not-inline",
            }
        },
    }

    assert validate_stack(spec) == ["operation create_finding must use auth_ref, not inline secrets"]


def test_openapi_yaml_import_maps_security_schemes() -> None:
    document = """
openapi: 3.1.0
info:
  title: Internal GRC
  version: 2026-04
servers:
  - url: https://grc.internal.example
components:
  securitySchemes:
    oauth:
      type: oauth2
      flows:
        clientCredentials:
          tokenUrl: https://idp.internal/token
          scopes:
            grc.write: Write GRC records
security:
  - oauth:
      - grc.write
paths:
  /findings:
    post:
      operationId: createFinding
      requestBody:
        content:
          application/json:
            schema:
              type: object
      responses:
        "201":
          description: created
          content:
            application/json:
              schema:
                type: object
                properties:
                  id:
                    type: string
                  url:
                    type: string
"""
    response = TestClient(app).post(
        "/hooks/json-stack:import-openapi",
        headers=HEADERS,
        json={
            "document": document,
            "stack_id": "internal_grc_yaml",
            "provider": "internal_grc",
            "selected_operations": ["POST /findings"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    manifest = payload["manifest"]
    assert manifest["auth"]["kind"] == "oauth2"
    assert manifest["auth"]["auth_ref"] == "secret:internal_grc_oauth"
    assert manifest["auth"]["scopes"] == ["grc.write"]
    assert manifest["operations"]["createfinding"]["output_map"] == {"id": "$.id", "url": "$.url"}


def test_catalog_request_rendering() -> None:
    spec = get_stack("servicenow_grc_json")
    assert spec is not None
    operation = spec["operations"]["query_table"]
    request = build_request(
        spec,
        operation,
        {
            "instance": "acme",
            "table_name": "sn_grc_issue",
            "sysparm_query": "state=open",
            "sysparm_fields": "number,short_description",
            "sysparm_limit": 25,
        },
    )

    assert request["url"].startswith("https://acme.service-now.com/api/now/table/sn_grc_issue")
    assert "sysparm_limit=25" in request["url"]


def test_json_stack_live_call_requires_configured_secret() -> None:
    spec = {
        "id": "unit_test_json",
        "name": "Unit Test JSON",
        "provider": "unit_test",
        "version": "1",
        "base_url": "https://example.invalid",
        "auth": {"kind": "bearer", "auth_ref": "secret:unit_test_missing_secret"},
        "operations": {
            "read": {
                "direction": "in",
                "effect_radius": "internal",
                "method": "GET",
                "path": "/resource",
            }
        },
    }

    result = asyncio.run(call_stack(spec, "read", {}, dry_run=False))

    assert result.ok is False
    assert result.error == "missing-secret"
    assert result.outputs["env_key"] == "UNIT_TEST_MISSING_SECRET"
