from typing import Any


def propose_change(args: dict[str, Any]) -> dict[str, Any]:
    finding = args.get("finding", {})
    target = str(args.get("target", "tools.py"))
    return {
        "kind": "code",
        "target": target,
        "status": "proposed",
        "finding_title": finding.get("title", "control gap"),
        "diff": (
            f"--- a/{target}\n"
            f"+++ b/{target}\n"
            "@@\n"
            "+allowed_domains = {'northwind.test', 'customer.example'}\n"
            "+assert recipient.rsplit('@', 1)[-1] in allowed_domains\n"
        ),
    }
