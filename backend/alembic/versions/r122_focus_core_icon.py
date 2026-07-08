"""Focus family icons (r122) — the core-type icon, lineage-resolved.

One nullable column on focus_cores ONLY. The icon is FAMILY IDENTITY:
every variation renders its lineage ROOT core's CURRENT icon, resolved at
read — inherited, never copied, deliberately NOT overridable downstream
(downstream customization would defeat at-a-glance family identification).
It does NOT ride the V-2 offer/publish system: changing a core's icon is
immediate everywhere, deliberately (identity, not versioned content).

Revision ID: r122_focus_core_icon
Revises: r121_artifact_update_offers
"""
from alembic import op
import sqlalchemy as sa

revision = "r122_focus_core_icon"
down_revision = "r121_artifact_update_offers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "focus_cores",
        sa.Column("icon", sa.String(48), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("focus_cores", "icon")
