from fastapi.testclient import TestClient

from praetor_api.main import app

HEADERS = {"Authorization": "Bearer dev"}


def test_proposed_change_sandbox_approval_apply_and_audit_packet() -> None:
    client = TestClient(app)
    findings = client.get("/findings", headers=HEADERS).json()
    change_id = findings[0]["proposed_change_ids"][0]
    assert findings[0]["id"] == "finding_send_email"
    assert change_id == "pc_send_email_validator"

    sandbox = client.post(f"/proposed-changes/{change_id}:sandbox-run", headers=HEADERS)
    assert sandbox.status_code == 200
    assert sandbox.json()["exit_code"] == 0

    approve = client.post(f"/proposed-changes/{change_id}:approve", headers=HEADERS)
    assert approve.status_code == 200
    assert approve.json()["ok"] is True

    apply = client.post(f"/proposed-changes/{change_id}:apply", headers=HEADERS)
    assert apply.status_code == 200
    assert apply.json()["pr_url"].endswith("/pull/42")

    evidence = client.get("/evidence-records", headers=HEADERS)
    assert evidence.status_code == 200
    assert evidence.json()[0]["hash"]

    packet = client.post("/audit-packets:generate", headers=HEADERS)
    assert packet.status_code == 200
    assert packet.json()["packet_hash"] == "a" * 64
