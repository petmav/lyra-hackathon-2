from __future__ import annotations

import json
import asyncio
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from praetor_api.models.asset import Asset
from praetor_api.models.finding import Finding
from praetor_api.models.proposed_change import ProposedChange
from praetor_api.models.step_run import StepRun
from praetor_api.models.workflow import Workflow
from praetor_api.models.workflow_run import WorkflowRun
from praetor_api.services.demo_workflows import CODE_COMPLIANCE_SCAN
from praetor_api.services.event_stream import append_persisted_event
from praetor_api.services.model_providers import ModelProviderError, complete, provider_configured
from praetor_api.settings import get_settings

ASSET_EXTERNAL_ID = "asset_northwind_support_bot"
ASSET_URN = "urn:praetor:asset:demo:northwind-support-bot"
WORKFLOW_URN = CODE_COMPLIANCE_SCAN["urn"]
WORKFLOW_RUN_URN_PREFIX = "urn:praetor:workflow-run:"
FINDING_URN_PREFIX = "urn:praetor:finding:"
PROPOSED_CHANGE_URN_PREFIX = "urn:praetor:proposed_change:"


WORKFLOW_TEMPLATES: dict[str, dict[str, Any]] = {
    "code_compliance_scan": {
        **CODE_COMPLIANCE_SCAN,
        "steps": [
            {"id": "pull", "type": "hook.in", "with": {"repo_url": "{{ inputs.repo_url }}"}},
            {"id": "scan", "type": "agent", "depends_on": ["pull"], "with": {"files": "{{ steps.pull.outputs.files }}"}},
            {"id": "emit", "type": "finding.emit", "depends_on": ["scan"], "with": {"findings": "{{ steps.scan.outputs.findings }}"}},
        ],
    },
    "code_compliance_scan_full": {
        "id": "code_compliance_scan_full",
        "urn": "urn:praetor:workflow:demo:code-compliance-scan-full",
        "name": "code_compliance_scan_full",
        "description": "Pull code, retrieve controls, scan, propose a fix, gate it, and open a PR.",
        "trigger": "manual",
        "required_hooks": ["github_stub"],
        "required_corpora": ["iso_42001", "internal_data_min"],
        "steps": [
            {"id": "pull", "type": "hook.in", "with": {"repo_url": "{{ inputs.repo_url }}"}},
            {"id": "retrieve_controls", "type": "corpus.query", "depends_on": ["pull"], "with": {"query": "recipient domain validation for email tools", "corpora": ["iso_42001", "internal_data_min"]}},
            {"id": "scan", "type": "agent", "depends_on": ["retrieve_controls"], "with": {"files": "{{ steps.pull.outputs.files }}"}},
            {"id": "emit", "type": "finding.emit", "depends_on": ["scan"], "with": {"findings": "{{ steps.scan.outputs.findings }}"}},
            {"id": "propose", "type": "change.propose", "depends_on": ["emit"], "with": {"target": "tools.py"}},
            {"id": "policy_gate", "type": "gate.policy", "depends_on": ["propose"], "with": {"severity": "high"}},
            {"id": "human_gate", "type": "gate.human", "depends_on": ["policy_gate"], "with": {"role_required": "grc_reviewer"}},
            {"id": "open_pr", "type": "hook.out", "depends_on": ["human_gate"], "with": {"hook_id": "github_stub", "operation": "open_pr"}},
        ],
    },
    "vendor_risk_review": {
        "id": "vendor_risk_review",
        "urn": "urn:praetor:workflow:demo:vendor-risk-review",
        "name": "vendor_risk_review",
        "description": "Retrieve vendor risk policy and emit any review findings.",
        "trigger": "manual",
        "required_hooks": [],
        "required_corpora": ["internal_data_min"],
        "steps": [
            {"id": "retrieve_policy", "type": "corpus.query", "with": {"query": "vendor AI risk review", "corpora": ["internal_data_min"]}},
            {"id": "emit", "type": "finding.emit", "depends_on": ["retrieve_policy"], "with": {"findings": []}},
        ],
    },
    "policy_gap_analysis": {
        "id": "policy_gap_analysis",
        "urn": "urn:praetor:workflow:demo:policy-gap-analysis",
        "name": "policy_gap_analysis",
        "description": "Retrieve controls and summarize policy gaps.",
        "trigger": "manual",
        "required_hooks": [],
        "required_corpora": ["iso_42001"],
        "steps": [
            {"id": "retrieve_controls", "type": "corpus.query", "with": {"query": "policy gap controls", "corpora": ["iso_42001"]}},
            {"id": "summarize", "type": "transform", "depends_on": ["retrieve_controls"], "with": {"summary": "deterministic policy gap summary"}},
        ],
    },
    "evidence_collection": {
        "id": "evidence_collection",
        "urn": "urn:praetor:workflow:demo:evidence-collection",
        "name": "evidence_collection",
        "description": "Collect evidence candidates from connected source systems.",
        "trigger": "manual",
        "required_hooks": ["localfiles_stub"],
        "required_corpora": [],
        "steps": [
            {"id": "read_files", "type": "hook.in", "with": {"repo_url": "stub://evidence"}},
            {"id": "emit", "type": "finding.emit", "depends_on": ["read_files"], "with": {"findings": []}},
        ],
    },
    "ai_system_intake": {
        "id": "ai_system_intake",
        "urn": "urn:praetor:workflow:demo:ai-system-intake",
        "name": "ai_system_intake",
        "description": "Classify a new AI system and run the first policy gate.",
        "trigger": "manual",
        "required_hooks": [],
        "required_corpora": [],
        "steps": [
            {"id": "classify", "type": "transform", "with": {"asset_type": "ai_system", "risk_tier": "L2"}},
            {"id": "policy_gate", "type": "gate.policy", "depends_on": ["classify"], "with": {"severity": "medium"}},
        ],
    },
}
WORKFLOW_BY_URN = {template["urn"]: template for template in WORKFLOW_TEMPLATES.values()}


def _entity_slug(urn: str, prefix: str) -> str:
    if urn.startswith(prefix):
        return urn.removeprefix(prefix)
    return urn


def _workflow_row_to_api(row: Workflow) -> dict[str, Any]:
    template = WORKFLOW_BY_URN.get(row.urn)
    workflow_id = template["id"] if template else _entity_slug(row.urn, "urn:praetor:workflow:demo:")
    return {
        "id": workflow_id,
        "urn": row.urn,
        "name": row.name,
        "description": template["description"] if template else row.name,
        "definition": row.definition,
        "trigger": row.trigger,
        "trigger_config": row.trigger_config,
        "inputs_schema": row.inputs_schema,
        "outputs_schema": row.outputs_schema,
        "required_hooks": row.required_hooks,
        "required_corpora": row.required_corpora,
        "default_policy_set": row.default_policy_set,
        "template_origin": row.template_origin,
    }


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
        config={"external_id": ASSET_EXTERNAL_ID, "runtime": "demo-production"},
        fingerprint="northwind-support-bot-demo",
    )
    session.add(asset)
    await session.flush()
    return asset


async def ensure_workflow(session: AsyncSession, workflow_id: str = CODE_COMPLIANCE_SCAN["id"]) -> Workflow:
    template = _template_for(workflow_id)
    result = await session.execute(select(Workflow).where(Workflow.urn == template["urn"]))
    workflow = result.scalar_one_or_none()
    if workflow is not None:
        return workflow

    workflow = Workflow(
        urn=template["urn"],
        name=template["name"],
        definition=_definition_summary(template),
        trigger=template["trigger"],
        trigger_config={"mode": "manual"},
        inputs_schema={"type": "object"},
        outputs_schema={"type": "object"},
        required_hooks=template["required_hooks"],
        required_corpora=template["required_corpora"],
        default_policy_set="praetor-demo",
        template_origin="apps/workflow/templates",
    )
    session.add(workflow)
    await session.flush()
    return workflow


async def list_workflows(session: AsyncSession) -> list[dict[str, Any]]:
    workflows = [await ensure_workflow(session, workflow_id) for workflow_id in WORKFLOW_TEMPLATES]
    await session.commit()
    return [_workflow_row_to_api(workflow) for workflow in workflows]


async def get_workflow(session: AsyncSession, workflow_id: str) -> dict[str, Any] | None:
    if workflow_id not in WORKFLOW_TEMPLATES and workflow_id not in WORKFLOW_BY_URN:
        return None
    workflow = await ensure_workflow(session, workflow_id)
    await session.commit()
    return _workflow_row_to_api(workflow)


def _finding_payload(finding_slug: str) -> dict[str, Any]:
    return {
        "id": finding_slug,
        "title": "send_email lacks recipient domain validation",
        "description": "The Northwind support-bot can send email to arbitrary recipient domains.",
        "severity": "high",
        "confidence": 0.92,
        "obligations_cited": [
            "urn:praetor:obligation:demo:iso-42001-8-3",
            "urn:praetor:obligation:demo:internal-data-min",
        ],
        "documents_cited": [],
        "status": "open",
    }


async def run_code_compliance_scan(
    session: AsyncSession,
    inputs: dict[str, Any],
    *,
    model_provider: str = "openai",
    model: str = "gpt-4.1-mini",
) -> dict[str, Any]:
    return await run_workflow(
        session,
        CODE_COMPLIANCE_SCAN["id"],
        inputs,
        model_provider=model_provider,
        model=model,
    )


async def run_workflow(
    session: AsyncSession,
    workflow_id: str,
    inputs: dict[str, Any],
    *,
    model_provider: str = "openai",
    model: str = "gpt-4.1-mini",
) -> dict[str, Any]:
    run = await enqueue_workflow_run(
        session,
        workflow_id,
        inputs,
        model_provider=model_provider,
        model=model,
        initial_status="running",
    )
    processed = await process_workflow_run(session, run["id"])
    if processed is None:
        raise RuntimeError("workflow run was not persisted")
    return processed


async def enqueue_workflow_run(
    session: AsyncSession,
    workflow_id: str,
    inputs: dict[str, Any],
    *,
    model_provider: str = "openai",
    model: str = "gpt-4.1-mini",
    initial_status: str = "queued",
) -> dict[str, Any]:
    template = _template_for(workflow_id)
    asset = await _ensure_asset(session)
    workflow = await ensure_workflow(session, template["id"])
    run_slug = f"wfr_{uuid4().hex[:12]}"

    workflow_run = WorkflowRun(
        urn=f"{WORKFLOW_RUN_URN_PREFIX}{run_slug}",
        workflow_id=workflow.id,
        asset_id=asset.id,
        triggered_by="api",
        status=initial_status,
        inputs=inputs,
        outputs={
            "workflow_id": template["id"],
            "findings": [],
            "proposed_changes": [],
            "model_provider": model_provider,
            "model": model,
            "step_order": [step["id"] for step in template["steps"]],
            "execution_mode": "queued" if initial_status == "queued" else "sync",
        },
        evidence_record_ids=[],
    )
    session.add(workflow_run)
    await session.flush()

    step_rows = [
        StepRun(
            workflow_run_id=workflow_run.id,
            step_id=step["id"],
            step_type=step["type"],
            status="pending",
            emitted_finding_ids=[],
            emitted_proposal_ids=[],
            inputs_redacted=_redacted_inputs(step, inputs, model_provider, model),
            outputs_redacted={},
        )
        for step in template["steps"]
    ]
    session.add_all(step_rows)
    await session.commit()
    return await workflow_run_by_id(session, run_slug) or {"id": run_slug, "status": initial_status}


async def drain_queued_workflows(session: AsyncSession, *, limit: int = 1) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 25))
    result = await session.execute(
        select(WorkflowRun)
        .where(WorkflowRun.status == "queued")
        .order_by(WorkflowRun.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    queued = list(result.scalars().all())
    processed: list[dict[str, Any]] = []
    for row in queued:
        run_id = _entity_slug(row.urn, WORKFLOW_RUN_URN_PREFIX)
        run = await process_workflow_run(session, run_id)
        if run is not None:
            processed.append(run)
    return processed


async def process_workflow_run(session: AsyncSession, run_id: str) -> dict[str, Any] | None:
    workflow_run = await _find_workflow_run(session, run_id)
    if workflow_run is None:
        return None
    if workflow_run.status not in {"queued", "running"}:
        return await workflow_run_by_id(session, run_id)

    outputs = workflow_run.outputs or {}
    template = _template_for(outputs.get("workflow_id", CODE_COMPLIANCE_SCAN["id"]))
    asset = await session.get(Asset, workflow_run.asset_id)
    if asset is None:
        raise RuntimeError("workflow run asset is missing")

    step_result = await session.execute(
        select(StepRun).where(StepRun.workflow_run_id == workflow_run.id)
    )
    step_rows = list(step_result.scalars().all())
    if not step_rows:
        for step in template["steps"]:
            session.add(
                StepRun(
                    workflow_run_id=workflow_run.id,
                    step_id=step["id"],
                    step_type=step["type"],
                    status="pending",
                    emitted_finding_ids=[],
                    emitted_proposal_ids=[],
                    inputs_redacted=_redacted_inputs(
                        step,
                        workflow_run.inputs,
                        outputs.get("model_provider", get_settings().default_model_provider),
                        outputs.get("model", get_settings().default_model_name),
                    ),
                    outputs_redacted={},
                )
            )
        await session.flush()
        step_result = await session.execute(
            select(StepRun).where(StepRun.workflow_run_id == workflow_run.id)
        )
        step_rows = list(step_result.scalars().all())

    workflow_run.status = "running"
    await session.commit()

    row_by_step = {row.step_id: row for row in step_rows}
    context: dict[str, Any] = {"inputs": workflow_run.inputs, "steps": {}}
    findings: list[dict[str, Any]] = list(outputs.get("findings", []))
    proposals: list[dict[str, Any]] = list(outputs.get("proposed_changes", []))
    model_provider = outputs.get("model_provider", get_settings().default_model_provider)
    model = outputs.get("model", get_settings().default_model_name)
    final_status = "succeeded"

    for row in step_rows:
        if row.status == "succeeded":
            context["steps"][row.step_id] = {
                "outputs": row.outputs_redacted,
                "status": row.status,
            }

    while True:
        pending = [
            step
            for step in template["steps"]
            if row_by_step[step["id"]].status == "pending"
            and all(context["steps"].get(dep, {}).get("status") == "succeeded" for dep in step.get("depends_on", []))
        ]
        if not pending:
            break

        for step in pending:
            row_by_step[step["id"]].status = "running"
        await session.commit()

        results = await asyncio.gather(
            *[
                _execute_with_retries(
                    step,
                    context,
                    model_provider=model_provider,
                    model=model,
                )
                for step in pending
            ]
        )

        for step, (step_outputs, step_status) in zip(pending, results, strict=True):
            row = row_by_step[step["id"]]
            emitted = step_outputs.get("emitted", [])
            proposed = step_outputs.get("proposed_changes", [])
            row.status = step_status
            row.outputs_redacted = step_outputs
            row.emitted_finding_ids = [
                item["id"] for item in emitted if isinstance(item, dict) and "id" in item
            ]
            row.emitted_proposal_ids = [
                item["id"] for item in proposed if isinstance(item, dict) and "id" in item
            ]
            context["steps"][step["id"]] = {"outputs": step_outputs, "status": step_status}
            if step["type"] == "finding.emit" and isinstance(emitted, list):
                findings.extend(item for item in emitted if isinstance(item, dict))
            if step["type"] == "change.propose" and isinstance(proposed, list):
                proposals.extend(item for item in proposed if isinstance(item, dict))
            if step_status != "succeeded":
                final_status = step_status

        await session.commit()
        if final_status != "succeeded":
            break

    if final_status == "succeeded":
        incomplete = [row for row in row_by_step.values() if row.status in {"pending", "running"}]
        final_status = "running" if incomplete else "succeeded"
    if final_status in {"failed", "cancelled"}:
        for row in row_by_step.values():
            if row.status == "pending":
                row.status = "blocked"

    workflow_run.status = final_status
    workflow_run.outputs = {
        **outputs,
        "findings": findings,
        "proposed_changes": proposals,
        "step_order": [step["id"] for step in template["steps"]],
    }
    await session.flush()
    await _persist_findings_and_proposals(session, workflow_run, asset, findings, proposals)
    await session.commit()
    await session.refresh(workflow_run)

    run = await workflow_run_by_id(session, run_id)
    if run is None:
        raise RuntimeError("workflow run was not persisted")

    await _publish_run_events(session, asset, workflow_run, run, workflow_run.inputs)
    from praetor_api.services import production_reviews

    await production_reviews.sweep_evidence_records(session)
    await session.commit()
    return run


async def _persist_findings_and_proposals(
    session: AsyncSession,
    workflow_run: WorkflowRun,
    asset: Asset,
    findings: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
) -> None:
    existing_finding_rows = await session.execute(
        select(Finding).where(Finding.workflow_run_id == workflow_run.id)
    )
    finding_rows = {
        _entity_slug(row.urn, FINDING_URN_PREFIX): row
        for row in existing_finding_rows.scalars().all()
    }

    for finding in findings:
        finding_id = finding.get("id")
        if not finding_id or finding_id in finding_rows:
            continue
        finding_row = Finding(
            urn=f"{FINDING_URN_PREFIX}{finding_id}",
            workflow_run_id=workflow_run.id,
            asset_id=asset.id,
            title=finding["title"],
            description=finding["description"],
            severity=finding["severity"],
            obligations_cited=finding["obligations_cited"],
            documents_cited=finding["documents_cited"],
            confidence=finding["confidence"],
            status=finding["status"],
            proposed_change_ids=[],
        )
        session.add(finding_row)
        finding_rows[finding_id] = finding_row
    await session.flush()

    existing_proposals = await session.execute(
        select(ProposedChange).where(
            ProposedChange.urn.in_([
                f"{PROPOSED_CHANGE_URN_PREFIX}{proposal['id']}"
                for proposal in proposals
                if isinstance(proposal, dict) and proposal.get("id")
            ])
        )
    )
    existing_proposal_ids = {
        _entity_slug(row.urn, PROPOSED_CHANGE_URN_PREFIX)
        for row in existing_proposals.scalars().all()
    }

    for proposal in proposals:
        proposal_id = proposal.get("id")
        if not proposal_id or proposal_id in existing_proposal_ids:
            continue
        finding_row = finding_rows.get(proposal.get("finding_id"))
        if finding_row is None:
            continue
        session.add(
            ProposedChange(
                urn=f"{PROPOSED_CHANGE_URN_PREFIX}{proposal_id}",
                finding_id=finding_row.id,
                kind=proposal["kind"],
                diff=proposal["diff"],
                diff_format=proposal["diff_format"],
                target_asset_id=asset.id,
                target_hook_id=None,
                obligations_addressed=proposal["obligations_addressed"],
                residual_risk_estimate=proposal["residual_risk_estimate"],
                sandbox_run_id=None,
                status="proposed",
                approver=None,
                applied_at=None,
                apply_via_hook_id=None,
            )
        )
        finding_row.proposed_change_ids = [
            *list(finding_row.proposed_change_ids or []),
            proposal_id,
        ]


async def resume_workflow_run(
    session: AsyncSession,
    run_id: str,
    *,
    approved: bool = True,
    approver: str = "api",
) -> dict[str, Any] | None:
    workflow_run = await _find_workflow_run(session, run_id)
    if workflow_run is None:
        return None
    if workflow_run.status != "awaiting_approval":
        return await workflow_run_by_id(session, run_id)

    outputs = workflow_run.outputs or {}
    workflow_id = outputs.get("workflow_id", CODE_COMPLIANCE_SCAN["id"])
    template = _template_for(workflow_id)
    asset = await session.get(Asset, workflow_run.asset_id)
    if asset is None:
        raise RuntimeError("workflow run asset is missing")

    result = await session.execute(select(StepRun).where(StepRun.workflow_run_id == workflow_run.id))
    existing_steps = list(result.scalars().all())
    step_order = {step_id: index for index, step_id in enumerate(outputs.get("step_order", []))}
    existing_steps.sort(key=lambda row: step_order.get(row.step_id, 999))
    existing_by_id = {row.step_id: row for row in existing_steps}
    awaiting_step = next((row for row in existing_steps if row.status == "awaiting_approval"), None)
    if awaiting_step is None:
        workflow_run.status = "succeeded"
        await session.commit()
        return await workflow_run_by_id(session, run_id)

    awaiting_step.status = "succeeded" if approved else "cancelled"
    awaiting_step.outputs_redacted = {
        **(awaiting_step.outputs_redacted or {}),
        "approved": approved,
        "approver": approver,
    }
    if not approved:
        workflow_run.status = "cancelled"
        await session.commit()
        run = await workflow_run_by_id(session, run_id)
        if run is not None:
            await _publish_resume_events(session, asset, workflow_run, [awaiting_step], run)
            from praetor_api.services import production_reviews

            await production_reviews.sweep_evidence_records(session)
            await session.commit()
        return run

    workflow_run.status = "running"
    for row in existing_steps:
        if row.status == "blocked":
            row.status = "pending"
    await session.commit()
    return await process_workflow_run(session, run_id)

    context: dict[str, Any] = {"inputs": workflow_run.inputs, "steps": {}}
    for row in existing_steps:
        context["steps"][row.step_id] = {"outputs": row.outputs_redacted, "status": row.status}

    template_steps = template["steps"]
    resume_index = next(
        (index for index, step in enumerate(template_steps) if step["id"] == awaiting_step.step_id),
        len(template_steps) - 1,
    )
    new_steps: list[StepRun] = []
    status = "succeeded"
    model_provider = outputs.get("model_provider", get_settings().default_model_provider)
    model = outputs.get("model", get_settings().default_model_name)

    for step in template_steps[resume_index + 1:]:
        if step["id"] in existing_by_id:
            continue
        step_outputs, step_status = await _execute_with_retries(
            step,
            context,
            model_provider=model_provider,
            model=model,
        )
        context["steps"][step["id"]] = {"outputs": step_outputs, "status": step_status}
        emitted = step_outputs.get("emitted", [])
        proposed = step_outputs.get("proposed_changes", [])
        row = StepRun(
            workflow_run_id=workflow_run.id,
            step_id=step["id"],
            step_type=step["type"],
            status=step_status,
            emitted_finding_ids=[item["id"] for item in emitted if isinstance(item, dict) and "id" in item],
            emitted_proposal_ids=[item["id"] for item in proposed if isinstance(item, dict) and "id" in item],
            inputs_redacted=_redacted_inputs(step, workflow_run.inputs, model_provider, model),
            outputs_redacted=step_outputs,
        )
        session.add(row)
        new_steps.append(row)
        if step_status != "succeeded":
            status = step_status
            break

    workflow_run.status = status
    workflow_run.outputs = {
        **outputs,
        "step_order": [
            *outputs.get("step_order", []),
            *[row.step_id for row in new_steps],
        ],
    }
    await session.commit()
    run = await workflow_run_by_id(session, run_id)
    if run is not None:
        await _publish_resume_events(session, asset, workflow_run, [awaiting_step, *new_steps], run)
        from praetor_api.services import production_reviews

        await production_reviews.sweep_evidence_records(session)
        await session.commit()
    return run


async def cancel_workflow_run(session: AsyncSession, run_id: str) -> bool:
    workflow_run = await _find_workflow_run(session, run_id)
    if workflow_run is None:
        return False
    workflow_run.status = "cancelled"
    asset = await session.get(Asset, workflow_run.asset_id)
    await session.commit()
    if asset is not None:
        external_id = _entity_slug(workflow_run.urn, WORKFLOW_RUN_URN_PREFIX)
        await append_persisted_event(
            session,
            asset_record_id=asset.id,
            asset_id=(asset.config or {}).get("external_id", ASSET_EXTERNAL_ID),
            workflow_run_record_id=workflow_run.id,
            workflow_run_id=external_id,
            event_type="workflow.run.finished",
            actor="workflow_runtime",
            payload={"status": "cancelled"},
        )
        await session.commit()
    return True


async def workflow_run_by_id(session: AsyncSession, run_id: str) -> dict[str, Any] | None:
    workflow_run = await _find_workflow_run(session, run_id)
    if workflow_run is None:
        return None

    result = await session.execute(
        select(StepRun).where(StepRun.workflow_run_id == workflow_run.id)
    )
    steps = list(result.scalars().all())
    return _workflow_run_to_api(workflow_run, steps)


async def list_workflow_runs(session: AsyncSession) -> list[dict[str, Any]]:
    result = await session.execute(select(WorkflowRun).order_by(WorkflowRun.created_at.desc()))
    rows = list(result.scalars().all())
    runs: list[dict[str, Any]] = []
    for row in rows:
        step_result = await session.execute(
            select(StepRun).where(StepRun.workflow_run_id == row.id)
        )
        runs.append(_workflow_run_to_api(row, list(step_result.scalars().all())))
    return runs


async def _find_workflow_run(session: AsyncSession, run_id: str) -> WorkflowRun | None:
    filters = [WorkflowRun.urn == f"{WORKFLOW_RUN_URN_PREFIX}{run_id}"]
    try:
        filters.append(WorkflowRun.id == UUID(run_id))
    except ValueError:
        pass

    result = await session.execute(select(WorkflowRun).where(or_(*filters)))
    return result.scalar_one_or_none()


def _workflow_run_to_api(row: WorkflowRun, steps: list[StepRun]) -> dict[str, Any]:
    outputs = row.outputs or {}
    workflow_id = outputs.get("workflow_id", CODE_COMPLIANCE_SCAN["id"])
    template = WORKFLOW_TEMPLATES.get(workflow_id, WORKFLOW_TEMPLATES[CODE_COMPLIANCE_SCAN["id"]])
    depends_by_step = {
        step["id"]: list(step.get("depends_on", []))
        for step in template["steps"]
    }
    step_order = {step_id: index for index, step_id in enumerate(outputs.get("step_order", []))}
    steps = sorted(steps, key=lambda step: step_order.get(step.step_id, 999))
    external_id = _entity_slug(row.urn, WORKFLOW_RUN_URN_PREFIX)
    return {
        "id": external_id,
        "urn": row.urn,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "created_by": row.created_by,
        "version": row.version,
        "workflow_id": workflow_id,
        "asset_id": ASSET_EXTERNAL_ID,
        "status": row.status,
        "triggered_by": row.triggered_by,
        "triggered_at": row.created_at.isoformat(),
        "finished_at": row.updated_at.isoformat() if row.status in {"succeeded", "failed", "cancelled"} else None,
        "inputs": row.inputs,
        "model_provider": outputs.get("model_provider", "openai"),
        "model": outputs.get("model", "gpt-4.1-mini"),
        "outputs": {"findings": outputs.get("findings", [])},
        "evidence_record_ids": row.evidence_record_ids,
        "step_runs": [
            {
                "id": f"stp_{step.id.hex[:12]}",
                "workflow_run_id": external_id,
                "step_id": step.step_id,
                "step_type": step.step_type,
                "status": step.status,
                "inputs_redacted": step.inputs_redacted,
                "outputs_redacted": step.outputs_redacted,
                "emitted_finding_ids": step.emitted_finding_ids,
                "emitted_proposal_ids": step.emitted_proposal_ids,
                "depends_on": depends_by_step.get(step.step_id, []),
            }
            for step in steps
        ],
    }


async def _publish_run_events(
    session: AsyncSession,
    asset: Asset,
    workflow_run: WorkflowRun,
    run: dict[str, Any],
    inputs: dict[str, Any],
) -> None:
    await append_persisted_event(
        session,
        asset_record_id=asset.id,
        asset_id=ASSET_EXTERNAL_ID,
        workflow_run_record_id=workflow_run.id,
        workflow_run_id=run["id"],
        event_type="workflow.run.started",
        actor="workflow_runtime",
        payload={"workflow_id": run["workflow_id"], "inputs": inputs},
    )
    for step in run["step_runs"]:
        await append_persisted_event(
            session,
            asset_record_id=asset.id,
            asset_id=ASSET_EXTERNAL_ID,
            workflow_run_record_id=workflow_run.id,
            workflow_run_id=run["id"],
            workflow_step_id=step["step_id"],
            event_type="workflow.step.finished",
            actor="workflow_runtime",
            payload={
                "step_id": step["step_id"],
                "step_type": step["step_type"],
                "status": step["status"],
                "outputs_redacted": step["outputs_redacted"],
            },
        )
    for finding in run["outputs"].get("findings", []):
        await append_persisted_event(
            session,
            asset_record_id=asset.id,
            asset_id=ASSET_EXTERNAL_ID,
            workflow_run_record_id=workflow_run.id,
            workflow_run_id=run["id"],
            event_type="finding.emitted",
            actor="workflow_runtime",
            payload={"finding": finding},
        )
    await append_persisted_event(
        session,
        asset_record_id=asset.id,
        asset_id=ASSET_EXTERNAL_ID,
        workflow_run_record_id=workflow_run.id,
        workflow_run_id=run["id"],
        event_type="workflow.run.finished",
        actor="workflow_runtime",
        payload={"status": run["status"]},
    )


async def _publish_resume_events(
    session: AsyncSession,
    asset: Asset,
    workflow_run: WorkflowRun,
    steps: list[StepRun],
    run: dict[str, Any],
) -> None:
    external_run_id = run["id"]
    asset_id = (asset.config or {}).get("external_id", ASSET_EXTERNAL_ID)
    for step in steps:
        await append_persisted_event(
            session,
            asset_record_id=asset.id,
            asset_id=asset_id,
            workflow_run_record_id=workflow_run.id,
            workflow_run_id=external_run_id,
            workflow_step_id=step.step_id,
            event_type="workflow.step.finished",
            actor="workflow_runtime",
            payload={
                "step_id": step.step_id,
                "step_type": step.step_type,
                "status": step.status,
                "outputs_redacted": step.outputs_redacted,
                "resumed": True,
            },
        )
    if run["status"] in {"succeeded", "failed", "cancelled"}:
        await append_persisted_event(
            session,
            asset_record_id=asset.id,
            asset_id=asset_id,
            workflow_run_record_id=workflow_run.id,
            workflow_run_id=external_run_id,
            event_type="workflow.run.finished",
            actor="workflow_runtime",
            payload={"status": run["status"], "resumed": True},
        )


def _template_for(workflow_id: str) -> dict[str, Any]:
    if workflow_id in WORKFLOW_TEMPLATES:
        return WORKFLOW_TEMPLATES[workflow_id]
    if workflow_id in WORKFLOW_BY_URN:
        return WORKFLOW_BY_URN[workflow_id]
    raise KeyError(workflow_id)


def _definition_summary(template: dict[str, Any]) -> str:
    return " -> ".join(step["id"] for step in template["steps"])


async def _execute_step(
    step: dict[str, Any],
    context: dict[str, Any],
    *,
    model_provider: str,
    model: str,
) -> tuple[dict[str, Any], str]:
    step_type = step["type"]
    inputs = context["inputs"]
    if step_type == "hook.in":
        repo_url = inputs.get("repo_url") or step.get("with", {}).get("repo_url") or "stub://support-bot"
        return {"repo_url": repo_url, "files": ["tools.py", "README.md"]}, "succeeded"
    if step_type == "corpus.query":
        return {
            "hits": [
                {
                    "corpus_id": corpus_id,
                    "title": f"{corpus_id} control excerpt",
                    "excerpt": "Email tools must validate recipient domains before sending.",
                    "score": 0.91,
                }
                for corpus_id in step.get("with", {}).get("corpora", [])
            ]
        }, "succeeded"
    if step_type == "agent":
        finding_slug = f"fnd_{uuid4().hex[:12]}"
        model_call = await _run_agent_model(
            step,
            context,
            provider=model_provider,
            model=model,
        )
        return {
            "model_provider": model_provider,
            "model": model,
            "model_call": model_call,
            "findings": [_finding_payload(finding_slug)],
        }, "succeeded" if model_call.get("ok", True) else "failed"
    if step_type == "finding.emit":
        upstream = _latest_step_outputs(context, "agent")
        findings = step.get("with", {}).get("findings")
        if not isinstance(findings, list):
            findings = upstream.get("findings", [])
        return {"count": len(findings), "emitted": findings}, "succeeded"
    if step_type == "change.propose":
        emitted = _latest_step_outputs(context, "finding.emit").get("emitted", [])
        finding = emitted[0] if emitted and isinstance(emitted[0], dict) else {}
        title = finding.get("title", "No finding emitted")
        target = step.get("with", {}).get("target", "tools.py")
        proposal_id = f"chg_{uuid4().hex[:12]}"
        proposed_change = {
            "id": proposal_id,
            "finding_id": finding.get("id"),
            "kind": "code",
            "diff_format": "unified",
            "diff": (
                f"--- a/{target}\n"
                f"+++ b/{target}\n"
                "@@\n"
                "+allowed_domains = {'northwind.test', 'customer.example'}\n"
                " def send_email(recipient, subject, body):\n"
                "+    assert recipient.rsplit('@', 1)[-1] in allowed_domains\n"
                "     return smtp.send(recipient, subject, body)\n"
            ),
            "obligations_addressed": finding.get("obligations_cited", []),
            "residual_risk_estimate": "Low after allowlist validation and policy supervision remain active.",
        }
        return {
            "proposal_id": proposal_id,
            "finding_title": title,
            "target": target,
            "proposed_changes": [proposed_change],
        }, "succeeded"
    if step_type == "gate.policy":
        severity = step.get("with", {}).get("severity", "low")
        return {"decision": "allow", "severity": severity, "policy_set": "praetor-demo"}, "succeeded"
    if step_type == "gate.human":
        approved = inputs.get("approved", True)
        if approved is False:
            return {"role_required": step.get("with", {}).get("role_required", "reviewer")}, "awaiting_approval"
        return {"approved": True, "approver": "demo-analyst"}, "succeeded"
    if step_type == "hook.out":
        return {
            "hook_id": step.get("with", {}).get("hook_id", "github_stub"),
            "operation": step.get("with", {}).get("operation", "open_pr"),
            "url": "https://github.example/northwind/support-bot/pull/42",
        }, "succeeded"
    if step_type == "transform":
        return json.loads(json.dumps(step.get("with", {}))), "succeeded"
    return {"unsupported_step_type": step_type}, "failed"


async def _execute_with_retries(
    step: dict[str, Any],
    context: dict[str, Any],
    *,
    model_provider: str,
    model: str,
) -> tuple[dict[str, Any], str]:
    retry = step.get("retry", {})
    max_attempts = int(retry.get("max_attempts", 1)) if isinstance(retry, dict) else 1
    max_attempts = max(1, max_attempts)
    last_outputs: dict[str, Any] = {}
    last_status = "failed"
    for attempt in range(1, max_attempts + 1):
        last_outputs, last_status = await _execute_step(
            step,
            context,
            model_provider=model_provider,
            model=model,
        )
        last_outputs = {
            **last_outputs,
            "attempt": attempt,
            "max_attempts": max_attempts,
        }
        if last_status in {"succeeded", "awaiting_approval"}:
            return last_outputs, last_status
    return last_outputs, last_status


async def _run_agent_model(
    step: dict[str, Any],
    context: dict[str, Any],
    *,
    provider: str,
    model: str,
) -> dict[str, Any]:
    settings = get_settings()
    mode = settings.agent_model_mode
    live_requested = mode == "live" or (mode == "auto" and provider_configured(provider))
    prompt = _agent_prompt(step, context)
    try:
        result = await complete(
            prompt,
            provider=provider,
            model=model,
            system=(
                "You are Praetor's governed compliance workflow agent. "
                "Inspect the supplied run context and return concise findings."
            ),
            dry_run=not live_requested,
        )
    except ModelProviderError as exc:
        if mode == "live":
            return {
                "ok": False,
                "mode": "live",
                "provider": provider,
                "model": model,
                "configured": provider_configured(provider),
                "error": str(exc),
                "text": "",
            }
        fallback = await complete(
            prompt,
            provider=provider,
            model=model,
            dry_run=True,
        )
        return {
            "ok": True,
            "mode": "dry_run_fallback",
            "provider": provider,
            "model": model,
            "configured": False,
            "error": str(exc),
            "text": fallback.get("text", ""),
        }
    return {
        "ok": True,
        "mode": "live" if live_requested else "dry_run",
        "provider": result["provider"],
        "model": result["model"],
        "configured": provider_configured(provider),
        "text": result.get("text", ""),
        "usage": result.get("usage", {}),
    }


def _agent_prompt(step: dict[str, Any], context: dict[str, Any]) -> str:
    inputs = context.get("inputs", {})
    prior_steps = context.get("steps", {})
    return json.dumps(
        {
            "step_id": step.get("id"),
            "step_type": step.get("type"),
            "inputs": inputs,
            "prior_step_outputs": {
                step_id: state.get("outputs", {})
                for step_id, state in prior_steps.items()
            },
            "task": "Identify compliance findings and cite relevant controls.",
        },
        sort_keys=True,
    )


def _latest_step_outputs(context: dict[str, Any], step_type: str) -> dict[str, Any]:
    for step_state in reversed(list(context["steps"].values())):
        outputs = step_state.get("outputs", {})
        if step_type == "agent" and "findings" in outputs:
            return outputs
        if step_type == "finding.emit" and "emitted" in outputs:
            return outputs
    return {}


def _redacted_inputs(
    step: dict[str, Any],
    inputs: dict[str, Any],
    model_provider: str,
    model: str,
) -> dict[str, Any]:
    if step["type"] == "agent":
        return {"model_provider": model_provider, "model": model}
    if step["type"] == "hook.in":
        return {"repo_url": inputs.get("repo_url", step.get("with", {}).get("repo_url", "stub://support-bot"))}
    return json.loads(json.dumps(step.get("with", {})))
