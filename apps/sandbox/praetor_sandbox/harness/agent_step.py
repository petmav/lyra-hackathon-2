from __future__ import annotations

import json
import os
from typing import Any


MARKER = "PRAETOR_AGENT_STEP_OUTPUT="


def main() -> None:
    payload = _manifest_payload()
    finding = payload.get("expected_finding")
    if not isinstance(finding, dict):
        finding = _fallback_finding(payload)

    output = {
        "ok": True,
        "model_provider": str(payload.get("model_provider") or os.getenv("PRAETOR_MODEL_PROVIDER") or "openai"),
        "model": str(payload.get("model") or os.getenv("PRAETOR_MODEL") or "gpt-5.4-mini"),
        "model_call": {
            "ok": True,
            "mode": "sandbox_dry_run",
            "provider": str(payload.get("model_provider") or os.getenv("PRAETOR_MODEL_PROVIDER") or "openai"),
            "model": str(payload.get("model") or os.getenv("PRAETOR_MODEL") or "gpt-5.4-mini"),
            "configured": False,
            "text": "Sandbox harness produced a governed structured finding from supplied workflow context.",
            "usage": {},
        },
        "findings": [finding],
        "tools": [
            {"name": "corpus_query", "status": "ok"},
            {"name": "cite_obligation", "status": "ok"},
            {"name": "emit_finding", "status": "ok"},
        ],
        "memory_writes": [
            {
                "key": f"{payload.get('workflow_run_id', 'workflow')}:{payload.get('step_id', 'agent')}:finding",
                "provenance": "sandbox://agent_step",
            }
        ],
    }
    print("praetor sandbox agent harness completed", flush=True)
    print(f"{MARKER}{json.dumps(output, sort_keys=True)}", flush=True)


def _manifest_payload() -> dict[str, Any]:
    raw = os.getenv("PRAETOR_AGENT_MANIFEST_JSON", "{}")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _fallback_finding(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(payload.get("finding_id") or "fnd_sandbox"),
        "title": "Sandbox agent finding",
        "description": "The sandbox agent emitted a governed fallback finding.",
        "severity": "medium",
        "confidence": 0.5,
        "obligations_cited": [],
        "documents_cited": [],
        "status": "open",
    }


if __name__ == "__main__":
    main()
