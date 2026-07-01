"""MoC task triggers — the descriptive trigger substrate (MoC Triggers T-1a).

Two tables:
- `moc_task_trigger` — the per-task trigger collection (mirrors the focus-join
  structure: task_catalog_id FK ON DELETE CASCADE). `kind` CHECK-constrained
  {schedule|event|manual}; `config` JSONB (kind-specific — schedule shapes mirror
  workflow_scheduler 1:1; event carries a conditions LIST for filtered→rich).
- `moc_trigger_event_catalog` — the curated, seeded, editable event vocabulary
  (2a vocabulary-store philosophy). Three-tier scope; partial unique indexes keep
  platform (vertical NULL) + vertical-scoped events dup-free.

DESCRIPTIVE only — no firing. Execution is the deferred T-2 canvas↔runtime bridge.

Revision ID: r115_moc_task_triggers
Revises: r114_moc_task_vocabulary
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r115_moc_task_triggers"
down_revision = "r114_moc_task_vocabulary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "moc_task_trigger",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "task_catalog_id", sa.String(36),
            sa.ForeignKey("moc_task_catalog.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("config", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("label", sa.String(200), nullable=True),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "kind IN ('schedule', 'event', 'manual')",
            name="ck_moc_task_trigger_kind",
        ),
    )
    op.create_index(
        "ix_moc_task_trigger_task_catalog_id", "moc_task_trigger", ["task_catalog_id"]
    )

    op.create_table(
        "moc_trigger_event_catalog",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_key", sa.String(120), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("entity", sa.String(64), nullable=True),
        sa.Column(
            "filterable_fields", JSONB, nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("scope", sa.String(32), nullable=False, server_default="platform_default"),
        sa.Column(
            "vertical", sa.String(32),
            sa.ForeignKey("verticals.slug"), nullable=True,
        ),
        sa.Column(
            "tenant_id", sa.String(36),
            sa.ForeignKey("companies.id"), nullable=True,
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "scope IN ('platform_default', 'vertical_default', 'tenant_override')",
            name="ck_moc_trigger_event_catalog_scope",
        ),
    )
    op.create_index(
        "ix_moc_trigger_event_catalog_vertical", "moc_trigger_event_catalog", ["vertical"]
    )
    op.create_index(
        "ix_moc_trigger_event_catalog_tenant_id", "moc_trigger_event_catalog", ["tenant_id"]
    )
    # No-dup-event guards (platform rows have vertical NULL → a separate partial).
    op.create_index(
        "uq_moc_trigger_event_platform", "moc_trigger_event_catalog",
        ["event_key", "scope"], unique=True,
        postgresql_where=sa.text("vertical IS NULL"),
    )
    op.create_index(
        "uq_moc_trigger_event_scoped", "moc_trigger_event_catalog",
        ["event_key", "scope", "vertical"], unique=True,
        postgresql_where=sa.text("vertical IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_moc_trigger_event_scoped", table_name="moc_trigger_event_catalog")
    op.drop_index("uq_moc_trigger_event_platform", table_name="moc_trigger_event_catalog")
    op.drop_index("ix_moc_trigger_event_catalog_tenant_id", table_name="moc_trigger_event_catalog")
    op.drop_index("ix_moc_trigger_event_catalog_vertical", table_name="moc_trigger_event_catalog")
    op.drop_table("moc_trigger_event_catalog")
    op.drop_index("ix_moc_task_trigger_task_catalog_id", table_name="moc_task_trigger")
    op.drop_table("moc_task_trigger")
