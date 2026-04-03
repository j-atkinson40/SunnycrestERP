"""Create manufacturer_company_profiles and crm_settings tables.

Revision ID: r48_manufacturer_profiles_crm_settings
Revises: r47_activity_log
"""

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r48_manufacturer_profiles_crm_settings"
down_revision = "r47_activity_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── manufacturer_company_profiles ────────────────────────────────────
    op.create_table(
        "manufacturer_company_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("master_company_id", sa.String(36), sa.ForeignKey("company_entities.id", ondelete="CASCADE"), nullable=False, unique=True),

        sa.Column("avg_days_between_orders", sa.Numeric(8, 2), nullable=True),
        sa.Column("last_order_date", sa.Date, nullable=True),
        sa.Column("order_count_12mo", sa.Integer, server_default="0"),
        sa.Column("order_count_all_time", sa.Integer, server_default="0"),
        sa.Column("total_revenue_12mo", sa.Numeric(12, 2), server_default="0"),
        sa.Column("total_revenue_all_time", sa.Numeric(12, 2), server_default="0"),
        sa.Column("most_ordered_vault_id", sa.String(36), nullable=True),
        sa.Column("most_ordered_vault_name", sa.String(200), nullable=True),

        sa.Column("avg_days_to_pay_recent", sa.Numeric(8, 2), nullable=True),
        sa.Column("avg_days_to_pay_prior", sa.Numeric(8, 2), nullable=True),

        sa.Column("health_score", sa.String(20), server_default="unknown"),
        sa.Column("health_reasons", JSONB, server_default="'[]'"),
        sa.Column("health_last_calculated", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_briefed_at", sa.DateTime(timezone=True), nullable=True),

        sa.Column("preferred_contact_method", sa.String(20), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),

        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_mfr_profiles_tenant", "manufacturer_company_profiles", ["company_id"])
    op.create_index("idx_mfr_profiles_health", "manufacturer_company_profiles", ["company_id", "health_score"])
    op.create_index("idx_mfr_profiles_last_order", "manufacturer_company_profiles", ["company_id", "last_order_date"])

    # ── crm_settings ────────────────────────────────────────────────────
    op.create_table(
        "crm_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, unique=True),

        sa.Column("pipeline_enabled", sa.Boolean, server_default="false"),
        sa.Column("health_scoring_enabled", sa.Boolean, server_default="true"),
        sa.Column("activity_log_enabled", sa.Boolean, server_default="true"),

        sa.Column("at_risk_days_multiplier", sa.Numeric(4, 2), server_default="2.0"),
        sa.Column("at_risk_payment_trend_days", sa.Integer, server_default="7"),
        sa.Column("at_risk_payment_threshold_days", sa.Integer, server_default="30"),

        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── Seed data ───────────────────────────────────────────────────────
    conn = op.get_bind()

    # Seed crm_settings for all tenants
    tenants = conn.execute(sa.text("SELECT id FROM companies WHERE is_active = true")).fetchall()
    for (tid,) in tenants:
        existing = conn.execute(sa.text("SELECT id FROM crm_settings WHERE company_id = :tid"), {"tid": tid}).fetchone()
        if not existing:
            conn.execute(sa.text(
                "INSERT INTO crm_settings (id, company_id) VALUES (:id, :tid)"
            ), {"id": str(uuid.uuid4()), "tid": tid})

    # Seed manufacturer profiles for every customer company_entity
    entities = conn.execute(sa.text(
        "SELECT id, company_id FROM company_entities WHERE is_customer = true"
    )).fetchall()
    for (eid, cid) in entities:
        existing = conn.execute(sa.text(
            "SELECT id FROM manufacturer_company_profiles WHERE master_company_id = :eid"
        ), {"eid": eid}).fetchone()
        if not existing:
            conn.execute(sa.text(
                "INSERT INTO manufacturer_company_profiles (id, company_id, master_company_id) VALUES (:id, :cid, :eid)"
            ), {"id": str(uuid.uuid4()), "cid": cid, "eid": eid})


def downgrade() -> None:
    op.drop_table("crm_settings")
    op.drop_table("manufacturer_company_profiles")
