"""Maps of Content — Phase 1 substrate.

One lean table (per the MoC Phase 0 verdict + settled decisions):

- moc_pages — an authored, artifact-first navigation page. Per-vertical
  today (scope='vertical_default', vertical set); the column shape carries
  the full three-tier scope (platform_default → vertical_default →
  tenant_override) so the tenant tier is reachable later without a
  migration, even though it ships empty. `sections` is an ordered JSONB
  array of sections, each holding an ordered array of typed
  artifact-reference rows {builder, artifact_id, label, icon}. Reference
  resolution happens at READ time and is orphan-tolerant — a row whose
  artifact no longer exists renders unavailable, never errors.

Actor attribution (created_by / updated_by) is FK-less VARCHAR(36) — the
realm-agnostic pattern (a value may originate from either a tenant `User`
or a platform `PlatformUser`; no schema-level FK to one realm's table).

Revision ID: r111_moc_pages
Revises: r110_jcf_assembly
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r111_moc_pages"
down_revision = "r110_jcf_assembly"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "moc_pages",
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
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "sections",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_check_constraint(
        "ck_moc_pages_scope",
        "moc_pages",
        "scope IN ('platform_default', 'vertical_default', "
        "'tenant_override')",
    )
    # One active page per identity tuple. NULLS NOT DISTINCT (PG15+) so the
    # NULL tenant_id / vertical of platform+vertical-scope rows still
    # collide on (scope, vertical, slug).
    op.create_index(
        "uq_moc_pages_identity_active",
        "moc_pages",
        ["scope", "vertical", "tenant_id", "slug"],
        unique=True,
        postgresql_where=sa.text("is_active"),
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    op.drop_index("uq_moc_pages_identity_active", table_name="moc_pages")
    op.drop_constraint("ck_moc_pages_scope", "moc_pages", type_="check")
    op.drop_table("moc_pages")
