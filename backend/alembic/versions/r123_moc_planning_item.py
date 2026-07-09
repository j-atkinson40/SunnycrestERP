"""MoC Planning items (r123) — the personal build-backlog on the maps.

The map shows what's NEEDED, not just what exists: typed planning items
(feature / workflow / focus / document — the operator's sections), grouped
by kind with status, rendered as a Planning section on the platform +
vertical maps. PERSONAL-SCOPED: items belong to the authenticated platform
user (owner_user_id) — the section is the current user's lens; another
user's items never render.

`created_artifact_slug` is the FORWARD HOOK — nullable, UNUSED this arc:
the future plan→artifact conversion's landing column (a "workflow to
create" item becoming a real workflow records the artifact's slug here).
Schema-ready, zero behavior.

Revision ID: r123_moc_planning_item
Revises: r122_focus_core_icon
"""
from alembic import op
import sqlalchemy as sa

revision = "r123_moc_planning_item"
down_revision = "r122_focus_core_icon"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "moc_planning_item",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "owner_user_id",
            sa.String(36),
            sa.ForeignKey(
                "platform_users.id",
                name="fk_moc_planning_item_owner",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        # The established tiers — where the item lives (which map shows it).
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column(
            "vertical",
            sa.String(32),
            sa.ForeignKey(
                "verticals.slug",
                name="fk_moc_planning_item_vertical",
                ondelete="RESTRICT",
            ),
            nullable=True,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        # Long-form "how it's going to work" design note.
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default="planned"
        ),
        sa.Column(
            "display_order", sa.Integer(), nullable=False, server_default="0"
        ),
        # FORWARD HOOK (unused this arc): the plan→artifact conversion's
        # landing column.
        sa.Column("created_artifact_slug", sa.String(96), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "scope IN ('platform_default', 'vertical_default')",
            name="ck_moc_planning_item_scope",
        ),
        sa.CheckConstraint(
            "("
            "(scope = 'platform_default' AND vertical IS NULL)"
            " OR (scope = 'vertical_default' AND vertical IS NOT NULL)"
            ")",
            name="ck_moc_planning_item_scope_vertical",
        ),
        # Extensible the trigger-kind way: widen the CHECK when a kind joins.
        sa.CheckConstraint(
            "kind IN ('feature', 'workflow', 'focus', 'document')",
            name="ck_moc_planning_item_kind",
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'in_progress', 'done')",
            name="ck_moc_planning_item_status",
        ),
    )
    op.create_index(
        "ix_moc_planning_item_owner_scope",
        "moc_planning_item",
        ["owner_user_id", "scope", "vertical"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_moc_planning_item_owner_scope", table_name="moc_planning_item"
    )
    op.drop_table("moc_planning_item")
