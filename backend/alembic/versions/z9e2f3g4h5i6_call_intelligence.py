"""Call Intelligence tables: ringcentral_call_log, ringcentral_call_extractions

Revision ID: z9e2f3g4h5i6
Revises: z9d3e4f5g6h7
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "z9e2f3g4h5i6"
down_revision = "z9d3e4f5g6h7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ringcentral_call_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("rc_call_id", sa.String(200), nullable=True),
        sa.Column("rc_session_id", sa.String(200), nullable=True),
        sa.Column("rc_recording_id", sa.String(200), nullable=True),
        sa.Column("direction", sa.String(20), nullable=False, server_default="inbound"),
        sa.Column("call_status", sa.String(30), nullable=False, server_default="completed"),
        sa.Column("caller_number", sa.String(50), nullable=True),
        sa.Column("caller_name", sa.String(300), nullable=True),
        sa.Column("callee_number", sa.String(50), nullable=True),
        sa.Column("callee_name", sa.String(300), nullable=True),
        sa.Column("extension_id", sa.String(100), nullable=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("company_entity_id", sa.String(36), sa.ForeignKey("company_entities.id"), nullable=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("transcription", sa.Text, nullable=True),
        sa.Column("transcription_source", sa.String(30), nullable=True),
        sa.Column("order_created", sa.Boolean, server_default="false"),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("sales_orders.id"), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_rc_call_log_tenant_started", "ringcentral_call_log", ["tenant_id", "started_at"])
    op.create_index("ix_rc_call_log_rc_call_id", "ringcentral_call_log", ["rc_call_id"])

    op.create_table(
        "ringcentral_call_extractions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("call_log_id", sa.String(36), sa.ForeignKey("ringcentral_call_log.id"), nullable=False),
        sa.Column("master_company_id", sa.String(36), sa.ForeignKey("company_entities.id"), nullable=True),
        # Extracted fields
        sa.Column("funeral_home_name", sa.String(500), nullable=True),
        sa.Column("deceased_name", sa.String(500), nullable=True),
        sa.Column("vault_type", sa.String(200), nullable=True),
        sa.Column("vault_size", sa.String(100), nullable=True),
        sa.Column("cemetery_name", sa.String(500), nullable=True),
        sa.Column("burial_date", sa.Date, nullable=True),
        sa.Column("burial_time", sa.Time, nullable=True),
        sa.Column("grave_location", sa.String(200), nullable=True),
        sa.Column("special_requests", sa.Text, nullable=True),
        # Confidence + missing
        sa.Column("confidence_json", JSONB, nullable=True),
        sa.Column("missing_fields", JSONB, nullable=True),
        # Call metadata
        sa.Column("call_summary", sa.Text, nullable=True),
        sa.Column("call_type", sa.String(50), nullable=True),
        sa.Column("urgency", sa.String(20), nullable=True),
        sa.Column("suggested_callback", sa.Boolean, server_default="false"),
        # Status
        sa.Column("draft_order_created", sa.Boolean, server_default="false"),
        sa.Column("draft_order_id", sa.String(36), sa.ForeignKey("sales_orders.id"), nullable=True),
        sa.Column("reviewed_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_rc_extraction_call_log", "ringcentral_call_extractions", ["call_log_id"])


def downgrade() -> None:
    op.drop_table("ringcentral_call_extractions")
    op.drop_table("ringcentral_call_log")
