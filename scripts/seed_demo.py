from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import sys

os.environ.setdefault("PRAETOR_SEED_DEMO_DATA", "1")

from sqlalchemy import delete

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from praetor_api.db import AsyncSessionLocal  # noqa: E402
from praetor_api.models.agent_event import AgentEvent  # noqa: E402
from praetor_api.models.asset import Asset  # noqa: E402
from praetor_api.models.audit_packet import AuditPacket  # noqa: E402
from praetor_api.models.corpus import Corpus  # noqa: E402
from praetor_api.models.document import Document  # noqa: E402
from praetor_api.models.document_chunk import DocumentChunk  # noqa: E402
from praetor_api.models.evidence_record import EvidenceRecord  # noqa: E402
from praetor_api.models.finding import Finding  # noqa: E402
from praetor_api.models.hook import Hook  # noqa: E402
from praetor_api.models.hook_call import HookCall  # noqa: E402
from praetor_api.models.proposed_change import ProposedChange  # noqa: E402
from praetor_api.models.sandbox_run import SandboxRun  # noqa: E402
from praetor_api.models.step_run import StepRun  # noqa: E402
from praetor_api.models.workflow import Workflow  # noqa: E402
from praetor_api.models.workflow_run import WorkflowRun  # noqa: E402
from praetor_api.services import production_corpus, production_hooks, production_reviews  # noqa: E402
from praetor_api.services import production_workflows  # noqa: E402


async def reset() -> None:
    async with AsyncSessionLocal() as session:
        for model in (
            AuditPacket,
            EvidenceRecord,
            SandboxRun,
            ProposedChange,
            Finding,
            DocumentChunk,
            Document,
            Corpus,
            HookCall,
            Hook,
            AgentEvent,
            StepRun,
            WorkflowRun,
            Workflow,
            Asset,
        ):
            await session.execute(delete(model))
        await session.commit()


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        await production_hooks.list_hooks(session)

    async with AsyncSessionLocal() as session:
        await production_corpus.ingest_document(
            session,
            "internal_data_min",
            "Internal data minimisation policy",
            "seed://internal-data-min",
            "Email tools must validate recipient domains.\n\nAgents should minimize customer data exposure.",
        )

    async with AsyncSessionLocal() as session:
        await production_workflows.run_code_compliance_scan(
            session,
            {"repo_url": "stub://support-bot"},
            model_provider="openai",
            model="gpt-4.1-mini",
        )

    async with AsyncSessionLocal() as session:
        findings = await production_reviews.list_findings(session)
    change_id = next(row["proposed_change_ids"][0] for row in findings if row["proposed_change_ids"])

    async with AsyncSessionLocal() as session:
        await production_reviews.create_sandbox_run(session, change_id)
    async with AsyncSessionLocal() as session:
        await production_reviews.list_evidence_records(session)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed deterministic Praetor production demo data.")
    parser.add_argument("--reset", action="store_true", help="delete existing demo rows before seeding")
    args = parser.parse_args()

    if args.reset:
        await reset()
    await seed()
    print("Praetor production demo data seeded.")


if __name__ == "__main__":
    asyncio.run(main())
