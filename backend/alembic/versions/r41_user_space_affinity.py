"""Workflow Arc Phase 8e.1 — user_space_affinity table.

Per-user, per-space topical affinity signal for command bar ranking.
Rows are created/updated by POST /api/v1/spaces/affinity/visit and
read by command_bar/retrieval.py to boost relevant results.

Composite PK on (user_id, space_id, target_type, target_id) —
upsert semantics via INSERT ... ON CONFLICT DO UPDATE.

Partial index on (user_id, space_id) WHERE visit_count > 0 — the
read-path prefetch in command_bar/retrieval.py runs exactly this
query shape once per command_bar query.

Future-proofing index on (user_id, last_visited_at DESC) WHERE
visit_count > 0 — anticipated post-arc consumers (briefings
recommendations, dashboard personalization) need "top N by recency"
per-user queries.

CHECK constraint on target_type enumerates the four values
(nav_item, saved_view, entity_record, triage_queue). Documented in
SPACES_ARCHITECTURE.md §9.

Revision ID: r41_user_space_affinity
Down Revision: r40_aftercare_email_template
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "r41_user_space_affinity"
down_revision = "r40_aftercare_email_template"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_space_affinity",
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=False),
        # Matches SpaceConfig.space_id ("sp_<12 hex>") — spaces live
        # in JSONB, so there's no FK target. Documented in
        # SPACES_ARCHITECTURE.md.
        sa.Column("space_id", sa.String(36), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.String(255), nullable=False),
        sa.Column(
            "visit_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "last_visited_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint(
            "user_id",
            "space_id",
            "target_type",
            "target_id",
            name="pk_user_space_affinity",
        ),
        sa.CheckConstraint(
            "target_type IN ('nav_item', 'saved_view', "
            "'entity_record', 'triage_queue')",
            name="ck_user_space_affinity_target_type",
        ),
    )
    # Partial index — the read path's exact query shape. Partial
    # because rows with visit_count=0 shouldn't exist (we never
    # insert them) but defense-in-depth keeps the index size
    # proportional to active affinity.
    op.create_index(
        "ix_user_space_affinity_user_space_active",
        "user_space_affinity",
        ["user_id", "space_id"],
        postgresql_where=sa.text("visit_count > 0"),
    )
    # Future-proofing — anticipated recency-ordered consumers.
    op.create_index(
        "ix_user_space_affinity_user_recent_active",
        "user_space_affinity",
        ["user_id", sa.text("last_visited_at DESC")],
        postgresql_where=sa.text("visit_count > 0"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_space_affinity_user_recent_active",
        table_name="user_space_affinity",
    )
    op.drop_index(
        "ix_user_space_affinity_user_space_active",
        table_name="user_space_affinity",
    )
    op.drop_table("user_space_affinity")
