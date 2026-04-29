from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from string import Formatter
from time import perf_counter
from typing import Any
from urllib.parse import urlencode

import httpx

from praetor_api.services.secrets import MissingSecretError, require_secret, secret_status


REQUIRED_SPEC_FIELDS = {"id", "name", "provider", "version", "auth", "operations"}
SUPPORTED_AUTH_KINDS = {"oauth2", "bearer", "api_key", "basic", "none"}
SUPPORTED_DIRECTIONS = {"in", "out", "both", "supervise"}


@dataclass(frozen=True)
class JsonStackResult:
    ok: bool
    outputs: dict[str, Any]
    latency_ms: int
    error: str | None = None


def stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


JSON_STACK_CATALOG: dict[str, dict[str, Any]] = {
    "onedrive_json": {
        "id": "onedrive_json",
        "name": "OneDrive / SharePoint JSON stack",
        "provider": "microsoft_graph",
        "version": "2026-04",
        "base_url": "https://graph.microsoft.com/v1.0",
        "auth": {
            "kind": "oauth2",
            "auth_ref": "secret:microsoft_graph_oauth",
            "scopes": ["Files.Read", "Files.ReadWrite", "Sites.Read.All"],
        },
        "operations": {
            "list_children": {
                "direction": "in",
                "effect_radius": "internal",
                "method": "GET",
                "path": "/me/drive/root:/{folder_path}:/children",
                "query": {"$select": "id,name,webUrl,file,folder,lastModifiedDateTime"},
                "input_schema": {"folder_path": "string"},
                "output_map": {"items": "$.value"},
            },
            "upload_small_file": {
                "direction": "out",
                "effect_radius": "external_trusted",
                "method": "PUT",
                "path": "/me/drive/root:/{folder_path}/{filename}:/content",
                "body_template": "{content}",
                "input_schema": {"folder_path": "string", "filename": "string", "content": "string"},
                "output_map": {"drive_item_id": "$.id", "web_url": "$.webUrl"},
            },
        },
    },
    "microsoft_mail_json": {
        "id": "microsoft_mail_json",
        "name": "Microsoft Graph Mail JSON stack",
        "provider": "microsoft_graph_mail",
        "version": "2026-04",
        "base_url": "https://graph.microsoft.com/v1.0",
        "auth": {
            "kind": "oauth2",
            "auth_ref": "secret:microsoft_graph_oauth",
            "scopes": ["Mail.Send"],
        },
        "operations": {
            "send_mail": {
                "direction": "out",
                "effect_radius": "external_trusted",
                "method": "POST",
                "path": "/me/sendMail",
                "body_template": {
                    "message": {
                        "subject": "{subject}",
                        "body": {"contentType": "HTML", "content": "{body_html}"},
                        "toRecipients": "{to_recipients}",
                    },
                    "saveToSentItems": "{save_to_sent_items}",
                },
                "input_schema": {
                    "subject": "string",
                    "body_html": "string",
                    "to_recipients": "array",
                    "save_to_sent_items": "boolean",
                },
                "output_map": {"status": "$.status"},
            }
        },
    },
    "power_platform_json": {
        "id": "power_platform_json",
        "name": "Power Platform custom connector JSON stack",
        "provider": "power_platform",
        "version": "2026-04",
        "base_url": "https://api.powerplatform.com",
        "auth": {
            "kind": "oauth2",
            "auth_ref": "secret:power_platform_oauth",
            "scopes": ["customconnector.read", "customconnector.write"],
        },
        "operations": {
            "import_openapi_connector": {
                "direction": "out",
                "effect_radius": "external_trusted",
                "method": "POST",
                "path": "/providers/Microsoft.PowerApps/apis/{connector_id}",
                "body_template": {
                    "displayName": "{display_name}",
                    "openApiDefinition": "{openapi_definition}",
                },
                "input_schema": {
                    "connector_id": "string",
                    "display_name": "string",
                    "openapi_definition": "object",
                },
                "output_map": {"connector_id": "$.name"},
            }
        },
    },
    "salesforce_json": {
        "id": "salesforce_json",
        "name": "Salesforce REST / MCP JSON stack",
        "provider": "salesforce",
        "version": "2026-04",
        "base_url": "{instance_url}",
        "auth": {
            "kind": "oauth2",
            "auth_ref": "secret:salesforce_oauth",
            "scopes": ["api", "refresh_token"],
        },
        "operations": {
            "describe_sobject": {
                "direction": "in",
                "effect_radius": "internal",
                "method": "GET",
                "path": "/services/data/{api_version}/sobjects/{object_name}/describe",
                "input_schema": {
                    "instance_url": "string",
                    "api_version": "string",
                    "object_name": "string",
                },
                "output_map": {"fields": "$.fields"},
            },
            "create_sobject": {
                "direction": "out",
                "effect_radius": "external_trusted",
                "method": "POST",
                "path": "/services/data/{api_version}/sobjects/{object_name}",
                "body_template": "{record}",
                "input_schema": {
                    "instance_url": "string",
                    "api_version": "string",
                    "object_name": "string",
                    "record": "object",
                },
                "output_map": {"id": "$.id", "success": "$.success"},
            },
        },
    },
    "servicenow_grc_json": {
        "id": "servicenow_grc_json",
        "name": "ServiceNow IRM / GRC JSON stack",
        "provider": "servicenow_irm",
        "version": "2026-04",
        "base_url": "https://{instance}.service-now.com",
        "auth": {
            "kind": "oauth2",
            "auth_ref": "secret:servicenow_oauth",
            "scopes": ["table.read", "table.write"],
        },
        "operations": {
            "query_table": {
                "direction": "in",
                "effect_radius": "internal",
                "method": "GET",
                "path": "/api/now/table/{table_name}",
                "query": {
                    "sysparm_query": "{sysparm_query}",
                    "sysparm_fields": "{sysparm_fields}",
                    "sysparm_limit": "{sysparm_limit}",
                },
                "input_schema": {
                    "instance": "string",
                    "table_name": "string",
                    "sysparm_query": "string",
                    "sysparm_fields": "string",
                    "sysparm_limit": "integer",
                },
                "output_map": {"records": "$.result"},
            },
            "create_issue": {
                "direction": "out",
                "effect_radius": "external_trusted",
                "method": "POST",
                "path": "/api/now/table/{table_name}",
                "body_template": "{record}",
                "input_schema": {"instance": "string", "table_name": "string", "record": "object"},
                "output_map": {"sys_id": "$.result.sys_id"},
            },
        },
    },
    "onetrust_grc_json": {
        "id": "onetrust_grc_json",
        "name": "OneTrust GRC JSON stack",
        "provider": "onetrust",
        "version": "2026-04",
        "base_url": "https://{tenant}.onetrust.com",
        "auth": {
            "kind": "oauth2",
            "auth_ref": "secret:onetrust_oauth",
            "scopes": ["risk.read", "risk.write", "evidence.read"],
        },
        "operations": {
            "list_risks": {
                "direction": "in",
                "effect_radius": "internal",
                "method": "GET",
                "path": "/api/risks",
                "query": {"status": "{status}"},
                "input_schema": {"tenant": "string", "status": "string"},
                "output_map": {"risks": "$.data"},
            },
            "create_evidence": {
                "direction": "out",
                "effect_radius": "external_trusted",
                "method": "POST",
                "path": "/api/evidence",
                "body_template": "{evidence}",
                "input_schema": {"tenant": "string", "evidence": "object"},
                "output_map": {"id": "$.id"},
            },
        },
    },
    "github_json": {
        "id": "github_json",
        "name": "GitHub REST JSON stack",
        "provider": "github",
        "version": "2026-04",
        "base_url": "https://api.github.com",
        "auth": {"kind": "bearer", "auth_ref": "secret:github_token", "scopes": ["repo", "pull_requests:write"]},
        "operations": {
            "list_pull_requests": {
                "direction": "in",
                "effect_radius": "internal",
                "method": "GET",
                "path": "/repos/{owner}/{repo}/pulls",
                "query": {"state": "{state}"},
                "input_schema": {"owner": "string", "repo": "string", "state": "string"},
                "output_map": {"pull_requests": "$"},
            },
            "create_pull_request": {
                "direction": "out",
                "effect_radius": "external_trusted",
                "method": "POST",
                "path": "/repos/{owner}/{repo}/pulls",
                "body_template": {"title": "{title}", "head": "{head}", "base": "{base}", "body": "{body}"},
                "input_schema": {"owner": "string", "repo": "string", "title": "string", "head": "string", "base": "string", "body": "string"},
                "output_map": {"url": "$.html_url", "number": "$.number"},
            },
        },
    },
    "gitlab_json": {
        "id": "gitlab_json",
        "name": "GitLab REST JSON stack",
        "provider": "gitlab",
        "version": "2026-04",
        "base_url": "{gitlab_url}/api/v4",
        "auth": {"kind": "bearer", "auth_ref": "secret:gitlab_token", "scopes": ["api", "read_api"]},
        "operations": {
            "list_merge_requests": {
                "direction": "in",
                "effect_radius": "internal",
                "method": "GET",
                "path": "/projects/{project_id}/merge_requests",
                "query": {"state": "{state}"},
                "input_schema": {"gitlab_url": "string", "project_id": "string", "state": "string"},
                "output_map": {"merge_requests": "$"},
            },
            "create_merge_request": {
                "direction": "out",
                "effect_radius": "external_trusted",
                "method": "POST",
                "path": "/projects/{project_id}/merge_requests",
                "body_template": {"source_branch": "{source_branch}", "target_branch": "{target_branch}", "title": "{title}", "description": "{description}"},
                "input_schema": {"gitlab_url": "string", "project_id": "string", "source_branch": "string", "target_branch": "string", "title": "string", "description": "string"},
                "output_map": {"url": "$.web_url", "iid": "$.iid"},
            },
        },
    },
    "azure_devops_json": {
        "id": "azure_devops_json",
        "name": "Azure DevOps Git JSON stack",
        "provider": "azure_devops",
        "version": "2026-04",
        "base_url": "https://dev.azure.com/{organization}/{project}/_apis",
        "auth": {"kind": "bearer", "auth_ref": "secret:azure_devops_token", "scopes": ["vso.code", "vso.code_write"]},
        "operations": {
            "create_pull_request": {
                "direction": "out",
                "effect_radius": "external_trusted",
                "method": "POST",
                "path": "/git/repositories/{repository_id}/pullrequests",
                "query": {"api-version": "7.1"},
                "body_template": {"sourceRefName": "{source_ref}", "targetRefName": "{target_ref}", "title": "{title}", "description": "{description}"},
                "input_schema": {"organization": "string", "project": "string", "repository_id": "string", "source_ref": "string", "target_ref": "string", "title": "string", "description": "string"},
                "output_map": {"pull_request_id": "$.pullRequestId", "url": "$.url"},
            }
        },
    },
    "jira_json": {
        "id": "jira_json",
        "name": "Jira Cloud JSON stack",
        "provider": "jira",
        "version": "2026-04",
        "base_url": "https://{site}.atlassian.net",
        "auth": {"kind": "bearer", "auth_ref": "secret:jira_oauth", "scopes": ["read:jira-work", "write:jira-work"]},
        "operations": {
            "search_issues": {
                "direction": "in",
                "effect_radius": "internal",
                "method": "GET",
                "path": "/rest/api/3/search",
                "query": {"jql": "{jql}", "maxResults": "{max_results}"},
                "input_schema": {"site": "string", "jql": "string", "max_results": "integer"},
                "output_map": {"issues": "$.issues"},
            },
            "create_issue": {
                "direction": "out",
                "effect_radius": "external_trusted",
                "method": "POST",
                "path": "/rest/api/3/issue",
                "body_template": "{issue}",
                "input_schema": {"site": "string", "issue": "object"},
                "output_map": {"key": "$.key", "id": "$.id"},
            },
        },
    },
    "confluence_json": {
        "id": "confluence_json",
        "name": "Confluence Cloud JSON stack",
        "provider": "confluence",
        "version": "2026-04",
        "base_url": "https://{site}.atlassian.net/wiki",
        "auth": {"kind": "bearer", "auth_ref": "secret:confluence_oauth", "scopes": ["read:confluence-content.all", "write:confluence-content"]},
        "operations": {
            "search_content": {
                "direction": "in",
                "effect_radius": "internal",
                "method": "GET",
                "path": "/rest/api/content/search",
                "query": {"cql": "{cql}", "limit": "{limit}"},
                "input_schema": {"site": "string", "cql": "string", "limit": "integer"},
                "output_map": {"results": "$.results"},
            },
            "create_page": {
                "direction": "out",
                "effect_radius": "external_trusted",
                "method": "POST",
                "path": "/rest/api/content",
                "body_template": "{page}",
                "input_schema": {"site": "string", "page": "object"},
                "output_map": {"id": "$.id", "url": "$._links.webui"},
            },
        },
    },
    "google_drive_json": {
        "id": "google_drive_json",
        "name": "Google Drive JSON stack",
        "provider": "google_drive",
        "version": "2026-04",
        "base_url": "https://www.googleapis.com/drive/v3",
        "auth": {"kind": "oauth2", "auth_ref": "secret:google_drive_oauth", "scopes": ["https://www.googleapis.com/auth/drive.metadata.readonly", "https://www.googleapis.com/auth/drive.file"]},
        "operations": {
            "list_files": {
                "direction": "in",
                "effect_radius": "internal",
                "method": "GET",
                "path": "/files",
                "query": {"q": "{q}", "fields": "files(id,name,mimeType,webViewLink,modifiedTime)", "pageSize": "{page_size}"},
                "input_schema": {"q": "string", "page_size": "integer"},
                "output_map": {"files": "$.files"},
            }
        },
    },
    "slack_json": {
        "id": "slack_json",
        "name": "Slack Web API JSON stack",
        "provider": "slack",
        "version": "2026-04",
        "base_url": "https://slack.com/api",
        "auth": {"kind": "bearer", "auth_ref": "secret:slack_bot_token", "scopes": ["chat:write"]},
        "operations": {
            "post_message": {
                "direction": "out",
                "effect_radius": "external_trusted",
                "method": "POST",
                "path": "/chat.postMessage",
                "body_template": {"channel": "{channel}", "text": "{text}"},
                "input_schema": {"channel": "string", "text": "string"},
                "output_map": {"ok": "$.ok", "ts": "$.ts"},
            }
        },
    },
    "teams_json": {
        "id": "teams_json",
        "name": "Microsoft Teams Graph JSON stack",
        "provider": "microsoft_teams",
        "version": "2026-04",
        "base_url": "https://graph.microsoft.com/v1.0",
        "auth": {"kind": "oauth2", "auth_ref": "secret:microsoft_graph_oauth", "scopes": ["ChannelMessage.Send"]},
        "operations": {
            "send_channel_message": {
                "direction": "out",
                "effect_radius": "external_trusted",
                "method": "POST",
                "path": "/teams/{team_id}/channels/{channel_id}/messages",
                "body_template": {"body": {"contentType": "html", "content": "{content}"}},
                "input_schema": {"team_id": "string", "channel_id": "string", "content": "string"},
                "output_map": {"id": "$.id", "web_url": "$.webUrl"},
            }
        },
    },
    "notion_json": {
        "id": "notion_json",
        "name": "Notion API JSON stack",
        "provider": "notion",
        "version": "2026-04",
        "base_url": "https://api.notion.com/v1",
        "auth": {"kind": "bearer", "auth_ref": "secret:notion_token", "scopes": ["pages.read", "pages.write"]},
        "operations": {
            "create_page": {
                "direction": "out",
                "effect_radius": "external_trusted",
                "method": "POST",
                "path": "/pages",
                "body_template": "{page}",
                "input_schema": {"page": "object"},
                "output_map": {"id": "$.id", "url": "$.url"},
            }
        },
    },
    "linear_json": {
        "id": "linear_json",
        "name": "Linear GraphQL JSON stack",
        "provider": "linear",
        "version": "2026-04",
        "base_url": "https://api.linear.app",
        "auth": {"kind": "bearer", "auth_ref": "secret:linear_token", "scopes": ["issues:read", "issues:write"]},
        "operations": {
            "create_issue": {
                "direction": "out",
                "effect_radius": "external_trusted",
                "method": "POST",
                "path": "/graphql",
                "body_template": {
                    "query": "mutation IssueCreate($input: IssueCreateInput!) {{ issueCreate(input: $input) {{ success issue {{ id identifier title url }} }} }}",
                    "variables": {"input": "{issue}"},
                },
                "input_schema": {"issue": "object"},
                "output_map": {
                    "success": "$.data.issueCreate.success",
                    "id": "$.data.issueCreate.issue.id",
                    "url": "$.data.issueCreate.issue.url",
                },
            },
            "graphql": {
                "direction": "both",
                "effect_radius": "external_trusted",
                "method": "POST",
                "path": "/graphql",
                "body_template": {"query": "{query}", "variables": "{variables}"},
                "input_schema": {"query": "string", "variables": "object"},
                "output_map": {"data": "$.data"},
            }
        },
    },
    "okta_json": {
        "id": "okta_json",
        "name": "Okta Users JSON stack",
        "provider": "okta",
        "version": "2026-04",
        "base_url": "https://{org_domain}",
        "auth": {"kind": "oauth2", "auth_ref": "secret:okta_oauth", "scopes": ["okta.users.read", "okta.users.manage"]},
        "operations": {
            "list_users": {
                "direction": "in",
                "effect_radius": "internal",
                "method": "GET",
                "path": "/api/v1/users",
                "query": {"search": "{search}", "limit": "{limit}"},
                "input_schema": {"org_domain": "string", "search": "string", "limit": "integer"},
                "output_map": {"users": "$"},
            }
        },
    },
    "datadog_json": {
        "id": "datadog_json",
        "name": "Datadog Events JSON stack",
        "provider": "datadog",
        "version": "2026-04",
        "base_url": "https://api.{site}",
        "auth": {"kind": "api_key", "auth_ref": "secret:datadog_api_key", "scopes": ["events_read", "events_write"]},
        "operations": {
            "query_events": {
                "direction": "in",
                "effect_radius": "internal",
                "method": "GET",
                "path": "/api/v2/events",
                "query": {"filter[query]": "{query}", "page[limit]": "{limit}"},
                "input_schema": {"site": "string", "query": "string", "limit": "integer"},
                "output_map": {"events": "$.data"},
            }
        },
    },
    "splunk_hec_json": {
        "id": "splunk_hec_json",
        "name": "Splunk HEC JSON stack",
        "provider": "splunk",
        "version": "2026-04",
        "base_url": "https://{host}:8088",
        "auth": {"kind": "bearer", "auth_ref": "secret:splunk_hec_token", "scopes": ["hec:event"]},
        "operations": {
            "send_event": {
                "direction": "out",
                "effect_radius": "external_trusted",
                "method": "POST",
                "path": "/services/collector/event",
                "body_template": {"event": "{event}", "sourcetype": "{sourcetype}", "index": "{index}"},
                "input_schema": {"host": "string", "event": "object", "sourcetype": "string", "index": "string"},
                "output_map": {"text": "$.text", "code": "$.code"},
            }
        },
    },
    "zendesk_json": {
        "id": "zendesk_json",
        "name": "Zendesk Tickets JSON stack",
        "provider": "zendesk",
        "version": "2026-04",
        "base_url": "https://{subdomain}.zendesk.com",
        "auth": {"kind": "bearer", "auth_ref": "secret:zendesk_token", "scopes": ["tickets:read", "tickets:write"]},
        "operations": {
            "create_ticket": {
                "direction": "out",
                "effect_radius": "external_trusted",
                "method": "POST",
                "path": "/api/v2/tickets",
                "body_template": {"ticket": "{ticket}"},
                "input_schema": {"subdomain": "string", "ticket": "object"},
                "output_map": {"id": "$.ticket.id", "url": "$.ticket.url"},
            }
        },
    },
    "s3_presigned_json": {
        "id": "s3_presigned_json",
        "name": "S3-compatible presigned URL JSON stack",
        "provider": "s3_compatible",
        "version": "2026-04",
        "base_url": "{presigned_base_url}",
        "auth": {"kind": "none", "auth_ref": None, "scopes": ["object.put.presigned", "object.get.presigned"]},
        "operations": {
            "put_object_presigned": {
                "direction": "out",
                "effect_radius": "external_trusted",
                "method": "PUT",
                "path": "{presigned_path}",
                "body_template": "{content}",
                "input_schema": {"presigned_base_url": "string", "presigned_path": "string", "content": "string"},
                "output_map": {"status": "$.status"},
            }
        },
    },
}


def catalog_summary() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "name": spec["name"],
            "provider": spec["provider"],
            "version": spec["version"],
            "auth": {
                "kind": spec["auth"].get("kind", "none"),
                **secret_status(spec["auth"].get("auth_ref")),
            },
            "operations": [
                {
                    "name": name,
                    "direction": operation["direction"],
                    "effect_radius": operation["effect_radius"],
                    "method": operation["method"],
                    "path": operation["path"],
                }
                for name, operation in spec["operations"].items()
            ],
        }
        for spec in JSON_STACK_CATALOG.values()
    ]


def get_stack(stack_id: str) -> dict[str, Any] | None:
    spec = JSON_STACK_CATALOG.get(stack_id)
    return deepcopy(spec) if spec else None


def validate_stack(spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_SPEC_FIELDS - set(spec)
    if missing:
        errors.append(f"missing required fields: {', '.join(sorted(missing))}")

    auth = spec.get("auth", {})
    if not isinstance(auth, dict):
        errors.append("auth must be an object")
    elif auth.get("kind") not in SUPPORTED_AUTH_KINDS:
        errors.append(f"auth.kind must be one of {sorted(SUPPORTED_AUTH_KINDS)}")
    elif auth.get("kind") != "none" and not auth.get("auth_ref"):
        errors.append("auth.auth_ref is required unless auth.kind is none")

    operations = spec.get("operations", {})
    if not isinstance(operations, dict) or not operations:
        errors.append("operations must be a non-empty object")
        return errors

    for name, operation in operations.items():
        if not isinstance(operation, dict):
            errors.append(f"operation {name} must be an object")
            continue
        for field in ("direction", "effect_radius", "method", "path"):
            if field not in operation:
                errors.append(f"operation {name} missing {field}")
        if operation.get("direction") not in SUPPORTED_DIRECTIONS:
            errors.append(f"operation {name} has unsupported direction")
        if "raw_secret" in operation or "secret" in operation:
            errors.append(f"operation {name} must use auth_ref, not inline secrets")
    return errors


async def call_stack(
    spec: dict[str, Any],
    operation_name: str,
    inputs: dict[str, Any],
    dry_run: bool = True,
) -> JsonStackResult:
    started = perf_counter()
    errors = validate_stack(spec)
    if errors:
        return JsonStackResult(False, {"validation_errors": errors}, _elapsed_ms(started), "invalid-spec")

    operation = spec["operations"].get(operation_name)
    if operation is None:
        return JsonStackResult(False, {}, _elapsed_ms(started), "unknown-operation")

    try:
        request = build_request(spec, operation, inputs, resolve_auth=not dry_run)
    except MissingSecretError as exc:
        return JsonStackResult(
            False,
            {"auth_ref": exc.auth_ref, "env_key": exc.env_key},
            _elapsed_ms(started),
            "missing-secret",
        )
    if dry_run:
        return JsonStackResult(
            True,
            {
                "mode": "json-stack-preview",
                "provider": spec["provider"],
                "operation": operation_name,
                "request": redact_request(request),
                "request_hash": stable_hash(redact_request(request)),
                "output_map": operation.get("output_map", {}),
            },
            _elapsed_ms(started),
        )

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.request(
                request["method"],
                request["url"],
                headers=request["headers"],
                json=request.get("json"),
                content=request.get("content"),
            )
            response.raise_for_status()
            payload = response.json() if response.content else {"status": response.status_code}
    except (httpx.HTTPError, ValueError) as exc:
        return JsonStackResult(False, {"request": redact_request(request)}, _elapsed_ms(started), exc.__class__.__name__)

    mapped = apply_output_map(payload, operation.get("output_map", {}))
    return JsonStackResult(
        True,
        {
            "response": payload,
            "mapped": mapped,
            "response_hash": stable_hash(payload),
            "request_hash": stable_hash(redact_request(request)),
        },
        _elapsed_ms(started),
    )


def build_request(
    spec: dict[str, Any],
    operation: dict[str, Any],
    inputs: dict[str, Any],
    *,
    resolve_auth: bool = False,
) -> dict[str, Any]:
    base_url = _render(str(spec.get("base_url", "")), inputs).rstrip("/")
    path = _render(str(operation["path"]), inputs)
    query = {
        key: _render(str(value), inputs)
        for key, value in operation.get("query", {}).items()
        if _render(str(value), inputs) not in {"", "None"}
    }
    url = f"{base_url}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"

    body_template = operation.get("body_template")
    auth_headers = _auth_headers(
        spec["auth"],
        spec.get("provider", ""),
        resolve=resolve_auth,
    )
    request: dict[str, Any] = {
        "method": operation["method"],
        "url": url,
        "headers": {
            "Accept": "application/json",
            "Content-Type": "application/json",
            **auth_headers,
        },
    }
    if body_template is not None:
        body = _render_value(body_template, inputs)
        if isinstance(body, str):
            request["content"] = body
        else:
            request["json"] = body
    return request


def redact_request(request: dict[str, Any]) -> dict[str, Any]:
    redacted = deepcopy(request)
    headers = redacted.get("headers", {})
    if "Authorization" in headers:
        headers["Authorization"] = "[redacted auth_ref]"
    if "X-API-Key" in headers:
        headers["X-API-Key"] = "[redacted auth_ref]"
    if "DD-API-KEY" in headers:
        headers["DD-API-KEY"] = "[redacted auth_ref]"
    return redacted


def apply_output_map(payload: Any, output_map: dict[str, str] | None) -> dict[str, Any]:
    if not output_map:
        return {"response": payload}
    return {key: _json_path(payload, path) for key, path in output_map.items()}


def _json_path(payload: Any, path: str) -> Any:
    if path == "$":
        return payload
    if not path.startswith("$."):
        return None
    value = payload
    for part in path[2:].split("."):
        if isinstance(value, dict):
            value = value.get(part)
            continue
        if isinstance(value, list) and part.isdigit():
            index = int(part)
            value = value[index] if 0 <= index < len(value) else None
            continue
        return None
    return value


def _auth_headers(auth: dict[str, Any], provider: str, *, resolve: bool) -> dict[str, str]:
    kind = auth.get("kind", "none")
    auth_ref = auth.get("auth_ref")
    if kind == "none":
        return {}
    if not resolve:
        return {"Authorization": f"{kind}:{auth_ref}"}

    token = require_secret(auth_ref)
    if kind in {"bearer", "oauth2"}:
        return {"Authorization": f"Bearer {token}"}
    if kind == "basic":
        return {"Authorization": f"Basic {token}"}
    if kind == "api_key":
        if provider == "datadog":
            return {"DD-API-KEY": token}
        return {"X-API-Key": token}
    return {}


def _render_value(value: Any, inputs: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: _render_value(item, inputs) for key, item in value.items()}
    if isinstance(value, list):
        return [_render_value(item, inputs) for item in value]
    if isinstance(value, str):
        fields = [field_name for _, field_name, _, _ in Formatter().parse(value) if field_name]
        if len(fields) == 1 and value == "{" + fields[0] + "}":
            return _lookup(inputs, fields[0])
        return _render(value, inputs)
    return value


def _render(template: str, inputs: dict[str, Any]) -> str:
    values = {key: _lookup(inputs, key) for _, key, _, _ in Formatter().parse(template) if key}
    return template.format(**values)


def _lookup(inputs: dict[str, Any], dotted: str) -> Any:
    value: Any = inputs
    for part in dotted.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return ""
    return value


def _elapsed_ms(started: float) -> int:
    return max(1, int((perf_counter() - started) * 1000))
