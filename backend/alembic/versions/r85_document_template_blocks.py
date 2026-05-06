"""Document template blocks (Phase D-10, June 2026).

Block-based document authoring. Templates that opt into block authoring
have one `document_template_blocks` row per block. The composer reads
blocks ordered by position, calls each block-kind's compile_to_jinja
function, and emits a complete Jinja string written back to
`document_template_versions.body_template`. Document_renderer then
renders the Jinja exactly as it does today — block authoring is a
new authoring path; the rendering pipeline is unchanged.

Existing 18 platform templates stay as Jinja with no block records;
they continue to render through document_renderer unchanged. Templates
authored as blocks have block records; their body_template is derived
from the blocks at save time.

Six initial block kinds canonical (composer registry source of truth):
  - header             (logo + company info + title + date)
  - body_section       (heading + content + optional accent)
  - line_items         (table over a variable list)
  - totals             (subtotal/tax/total presentation)
  - signature          (signature collection area with anchors)
  - conditional_wrapper (wraps child blocks with a Jinja condition)

The conditional_wrapper kind uses parent_block_id self-FK so child
blocks can be discovered + composed correctly. Top-level blocks have
parent_block_id NULL.

Migration head: r84_focus_compositions → r85_document_template_blocks.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r85_document_template_blocks"
down_revision = "r84_focus_compositions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "document_template_blocks" in set(inspector.get_table_names()):
        return

    op.create_table(
        "document_template_blocks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "template_version_id",
            sa.String(36),
            sa.ForeignKey(
                "document_template_versions.id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column("block_kind", sa.String(64), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column(
            "config",
            sa.JSON().with_variant(
                sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
                "postgresql",
            ),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # Jinja expression for conditional_wrapper kind; null for
        # unconditional blocks. Validated at write time, not enforced
        # at the schema level (a CHECK constraint would couple block
        # kind to condition presence which the registry handles
        # cleanly in service code).
        sa.Column("condition", sa.Text, nullable=True),
        # Self-FK for nested blocks inside a conditional_wrapper.
        # ON DELETE CASCADE so removing a wrapper removes its
        # children atomically.
        sa.Column(
            "parent_block_id",
            sa.String(36),
            sa.ForeignKey(
                "document_template_blocks.id", ondelete="CASCADE"
            ),
            nullable=True,
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

    # Composite index for ordered traversal — composer queries
    # `WHERE template_version_id = X ORDER BY position`.
    op.create_index(
        "ix_document_template_blocks_version_position",
        "document_template_blocks",
        ["template_version_id", "position"],
    )
    # Lookup index for child blocks of a wrapper.
    op.create_index(
        "ix_document_template_blocks_parent",
        "document_template_blocks",
        ["parent_block_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = {
        ix["name"]
        for ix in inspector.get_indexes("document_template_blocks")
    } if "document_template_blocks" in set(inspector.get_table_names()) else set()

    if "ix_document_template_blocks_parent" in existing_indexes:
        op.drop_index(
            "ix_document_template_blocks_parent",
            table_name="document_template_blocks",
        )
    if "ix_document_template_blocks_version_position" in existing_indexes:
        op.drop_index(
            "ix_document_template_blocks_version_position",
            table_name="document_template_blocks",
        )
    if "document_template_blocks" in set(inspector.get_table_names()):
        op.drop_table("document_template_blocks")
