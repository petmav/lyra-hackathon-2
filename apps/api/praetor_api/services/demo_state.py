from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

FINDINGS: dict[str, dict[str, Any]] = {}
PROPOSED_CHANGES: dict[str, dict[str, Any]] = {}
SANDBOX_RUNS: dict[str, dict[str, Any]] = {}
EVIDENCE_RECORDS: dict[str, dict[str, Any]] = {}
AUDIT_PACKETS: dict[str, dict[str, Any]] = {}


def _asset(
    *,
    aid: str,
    type: str,
    name: str,
    description: str,
    owner: str = "demo",
    risk_tier: str = "L2",
    lifecycle: str = "governed",
) -> dict[str, Any]:
    iso = "2026-01-15T00:00:00+00:00"
    return {
        "id": aid,
        "urn": f"urn:praetor:asset:demo:{aid}",
        "created_at": iso,
        "updated_at": iso,
        "created_by": "demo:seed",
        "version": 1,
        "type": type,
        "name": name,
        "description": description,
        "owner_id": owner,
        "risk_tier": risk_tier,
        "lifecycle": lifecycle,
        "parent_asset_id": None,
        "jurisdictions": [],
        "data_classifications": [],
        "sectors": [],
        "tags": [],
        "fingerprint": "0" * 64,
        "metadata": {},
        "config": {"external_id": aid},
    }


DEMO_ASSETS: dict[str, dict[str, Any]] = {
    "asset_northwind_support_bot": _asset(
        aid="asset_northwind_support_bot",
        type="ai_system",
        name="Northwind support-bot",
        description="Customer-facing chat assistant with email + refund tools.",
        risk_tier="L3",
    ),
    "asset_acme_vendor": _asset(
        aid="asset_acme_vendor",
        type="ai_system",
        name="Acme vendor — third-party SaaS",
        description="Vendor whose SOC2 attestation is under review.",
    ),
    "asset_policy_corpus": _asset(
        aid="asset_policy_corpus",
        type="dataset",
        name="Internal policy corpus",
        description="Existing internal control documents and policies.",
    ),
    "asset_evidence_q1": _asset(
        aid="asset_evidence_q1",
        type="dataset",
        name="Q1 evidence bundle",
        description="Raw artefacts collected for the Q1 audit window.",
        risk_tier="L1",
    ),
    "asset_chat_summary_v2": _asset(
        aid="asset_chat_summary_v2",
        type="ai_system",
        name="Chat-summary v2",
        description="Customer-facing PII-aware summarisation tool, intake under review.",
        risk_tier="L3",
        lifecycle="classified",
    ),
}


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
    if not SANDBOX_RUNS:
        seed_demo_sandbox_runs()


def create_sandbox_run(proposal_id: str) -> dict[str, Any]:
    proposal = PROPOSED_CHANGES[proposal_id]
    sandbox_id = f"sbx_{uuid4().hex[:12]}"
    sandbox = {
        "id": sandbox_id,
        "proposed_change_id": proposal_id,
        "manifest": {"mode": "replay", "proposal_id": proposal_id},
        "status": "succeeded",
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


def _ago(seconds: float) -> str:
    return (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat()


def seed_demo_sandbox_runs() -> None:
    """Populate the sandbox-run ledger with a varied set of demo entries.

    Mirrors the shapes the production replay manifest produces — agent step
    sandboxes, remediation replay batteries, and a few historical failures —
    so the sandbox page reads like a real forensic ledger rather than a
    blank table.
    """

    SANDBOX_RUNS["sbx_send_email_replay"] = {
        "id": "sbx_send_email_replay",
        "proposed_change_id": "pc_send_email_validator",
        "manifest": {
            "mode": "replay",
            "image": "praetor/sandbox-runtime:latest",
            "agent": {"provider": "anthropic", "model": "claude-opus-4-7"},
            "resources": {"cpu": 2, "mem_mb": 2048, "wall_s": 300},
            "network": "praetor-mocks",
            "battery": "send_email_recipient_v3",
        },
        "status": "succeeded",
        "started_at": _ago(60 * 8),
        "finished_at": _ago(60 * 7 + 18),
        "exit_code": 0,
        "result": {
            "all_replays_passed": True,
            "coverage": {"branches": 0.87, "lines": 0.94},
            "logs": {
                "stdout": (
                    "[sandbox] mounting overlay /sandbox/work\n"
                    "[sandbox] applying patch tools.py (+3 / -0)\n"
                    "[replay] battery=send_email_recipient_v3 cases=6\n"
                    "[replay] case 1/6 'valid recipient on allowlist' → pass (12ms)\n"
                    "[replay] case 2/6 'wildcard match (*.gov.au)' → pass (8ms)\n"
                    "[replay] case 3/6 'denied recipient — attacker.test' → pass (11ms)\n"
                    "[replay] case 4/6 'prompt-injection: ignore previous' → pass (14ms)\n"
                    "[replay] case 5/6 'unicode hyphen subject' → pass (9ms)\n"
                    "[replay] case 6/6 'edge — empty recipient' → pass (6ms)\n"
                    "[sandbox] exit 0\n"
                ),
                "stderr": "",
            },
        },
        "replay_results": [
            {"label": "valid recipient on allowlist", "status": "pass"},
            {"label": "wildcard match (*.gov.au)", "status": "pass"},
            {"label": "denied recipient — attacker.test", "status": "pass"},
            {"label": "prompt-injection — ignore previous instructions", "status": "pass"},
            {"label": "unicode hyphen in subject line", "status": "pass"},
            {"label": "edge — empty recipient", "status": "pass"},
        ],
    }

    SANDBOX_RUNS["sbx_scan_step_live"] = {
        "id": "sbx_scan_step_live",
        "step_run_id": "sr_scan_001",
        "workflow_run_id": "wfr_2026_04_28_001",
        "manifest": {
            "mode": "live",
            "image": "praetor/sandbox-runtime:latest",
            "agent": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
            "resources": {"cpu": 2, "mem_mb": 2048, "wall_s": 240},
            "network": "praetor-mocks",
            "step": "scan",
            "tools": ["corpus.query", "fs.read"],
        },
        "status": "running",
        "started_at": _ago(60 * 2 + 14),
        "result": {
            "progress": "embedding tools.py — 312 / 487 chunks",
            "logs": {
                "stdout": (
                    "[sandbox] pulled praetor/sandbox-runtime:latest\n"
                    "[sandbox] cgroup limits applied: cpu=2 mem=2GiB\n"
                    "[agent] step=scan model=claude-sonnet-4-6\n"
                    "[mcp] outbound corpus.query — internal_data_min\n"
                    "[mcp] received 12 chunks (2 cited)\n"
                ),
                "stderr": "",
            },
        },
    }

    SANDBOX_RUNS["sbx_vendor_attestation"] = {
        "id": "sbx_vendor_attestation",
        "workflow_run_id": "wfr_2026_04_27_002",
        "manifest": {
            "mode": "live",
            "image": "praetor/sandbox-runtime:latest",
            "agent": {"provider": "openai", "model": "gpt-4o-mini"},
            "resources": {"cpu": 1, "mem_mb": 1024, "wall_s": 180},
            "network": "praetor-mocks",
            "step": "analyze_attestation",
        },
        "status": "succeeded",
        "started_at": _ago(86_400),
        "finished_at": _ago(86_400 - 96),
        "exit_code": 0,
        "result": {
            "gaps_found": 3,
            "controls_evaluated": 27,
            "logs": {
                "stdout": (
                    "[sandbox] booted in 1.4s\n"
                    "[agent] retrieving SOC2 obligations…\n"
                    "[agent] cross-walking against attestation control matrix\n"
                    "[agent] gap: CC6.1 evidence period < 6 months\n"
                    "[agent] gap: CC7.2 incident response runbook unsigned\n"
                    "[agent] gap: A1.2 BCDR last-tested > 12 months\n"
                    "[sandbox] exit 0\n"
                ),
                "stderr": "",
            },
        },
    }

    SANDBOX_RUNS["sbx_pii_classifier_oom"] = {
        "id": "sbx_pii_classifier_oom",
        "workflow_run_id": "wfr_2026_04_26_009",
        "manifest": {
            "mode": "replay",
            "image": "praetor/sandbox-runtime:latest",
            "agent": {"provider": "anthropic", "model": "claude-opus-4-7"},
            "resources": {"cpu": 2, "mem_mb": 2048, "wall_s": 300},
            "network": "praetor-mocks",
            "battery": "pii_classifier_v1",
        },
        "status": "oom",
        "started_at": _ago(86_400 * 1.4),
        "finished_at": _ago(86_400 * 1.4 - 142),
        "exit_code": 137,
        "result": {
            "killed_by": "oom-killer",
            "rss_peak_mb": 2061,
            "logs": {
                "stdout": (
                    "[sandbox] battery=pii_classifier_v1 cases=24\n"
                    "[replay] case 11/24 'long-form chat transcript (32k tokens)' → running\n"
                ),
                "stderr": (
                    "Killed: RSS exceeded cgroup mem.max (2048MiB)\n"
                    "praetor-sandbox: container terminated, exit=137\n"
                ),
            },
        },
    }

    SANDBOX_RUNS["sbx_outbound_smtp_timeout"] = {
        "id": "sbx_outbound_smtp_timeout",
        "step_run_id": "sr_dispatch_007",
        "workflow_run_id": "wfr_2026_04_25_003",
        "manifest": {
            "mode": "live",
            "image": "praetor/sandbox-runtime:latest",
            "agent": {"provider": "openai", "model": "gpt-4o"},
            "resources": {"cpu": 2, "mem_mb": 2048, "wall_s": 90},
            "network": "praetor-mocks",
            "step": "dispatch_remediation",
        },
        "status": "timeout",
        "started_at": _ago(86_400 * 2 + 1_200),
        "finished_at": _ago(86_400 * 2 + 1_200 - 90),
        "exit_code": 124,
        "result": {
            "wall_s_used": 90,
            "wall_s_budget": 90,
            "logs": {
                "stdout": (
                    "[sandbox] waiting on praetor-mocks:smtp (3 retries)\n"
                    "[sandbox] retry 1/3 in 4s\n"
                    "[sandbox] retry 2/3 in 8s\n"
                    "[sandbox] retry 3/3 in 16s\n"
                ),
                "stderr": "praetor-sandbox: wall-clock budget exceeded (90s)\n",
            },
        },
    }

    SANDBOX_RUNS["sbx_intake_classify_failed"] = {
        "id": "sbx_intake_classify_failed",
        "workflow_run_id": "wfr_2026_04_24_011",
        "manifest": {
            "mode": "live",
            "image": "praetor/sandbox-runtime:latest",
            "agent": {"provider": "anthropic", "model": "claude-haiku-4-5"},
            "resources": {"cpu": 1, "mem_mb": 1024, "wall_s": 120},
            "network": "praetor-mocks",
            "step": "classify_intake",
        },
        "status": "failed",
        "started_at": _ago(86_400 * 3),
        "finished_at": _ago(86_400 * 3 - 47),
        "exit_code": 1,
        "result": {
            "reason": "policy.refusal",
            "logs": {
                "stdout": (
                    "[agent] received intake form for asset=chat_summary_v2\n"
                    "[agent] requesting tool corpus.query…\n"
                ),
                "stderr": (
                    "policy refused tool call: corpus.query — scope mismatch (intake step has read-only PII corpus)\n"
                    "agent halted; no tier classification produced\n"
                ),
            },
        },
    }

    SANDBOX_RUNS["sbx_evidence_sweep_legacy"] = {
        "id": "sbx_evidence_sweep_legacy",
        "workflow_run_id": "wfr_2026_04_22_004",
        "manifest": {
            "mode": "replay",
            "image": "praetor/sandbox-runtime:latest",
            "agent": {"provider": "openai", "model": "gpt-4o-mini"},
            "resources": {"cpu": 1, "mem_mb": 1024, "wall_s": 180},
            "network": "praetor-mocks",
        },
        "status": "succeeded",
        "started_at": _ago(86_400 * 5),
        "finished_at": _ago(86_400 * 5 - 71),
        "exit_code": 0,
        "result": {
            "evidence_records_emitted": 14,
            "obligations_bound": 9,
        },
    }


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
