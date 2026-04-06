"""Widget framework tables: widget_definitions, user_widget_layouts, extension_widgets

Revision ID: z9d3e4f5g6h7
Revises: z9c2d3e4f5g6
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "z9d3e4f5g6h7"
down_revision = "z9c2d3e4f5g6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "widget_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("widget_id", sa.String(100), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("page_contexts", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("default_size", sa.String(10), server_default="1x1"),
        sa.Column("min_size", sa.String(10), server_default="1x1"),
        sa.Column("max_size", sa.String(10), server_default="4x4"),
        sa.Column("supported_sizes", JSONB, server_default=sa.text("'[\"1x1\"]'::jsonb")),
        sa.Column("required_extension", sa.String(100), nullable=True),
        sa.Column("required_permission", sa.String(100), nullable=True),
        sa.Column("required_preset", sa.String(50), nullable=True),
        sa.Column("default_enabled", sa.Boolean, server_default="true"),
        sa.Column("default_position", sa.Integer, server_default="99"),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("is_system", sa.Boolean, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "user_widget_layouts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("page_context", sa.String(100), nullable=False),
        sa.Column("layout_config", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("tenant_id", "user_id", "page_context", name="uq_user_widget_layout"),
    )

    op.create_table(
        "extension_widgets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("extension_slug", sa.String(100), nullable=False),
        sa.Column("widget_id", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id", "extension_slug", "widget_id", name="uq_extension_widget"
        ),
    )


def downgrade() -> None:
    op.drop_table("extension_widgets")
    op.drop_table("user_widget_layouts")
    op.drop_table("widget_definitions")
