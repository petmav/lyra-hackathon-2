from typing import Any


def call_hook_out(args: dict[str, Any]) -> dict[str, Any]:
    hook_id = str(args.get("hook_id", "github_stub"))
    operation = str(args.get("operation", "open_pr"))
    payload = args.get("payload", {})

    if operation == "open_pr":
        return {
            "hook_id": hook_id,
            "operation": operation,
            "status": "succeeded",
            "pr_url": "https://github.example/northwind/support-bot/pull/42",
            "payload": payload,
        }

    return {"hook_id": hook_id, "operation": operation, "status": "succeeded", "payload": payload}
