from typing import Any


class AwaitingHumanApproval(RuntimeError):
    def __init__(self, approval: dict[str, Any]) -> None:
        super().__init__("workflow is awaiting human approval")
        self.approval = approval


def gate_human(args: dict[str, Any]) -> dict[str, Any]:
    approved = bool(args.get("approved", False))
    approval = {
        "subject": args.get("subject", "workflow_step"),
        "role_required": args.get("role_required", "grc_reviewer"),
        "status": "approved" if approved else "awaiting_approval",
    }
    if not approved:
        raise AwaitingHumanApproval(approval)
    return approval
