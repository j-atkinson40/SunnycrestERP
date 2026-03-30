"""r19 classification metadata — add AI classification columns to customers table.

Adds: classification_confidence, classification_method, classification_reasoning,
      classification_reviewed_by, classification_reviewed_at.

Backfills Sage-migrated customers that already have a customer_type set.

Revision ID: r19_classification_metadata
Revises: r18_extension_visibility
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "r19_classification_metadata"
down_revision = "r18_extension_visibility"
branch_labels = None
depends_on = None


def upgrade():
    # ── new columns ───────────────────────────────────────────────────────────
    op.add_column(
        "customers",
        sa.Column(
            "classification_confidence",
            sa.Float(),
            nullable=True,
            comment="0.0–1.0 confidence score from classification engine",
        ),
    )
    op.add_column(
        "customers",
        sa.Column(
            "classification_method",
            sa.String(30),
            nullable=True,
            comment="'name_rules', 'ai', 'manual', 'migration_import'",
        ),
    )
    op.add_column(
        "customers",
        sa.Column(
            "classification_reasoning",
            sa.Text(),
            nullable=True,
            comment="Human-readable explanation of why the type was assigned",
        ),
    )
    op.add_column(
        "customers",
        sa.Column(
            "classification_reviewed_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
            comment="User who manually confirmed or changed the type",
        ),
    )
    op.add_column(
        "customers",
        sa.Column(
            "classification_reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the classification was manually reviewed",
        ),
    )

    # ── backfill: Sage-migrated customers that already have a type ────────────
    # These were classified by Sage 'PC' codes + reclassify endpoints.
    # Mark them as migration_import with high confidence so they don't appear
    # in the "needs review" queue.
    op.execute(
        text("""
        UPDATE customers
        SET classification_method = 'migration_import',
            classification_confidence = 0.90,
            classification_reasoning = 'Type assigned during Sage 100 data migration'
        WHERE sage_customer_id IS NOT NULL
          AND customer_type IS NOT NULL
          AND customer_type != 'unknown'
          AND classification_method IS NULL
        """)
    )

    # Sage-migrated with no type → mark unknown so they surface in review queue
    op.execute(
        text("""
        UPDATE customers
        SET customer_type = 'unknown',
            classification_method = 'migration_import',
            classification_confidence = 0.0,
            classification_reasoning = 'Type could not be determined from Sage data'
        WHERE sage_customer_id IS NOT NULL
          AND (customer_type IS NULL OR customer_type = '')
          AND classification_method IS NULL
        """)
    )


def downgrade():
    op.drop_column("customers", "classification_reviewed_at")
    op.drop_column("customers", "classification_reviewed_by")
    op.drop_column("customers", "classification_reasoning")
    op.drop_column("customers", "classification_method")
    op.drop_column("customers", "classification_confidence")
