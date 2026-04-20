"""Phase 6 — Briefings table (morning + evening narrative briefings).

A new `briefings` table lives alongside the legacy `employee_briefings`
per the approved coexist-with-legacy strategy. Different semantics:
  - employee_briefings uses (company_id, user_id, briefing_date) daily unique
    — one briefing per user per day.
  - briefings uses (company_id, user_id, briefing_type, DATE(generated_at))
    daily-plus-type unique — morning AND evening can coexist same day.

Revision ID: r35_briefings_table
Revises: r34_tasks_and_triage
Create Date: 2026-04-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "r35_briefings_table"
down_revision = "r34_tasks_and_triage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "briefings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("briefing_type", sa.String(16), nullable=False),  # "morning" | "evening"
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "delivery_channels",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        # Narrative content
        sa.Column("narrative_text", sa.Text(), nullable=False),
        sa.Column(
            "structured_sections",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # Generation context
        sa.Column("active_space_id", sa.String(36), nullable=True),
        sa.Column("active_space_name", sa.String(128), nullable=True),
        sa.Column("role_slug", sa.String(64), nullable=True),
        sa.Column(
            "generation_context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        # Metrics
        sa.Column("generation_duration_ms", sa.Integer(), nullable=True),
        sa.Column("intelligence_cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # Hot-path index: user + type + generated_at DESC for "latest morning"
    # and briefing list pagination.
    op.create_index(
        "ix_briefings_user_type_generated",
        "briefings",
        ["user_id", "briefing_type", sa.text("generated_at DESC")],
    )
    # Tenant-level history listing.
    op.create_index(
        "ix_briefings_company_generated",
        "briefings",
        ["company_id", sa.text("generated_at DESC")],
    )
    # Daily-plus-type idempotency guard. The sweep job checks `DATE(generated_at)`
    # for today against this unique; prevents double-generation inside the
    # 15-minute window.
    op.create_index(
        "uq_briefings_user_type_date",
        "briefings",
        [
            "user_id",
            "briefing_type",
            sa.text("DATE(generated_at AT TIME ZONE 'UTC')"),
        ],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_briefings_user_type_date", table_name="briefings")
    op.drop_index("ix_briefings_company_generated", table_name="briefings")
    op.drop_index("ix_briefings_user_type_generated", table_name="briefings")
    op.drop_table("briefings")
