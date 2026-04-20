"""Phase 5 — Tasks + Triage infrastructure.

Four coherent schema changes:

  1. `tasks` table (CRUD-backed Task model — deferred from Phase 4).
     Columns: id (uuid PK), company_id FK, title, description,
     assignee_user_id FK (nullable), created_by_user_id FK,
     priority enum-as-varchar (low/normal/high/urgent),
     due_date, due_datetime, status (open/in_progress/blocked/
     done/cancelled), completed_at, related_entity_type +
     related_entity_id (polymorphic link to a vault entity),
     metadata_json JSONB, created_at / updated_at.

  2. `triage_sessions` table — per-user triage session state +
     resume capability. One row per started session. Lifecycle:
     start → next_item (many) → apply_action (many) → end.

  3. `triage_snoozes` table — generic snooze rows. Entity-type-
     agnostic so any triage queue can snooze its items uniformly.
     Indexed on (user_id, wake_at) for "my snoozed items" + on
     (wake_at) for the scheduler sweep that un-snoozes ready rows.

  4. GIN trigram index on `tasks.title` — Phase 1 command-bar
     resolver gains task search (SEARCHABLE_ENTITIES extension).
     CREATE INDEX CONCURRENTLY wrapped in autocommit block, same
     pattern as r31/r32/r33.

pg_trgm extension is assumed present (r31 installed it). Downgrade
drops everything this migration added; extension stays installed.

Revision ID: r34_tasks_and_triage
Revises: r33_company_entity_trigram_indexes
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = "r34_tasks_and_triage"
down_revision = "r33_company_entity_trigram_indexes"
branch_labels = None
depends_on = None


_CONCURRENT_INDEXES = [
    (
        "ix_tasks_title_trgm",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_tasks_title_trgm "
        "ON tasks USING gin (title gin_trgm_ops)",
    ),
]


def upgrade() -> None:
    # ── tasks ────────────────────────────────────────────────────────
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "assignee_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "priority",
            sa.String(16),
            nullable=False,
            server_default="normal",
        ),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("due_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="open",
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("related_entity_type", sa.String(64), nullable=True),
        sa.Column("related_entity_id", sa.String(36), nullable=True),
        sa.Column(
            "metadata_json",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_tasks_company_status_assignee",
        "tasks",
        ["company_id", "status", "assignee_user_id"],
    )
    op.create_index(
        "ix_tasks_company_due",
        "tasks",
        ["company_id", "due_date"],
    )
    op.create_index(
        "ix_tasks_related",
        "tasks",
        ["related_entity_type", "related_entity_id"],
        postgresql_where=sa.text("related_entity_id IS NOT NULL"),
    )

    # ── triage_sessions ──────────────────────────────────────────────
    op.create_table(
        "triage_sessions",
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
        sa.Column("queue_id", sa.String(64), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "items_processed_count",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "items_approved_count",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "items_rejected_count",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "items_snoozed_count",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column("current_item_id", sa.String(36), nullable=True),
        sa.Column(
            "cursor_meta",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index(
        "ix_triage_sessions_user_active",
        "triage_sessions",
        ["user_id", "queue_id"],
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.create_index(
        "ix_triage_sessions_company",
        "triage_sessions",
        ["company_id", "queue_id", "started_at"],
    )

    # ── triage_snoozes ───────────────────────────────────────────────
    # Generic entity-type-agnostic snoozes. Lookup patterns:
    #   - "my snoozed items" → (user_id, wake_at) range + entity_type filter
    #   - scheduler sweep → wake_at <= now() AND not yet un-snoozed
    op.create_table(
        "triage_snoozes",
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
        sa.Column("queue_id", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column(
            "wake_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column(
            "woken_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_triage_snoozes_user_wake",
        "triage_snoozes",
        ["user_id", "wake_at"],
    )
    # Partial on wake_at WHERE woken_at IS NULL — scheduler sweeps
    # only un-resolved snoozes.
    op.create_index(
        "ix_triage_snoozes_pending_wake",
        "triage_snoozes",
        ["wake_at"],
        postgresql_where=sa.text("woken_at IS NULL"),
    )
    # Unique per (user_id, queue_id, entity_type, entity_id) while un-
    # resolved — prevents double-snoozing the same item by the same
    # user. Re-snooze requires removing the prior pending row.
    op.create_index(
        "uq_triage_snoozes_active",
        "triage_snoozes",
        ["user_id", "queue_id", "entity_type", "entity_id"],
        unique=True,
        postgresql_where=sa.text("woken_at IS NULL"),
    )

    # ── GIN trigram on tasks.title ───────────────────────────────────
    # CREATE INDEX CONCURRENTLY must be in an autocommit block.
    with op.get_context().autocommit_block():
        for _, sql in _CONCURRENT_INDEXES:
            op.execute(sql)


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name, _ in reversed(_CONCURRENT_INDEXES):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
    op.drop_index("uq_triage_snoozes_active", table_name="triage_snoozes")
    op.drop_index("ix_triage_snoozes_pending_wake", table_name="triage_snoozes")
    op.drop_index("ix_triage_snoozes_user_wake", table_name="triage_snoozes")
    op.drop_table("triage_snoozes")
    op.drop_index("ix_triage_sessions_company", table_name="triage_sessions")
    op.drop_index("ix_triage_sessions_user_active", table_name="triage_sessions")
    op.drop_table("triage_sessions")
    op.drop_index("ix_tasks_related", table_name="tasks")
    op.drop_index("ix_tasks_company_due", table_name="tasks")
    op.drop_index("ix_tasks_company_status_assignee", table_name="tasks")
    op.drop_table("tasks")
