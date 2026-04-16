"""Legacy print designs — per-tenant catalog of Wilbert standard + custom prints."""

import uuid
from alembic import op
import sqlalchemy as sa

revision = "vault_06_legacy_prints"
down_revision = "admin_01_super_admin_tables"
branch_labels = None
depends_on = None


# Wilbert standard Legacy print catalog — seeded per company with vault program
WILBERT_STANDARD_PRINTS = [
    ("classic_rose", "Classic Rose", "Traditional rose design, timeless and universal."),
    ("american_flag", "American Flag", "Patriotic stars-and-stripes design."),
    ("praying_hands", "Praying Hands", "Religious hands in prayer."),
    ("guardian_angel", "Guardian Angel", "Protective angel figure."),
    ("autumn_leaves", "Autumn Leaves", "Falling leaves in warm tones."),
    ("last_supper", "The Last Supper", "Religious scene based on classic artwork."),
    ("cross_lilies", "Cross with Lilies", "Christian cross surrounded by Easter lilies."),
    ("eagle", "American Eagle", "Soaring bald eagle, patriotic."),
    ("mountain_sunrise", "Mountain Sunrise", "Landscape with mountains at sunrise."),
    ("ocean_waves", "Ocean Waves", "Peaceful ocean scene."),
]


def upgrade() -> None:
    op.create_table(
        "program_legacy_prints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("program_code", sa.String(50), nullable=False),  # 'vault' | 'urn'
        sa.Column("wilbert_catalog_key", sa.String(200), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("file_url", sa.String(500), nullable=True),
        sa.Column("thumbnail_url", sa.String(500), nullable=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_custom", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("price_addition", sa.Numeric(10, 2), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_program_legacy_prints_company_program",
        "program_legacy_prints",
        ["company_id", "program_code"],
    )
    op.create_index(
        "uq_wilbert_catalog_per_company_program",
        "program_legacy_prints",
        ["company_id", "program_code", "wilbert_catalog_key"],
        unique=True,
        postgresql_where=sa.text("wilbert_catalog_key IS NOT NULL"),
    )

    # Seed Wilbert standard prints for every company that has a vault program enrollment.
    # This runs for every existing company and is idempotent via the unique index.
    connection = op.get_bind()
    companies = connection.execute(
        sa.text(
            "SELECT DISTINCT company_id FROM wilbert_program_enrollments "
            "WHERE program_code = 'vault' AND is_active = true"
        )
    ).fetchall()

    for i, (company_id,) in enumerate(companies):
        for sort_order, (key, display_name, description) in enumerate(WILBERT_STANDARD_PRINTS):
            connection.execute(
                sa.text(
                    "INSERT INTO program_legacy_prints "
                    "(id, company_id, program_code, wilbert_catalog_key, display_name, "
                    "description, is_enabled, is_custom, sort_order) "
                    "VALUES (:id, :cid, 'vault', :key, :name, :desc, true, false, :so) "
                    "ON CONFLICT DO NOTHING"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "cid": company_id,
                    "key": key,
                    "name": display_name,
                    "desc": description,
                    "so": sort_order,
                },
            )


def downgrade() -> None:
    op.drop_index(
        "uq_wilbert_catalog_per_company_program",
        table_name="program_legacy_prints",
    )
    op.drop_index(
        "ix_program_legacy_prints_company_program",
        table_name="program_legacy_prints",
    )
    op.drop_table("program_legacy_prints")
