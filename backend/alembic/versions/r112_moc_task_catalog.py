"""Maps of Content — MoC-2a task-catalog substrate.

Two tables (per docs/investigations/moc_2_investigation.md Phase-0 completion):

- moc_task_catalog — a vertical-default TASK CATALOG: named recurring
  automations per vertical ("Funeral Home Billing", "New Legacy Order") — a
  NEW concept, NOT the runtime instance-tasks (vault_items/tasks). Mirrors
  moc_pages' three-tier scope (platform_default → vertical_default →
  tenant_override; ships vertical tier populated, tenant tier reachable).
  Each task references the ONE workflow_template it runs (workflow_template_id,
  nullable) and, via the join below, the MANY focus_templates it opens.

- moc_task_catalog_focuses — task↔focus_template join (a task opens 0..N
  focuses; "New Legacy Order" opens two).

frequency + task_type are FREE-FORM strings (descriptive, not derived):
workflow_templates carries no trigger/cron columns and no task-type taxonomy
exists. Recorded design judgment: free-form pending a stable vocabulary;
promote to enum if the type/frequency set stabilizes.

Artifact-reference FKs use ondelete SET NULL (workflow) / CASCADE (focus join)
so deleting a template never BLOCKS — and the READ-time resolver (the cards'
_resolve_workflow/_resolve_focus, reused) stays the orphan-tolerance layer for
any defensive stale id. Actor attribution is FK-less VARCHAR(36)
(realm-agnostic — tenant User or platform PlatformUser), matching moc_pages.

Revision ID: r112_moc_task_catalog
Revises: r111_moc_pages
"""
from alembic import op
import sqlalchemy as sa

revision = "r112_moc_task_catalog"
down_revision = "r111_moc_pages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "moc_task_catalog",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "scope", sa.String(32), nullable=False
        ),  # platform_default | vertical_default | tenant_override
        sa.Column(
            "vertical",
            sa.String(32),
            sa.ForeignKey("verticals.slug"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("icon", sa.String(64), nullable=True),
        sa.Column("frequency", sa.String(120), nullable=True),  # free-form descriptive
        sa.Column("task_type", sa.String(120), nullable=True),  # free-form → pill
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "workflow_template_id",
            sa.String(36),
            sa.ForeignKey("workflow_templates.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "display_order", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_check_constraint(
        "ck_moc_task_catalog_scope",
        "moc_task_catalog",
        "scope IN ('platform_default', 'vertical_default', "
        "'tenant_override')",
    )
    # One active task of a given name per identity tuple — the find-or-create
    # key for the idempotent seed (name + vertical). NULLS NOT DISTINCT so the
    # NULL tenant_id of vertical-scope rows still collides on (scope, vertical,
    # name).
    op.create_index(
        "uq_moc_task_catalog_identity_active",
        "moc_task_catalog",
        ["scope", "vertical", "tenant_id", "name"],
        unique=True,
        postgresql_where=sa.text("is_active"),
        postgresql_nulls_not_distinct=True,
    )

    op.create_table(
        "moc_task_catalog_focuses",
        sa.Column(
            "task_catalog_id",
            sa.String(36),
            sa.ForeignKey("moc_task_catalog.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "focus_template_id",
            sa.String(36),
            sa.ForeignKey("focus_templates.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "display_order", sa.Integer(), nullable=False, server_default="0"
        ),
    )


def downgrade() -> None:
    op.drop_table("moc_task_catalog_focuses")
    op.drop_index(
        "uq_moc_task_catalog_identity_active", table_name="moc_task_catalog"
    )
    op.drop_constraint(
        "ck_moc_task_catalog_scope", "moc_task_catalog", type_="check"
    )
    op.drop_table("moc_task_catalog")
