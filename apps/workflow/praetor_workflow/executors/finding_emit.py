from typing import Any


def emit_finding(args: dict[str, Any]) -> dict[str, Any]:
    findings = args.get("findings", [])
    return {"emitted": findings, "count": len(findings)}
