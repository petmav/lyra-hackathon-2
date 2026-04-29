from typing import Any


def gate_policy(args: dict[str, Any]) -> dict[str, Any]:
    severity = str(args.get("severity", "info"))
    blocked = severity in {"critical", "block"}
    return {
        "outcome": "deny" if blocked else "allow",
        "blocked": blocked,
        "rationale": "critical risk requires manual remediation" if blocked else "policy gate passed",
    }
