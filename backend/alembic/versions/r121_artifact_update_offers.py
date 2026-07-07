"""Offered updates — publishes + offers (Focus Variations V-2).

The software-update model for templates: editing a default is PRIVATE
until an explicit PUBLISH (authored patch notes); publishing creates
OFFERS for downstream variation owners, who review the diff and accept
(pin-move apply) or decline (recallable, never nagging).

LEVEL-GENERIC from day one: `artifact_type` + `target_kind` are string
discriminators, NOT CHECK-constrained to today's values — workflows and
tenant-tier targets plug in later with ZERO schema change. V-2 populates
artifact_type='focus_core' + target_kind='focus_template' only.

Slug-keyed identities throughout (the C-2.1.2 canon): version bumps mint
new row ids, so offers reference lineages by slug + version, never row id.

`focus_cores.published_version` is the publish boundary: NULL = never
published (the resolver keeps today's live cascade — no behavior change
for existing content); set = the core's downstream templates resolve at
their pinned `inherits_from_core_version` snapshot until they accept.

Revision ID: r121_artifact_update_offers
Revises: r120_focus_template_verticals
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r121_artifact_update_offers"
down_revision = "r120_focus_template_verticals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artifact_publishes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("artifact_type", sa.String(32), nullable=False),
        sa.Column("source_slug", sa.String(96), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("patch_notes", sa.Text(), nullable=True),
        # The release's own delta (prior published version → this one);
        # {} on a first publish.
        sa.Column("derived_diff", JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.UniqueConstraint(
            "artifact_type", "source_slug", "version",
            name="uq_artifact_publishes_source_version",
        ),
    )
    op.create_index(
        "ix_artifact_publishes_source",
        "artifact_publishes",
        ["artifact_type", "source_slug"],
    )

    op.create_table(
        "artifact_update_offers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "publish_id",
            sa.String(36),
            sa.ForeignKey(
                "artifact_publishes.id",
                name="fk_artifact_update_offers_publish",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column("artifact_type", sa.String(32), nullable=False),
        sa.Column("source_slug", sa.String(96), nullable=False),
        # The target's pin when the offer was created → the published version.
        sa.Column("source_version_from", sa.Integer(), nullable=False),
        sa.Column("source_version_to", sa.Integer(), nullable=False),
        sa.Column("target_kind", sa.String(32), nullable=False),
        sa.Column("target_slug", sa.String(96), nullable=False),
        sa.Column("target_vertical", sa.String(32), nullable=True),
        # Tenant-tier targets (future target_kind) — schema-ready, unbuilt.
        sa.Column("target_tenant_id", sa.String(36), nullable=True),
        # Denormalized from the publish so the offer stays legible even if
        # notes are later edited on a future publish surface.
        sa.Column("patch_notes", sa.Text(), nullable=True),
        # Per-target delta (THIS target's pin → the published version) —
        # targets at different pins get different diffs.
        sa.Column("derived_diff", JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.String(36), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'superseded')",
            name="ck_artifact_update_offers_status",
        ),
    )
    op.create_index(
        "ix_artifact_update_offers_target",
        "artifact_update_offers",
        ["target_kind", "target_slug", "status"],
    )
    op.create_index(
        "ix_artifact_update_offers_source",
        "artifact_update_offers",
        ["artifact_type", "source_slug"],
    )

    op.add_column(
        "focus_cores",
        sa.Column("published_version", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("focus_cores", "published_version")
    op.drop_index(
        "ix_artifact_update_offers_source",
        table_name="artifact_update_offers",
    )
    op.drop_index(
        "ix_artifact_update_offers_target",
        table_name="artifact_update_offers",
    )
    op.drop_table("artifact_update_offers")
    op.drop_index(
        "ix_artifact_publishes_source", table_name="artifact_publishes"
    )
    op.drop_table("artifact_publishes")
