from typing import Any


def run_agent(args: dict[str, Any]) -> dict[str, Any]:
    files: dict[str, str] = args.get("files", {})
    findings: list[dict[str, Any]] = []

    for path, source in files.items():
        if "send_email" in source and "allowed_domains" not in source:
            findings.append(
                {
                    "title": "send_email lacks recipient domain validation",
                    "description": (
                        "The support-bot email tool can send to arbitrary recipient domains. "
                        "Hot-path policy should refuse the call, and the code should enforce an allowlist."
                    ),
                    "severity": "high",
                    "confidence": 0.92,
                    "path": path,
                    "obligations_cited": [
                        "urn:praetor:obligation:demo:iso-42001-8-3",
                        "urn:praetor:obligation:demo:internal-data-min",
                    ],
                }
            )

    return {"findings": findings}
