from __future__ import annotations

from unittest.mock import patch

from praetor_workflow import worker


def test_worker_drain_payload_includes_identity_and_lease(monkeypatch) -> None:
    calls: list[tuple[str, dict, str]] = []

    def fake_post_json(url: str, payload: dict, token: str) -> dict:
        calls.append((url, payload, token))
        if url.endswith("/workflow-runs:drain"):
            raise KeyboardInterrupt
        return {"count": 0}

    monkeypatch.setenv("PRAETOR_API_BASE", "http://api.test")
    monkeypatch.setenv("DEV_BEARER", "token")
    monkeypatch.setenv("PRAETOR_WORKFLOW_WORKER_ID", "worker-a")
    monkeypatch.setenv("PRAETOR_WORKFLOW_STEP_LEASE_SECONDS", "45")
    monkeypatch.setenv("PRAETOR_WORKFLOW_WORKER_INTERVAL_SECONDS", "0")

    with patch.object(worker, "_post_json", fake_post_json):
        try:
            worker.main()
        except KeyboardInterrupt:
            pass

    assert calls[0] == (
        "http://api.test/workflow-schedules:tick",
        {"limit": 4},
        "token",
    )
    assert calls[1] == (
        "http://api.test/workflow-runs:drain",
        {"limit": 4, "worker_id": "worker-a", "lease_seconds": 45},
        "token",
    )
