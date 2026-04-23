"""Phase A Session 4 — Focus persistence: focus_sessions + focus_layout_defaults.

Two tables. `focus_sessions` stores per-user active + recently-closed
Focus sessions with their layout_state (widget positions + sizes +
anchors). `focus_layout_defaults` stores per-tenant admin-configured
baselines for a given focus_type. Frontend asks the service for "layout
for focus X" and the 3-tier resolver (see focus_session_service) picks:

    active user session → recent closed user session (within 24h)
     → tenant default → null

Soft-delete convention matches other per-user state tables (spaces,
saved views): `is_active=False` instead of row delete. `closed_at`
timestamp captures when the session ended, for the recent-closed
window on resume.

No soft delete on focus_layout_defaults — admin-managed, rows are
authoritative baselines.

Revision ID: r48_focus_sessions_and_layout_defaults
Revises: r47_users_template_defaults_retrofit
Create Date: 2026-04-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "r48_focus_sessions_and_layout_defaults"
down_revision = "r47_users_template_defaults_retrofit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # focus_sessions — per-user, per-focus session state with layout JSONB.
    op.create_table(
        "focus_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("focus_type", sa.String(64), nullable=False),
        sa.Column(
            "layout_state",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "closed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_interacted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # Hot path: resolve active session for (user, focus_type).
    # Partial index keeps the index small — only active rows matter for
    # the "resume where you left off" lookup.
    op.create_index(
        "ix_focus_sessions_user_active",
        "focus_sessions",
        ["user_id", "focus_type"],
        unique=False,
        postgresql_where=sa.text("is_active = true"),
    )
    # Recent-closed fallback: list closed sessions by user, most recent
    # first. Partial on closed_at IS NOT NULL so only closed rows index.
    op.create_index(
        "ix_focus_sessions_user_closed",
        "focus_sessions",
        ["user_id", "focus_type", sa.text("closed_at DESC")],
        unique=False,
        postgresql_where=sa.text("closed_at IS NOT NULL"),
    )
    # Company scoping for tenant-isolation audits (rare path but cheap).
    op.create_index(
        "ix_focus_sessions_company",
        "focus_sessions",
        ["company_id"],
        unique=False,
    )

    # focus_layout_defaults — per-tenant admin baseline per focus_type.
    op.create_table(
        "focus_layout_defaults",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("focus_type", sa.String(64), nullable=False),
        sa.Column(
            "layout_state",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # One default per (tenant, focus_type). UNIQUE doubles as lookup index.
    op.create_index(
        "uq_focus_layout_defaults_tenant_type",
        "focus_layout_defaults",
        ["company_id", "focus_type"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_focus_layout_defaults_tenant_type",
        table_name="focus_layout_defaults",
    )
    op.drop_table("focus_layout_defaults")
    op.drop_index("ix_focus_sessions_company", table_name="focus_sessions")
    op.drop_index("ix_focus_sessions_user_closed", table_name="focus_sessions")
    op.drop_index("ix_focus_sessions_user_active", table_name="focus_sessions")
    op.drop_table("focus_sessions")
