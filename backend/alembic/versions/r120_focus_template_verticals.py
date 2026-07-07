"""Focus template verticals join (Focus Variations V-1).

One variation, several vertical homes: a Tier 2 focus template (a
"variation" created from a Tier 1 core via the guided flow) can serve
MULTIPLE verticals. The row's own `vertical` column stays the HOME
vertical (the CHECK correlation unchanged); this join carries the full
set of verticals the variation surfaces in.

SLUG-KEYED, deliberately: focus_template version bumps mint new row ids
(deactivate prior + insert at version+1), so an id-keyed join would need
re-writing on every edit. `template_slug` is the lineage's stable
identity (the C-2.1.2 canon) — join rows survive version rotation with
zero churn.

Revision ID: r120_focus_template_verticals
Revises: r119_moc_domain_event
"""
from alembic import op
import sqlalchemy as sa

revision = "r120_focus_template_verticals"
down_revision = "r119_moc_domain_event"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "focus_template_verticals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("template_slug", sa.String(96), nullable=False),
        sa.Column(
            "vertical",
            sa.String(32),
            sa.ForeignKey(
                "verticals.slug",
                name="fk_focus_template_verticals_vertical",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.UniqueConstraint(
            "template_slug",
            "vertical",
            name="uq_focus_template_verticals_slug_vertical",
        ),
    )
    op.create_index(
        "ix_focus_template_verticals_vertical",
        "focus_template_verticals",
        ["vertical"],
    )
    op.create_index(
        "ix_focus_template_verticals_slug",
        "focus_template_verticals",
        ["template_slug"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_focus_template_verticals_slug",
        table_name="focus_template_verticals",
    )
    op.drop_index(
        "ix_focus_template_verticals_vertical",
        table_name="focus_template_verticals",
    )
    op.drop_table("focus_template_verticals")
