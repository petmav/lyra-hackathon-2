from __future__ import annotations

import asyncio
from pathlib import Path
import sys

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


async def main() -> None:
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
    print("Praetor production database rows cleared without demo reseed.")


if __name__ == "__main__":
    asyncio.run(main())
