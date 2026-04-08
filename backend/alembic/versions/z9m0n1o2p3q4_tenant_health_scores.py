"""Create tenant_health_scores table and seed rows for existing tenants.

Revision ID: z9m0n1o2p3q4
Revises: z9l9m0n1o2p3
Create Date: 2026-04-08
"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "z9m0n1o2p3q4"
down_revision = "z9l9m0n1o2p3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_health_scores",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, unique=True),
        # Overall score
        sa.Column("score", sa.String(20), server_default="unknown"),
        # Component scores
        sa.Column("api_health", sa.String(20), server_default="unknown"),
        sa.Column("auth_health", sa.String(20), server_default="unknown"),
        sa.Column("data_health", sa.String(20), server_default="unknown"),
        sa.Column("background_job_health", sa.String(20), server_default="unknown"),
        # Incident stats
        sa.Column("open_incident_count", sa.Integer(), server_default="0"),
        sa.Column("last_incident_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_healthy_at", sa.DateTime(timezone=True), nullable=True),
        # Explanation
        sa.Column("reasons", postgresql.JSONB(), server_default="[]"),
        # Metadata
        sa.Column("last_calculated", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_index("idx_tenant_health_score", "tenant_health_scores", ["score"])

    # Data migration: seed a health score row for every existing tenant
    conn = op.get_bind()
    tenants = conn.execute(sa.text("SELECT id FROM companies WHERE is_active = true")).fetchall()
    for (tenant_id,) in tenants:
        # Skip if already seeded (idempotent)
        existing = conn.execute(
            sa.text("SELECT 1 FROM tenant_health_scores WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        ).fetchone()
        if existing:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO tenant_health_scores (id, tenant_id, score) "
                "VALUES (:id, :tid, 'unknown')"
            ),
            {"id": str(uuid.uuid4()), "tid": tenant_id},
        )


def downgrade() -> None:
    op.drop_index("idx_tenant_health_score", table_name="tenant_health_scores")
    op.drop_table("tenant_health_scores")
