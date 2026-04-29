import os

import pytest

if os.getenv("PRAETOR_RUN_DB_TESTS") != "1":
    pytest.skip("set PRAETOR_RUN_DB_TESTS=1 to run Postgres integration tests", allow_module_level=True)

from praetor_api.db import AsyncSessionLocal
from praetor_api.models.asset import Asset
from praetor_api.models.sandbox_run import SandboxRun
from praetor_api.services import production_corpus, production_hooks, production_reviews
from praetor_api.services import production_workflows
from sqlalchemy import select


@pytest.mark.asyncio
async def test_production_workflow_events_and_review_lifecycle() -> None:
    async with AsyncSessionLocal() as session:
        run = await production_workflows.run_code_compliance_scan(
            session,
            {"repo_url": "stub://support-bot"},
            model_provider="openai",
            model="gpt-4.1-mini",
        )

    async with AsyncSessionLocal() as session:
        read = await production_workflows.workflow_run_by_id(session, run["id"])

    assert read is not None
    assert read["status"] == "succeeded"
    assert read["step_runs"][-1]["step_id"] == "emit"
    scan_step = next(step for step in read["step_runs"] if step["step_id"] == "scan")
    assert scan_step["sandbox_run_id"].startswith("sbx_")
    assert scan_step["outputs_redacted"]["workflow_agent_asset_urn"].startswith(
        "urn:praetor:asset:workflow_agent:"
    )

    async with AsyncSessionLocal() as session:
        sandbox_count = await session.scalar(select(SandboxRun).where(SandboxRun.step_run_id.is_not(None)).limit(1))
        workflow_agent = await session.scalar(select(Asset).where(Asset.type == "workflow_agent").limit(1))

    assert sandbox_count is not None
    assert workflow_agent is not None

    async with AsyncSessionLocal() as session:
        workflows = await production_workflows.list_workflows(session)

    workflow_ids = {workflow["id"] for workflow in workflows}
    assert workflow_ids >= {"code_compliance_scan", "policy_gap_analysis", "ai_system_intake"}

    async with AsyncSessionLocal() as session:
        policy_run = await production_workflows.run_workflow(
            session,
            "policy_gap_analysis",
            {},
            model_provider="openai",
            model="gpt-5.4-mini",
        )

    assert policy_run["workflow_id"] == "policy_gap_analysis"
    assert policy_run["status"] == "succeeded"
    assert policy_run["step_runs"][-1]["step_id"] == "summarize"

    async with AsyncSessionLocal() as session:
        findings = await production_reviews.list_findings(session)

    change_id = next(row["proposed_change_ids"][0] for row in findings if row["proposed_change_ids"])

    async with AsyncSessionLocal() as session:
        sandbox = await production_reviews.create_sandbox_run(session, change_id)

    assert sandbox is not None
    assert sandbox["exit_code"] == 0


@pytest.mark.asyncio
async def test_queued_workflow_drain_executes_persisted_run() -> None:
    async with AsyncSessionLocal() as session:
        queued = await production_workflows.enqueue_workflow_run(
            session,
            "code_compliance_scan",
            {"repo_url": "stub://support-bot"},
            model_provider="openai",
            model="gpt-5.4-mini",
        )

    assert queued["status"] == "queued"
    assert {step["status"] for step in queued["step_runs"]} == {"pending"}

    async with AsyncSessionLocal() as session:
        processed = await production_workflows.drain_queued_workflows(session, limit=1)

    assert len(processed) == 1
    assert processed[0]["id"] == queued["id"]
    assert processed[0]["status"] == "succeeded"
    assert processed[0]["outputs"]["findings"][0]["severity"] == "high"
    scan_step = next(step for step in processed[0]["step_runs"] if step["step_id"] == "scan")
    assert scan_step["sandbox_run_id"].startswith("sbx_")
    assert scan_step["outputs_redacted"]["sandbox"]["mode"] in {"replay", "docker", "docker-socket"}


@pytest.mark.asyncio
async def test_production_hooks_and_corpus_persist() -> None:
    async with AsyncSessionLocal() as session:
        hooks = await production_hooks.list_hooks(session)

    assert {hook["id"] for hook in hooks} >= {"github_stub", "slack_stub", "localfiles_stub"}

    async with AsyncSessionLocal() as session:
        call = await production_hooks.call_hook(
            session,
            "github_stub",
            "open_pr",
            {"branch": "praetor/integration"},
            True,
        )

    assert call["status"] == "succeeded"

    async with AsyncSessionLocal() as session:
        doc = await production_corpus.ingest_document(
            session,
            "internal_data_min",
            "Integration policy",
            "seed://integration-policy",
            "Email tools must validate recipient domains.",
        )

    assert doc["chunk_count"] == 1

    async with AsyncSessionLocal() as session:
        hits = await production_corpus.search(session, "internal_data_min", "recipient domains", 3)

    assert hits[0]["score"] > 0
