"""Initial Praetor schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

try:
    from pgvector.sqlalchemy import Vector
except ModuleNotFoundError:
    from sqlalchemy.types import UserDefinedType

    class Vector(UserDefinedType):
        cache_ok = True

        def __init__(self, dim: int) -> None:
            self.dim = dim

        def get_col_spec(self, **kw) -> str:
            return f"VECTOR({self.dim})"

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def entity_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("urn", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    ]


def create_entity_indexes(table: str) -> None:
    op.create_index(op.f(f"ix_{table}_urn"), table, ["urn"], unique=True)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        DO $$
        BEGIN
            CREATE EXTENSION IF NOT EXISTS timescaledb;
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'timescaledb extension unavailable; agent_event will remain a regular table';
        END $$;
        """
    )

    op.create_table(
        "asset",
        *entity_columns(),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("owner_id", sa.String(255), nullable=False),
        sa.Column("risk_tier", sa.String(8), nullable=False),
        sa.Column("lifecycle", sa.String(32), nullable=False),
        sa.Column("parent_asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset.id")),
        sa.Column("jurisdictions", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("data_classifications", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("sectors", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
    )
    create_entity_indexes("asset")
    op.create_index("ix_asset_type", "asset", ["type"])

    op.create_table(
        "agent_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset.id"), nullable=False),
        sa.Column("run_id", sa.String(255)),
        sa.Column("parent_event_id", postgresql.UUID(as_uuid=True)),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("workflow_step_id", sa.String(255)),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("payload_redacted", postgresql.JSONB(), nullable=False),
        sa.Column("hash_chain_prev", sa.String(64), nullable=False),
        sa.Column("hash_chain_self", sa.String(64), nullable=False),
    )
    op.create_index("ix_agent_event_asset_id_ts", "agent_event", ["asset_id", "ts"])
    op.create_index("ix_agent_event_type", "agent_event", ["type"])
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_proc
                WHERE proname = 'create_hypertable'
            ) THEN
                PERFORM create_hypertable('agent_event', 'ts', if_not_exists => TRUE);
            END IF;
        END $$;
        """
    )

    op.create_table(
        "obligation",
        *entity_columns(),
        sa.Column("framework", sa.String(128), nullable=False),
        sa.Column("citation", sa.String(255), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("applicability", postgresql.JSONB(), nullable=False),
        sa.Column("severity_default", sa.String(32), nullable=False),
    )
    create_entity_indexes("obligation")
    op.create_index("ix_obligation_framework", "obligation", ["framework"])

    op.create_table(
        "workflow",
        *entity_columns(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("trigger", sa.String(32), nullable=False),
        sa.Column("trigger_config", postgresql.JSONB(), nullable=False),
        sa.Column("inputs_schema", postgresql.JSONB(), nullable=False),
        sa.Column("outputs_schema", postgresql.JSONB(), nullable=False),
        sa.Column("required_hooks", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("required_corpora", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("default_policy_set", sa.String(255), nullable=False),
        sa.Column("template_origin", sa.String(512)),
    )
    create_entity_indexes("workflow")

    op.create_table(
        "workflow_run",
        *entity_columns(),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow.id"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset.id"), nullable=False),
        sa.Column("triggered_by", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("inputs", postgresql.JSONB(), nullable=False),
        sa.Column("outputs", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_record_ids", postgresql.ARRAY(sa.String()), nullable=False),
    )
    create_entity_indexes("workflow_run")
    op.create_index("ix_workflow_run_status", "workflow_run", ["status"])

    op.create_table(
        "step_run",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_run.id"), nullable=False),
        sa.Column("step_id", sa.String(255), nullable=False),
        sa.Column("step_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("sandbox_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("hook_call_id", postgresql.UUID(as_uuid=True)),
        sa.Column("policy_decision_id", postgresql.UUID(as_uuid=True)),
        sa.Column("approval_id", postgresql.UUID(as_uuid=True)),
        sa.Column("emitted_finding_ids", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("emitted_proposal_ids", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("inputs_redacted", postgresql.JSONB(), nullable=False),
        sa.Column("outputs_redacted", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_step_run_status", "step_run", ["status"])

    op.create_table(
        "hook",
        *entity_columns(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("endpoint", sa.String(512), nullable=False),
        sa.Column("auth_ref", sa.String(255)),
        sa.Column("scopes", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("effect_radius", sa.String(64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
    )
    create_entity_indexes("hook")

    op.create_table(
        "hook_call",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("hook_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hook.id"), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("step_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("inputs_redacted", postgresql.JSONB(), nullable=False),
        sa.Column("outputs_redacted", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("errors", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("policy_decision_id", postgresql.UUID(as_uuid=True)),
    )
    op.create_index("ix_hook_call_status", "hook_call", ["status"])

    op.create_table(
        "corpus",
        *entity_columns(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("parent_corpus_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("corpus.id")),
        sa.Column("document_count", sa.Integer(), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True)),
    )
    create_entity_indexes("corpus")

    op.create_table(
        "document",
        *entity_columns(),
        sa.Column("corpus_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("corpus.id"), nullable=False),
        sa.Column("source_uri", sa.String(1024), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("citation", sa.String(255)),
        sa.Column("framework", sa.String(128)),
        sa.Column("jurisdiction", sa.String(64)),
        sa.Column("sector", sa.String(128)),
        sa.Column("text_path", sa.String(1024), nullable=False),
        sa.Column("parsed_structure", postgresql.JSONB(), nullable=False),
    )
    create_entity_indexes("document")

    op.create_table(
        "document_chunk",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document.id"), nullable=False),
        sa.Column("ord", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536)),
        sa.Column("keyword_tokens", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("citation_path", sa.String(512), nullable=False),
    )
    op.create_index(
        "ix_document_chunk_embedding",
        "document_chunk",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_with={"lists": 100},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "finding",
        *entity_columns(),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_run.id")),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset.id"), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("obligations_cited", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("documents_cited", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reviewer", sa.String(255)),
        sa.Column("proposed_change_ids", postgresql.ARRAY(sa.String()), nullable=False),
    )
    create_entity_indexes("finding")
    op.create_index("ix_finding_severity", "finding", ["severity"])
    op.create_index("ix_finding_status", "finding", ["status"])

    op.create_table(
        "proposed_change",
        *entity_columns(),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finding.id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("diff", sa.Text(), nullable=False),
        sa.Column("diff_format", sa.String(32), nullable=False),
        sa.Column("target_asset_id", postgresql.UUID(as_uuid=True)),
        sa.Column("target_hook_id", postgresql.UUID(as_uuid=True)),
        sa.Column("obligations_addressed", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("residual_risk_estimate", sa.Text()),
        sa.Column("sandbox_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("approver", sa.String(255)),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column("apply_via_hook_id", postgresql.UUID(as_uuid=True)),
    )
    create_entity_indexes("proposed_change")
    op.create_index("ix_proposed_change_status", "proposed_change", ["status"])

    op.create_table(
        "sandbox_run",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("step_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_run.id")),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("exit_code", sa.Integer()),
        sa.Column("result", postgresql.JSONB(), nullable=False),
    )

    op.create_table(
        "evidence_record",
        *entity_columns(),
        sa.Column("obligation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("obligation.id")),
        sa.Column("control_id", sa.String(255)),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset.id")),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_run.id")),
        sa.Column("event_ids", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("decision_ids", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
    )
    create_entity_indexes("evidence_record")

    op.create_table(
        "audit_packet",
        *entity_columns(),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scope", postgresql.JSONB(), nullable=False),
        sa.Column("pdf_path", sa.String(1024), nullable=False),
        sa.Column("json_sidecar_path", sa.String(1024), nullable=False),
        sa.Column("packet_hash", sa.String(64), nullable=False),
        sa.Column("signature", sa.String(512), nullable=False),
    )
    create_entity_indexes("audit_packet")

    op.create_table(
        "approval",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("subject_kind", sa.String(64), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by", sa.String(255), nullable=False),
        sa.Column("role_required", sa.String(255), nullable=False),
        sa.Column("decided_by", sa.String(255)),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("outcome", sa.String(32)),
    )

    op.create_table(
        "policy_decision",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("engine", sa.String(32), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True)),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("step_run_id", postgresql.UUID(as_uuid=True)),
    )
    op.create_index("ix_policy_decision_outcome", "policy_decision", ["outcome"])


def downgrade() -> None:
    tables: Sequence[str] = (
        "policy_decision",
        "approval",
        "audit_packet",
        "evidence_record",
        "sandbox_run",
        "proposed_change",
        "finding",
        "document_chunk",
        "document",
        "corpus",
        "hook_call",
        "hook",
        "step_run",
        "workflow_run",
        "workflow",
        "obligation",
        "agent_event",
        "asset",
    )
    for table in tables:
        op.drop_table(table)
