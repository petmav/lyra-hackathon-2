import type { Hook, JsonStackCategory } from "@/lib/api/types";

/**
 * Map a hook id to its integration category. The backend doesn't return
 * category, so we derive it from the stable stack id. Stays in sync with
 * the categories listed in docs/JSON_STACK_HOOKS.md.
 */
export function categorizeHook(hook: Pick<Hook, "id" | "kind">): JsonStackCategory {
  if (hook.kind === "mcp") return "platform";
  return categoryForStackId(hook.id);
}

export function categoryForStackId(id: string): JsonStackCategory {
  switch (id) {
    case "github_json":
    case "gitlab_json":
    case "azure_devops_json":
      return "code";
    case "jira_json":
    case "zendesk_json":
    case "servicenow_grc_json":
      return "ticketing";
    case "onedrive_json":
    case "google_drive_json":
    case "confluence_json":
    case "notion_json":
      return "docs";
    case "slack_json":
    case "teams_json":
      return "collaboration";
    case "salesforce_json":
      return "crm";
    case "okta_json":
      return "identity";
    case "datadog_json":
    case "splunk_hec_json":
      return "observability";
    case "onetrust_grc_json":
      return "grc";
    case "s3_presigned_json":
      return "storage";
    case "linear_json":
      return "ticketing";
    case "power_platform_json":
      return "platform";
    default:
      return "platform";
  }
}

export const CATEGORY_LABEL: Record<JsonStackCategory, string> = {
  code: "Code & change",
  ticketing: "Ticketing",
  docs: "Docs & knowledge",
  collaboration: "Collaboration",
  crm: "CRM",
  identity: "Identity",
  observability: "Observability & SIEM",
  grc: "GRC & trust",
  storage: "Storage",
  platform: "Platform & native"
};

export const CATEGORY_ORDER: JsonStackCategory[] = [
  "code",
  "ticketing",
  "docs",
  "collaboration",
  "crm",
  "identity",
  "observability",
  "grc",
  "storage",
  "platform"
];

export function effectRadiusTone(r: string): "ok" | "warn" | "crit" | "muted" {
  if (r === "internal") return "ok";
  if (r === "external_trusted") return "warn";
  if (r === "external_public") return "crit";
  return "muted";
}

export function directionLabel(d: string): string {
  if (d === "in") return "inbound";
  if (d === "out") return "outbound";
  if (d === "both") return "both";
  return d;
}
