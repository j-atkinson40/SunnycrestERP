"""MoC task vocabulary — the constrained-but-editable value store (Task Editing 2a).

A row per vocabulary VALUE (kind = frequency|type). Scope mirrors
moc_task_catalog / moc_pages (platform_default → vertical_default →
tenant_override): a value is platform-wide (vertical NULL) or vertical-specific.
Resolves the canon free-form note to constrained-editable: a task's frequency/type
must exist here, but adding a value is an INSERT (no code change).

Two partial unique indexes keep platform (vertical NULL) + vertical-scoped values
free of duplicates without a functional COALESCE index.

Revision ID: r114_moc_task_vocabulary
Revises: r113_workflow_template_mirror_provenance
"""
from alembic import op
import sqlalchemy as sa

revision = "r114_moc_task_vocabulary"
down_revision = "r113_workflow_template_mirror_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "moc_task_vocabulary",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("value", sa.String(120), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False, server_default="platform_default"),
        sa.Column(
            "vertical", sa.String(32),
            sa.ForeignKey("verticals.slug"), nullable=True,
        ),
        sa.Column(
            "tenant_id", sa.String(36),
            sa.ForeignKey("companies.id"), nullable=True,
        ),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("kind IN ('frequency', 'type')", name="ck_moc_task_vocabulary_kind"),
        sa.CheckConstraint(
            "scope IN ('platform_default', 'vertical_default', 'tenant_override')",
            name="ck_moc_task_vocabulary_scope",
        ),
    )
    op.create_index("ix_moc_task_vocabulary_kind", "moc_task_vocabulary", ["kind"])
    op.create_index("ix_moc_task_vocabulary_vertical", "moc_task_vocabulary", ["vertical"])
    op.create_index("ix_moc_task_vocabulary_tenant_id", "moc_task_vocabulary", ["tenant_id"])
    # No-dup-value guards (platform rows have vertical NULL → a separate partial).
    op.create_index(
        "uq_moc_task_vocab_platform", "moc_task_vocabulary",
        ["kind", "scope", "value"], unique=True,
        postgresql_where=sa.text("vertical IS NULL"),
    )
    op.create_index(
        "uq_moc_task_vocab_scoped", "moc_task_vocabulary",
        ["kind", "scope", "vertical", "value"], unique=True,
        postgresql_where=sa.text("vertical IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_moc_task_vocab_scoped", table_name="moc_task_vocabulary")
    op.drop_index("uq_moc_task_vocab_platform", table_name="moc_task_vocabulary")
    op.drop_index("ix_moc_task_vocabulary_tenant_id", table_name="moc_task_vocabulary")
    op.drop_index("ix_moc_task_vocabulary_vertical", table_name="moc_task_vocabulary")
    op.drop_index("ix_moc_task_vocabulary_kind", table_name="moc_task_vocabulary")
    op.drop_table("moc_task_vocabulary")
