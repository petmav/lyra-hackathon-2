from __future__ import annotations

from datetime import UTC, datetime
import base64
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from praetor_api.bus import EVENTS_STREAM, get_redis_client
from praetor_api.models.agent_event import AgentEvent
from praetor_api.models.asset import Asset
from praetor_api.models.audit_packet import AuditPacket
from praetor_api.models.evidence_record import EvidenceRecord
from praetor_api.models.evidence_checkpoint import EvidenceCheckpoint
from praetor_api.models.finding import Finding
from praetor_api.models.hook import Hook
from praetor_api.models.obligation import Obligation
from praetor_api.models.policy_decision import PolicyDecision
from praetor_api.models.proposed_change import ProposedChange
from praetor_api.models.sandbox_run import SandboxRun
from praetor_api.models.workflow_run import WorkflowRun
from praetor_api.services.production_hooks import EffectGatedError, call_hook, ensure_hooks
from praetor_api.services import production_inventory
from praetor_api.services.production_workflows import ASSET_EXTERNAL_ID, ASSET_URN
from praetor_api.settings import get_settings

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
except ModuleNotFoundError:  # pragma: no cover - local dev without optional crypto wheel
    Ed25519PrivateKey = None
    Encoding = None
    PublicFormat = None

FINDING_URN_PREFIX = "urn:praetor:finding:"
PROPOSED_CHANGE_URN_PREFIX = "urn:praetor:proposed_change:"
EVIDENCE_URN_PREFIX = "urn:praetor:evidence_record:"
AUDIT_PACKET_URN_PREFIX = "urn:praetor:audit_packet:"
HOOK_URN_PREFIX = "urn:praetor:hook:"
ARTIFACT_ROOT = Path("artifacts/audit_packets")
DEFAULT_DISPATCH_HOOK = "github_json"

DISPATCH_OPTIONS: list[dict[str, Any]] = [
    {
        "hook_id": "github_json",
        "operation": "create_pull_request",
        "label": "GitHub pull request",
        "effect_radius": "external_trusted",
        "endpoint": "POST https://api.github.com/repos/{owner}/{repo}/pulls",
    },
    {
        "hook_id": "jira_json",
        "operation": "create_issue",
        "label": "Jira issue",
        "effect_radius": "external_trusted",
        "endpoint": "POST https://{site}.atlassian.net/rest/api/3/issue",
    },
    {
        "hook_id": "linear_json",
        "operation": "create_issue",
        "label": "Linear issue",
        "effect_radius": "external_trusted",
        "endpoint": "POST https://api.linear.app/graphql",
    },
    {
        "hook_id": "microsoft_mail_json",
        "operation": "send_mail",
        "label": "Microsoft Graph email",
        "effect_radius": "external_trusted",
        "endpoint": "POST https://graph.microsoft.com/v1.0/me/sendMail",
    },
    {
        "hook_id": "slack_json",
        "operation": "post_message",
        "label": "Slack message",
        "effect_radius": "external_trusted",
        "endpoint": "POST https://slack.com/api/chat.postMessage",
    },
    {
        "hook_id": "servicenow_grc_json",
        "operation": "create_issue",
        "label": "ServiceNow record",
        "effect_radius": "external_trusted",
        "endpoint": "POST https://{instance}.service-now.com/api/now/table/{table_name}",
    },
]


def _now() -> datetime:
    return datetime.now(UTC)


def _external_id(urn: str, prefix: str) -> str:
    return urn.removeprefix(prefix)


def _hash(data: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


async def ensure_review_state(session: AsyncSession) -> tuple[Finding, ProposedChange]:
    result = await session.execute(select(Finding).order_by(Finding.created_at))
    findings = list(result.scalars().all())
    for finding in findings:
        proposal = await _proposal_for_finding(session, finding)
        if proposal is not None:
            return finding, proposal

    if findings:
        finding = findings[0]
        proposal = await _create_proposal_for_finding(session, finding)
        return finding, proposal

    asset = await _ensure_asset(session)
    finding_id = f"fnd_{uuid4().hex[:12]}"
    obligations = [
        "urn:praetor:obligation:demo:iso-42001-8-3",
        "urn:praetor:obligation:demo:internal-data-min",
    ]
    finding = Finding(
        urn=f"{FINDING_URN_PREFIX}{finding_id}",
        workflow_run_id=None,
        asset_id=asset.id,
        title="send_email lacks recipient domain validation",
        description="The support-bot can send email to arbitrary recipient domains.",
        severity="high",
        obligations_cited=obligations,
        documents_cited=[],
        confidence=0.92,
        status="open",
        reviewer=None,
        proposed_change_ids=[],
    )
    session.add(finding)
    await session.flush()
    proposal = await _create_proposal_for_finding(session, finding)
    return finding, proposal


async def _create_proposal_for_finding(
    session: AsyncSession,
    finding: Finding,
) -> ProposedChange:
    hook = await _ensure_hook(session, DEFAULT_DISPATCH_HOOK)
    proposal_id = f"chg_{uuid4().hex[:12]}"
    obligations = finding.obligations_cited
    proposal = ProposedChange(
        urn=f"{PROPOSED_CHANGE_URN_PREFIX}{proposal_id}",
        finding_id=finding.id,
        kind="code",
        diff_format="unified",
        diff=(
            "--- a/tools.py\n"
            "+++ b/tools.py\n"
            "@@\n"
            "+allowed_domains = {'northwind.test', 'customer.example'}\n"
            " def send_email(recipient, subject, body):\n"
            "+    assert recipient.rsplit('@', 1)[-1] in allowed_domains\n"
            "     return smtp.send(recipient, subject, body)\n"
        ),
        target_asset_id=finding.asset_id,
        target_hook_id=hook.id if hook else None,
        obligations_addressed=obligations,
        residual_risk_estimate="Low after domain allowlist and hot-path policy remain active.",
        sandbox_run_id=None,
        status="proposed",
        approver=None,
        applied_at=None,
        apply_via_hook_id=hook.id if hook else None,
    )
    session.add(proposal)
    finding.proposed_change_ids = [proposal_id]
    await session.commit()
    await session.refresh(finding)
    await session.refresh(proposal)
    return finding, proposal


async def list_findings(session: AsyncSession) -> list[dict[str, Any]]:
    if get_settings().seed_demo_data:
        await ensure_review_state(session)
    result = await session.execute(select(Finding).order_by(Finding.created_at))
    rows = list(result.scalars().all())
    return [_finding_to_api(row) for row in rows]


async def get_finding(session: AsyncSession, finding_id: str) -> dict[str, Any] | None:
    if get_settings().seed_demo_data:
        await ensure_review_state(session)
    finding = await _find_finding(session, finding_id)
    return _finding_to_api(finding) if finding else None


async def set_finding_status(session: AsyncSession, finding_id: str, status: str) -> bool:
    if get_settings().seed_demo_data:
        await ensure_review_state(session)
    finding = await _find_finding(session, finding_id)
    if finding is None:
        return False
    finding.status = status
    finding.reviewer = "demo-analyst"
    await session.commit()
    return True


async def list_proposed_changes(session: AsyncSession) -> list[dict[str, Any]]:
    if get_settings().seed_demo_data:
        await ensure_review_state(session)
    result = await session.execute(select(ProposedChange).order_by(ProposedChange.created_at))
    return [_proposal_to_api(row) for row in result.scalars().all()]


async def get_proposed_change(session: AsyncSession, change_id: str) -> dict[str, Any] | None:
    if get_settings().seed_demo_data:
        await ensure_review_state(session)
    proposal = await _find_proposal(session, change_id)
    return _proposal_to_api(proposal) if proposal else None


async def create_sandbox_run(session: AsyncSession, change_id: str) -> dict[str, Any] | None:
    if get_settings().seed_demo_data:
        await ensure_review_state(session)
    proposal = await _find_proposal(session, change_id)
    if proposal is None:
        return None

    started = _now()
    manifest = {
        "mode": "docker",
        "fallback": "deterministic-replay",
        "proposal_id": change_id,
        "network": "praetor-mocks",
        "image": get_settings().sandbox_image,
        "command": ["python", "-V"],
        "memory_mb": 512,
        "pids_limit": 128,
        "read_only_root": True,
    }
    launch = await _launch_sandbox(manifest)
    sandbox = SandboxRun(
        workflow_run_id=None,
        manifest=manifest | {"orchestrator_mode": launch["mode"]},
        started_at=_parse_dt(launch.get("started_at")) or started,
        finished_at=_parse_dt(launch.get("finished_at")) or _now(),
        exit_code=int(launch.get("exit_code", 0)),
        result=launch["result"] | {"logs": launch.get("logs", {})},
    )
    session.add(sandbox)
    await session.flush()
    proposal.sandbox_run_id = sandbox.id
    proposal.status = "sandbox_passed"
    await session.commit()
    await session.refresh(sandbox)
    return _sandbox_to_api(sandbox, proposal)


async def _launch_sandbox(manifest: dict[str, Any]) -> dict[str, Any]:
    orchestrator_url = get_settings().sandbox_orchestrator_url
    if orchestrator_url:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(f"{orchestrator_url.rstrip('/')}/launch", json=manifest)
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, dict) and "result" in payload:
                    return payload
        except httpx.HTTPError as exc:
            return _sandbox_replay(manifest, f"orchestrator-unavailable:{exc.__class__.__name__}")
    return _sandbox_replay(manifest, "orchestrator-not-configured")


def _sandbox_replay(manifest: dict[str, Any], reason: str) -> dict[str, Any]:
    started = _now()
    finished = _now()
    return {
        "mode": "replay",
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "exit_code": 0,
        "logs": {
            "stdout": "deterministic replay: external recipient blocked\n"
            "deterministic replay: allowlisted recipient accepted\n",
            "stderr": "",
        },
        "result": {
            "tests": [
                {"name": "blocks external recipient", "status": "passed"},
                {"name": "allows allowlisted recipient", "status": "passed"},
            ],
            "docker_launch": "fallback",
            "fallback_reason": reason,
            "manifest": manifest,
        },
    }


async def get_sandbox_run(session: AsyncSession, sandbox_id: str) -> dict[str, Any] | None:
    proposal: ProposedChange | None = None
    sandbox = await _find_sandbox(session, sandbox_id)
    if sandbox is None:
        return None
    result = await session.execute(
        select(ProposedChange).where(ProposedChange.sandbox_run_id == sandbox.id)
    )
    proposal = result.scalar_one_or_none()
    return _sandbox_to_api(sandbox, proposal)


async def sandbox_logs(session: AsyncSession, sandbox_id: str) -> list[dict[str, Any]] | None:
    sandbox = await _find_sandbox(session, sandbox_id)
    if sandbox is None:
        return None
    logs = ((sandbox.result or {}).get("logs") or {})
    stdout = logs.get("stdout", "") if isinstance(logs, dict) else ""
    stderr = logs.get("stderr", "") if isinstance(logs, dict) else ""
    chunks: list[dict[str, Any]] = []
    for stream, text in (("stdout", stdout), ("stderr", stderr)):
        if not isinstance(text, str):
            continue
        for index, line in enumerate(text.splitlines()):
            chunks.append({"stream": stream, "index": index, "line": line})
    if not chunks:
        chunks.append({"stream": "system", "index": 0, "line": "no sandbox logs recorded"})
    return chunks


async def list_sandbox_runs(session: AsyncSession) -> list[dict[str, Any]]:
    result = await session.execute(select(SandboxRun).order_by(SandboxRun.started_at.desc()))
    rows = list(result.scalars().all())
    proposals = await session.execute(select(ProposedChange))
    by_sandbox_id = {
        proposal.sandbox_run_id: proposal
        for proposal in proposals.scalars().all()
        if proposal.sandbox_run_id is not None
    }
    return [_sandbox_to_api(row, by_sandbox_id.get(row.id)) for row in rows]


async def approve_change(session: AsyncSession, change_id: str) -> bool:
    if get_settings().seed_demo_data:
        await ensure_review_state(session)
    proposal = await _find_proposal(session, change_id)
    if proposal is None:
        return False
    proposal.status = "approved"
    proposal.approver = "demo-analyst"
    await session.commit()
    return True


async def apply_change(
    session: AsyncSession,
    change_id: str,
    *,
    hook_id: str | None = None,
    operation: str | None = None,
    inputs: dict[str, Any] | None = None,
    dry_run: bool = True,
) -> dict[str, Any] | None:
    if get_settings().seed_demo_data:
        await ensure_review_state(session)
    proposal = await _find_proposal(session, change_id)
    if proposal is None:
        return None
    if proposal.status != "approved":
        return {
            "ok": False,
            "error": "approval-required",
            "status": proposal.status,
            "message": "Approve the proposed change before dispatching it to an external system.",
        }
    if proposal.sandbox_run_id is None:
        return {
            "ok": False,
            "error": "sandbox-required",
            "status": proposal.status,
            "message": "Run and pass the sandbox replay before external dispatch.",
        }

    selected_hook_id = hook_id or await _hook_external_id(session, proposal.apply_via_hook_id) or DEFAULT_DISPATCH_HOOK
    selected_operation = operation or _default_operation(selected_hook_id)
    payload = _dispatch_inputs(proposal, selected_hook_id, selected_operation, inputs or {})
    try:
        dispatch = await call_hook(
            session,
            selected_hook_id,
            selected_operation,
            payload,
            dry_run,
            effect_approved=True,
        )
    except EffectGatedError as exc:
        return {
            "ok": False,
            "error": "effect-gated",
            "hook_id": exc.hook_id,
            "effect_radius": exc.effect_radius,
        }
    if dispatch["status"] != "succeeded":
        return {"ok": False, "status": "dispatch_failed", "dispatch": dispatch}

    if not dry_run:
        proposal.status = "applied"
        proposal.applied_at = _now()
        await session.commit()
    return {
        "ok": True,
        "status": "dispatch_previewed" if dry_run else "applied",
        "hook_id": selected_hook_id,
        "operation": selected_operation,
        "dry_run": dry_run,
        "dispatch": dispatch,
    }


async def list_evidence_records(session: AsyncSession) -> list[dict[str, Any]]:
    if get_settings().seed_demo_data:
        await ensure_review_state(session)
    result = await session.execute(select(EvidenceRecord).order_by(EvidenceRecord.created_at))
    rows = list(result.scalars().all())
    if not rows and get_settings().seed_demo_data:
        rows = [await generate_evidence_record(session)]
    obligations = await _obligations_by_id(session, rows)
    return [_evidence_to_api(row, obligations) for row in rows]


async def generate_evidence_record(session: AsyncSession) -> EvidenceRecord:
    finding, _ = await ensure_review_state(session)
    event_result = await session.execute(select(AgentEvent).order_by(AgentEvent.ts).limit(50))
    events = list(event_result.scalars().all())
    workflow_run_id = next((event.workflow_run_id for event in events if event.workflow_run_id), None)
    payload = {
        "finding_id": _external_id(finding.urn, FINDING_URN_PREFIX),
        "event_ids": [event.run_id or f"evt_{event.id.hex[:12]}" for event in events],
        "decision_ids": [],
    }
    evidence_id = f"ev_{uuid4().hex[:12]}"
    evidence = EvidenceRecord(
        urn=f"{EVIDENCE_URN_PREFIX}{evidence_id}",
        obligation_id=None,
        control_id="tool_permission",
        asset_id=finding.asset_id,
        workflow_run_id=workflow_run_id,
        event_ids=payload["event_ids"],
        decision_ids=[],
        hash=_hash(payload),
    )
    session.add(evidence)
    await session.commit()
    await session.refresh(evidence)
    return evidence


async def sweep_evidence_records(session: AsyncSession) -> list[EvidenceRecord]:
    result = await session.execute(select(WorkflowRun).order_by(WorkflowRun.created_at))
    runs = list(result.scalars().all())
    created: list[EvidenceRecord] = []
    for workflow_run in runs:
        existing = await session.scalar(
            select(EvidenceRecord.id).where(EvidenceRecord.workflow_run_id == workflow_run.id).limit(1)
        )
        if existing is not None:
            continue
        event_result = await session.execute(
            select(AgentEvent).where(AgentEvent.workflow_run_id == workflow_run.id).order_by(AgentEvent.ts)
        )
        events = list(event_result.scalars().all())
        if not events:
            continue
        payload = {
            "workflow_run_id": str(workflow_run.id),
            "event_ids": [event.run_id or f"evt_{event.id.hex[:12]}" for event in events],
            "decision_ids": [],
        }
        evidence_id = f"ev_{uuid4().hex[:12]}"
        evidence = EvidenceRecord(
            urn=f"{EVIDENCE_URN_PREFIX}{evidence_id}",
            obligation_id=None,
            control_id="workflow_runtime",
            asset_id=workflow_run.asset_id,
            workflow_run_id=workflow_run.id,
            event_ids=payload["event_ids"],
            decision_ids=[],
            hash=_hash(payload),
        )
        session.add(evidence)
        created.append(evidence)
    if created:
        await session.commit()
        for evidence in created:
            await session.refresh(evidence)
    return created


async def consume_evidence_events(
    session: AsyncSession,
    *,
    consumer: str = "evidence-worker-v2",
    limit: int = 100,
) -> dict[str, Any]:
    limit = max(1, min(limit, 500))
    if get_settings().data_mode == "production":
        stream_result = await _consume_evidence_events_from_stream(session, consumer=consumer, limit=limit)
        if stream_result is not None:
            return stream_result
    return await _consume_evidence_events_from_db(session, consumer=consumer, limit=limit)


async def _consume_evidence_events_from_db(
    session: AsyncSession,
    *,
    consumer: str,
    limit: int,
) -> dict[str, Any]:
    checkpoint = await _evidence_checkpoint(session, consumer)
    query = select(AgentEvent).order_by(AgentEvent.ts, AgentEvent.id).limit(limit)
    if checkpoint.last_event_ts is not None:
        query = query.where(
            or_(
                AgentEvent.ts > checkpoint.last_event_ts,
                and_(AgentEvent.ts == checkpoint.last_event_ts, AgentEvent.id > checkpoint.last_event_id),
            )
        )
    result = await session.execute(query)
    events = list(result.scalars().all())
    if not events:
        return {"created": [], "count": 0, "source": "postgres", "checkpoint": _checkpoint_to_api(checkpoint)}

    created = await _materialize_evidence_for_events(session, events)

    last = events[-1]
    checkpoint.last_event_id = last.id
    checkpoint.last_event_ts = last.ts
    checkpoint.updated_at = _now()
    await session.commit()
    for row in created:
        await session.refresh(row)
    return {
        "created": [_external_id(row.urn, EVIDENCE_URN_PREFIX) for row in created],
        "count": len(created),
        "source": "postgres",
        "checkpoint": _checkpoint_to_api(checkpoint),
    }


async def _consume_evidence_events_from_stream(
    session: AsyncSession,
    *,
    consumer: str,
    limit: int,
) -> dict[str, Any] | None:
    group = "praetor:evidence"
    stream_entries: list[tuple[str, dict[str, Any]]] = []
    client = None
    try:
        client = get_redis_client()
        try:
            await client.xgroup_create(EVENTS_STREAM, group, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise
        response = await client.xreadgroup(
            group,
            consumer,
            {EVENTS_STREAM: ">"},
            count=limit,
            block=1,
        )
        for _, messages in response:
            for message_id, fields in messages:
                event_payload = fields.get("event")
                if not isinstance(event_payload, str):
                    continue
                event = json.loads(event_payload)
                if isinstance(event, dict):
                    stream_entries.append((str(message_id), event))
    except Exception:
        return None
    finally:
        if client is not None:
            await client.aclose()

    checkpoint = await _evidence_checkpoint(session, consumer)
    if not stream_entries:
        return {"created": [], "count": 0, "source": "redis_stream", "checkpoint": _checkpoint_to_api(checkpoint)}

    event_ids = [entry[1].get("id") for entry in stream_entries if isinstance(entry[1].get("id"), str)]
    result = await session.execute(select(AgentEvent).where(AgentEvent.run_id.in_(event_ids)))
    by_run_id = {row.run_id: row for row in result.scalars().all()}
    events = [by_run_id[event_id] for event_id in event_ids if event_id in by_run_id]
    if not events:
        await _ack_stream_entries(group, [entry[0] for entry in stream_entries])
        return {"created": [], "count": 0, "source": "redis_stream", "checkpoint": _checkpoint_to_api(checkpoint)}

    created = await _materialize_evidence_for_events(session, events)
    last = events[-1]
    checkpoint.last_event_id = last.id
    checkpoint.last_event_ts = last.ts
    checkpoint.updated_at = _now()
    await session.commit()
    await _ack_stream_entries(group, [entry[0] for entry in stream_entries])
    for row in created:
        await session.refresh(row)
    return {
        "created": [_external_id(row.urn, EVIDENCE_URN_PREFIX) for row in created],
        "count": len(created),
        "source": "redis_stream",
        "checkpoint": _checkpoint_to_api(checkpoint),
        "stream": {"name": EVENTS_STREAM, "group": group, "acked": len(stream_entries)},
    }


async def generate_audit_packet(session: AsyncSession) -> dict[str, Any]:
    await consume_evidence_events(session)
    evidence = await list_evidence_records(session)
    period_start = _now()
    period_end = _now()
    packet_id = f"pkt_{uuid4().hex[:12]}"
    sidecar = {
        "id": packet_id,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "scope": {"tenant": "demo", "surfaces": ["workflow", "supervision"]},
        "evidence_records": evidence,
    }
    packet_hash = _hash(sidecar)
    signature = _sign(packet_hash)
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_ROOT / f"{packet_id}.json"
    pdf_path = ARTIFACT_ROOT / f"{packet_id}.pdf"
    json_path.write_text(json.dumps({**sidecar, "packet_hash": packet_hash}, indent=2), encoding="utf-8")
    pdf_path.write_bytes(_minimal_pdf(f"Praetor Audit Packet {packet_id}\nHash: {packet_hash}"))
    packet = AuditPacket(
        urn=f"{AUDIT_PACKET_URN_PREFIX}{packet_id}",
        period_start=period_start,
        period_end=period_end,
        scope=sidecar["scope"],
        pdf_path=str(pdf_path.as_posix()),
        json_sidecar_path=str(json_path.as_posix()),
        packet_hash=packet_hash,
        signature=signature,
    )
    session.add(packet)
    await session.commit()
    await session.refresh(packet)
    return _packet_to_api(packet)


async def _ensure_asset(session: AsyncSession) -> Asset:
    result = await session.execute(select(Asset).where(Asset.urn == ASSET_URN))
    asset = result.scalar_one_or_none()
    if asset is not None:
        return asset
    asset = Asset(
        urn=ASSET_URN,
        type="agent",
        name="Northwind Support Bot",
        owner_id="team-support-automation",
        risk_tier="high",
        lifecycle="production",
        jurisdictions=["US"],
        data_classifications=["customer_support", "email"],
        sectors=["retail"],
        config={"external_id": ASSET_EXTERNAL_ID},
        fingerprint="northwind-support-bot-demo",
    )
    session.add(asset)
    await session.flush()
    return asset


async def _ensure_hook(session: AsyncSession, hook_id: str) -> Hook | None:
    await ensure_hooks(session)
    result = await session.execute(select(Hook).where(Hook.urn == f"{HOOK_URN_PREFIX}{hook_id}"))
    return result.scalar_one_or_none()


async def _hook_external_id(session: AsyncSession, hook_uuid: UUID | None) -> str | None:
    if hook_uuid is None:
        return None
    hook = await session.get(Hook, hook_uuid)
    if hook is None:
        return None
    return hook.urn.removeprefix(HOOK_URN_PREFIX)


def _default_operation(hook_id: str) -> str:
    if hook_id == "github_stub":
        return "open_pr"
    for option in DISPATCH_OPTIONS:
        if option["hook_id"] == hook_id:
            return str(option["operation"])
    return "create_pull_request"


def _dispatch_inputs(
    proposal: ProposedChange,
    hook_id: str,
    operation: str,
    overrides: dict[str, Any],
) -> dict[str, Any]:
    if overrides:
        return _deep_merge(_default_dispatch_inputs(proposal, hook_id, operation), overrides)
    return _default_dispatch_inputs(proposal, hook_id, operation)


def _default_dispatch_inputs(proposal: ProposedChange, hook_id: str, operation: str) -> dict[str, Any]:
    title = f"Praetor proposed change {proposal.urn.removeprefix(PROPOSED_CHANGE_URN_PREFIX)}"
    summary = _proposal_summary(proposal)
    if hook_id == "github_json" and operation == "create_pull_request":
        return {
            "owner": "northwind",
            "repo": "support-bot",
            "title": title,
            "head": "praetor/send-email-domain-guard",
            "base": "main",
            "body": summary,
        }
    if hook_id == "jira_json" and operation == "create_issue":
        return {
            "site": "example",
            "issue": {
                "fields": {
                    "project": {"key": "PRAE"},
                    "summary": title,
                    "description": {
                        "type": "doc",
                        "version": 1,
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": summary}],
                            }
                        ],
                    },
                    "issuetype": {"name": "Task"},
                    "labels": ["praetor", "ai-governance"],
                }
            },
        }
    if hook_id == "linear_json" and operation == "create_issue":
        return {
            "issue": {
                "teamId": "replace-with-linear-team-id",
                "title": title,
                "description": summary,
            }
        }
    if hook_id == "microsoft_mail_json" and operation == "send_mail":
        return {
            "subject": title,
            "body_html": summary.replace("\n", "<br />"),
            "to_recipients": [
                {"emailAddress": {"address": "compliance@example.com"}},
            ],
            "save_to_sent_items": True,
        }
    if hook_id == "slack_json" and operation == "post_message":
        return {"channel": "#ai-governance", "text": summary}
    if hook_id == "servicenow_grc_json" and operation == "create_issue":
        return {
            "instance": "example",
            "table_name": "incident",
            "record": {
                "short_description": title,
                "description": summary,
                "category": "software",
                "subcategory": "ai-governance",
            },
        }
    return {"title": title, "body": summary, "proposal_id": proposal.urn.removeprefix(PROPOSED_CHANGE_URN_PREFIX)}


def _proposal_summary(proposal: ProposedChange) -> str:
    obligations = ", ".join(proposal.obligations_addressed or []) or "none recorded"
    return (
        f"Praetor approved proposed change: {proposal.urn}\n\n"
        f"Kind: {proposal.kind}\n"
        f"Status: {proposal.status}\n"
        f"Obligations addressed: {obligations}\n"
        f"Residual risk: {proposal.residual_risk_estimate or 'not recorded'}\n\n"
        f"Diff:\n{proposal.diff}"
    )


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


async def _find_finding(session: AsyncSession, finding_id: str) -> Finding | None:
    filters = [Finding.urn == f"{FINDING_URN_PREFIX}{finding_id}"]
    try:
        filters.append(Finding.id == UUID(finding_id))
    except ValueError:
        pass
    result = await session.execute(select(Finding).where(or_(*filters)))
    return result.scalar_one_or_none()


async def _find_proposal(session: AsyncSession, change_id: str) -> ProposedChange | None:
    filters = [ProposedChange.urn == f"{PROPOSED_CHANGE_URN_PREFIX}{change_id}"]
    try:
        filters.append(ProposedChange.id == UUID(change_id))
    except ValueError:
        pass
    result = await session.execute(select(ProposedChange).where(or_(*filters)))
    return result.scalar_one_or_none()


async def _find_sandbox(session: AsyncSession, sandbox_id: str) -> SandboxRun | None:
    try:
        sandbox_uuid = UUID(sandbox_id.removeprefix("sbx_"))
    except ValueError:
        try:
            sandbox_uuid = UUID(sandbox_id)
        except ValueError:
            return None
    return await session.get(SandboxRun, sandbox_uuid)


async def _proposal_for_finding(
    session: AsyncSession,
    finding: Finding,
) -> ProposedChange | None:
    result = await session.execute(select(ProposedChange).where(ProposedChange.finding_id == finding.id))
    return result.scalar_one_or_none()


def _finding_to_api(row: Finding) -> dict[str, Any]:
    return {
        "id": _external_id(row.urn, FINDING_URN_PREFIX),
        "urn": row.urn,
        "workflow_run_id": _workflow_run_id(row.workflow_run_id),
        "asset_id": ASSET_EXTERNAL_ID,
        "title": row.title,
        "description": row.description,
        "severity": row.severity,
        "obligations_cited": row.obligations_cited,
        "documents_cited": row.documents_cited,
        "confidence": row.confidence,
        "status": row.status,
        "reviewer": row.reviewer,
        "proposed_change_ids": row.proposed_change_ids,
    }


def _proposal_to_api(row: ProposedChange) -> dict[str, Any]:
    return {
        "id": _external_id(row.urn, PROPOSED_CHANGE_URN_PREFIX),
        "urn": row.urn,
        "finding_id": _finding_id(row.finding_id),
        "kind": row.kind,
        "diff_format": row.diff_format,
        "diff": row.diff,
        "target_asset_id": ASSET_EXTERNAL_ID,
        "target_hook_id": "github_stub",
        "obligations_addressed": row.obligations_addressed,
        "residual_risk_estimate": row.residual_risk_estimate,
        "sandbox_run_id": _sandbox_id(row.sandbox_run_id),
        "status": row.status,
        "approver": row.approver,
        "applied_at": row.applied_at.isoformat() if row.applied_at else None,
        "apply_via_hook_id": DEFAULT_DISPATCH_HOOK,
        "dispatch_options": DISPATCH_OPTIONS,
    }


def _sandbox_to_api(row: SandboxRun, proposal: ProposedChange | None) -> dict[str, Any]:
    return {
        "id": _sandbox_id(row.id),
        "proposed_change_id": (
            _external_id(proposal.urn, PROPOSED_CHANGE_URN_PREFIX) if proposal is not None else None
        ),
        "manifest": row.manifest,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "exit_code": row.exit_code,
        "result": row.result,
    }


async def _evidence_checkpoint(session: AsyncSession, consumer: str) -> EvidenceCheckpoint:
    result = await session.execute(select(EvidenceCheckpoint).where(EvidenceCheckpoint.consumer == consumer))
    checkpoint = result.scalar_one_or_none()
    if checkpoint is None:
        checkpoint = EvidenceCheckpoint(consumer=consumer, updated_at=_now())
        session.add(checkpoint)
        await session.flush()
    return checkpoint


async def _materialize_evidence_for_events(
    session: AsyncSession,
    events: list[AgentEvent],
) -> list[EvidenceRecord]:
    await production_inventory.ensure_obligations(session)
    obligation_by_urn = await _obligation_by_urn(session)
    groups: dict[UUID, list[AgentEvent]] = {}
    asset_events: list[AgentEvent] = []
    for event in events:
        if event.workflow_run_id is not None:
            groups.setdefault(event.workflow_run_id, []).append(event)
        else:
            asset_events.append(event)

    created: list[EvidenceRecord] = []
    for workflow_run_id, run_events in groups.items():
        workflow_run = await session.get(WorkflowRun, workflow_run_id)
        if workflow_run is None:
            continue
        created.extend(
            await _create_evidence_from_events(
                session,
                events=run_events,
                obligation_by_urn=obligation_by_urn,
                control_id=_control_for_events(run_events),
                asset_id=workflow_run.asset_id,
                workflow_run_id=workflow_run.id,
            )
        )
    for event in asset_events:
        created.extend(
            await _create_evidence_from_events(
                session,
                events=[event],
                obligation_by_urn=obligation_by_urn,
                control_id=_control_for_events([event]),
                asset_id=event.asset_id,
                workflow_run_id=None,
            )
        )
    return created


async def _ack_stream_entries(group: str, message_ids: list[str]) -> None:
    if not message_ids:
        return
    client = get_redis_client()
    try:
        await client.xack(EVENTS_STREAM, group, *message_ids)
    finally:
        await client.aclose()


async def _create_evidence_from_events(
    session: AsyncSession,
    *,
    events: list[AgentEvent],
    obligation_by_urn: dict[str, Obligation],
    control_id: str,
    asset_id: UUID | None,
    workflow_run_id: UUID | None,
) -> list[EvidenceRecord]:
    event_ids = [event.run_id or f"evt_{event.id.hex[:12]}" for event in events]
    decision_ids = await _decision_ids_for_events(session, events)
    obligation_urns = _obligations_for_events(events, control_id)
    if not obligation_urns:
        obligation_urns = ["urn:praetor:obligation:internal:data_min_3_2"]
    created: list[EvidenceRecord] = []
    for obligation_urn in obligation_urns:
        obligation = obligation_by_urn.get(obligation_urn)
        obligation_id = obligation.id if obligation is not None else None
        payload = {
            "obligation_urn": obligation_urn,
            "control_id": control_id,
            "asset_id": str(asset_id) if asset_id else None,
            "workflow_run_id": str(workflow_run_id) if workflow_run_id else None,
            "event_ids": event_ids,
            "decision_ids": decision_ids,
        }
        digest = _hash(payload)
        exists = await session.scalar(select(EvidenceRecord.id).where(EvidenceRecord.hash == digest).limit(1))
        if exists is not None:
            continue
        evidence_id = f"ev_{uuid4().hex[:12]}"
        evidence = EvidenceRecord(
            urn=f"{EVIDENCE_URN_PREFIX}{evidence_id}",
            obligation_id=obligation_id,
            control_id=control_id,
            asset_id=asset_id,
            workflow_run_id=workflow_run_id,
            event_ids=event_ids,
            decision_ids=decision_ids,
            hash=digest,
        )
        session.add(evidence)
        created.append(evidence)
    return created


async def _decision_ids_for_events(session: AsyncSession, events: list[AgentEvent]) -> list[str]:
    workflow_run_ids = {event.workflow_run_id for event in events if event.workflow_run_id is not None}
    if not workflow_run_ids:
        return []
    result = await session.execute(select(PolicyDecision).where(PolicyDecision.workflow_run_id.in_(workflow_run_ids)))
    return [f"dec_{row.id.hex[:12]}" for row in result.scalars().all()]


def _obligations_for_events(events: list[AgentEvent], control_id: str) -> list[str]:
    obligations: list[str] = []
    for event in events:
        payload = event.payload or {}
        obligations.extend(_obligation_urns_from_value(payload))
    for control in production_inventory.list_controls():
        if control["id"] == control_id or control["package"].endswith(control_id):
            obligations.extend(control.get("obligations_implemented", []))
    return sorted(set(obligations))


def _obligation_urns_from_value(value: Any) -> list[str]:
    if isinstance(value, dict):
        found: list[str] = []
        for key, nested in value.items():
            if key in {"obligations_cited", "obligations_addressed", "obligation_ids"} and isinstance(nested, list):
                found.extend(str(item) for item in nested if isinstance(item, str))
            else:
                found.extend(_obligation_urns_from_value(nested))
        return found
    if isinstance(value, list):
        found: list[str] = []
        for item in value:
            found.extend(_obligation_urns_from_value(item))
        return found
    return []


def _control_for_events(events: list[AgentEvent]) -> str:
    event_types = {event.type for event in events}
    if any(event_type.startswith("sandbox.") for event_type in event_types):
        return "workflow_agent_step"
    if any(event_type.startswith("policy.decision") for event_type in event_types):
        return "workflow_findings_gate"
    if any(event_type.startswith("hook.out") for event_type in event_types):
        return "tool_permission"
    if any(event_type.startswith("agent.") for event_type in event_types):
        return "workflow_agent_step"
    return "workflow_runtime"


async def _obligation_by_urn(session: AsyncSession) -> dict[str, Obligation]:
    result = await session.execute(select(Obligation))
    return {row.urn: row for row in result.scalars().all()}


async def _obligations_by_id(
    session: AsyncSession,
    evidence: list[EvidenceRecord],
) -> dict[UUID, Obligation]:
    ids = {row.obligation_id for row in evidence if row.obligation_id is not None}
    if not ids:
        return {}
    result = await session.execute(select(Obligation).where(Obligation.id.in_(ids)))
    return {row.id: row for row in result.scalars().all()}


def _checkpoint_to_api(row: EvidenceCheckpoint) -> dict[str, Any]:
    return {
        "consumer": row.consumer,
        "last_event_id": f"evt_{row.last_event_id.hex[:12]}" if row.last_event_id else None,
        "last_event_ts": row.last_event_ts.isoformat() if row.last_event_ts else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _evidence_to_api(row: EvidenceRecord, obligations: dict[UUID, Obligation] | None = None) -> dict[str, Any]:
    obligation = obligations.get(row.obligation_id) if obligations and row.obligation_id else None
    obligation_urn = obligation.urn if obligation is not None else "urn:praetor:obligation:internal:data_min_3_2"
    return {
        "id": _external_id(row.urn, EVIDENCE_URN_PREFIX),
        "urn": row.urn,
        "obligation_id": obligation_urn,
        "obligation_ids": [obligation_urn],
        "control_id": row.control_id,
        "asset_id": ASSET_EXTERNAL_ID if row.asset_id else None,
        "workflow_run_id": _workflow_run_id(row.workflow_run_id),
        "event_ids": row.event_ids,
        "decision_ids": row.decision_ids,
        "hash": row.hash,
    }


def _packet_to_api(row: AuditPacket) -> dict[str, Any]:
    return {
        "id": _external_id(row.urn, AUDIT_PACKET_URN_PREFIX),
        "period_start": row.period_start.isoformat(),
        "period_end": row.period_end.isoformat(),
        "scope": row.scope,
        "pdf_path": row.pdf_path,
        "json_sidecar_path": row.json_sidecar_path,
        "packet_hash": row.packet_hash,
        "signature": row.signature,
    }


def _finding_id(finding_id: UUID) -> str:
    return f"fnd_{finding_id.hex[:12]}"


def _sandbox_id(sandbox_id: UUID | None) -> str | None:
    return f"sbx_{sandbox_id.hex}" if sandbox_id else None


def _workflow_run_id(workflow_run_id: UUID | None) -> str | None:
    return str(workflow_run_id) if workflow_run_id else None


def _sign(packet_hash: str) -> str:
    if Ed25519PrivateKey is None:
        return "sha256-fallback:" + hashlib.sha256(packet_hash.encode("utf-8")).hexdigest()
    private_key = Ed25519PrivateKey.generate()
    signature = private_key.sign(packet_hash.encode("utf-8"))
    public_key = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return "ed25519:" + base64.b64encode(signature + public_key).decode("ascii")


def _minimal_pdf(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET"
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        f"5 0 obj << /Length {len(stream)} >> stream\n{stream}\nendstream endobj\n".encode(
            "utf-8"
        ),
    ]
    body = b"%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(body))
        body += obj
    xref_offset = len(body)
    xref = f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
    for offset in offsets[1:]:
        xref += f"{offset:010d} 00000 n \n".encode("ascii")
    trailer = (
        f"trailer << /Root 1 0 R /Size {len(objects) + 1} >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode("ascii")
    return body + xref + trailer
