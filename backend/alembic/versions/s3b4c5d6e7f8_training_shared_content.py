"""Make tenant_id nullable on training tables to support shared (system-wide) content.

Procedures and curriculum tracks with tenant_id IS NULL are shared across all
manufacturing tenants rather than duplicated per tenant.

Revision ID: s3b4c5d6e7f8
Revises: r7_create_missing
Create Date: 2026-03-27
"""

from alembic import op
import sqlalchemy as sa

revision = "s3b4c5d6e7f8"
down_revision = "r7_create_missing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make tenant_id nullable on training_procedures
    op.execute("ALTER TABLE training_procedures ALTER COLUMN tenant_id DROP NOT NULL")

    # Make tenant_id nullable on training_curriculum_tracks
    op.execute("ALTER TABLE training_curriculum_tracks ALTER COLUMN tenant_id DROP NOT NULL")

    # Add partial unique indexes to enforce uniqueness for shared (null tenant) content
    # (The existing unique constraints on (tenant_id, key) don't prevent duplicate NULLs in PostgreSQL)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_procedure_key_shared
        ON training_procedures (procedure_key)
        WHERE tenant_id IS NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_curriculum_track_shared
        ON training_curriculum_tracks (training_role)
        WHERE tenant_id IS NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_procedure_key_shared")
    op.execute("DROP INDEX IF EXISTS uq_curriculum_track_shared")
    # Note: restoring NOT NULL would fail if shared rows exist — handle manually
