from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from praetor_api.services.json_stack import JSON_STACK_CATALOG, build_request, get_stack, redact_request

BASE_HOOKS: dict[str, dict[str, Any]] = {
    "github_stub": {
        "id": "github_stub",
        "name": "GitHub MCP stub",
        "kind": "mcp",
        "direction": "both",
        "endpoint": "http://mcp-github-stub:8800",
        "scopes": ["repo:read", "pull_request:write"],
        "effect_radius": "external_trusted",
        "enabled": True,
    },
    "slack_stub": {
        "id": "slack_stub",
        "name": "Slack MCP stub",
        "kind": "mcp",
        "direction": "out",
        "endpoint": "http://mcp-slack-stub:8800",
        "scopes": ["approval:request"],
        "effect_radius": "external_trusted",
        "enabled": True,
    },
    "localfiles_stub": {
        "id": "localfiles_stub",
        "name": "Local files MCP stub",
        "kind": "mcp",
        "direction": "in",
        "endpoint": "http://mcp-localfiles-stub:8800",
        "scopes": ["files:read"],
        "effect_radius": "internal",
        "enabled": True,
    },
}
HOOKS: dict[str, dict[str, Any]] = {**BASE_HOOKS}


def _json_stack_hooks() -> dict[str, dict[str, Any]]:
    hooks: dict[str, dict[str, Any]] = {}
    for stack_id, spec in JSON_STACK_CATALOG.items():
        directions = {operation["direction"] for operation in spec["operations"].values()}
        if "both" in directions or {"in", "out"} <= directions:
            direction = "both"
        elif "out" in directions:
            direction = "out"
        else:
            direction = "in"
        effect_radius = (
            "external_trusted"
            if any(operation["effect_radius"] != "internal" for operation in spec["operations"].values())
            else "internal"
        )
        hooks[stack_id] = {
            "id": stack_id,
            "name": spec["name"],
            "kind": "json_stack",
            "direction": direction,
            "endpoint": f"json-stack://{stack_id}",
            "scopes": spec.get("auth", {}).get("scopes", []),
            "effect_radius": effect_radius,
            "enabled": True,
        }
    return hooks


HOOKS.update(_json_stack_hooks())
CALLS: list[dict[str, Any]] = []


def test_hook(hook_id: str) -> dict[str, Any]:
    if hook_id not in HOOKS:
        raise KeyError(hook_id)
    return {"ok": True, "resources_count": 12, "latency_ms": 42}


def simulate_hook_outputs(
    hook_id: str,
    operation: str,
    inputs: dict[str, Any],
    dry_run: bool = True,
) -> dict[str, Any]:
    if hook_id not in HOOKS:
        raise KeyError(hook_id)

    if hook_id == "github_stub" and operation == "open_pr":
        return {
            "pr_url": "https://github.example/northwind/support-bot/pull/42",
            "branch": inputs.get("branch", "praetor/send-email-domain-guard"),
        }
    if hook_id == "github_stub" and operation == "read_repo":
        return {
            "repo_url": inputs.get("repo_url", "stub://support-bot"),
            "files": ["agent.py", "tools.py"],
        }
    if hook_id == "slack_stub" and operation == "request_approval":
        return {
            "approval_url": "https://slack.example/archives/C-demo/p-approval",
            "status": "requested",
        }
    if hook_id == "localfiles_stub" and operation == "read":
        return {
            "path": inputs.get("path", "/sandbox/work"),
            "content": "",
        }
    if hook_id in JSON_STACK_CATALOG:
        spec = get_stack(hook_id)
        if spec and operation in spec["operations"]:
            request = build_request(spec, spec["operations"][operation], inputs)
            return {
                "mode": "json-stack-preview",
                "provider": spec["provider"],
                "operation": operation,
                "request": redact_request(request),
                "output_map": spec["operations"][operation].get("output_map", {}),
                "dry_run": dry_run,
            }
    return {"status": "accepted", "dry_run": dry_run}


def call_hook(hook_id: str, operation: str, inputs: dict[str, Any], dry_run: bool = True) -> dict[str, Any]:
    if hook_id not in HOOKS:
        raise KeyError(hook_id)

    outputs = simulate_hook_outputs(hook_id, operation, inputs, dry_run)

    call = {
        "id": f"hkc_{uuid4().hex[:12]}",
        "hook_id": hook_id,
        "operation": operation,
        "direction": HOOKS[hook_id]["direction"],
        "inputs_redacted": inputs,
        "outputs_redacted": outputs,
        "status": "succeeded",
        "latency_ms": 42,
        "dry_run": dry_run,
        "created_at": datetime.now(UTC).isoformat(),
    }
    CALLS.append(call)
    return call
