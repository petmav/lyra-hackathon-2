# Praetor JSON Hook Stack

The JSON Hook Stack is Praetor's proprietary manifest format for connecting internal systems and external SaaS tools without writing a bespoke adapter for every platform.

It complements MCP. Use MCP when a vendor or internal team exposes tools/resources as an MCP server. Use JSON Stack when the target system is REST, OpenAPI-described, internal, or not ready for a full MCP server.

## Research Notes

The first catalog entries mirror common enterprise integration surfaces:

- OneDrive and SharePoint use Microsoft Graph `driveItem` resources for files and folders. Folder listing maps to `driveItem.children`; file addressing can be by id or path.
- Power Platform custom connectors are described through OpenAPI definitions. This is a close match for JSON Stack because both rely on operation descriptions, request shape, auth, and response shape.
- Salesforce exposes REST sObject resources for CRUD operations under `/services/data/{version}/sobjects/...`; Salesforce also publishes hosted MCP server profiles for scoped SObject reads/mutations.
- ServiceNow exposes standard REST APIs and Table API patterns under `/api/now/table/{tableName}`, with query parameters such as `sysparm_query`, `sysparm_fields`, and `sysparm_limit`.
- OneTrust publishes API references for integrating external systems into its trust, privacy, risk, third-party, and compliance workflows.

## Manifest Shape

```json
{
  "id": "internal_grc_json",
  "name": "Internal GRC JSON stack",
  "provider": "internal_grc",
  "version": "2026-04",
  "base_url": "https://grc.internal.example",
  "auth": {
    "kind": "bearer",
    "auth_ref": "secret:internal_grc_token",
    "scopes": ["findings.read", "findings.write"]
  },
  "operations": {
    "create_finding": {
      "direction": "out",
      "effect_radius": "external_trusted",
      "method": "POST",
      "path": "/api/findings",
      "body_template": {
        "title": "{finding.title}",
        "severity": "{finding.severity}",
        "source": "praetor"
      },
      "input_schema": {
        "finding": "object"
      },
      "output_map": {
        "external_id": "$.id",
        "url": "$.url"
      }
    }
  }
}
```

Rules:

- Raw secrets are not allowed in manifests. Use `auth.auth_ref`.
- Each operation declares direction, effect radius, method, path, inputs, and output mapping.
- `external_trusted` and `external_public` operations should be treated as write/effectful operations and routed through human or policy gates before live execution.
- Dry-run preview is the default; it returns the rendered request with auth redacted.

## API

- `GET /hooks/json-stack/catalog`
- `GET /hooks/json-stack/catalog/{stack_id}`
- `POST /hooks/json-stack:validate`
- `POST /hooks/json-stack:preview`
- `POST /hooks/{hook_id}:call`

Built-in stack ids:

- `onedrive_json`
- `power_platform_json`
- `salesforce_json`
- `servicenow_grc_json`
- `onetrust_grc_json`
- `github_json`
- `gitlab_json`
- `azure_devops_json`
- `jira_json`
- `confluence_json`
- `google_drive_json`
- `slack_json`
- `teams_json`
- `notion_json`
- `linear_json`
- `okta_json`
- `datadog_json`
- `splunk_hec_json`
- `zendesk_json`
- `s3_presigned_json`

Coverage by category:

- Code and change management: GitHub, GitLab, Azure DevOps.
- Ticketing and service management: Jira, Zendesk, ServiceNow.
- Knowledge and documents: OneDrive/SharePoint, Google Drive, Confluence, Notion.
- Collaboration: Slack, Microsoft Teams.
- CRM and business systems: Salesforce.
- Identity: Okta.
- Observability and SIEM: Datadog, Splunk HEC.
- GRC and trust systems: ServiceNow IRM, OneTrust.
- Internal/object storage: S3-compatible presigned URLs and custom internal manifests.

## Example Preview

```json
{
  "stack_id": "salesforce_json",
  "operation": "create_sobject",
  "inputs": {
    "instance_url": "https://example.my.salesforce.com",
    "api_version": "v66.0",
    "object_name": "Task",
    "record": {
      "Subject": "Review Praetor finding"
    }
  }
}
```

The preview renders a request to:

```text
POST https://example.my.salesforce.com/services/data/v66.0/sobjects/Task
```

with the authorization header redacted.

## Implementation Notes

Current support:

- Cataloged system templates for Microsoft Graph/OneDrive, Power Platform, Salesforce, ServiceNow IRM, OneTrust GRC, code hosts, ticketing systems, collaboration systems, identity, observability, SIEM, and S3-compatible storage.
- Manifest validation, including blocking inline secrets.
- Request rendering from typed inputs.
- Dry-run preview through dedicated JSON Stack endpoints.
- Production hook-call integration through hooks with `kind=json_stack`.
- Environment-backed `auth_ref` resolution for non-dry-run calls.
- Proposed-change dispatch can route approved remediation to GitHub, Jira, Linear, Microsoft Graph email, Slack, and ServiceNow through JSON Stack hooks.
- User-provided JSON Stack manifests persist as first-class production `hook` records through `POST /hooks/json-stack`.
- JSON Stack live responses evaluate operation `output_map` entries into normalized mapped fields, and hook calls carry idempotency keys to avoid duplicate external writes.
- The hooks UI can import OpenAPI JSON or YAML, select operations when JSON preview is available, convert them through the backend importer, preserve supported `securitySchemes` metadata, validate, and persist them.

Next implementation steps:

- Replace the current proposed-change approval marker with first-class policy decision rows for every effect-radius approval.
- Add broader OpenAPI coverage for callbacks, links, multipart bodies, and polymorphic schemas.
