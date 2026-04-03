"""Create ai_settings and user_ai_preferences tables.

Revision ID: r51_ai_settings
Revises: r50_company_classification
"""

import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r51_ai_settings"
down_revision = "r50_company_classification"
branch_labels = None
depends_on = None

_DEFAULT_SECTIONS = '{"orders":true,"collections":true,"legacies":true,"follow_ups":true,"at_risk_accounts":true,"inventory":true,"pattern_alerts":true}'


def upgrade() -> None:
    op.create_table(
        "ai_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, unique=True),

        # Morning briefing
        sa.Column("briefing_narrative_enabled", sa.Boolean, server_default="true"),
        sa.Column("briefing_narrative_tone", sa.String(20), server_default="concise"),
        sa.Column("briefing_narrative_sections", JSONB, server_default=f"'{_DEFAULT_SECTIONS}'"),
        sa.Column("weekly_summary_enabled", sa.Boolean, server_default="false"),
        sa.Column("weekly_summary_day", sa.String(10), server_default="monday"),
        sa.Column("weekly_summary_time", sa.String(5), server_default="07:00"),
        sa.Column("pattern_alerts_enabled", sa.Boolean, server_default="true"),
        sa.Column("pattern_alerts_sensitivity", sa.String(20), server_default="moderate"),
        sa.Column("prep_notes_enabled", sa.Boolean, server_default="true"),
        sa.Column("seasonal_intelligence_enabled", sa.Boolean, server_default="false"),

        # CRM intelligence
        sa.Column("conversational_lookup_enabled", sa.Boolean, server_default="true"),
        sa.Column("natural_language_filters_enabled", sa.Boolean, server_default="true"),
        sa.Column("smart_followup_enabled", sa.Boolean, server_default="true"),
        sa.Column("duplicate_detection_enabled", sa.Boolean, server_default="true"),
        sa.Column("auto_enrichment_enabled", sa.Boolean, server_default="false"),
        sa.Column("upsell_detector_enabled", sa.Boolean, server_default="true"),
        sa.Column("account_rescue_enabled", sa.Boolean, server_default="false"),
        sa.Column("relationship_scoring_enabled", sa.Boolean, server_default="true"),
        sa.Column("payment_prediction_enabled", sa.Boolean, server_default="false"),
        sa.Column("new_customer_intelligence_enabled", sa.Boolean, server_default="true"),

        # Command bar
        sa.Column("command_bar_enabled", sa.Boolean, server_default="true"),
        sa.Column("command_bar_action_tier", sa.String(20), server_default="review"),

        # Voice
        sa.Column("voice_memo_enabled", sa.Boolean, server_default="false"),
        sa.Column("voice_commands_enabled", sa.Boolean, server_default="false"),

        # Per-user
        sa.Column("allow_per_user_settings", sa.Boolean, server_default="false"),

        # Call intelligence
        sa.Column("after_call_intelligence_enabled", sa.Boolean, server_default="true"),
        sa.Column("commitment_detection_enabled", sa.Boolean, server_default="true"),
        sa.Column("tone_analysis_enabled", sa.Boolean, server_default="false"),

        # Cost/usage
        sa.Column("founding_licensee", sa.Boolean, server_default="false"),
        sa.Column("google_places_calls_month", sa.Integer, server_default="0"),
        sa.Column("transcription_minutes_month", sa.Integer, server_default="0"),
        sa.Column("claude_api_calls_month", sa.Integer, server_default="0"),
        sa.Column("usage_reset_date", sa.Date, nullable=True),

        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "user_ai_preferences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("briefing_narrative_enabled", sa.Boolean, nullable=True),
        sa.Column("briefing_narrative_tone", sa.String(20), nullable=True),
        sa.Column("command_bar_action_tier", sa.String(20), nullable=True),
        sa.Column("voice_memo_enabled", sa.Boolean, nullable=True),
        sa.Column("voice_commands_enabled", sa.Boolean, nullable=True),
        sa.Column("pattern_alerts_enabled", sa.Boolean, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_user_ai_prefs_unique", "user_ai_preferences", ["tenant_id", "user_id"], unique=True)

    # Seed for existing tenants (Sunnycrest as founding licensee)
    conn = op.get_bind()
    tenants = conn.execute(sa.text("SELECT id, slug FROM companies WHERE is_active = true")).fetchall()
    for tid, slug in tenants:
        is_founding = (slug == "sunnycrest")
        conn.execute(sa.text(
            "INSERT INTO ai_settings (id, tenant_id, founding_licensee) VALUES (:id, :tid, :fl)"
        ), {"id": str(uuid.uuid4()), "tid": tid, "fl": is_founding})


def downgrade() -> None:
    op.drop_table("user_ai_preferences")
    op.drop_table("ai_settings")
