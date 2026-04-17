"""Workflow Polish — step params table + is_core + added_steps + is_coming_soon."""

from alembic import op
import sqlalchemy as sa


revision = "fh_04_workflow_params"
down_revision = "vault_08_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. workflow_step_params — per-tenant configurable knobs on Tier 1 steps
    op.create_table(
        "workflow_step_params",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "workflow_id",
            sa.String(36),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=True),
        # company_id NULL = platform default. company_id set = tenant override.
        sa.Column("step_key", sa.String(100), nullable=False),
        sa.Column("param_key", sa.String(100), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("param_type", sa.String(50), nullable=False),
        sa.Column("default_value", sa.JSON, nullable=True),
        sa.Column("current_value", sa.JSON, nullable=True),
        sa.Column(
            "is_configurable",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("validation", sa.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_workflow_step_params_lookup",
        "workflow_step_params",
        ["workflow_id", "step_key", "param_key", "company_id"],
    )

    # 2. is_core flag on workflow_steps
    op.add_column(
        "workflow_steps",
        sa.Column("is_core", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )

    # 3. added_steps JSON on workflow_enrollments
    op.add_column(
        "workflow_enrollments",
        sa.Column("added_steps", sa.JSON, nullable=True),
    )

    # 4. is_coming_soon flag on workflows
    op.add_column(
        "workflows",
        sa.Column(
            "is_coming_soon",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("workflows", "is_coming_soon")
    op.drop_column("workflow_enrollments", "added_steps")
    op.drop_column("workflow_steps", "is_core")
    op.drop_index("ix_workflow_step_params_lookup", table_name="workflow_step_params")
    op.drop_table("workflow_step_params")
