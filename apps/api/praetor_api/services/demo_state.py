from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

FINDINGS: dict[str, dict[str, Any]] = {}
PROPOSED_CHANGES: dict[str, dict[str, Any]] = {}
SANDBOX_RUNS: dict[str, dict[str, Any]] = {}
EVIDENCE_RECORDS: dict[str, dict[str, Any]] = {}
AUDIT_PACKETS: dict[str, dict[str, Any]] = {}


def now() -> str:
    return datetime.now(UTC).isoformat()


def create_demo_finding(workflow_run_id: str | None = None) -> dict[str, Any]:
    finding_id = "finding_send_email"
    proposal_id = "pc_send_email_validator"
    finding = {
        "id": finding_id,
        "urn": f"urn:praetor:finding:demo:{finding_id}",
        "workflow_run_id": workflow_run_id,
        "asset_id": "asset_northwind_support_bot",
        "title": "send_email lacks recipient domain validation",
        "description": "The support-bot can send email to arbitrary recipient domains.",
        "severity": "high",
        "obligations_cited": [
            "urn:praetor:obligation:demo:iso-42001-8-3",
            "urn:praetor:obligation:demo:internal-data-min",
        ],
        "documents_cited": [],
        "confidence": 0.92,
        "status": "open",
        "reviewer": None,
        "proposed_change_ids": [proposal_id],
    }
    proposal = {
        "id": proposal_id,
        "urn": f"urn:praetor:proposed_change:demo:{proposal_id}",
        "finding_id": finding_id,
        "kind": "code",
        "diff_format": "unified",
        "diff": (
            "--- a/tools.py\n"
            "+++ b/tools.py\n"
            "@@\n"
            "+allowed_domains = {'northwind.test', 'customer.example'}\n"
            " def send_email(recipient, subject, body):\n"
            "+    assert recipient.rsplit('@', 1)[-1] in allowed_domains\n"
            "     return smtp.send(recipient, subject, body)\n"
        ),
        "target_asset_id": "asset_northwind_support_bot",
        "target_hook_id": "github_stub",
        "obligations_addressed": finding["obligations_cited"],
        "residual_risk_estimate": "Low after domain allowlist and hot-path policy remain active.",
        "sandbox_run_id": None,
        "status": "proposed",
        "approver": None,
        "applied_at": None,
        "apply_via_hook_id": "github_stub",
    }
    FINDINGS[finding_id] = finding
    PROPOSED_CHANGES[proposal_id] = proposal
    return finding


def ensure_demo_state() -> None:
    if not FINDINGS:
        create_demo_finding()


def create_sandbox_run(proposal_id: str) -> dict[str, Any]:
    proposal = PROPOSED_CHANGES[proposal_id]
    sandbox_id = f"sbx_{uuid4().hex[:12]}"
    sandbox = {
        "id": sandbox_id,
        "proposed_change_id": proposal_id,
        "manifest": {"mode": "replay", "proposal_id": proposal_id},
        "started_at": now(),
        "finished_at": now(),
        "exit_code": 0,
        "result": {
            "tests": [
                {"name": "blocks external recipient", "status": "passed"},
                {"name": "allows allowlisted recipient", "status": "passed"},
            ]
        },
    }
    SANDBOX_RUNS[sandbox_id] = sandbox
    proposal["sandbox_run_id"] = sandbox_id
    proposal["status"] = "sandbox_passed"
    return sandbox


def generate_evidence() -> dict[str, Any]:
    evidence_id = f"ev_{uuid4().hex[:12]}"
    evidence = {
        "id": evidence_id,
        "urn": f"urn:praetor:evidence_record:demo:{evidence_id}",
        "obligation_id": "urn:praetor:obligation:demo:internal-data-min",
        "control_id": "tool_permission",
        "asset_id": "asset_northwind_support_bot",
        "workflow_run_id": None,
        "event_ids": [],
        "decision_ids": [],
        "hash": uuid4().hex + uuid4().hex,
    }
    EVIDENCE_RECORDS[evidence_id] = evidence
    return evidence
