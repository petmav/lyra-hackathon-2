from __future__ import annotations

import json
import os
import subprocess
import sys


def test_agent_harness_emits_structured_output() -> None:
    finding = {
        "id": "fnd_test",
        "title": "Test finding",
        "description": "Harness finding.",
        "severity": "high",
        "confidence": 0.9,
        "obligations_cited": [],
        "documents_cited": [],
        "status": "open",
    }
    env = {
        **os.environ,
        "PRAETOR_AGENT_MANIFEST_JSON": json.dumps(
            {
                "workflow_run_id": "wfr_test",
                "step_id": "scan",
                "model_provider": "openai",
                "model": "gpt-5.4-mini",
                "expected_finding": finding,
            }
        ),
    }
    completed = subprocess.run(
        [sys.executable, "-m", "praetor_sandbox.harness.agent_step"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    marker_line = next(line for line in completed.stdout.splitlines() if line.startswith("PRAETOR_AGENT_STEP_OUTPUT="))
    output = json.loads(marker_line.split("=", 1)[1])

    assert output["ok"] is True
    assert output["model_call"]["mode"] == "sandbox_dry_run"
    assert output["findings"][0]["id"] == "fnd_test"
