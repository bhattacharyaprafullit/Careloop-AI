"""Initial schema and insert-only protections for CareLoop AI (M4).

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-28 00:00:00
"""
import logging
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

logger = logging.getLogger(__name__)

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

JsonType = sa.JSON().with_variant(JSONB(), "postgresql")
INSERT_ONLY_TABLES = ("case_events", "closures", "llm_outputs")


def upgrade() -> None:
    op.create_table(
        "sandboxes",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("clock_offset_hours", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sandboxes_token_hash", "sandboxes", ["token_hash"], unique=True)

    op.create_table(
        "patients",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("sandbox_id", sa.String(64), nullable=False),
        sa.Column("alias", sa.String(32), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("insurance", sa.String(32), nullable=False),
        sa.Column("distance_miles", sa.Float(), nullable=False),
        sa.Column("portal_active", sa.Boolean(), nullable=False),
        sa.Column("prior_noshow_count", sa.Integer(), nullable=False),
        sa.Column("prior_noshow_ratio", sa.Float(), nullable=False),
        sa.Column("days_since_last_encounter", sa.Integer(), nullable=False),
    )
    op.create_index("ix_patients_sandbox_id", "patients", ["sandbox_id"])

    op.create_table(
        "cases",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("sandbox_id", sa.String(64), nullable=False),
        sa.Column("patient_id", sa.String(64), nullable=False),
        sa.Column("screening_type", sa.String(32), nullable=False),
        sa.Column("severity_grade", sa.Integer(), nullable=False),
        sa.Column("urgency_tier", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("state_entered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("owner_role", sa.String(24), nullable=True),
        sa.Column("owner_id", sa.String(64), nullable=True),
        sa.Column("escalated", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("finding_to_order_days", sa.Float(), nullable=False),
        sa.Column("scheduling_lead_time", sa.Float(), nullable=False),
        sa.Column("contact_attempts", sa.Integer(), nullable=False),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("patient_token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_cases_sandbox_state", "cases", ["sandbox_id", "state"])
    op.create_index("ix_cases_sandbox_escalated", "cases", ["sandbox_id", "escalated"])
    op.create_index("ix_cases_patient_id", "cases", ["patient_id"])
    op.create_index("ix_cases_patient_token_hash", "cases", ["patient_token_hash"])

    op.create_table(
        "case_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("sandbox_id", sa.String(64), nullable=False),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(48), nullable=False),
        sa.Column("from_state", sa.String(40), nullable=True),
        sa.Column("to_state", sa.String(40), nullable=True),
        sa.Column("actor_role", sa.String(24), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("payload", JsonType, nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_case_events_case_at", "case_events", ["case_id", "at"])
    op.create_index("ix_case_events_sandbox_id", "case_events", ["sandbox_id"])

    op.create_table(
        "evidence",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("sandbox_id", sa.String(64), nullable=False),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("type", sa.String(48), nullable=False),
        sa.Column("ref", sa.String(128), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_evidence_case_id", "evidence", ["case_id"])

    op.create_table(
        "risk_scores",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("sandbox_id", sa.String(64), nullable=False),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("stage", sa.String(40), nullable=False),
        sa.Column("p_dropoff", sa.Float(), nullable=False),
        sa.Column("median_days", sa.Float(), nullable=False),
        sa.Column("p_open_30", sa.Float(), nullable=False),
        sa.Column("p_open_60", sa.Float(), nullable=False),
        sa.Column("p_open_90", sa.Float(), nullable=False),
        sa.Column("shap", JsonType, nullable=False),
        sa.Column("survival_curve", JsonType, nullable=False),
        sa.Column("model_version", sa.String(32), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_risk_scores_case_id", "risk_scores", ["case_id"])

    op.create_table(
        "referrals",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("sandbox_id", sa.String(64), nullable=False),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("from_org", sa.String(128), nullable=False),
        sa.Column("to_org", sa.String(128), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("reason_code", sa.String(48), nullable=True),
        sa.Column("sbar", JsonType, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_referrals_case_id", "referrals", ["case_id"])

    op.create_table(
        "consults",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("sandbox_id", sa.String(64), nullable=False),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("thread", JsonType, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_consults_case_id", "consults", ["case_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("sandbox_id", sa.String(64), nullable=False),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(24), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("teachback_label", sa.String(24), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_messages_case_id", "messages", ["case_id"])

    op.create_table(
        "pending_approvals",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("sandbox_id", sa.String(64), nullable=False),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("action_type", sa.String(48), nullable=False),
        sa.Column("payload", JsonType, nullable=False),
        sa.Column("reasons", JsonType, nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("decision", sa.String(24), nullable=True),
        sa.Column("decided_by", sa.String(64), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pending_approvals_case_id", "pending_approvals", ["case_id"])

    op.create_table(
        "closures",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("sandbox_id", sa.String(64), nullable=False),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("evidence_type", sa.String(48), nullable=True),
        sa.Column("override_by", sa.String(64), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_closures_case_id", "closures", ["case_id"])

    op.create_table(
        "delay_reasons",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("sandbox_id", sa.String(64), nullable=False),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("code", sa.String(48), nullable=False),
        sa.Column("proposed_by", sa.String(16), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_delay_reasons_case_id", "delay_reasons", ["case_id"])

    op.create_table(
        "llm_outputs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("sandbox_id", sa.String(64), nullable=False),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("output", JsonType, nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("faithful_ok", sa.Boolean(), nullable=False),
        sa.Column("ads", sa.Float(), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_llm_outputs_input_hash", "llm_outputs", ["input_hash"])
    op.create_index("ix_llm_outputs_case_id", "llm_outputs", ["case_id"])

    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        for tbl in INSERT_ONLY_TABLES:
            op.execute(
                f"CREATE TRIGGER IF NOT EXISTS trg_{tbl}_no_update "
                f"BEFORE UPDATE ON {tbl} BEGIN "
                f"SELECT RAISE(ABORT, '{tbl} is insert-only: UPDATE forbidden'); END;"
            )
            op.execute(
                f"CREATE TRIGGER IF NOT EXISTS trg_{tbl}_no_delete "
                f"BEFORE DELETE ON {tbl} "
                f"WHEN EXISTS (SELECT 1 FROM sandboxes s WHERE s.id = OLD.sandbox_id) "
                f"BEGIN SELECT RAISE(ABORT, '{tbl} is insert-only: DELETE forbidden'); END;"
            )
    elif dialect == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION forbid_insert_only_mutation()
            RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'UPDATE' THEN
                    RAISE EXCEPTION '% is insert-only: UPDATE forbidden', TG_TABLE_NAME;
                ELSIF TG_OP = 'DELETE' THEN
                    IF EXISTS (SELECT 1 FROM sandboxes s WHERE s.id = OLD.sandbox_id) THEN
                        RAISE EXCEPTION '% is insert-only: DELETE forbidden', TG_TABLE_NAME;
                    END IF;
                    RETURN OLD;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        for tbl in INSERT_ONLY_TABLES:
            op.execute(
                f"CREATE TRIGGER trg_{tbl}_immutable "
                f"BEFORE UPDATE OR DELETE ON {tbl} "
                f"FOR EACH ROW EXECUTE FUNCTION forbid_insert_only_mutation();"
            )
        op.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'careloop_app') THEN
                    REVOKE UPDATE, DELETE ON case_events, closures, llm_outputs FROM careloop_app;
                END IF;
            END $$;
            """
        )


def downgrade() -> None:
    for tbl in (
        "llm_outputs",
        "delay_reasons",
        "closures",
        "pending_approvals",
        "messages",
        "consults",
        "referrals",
        "risk_scores",
        "evidence",
        "case_events",
        "cases",
        "patients",
        "sandboxes",
    ):
        op.drop_table(tbl)
