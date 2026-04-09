"""Add safety_program_generations table.

Revision ID: r15_safety_program_generation
Revises: r14_urn_catalog_pdf_fetch
Create Date: 2026-04-09
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "r15_safety_program_generation"
down_revision = "r14_urn_catalog_pdf_fetch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "safety_program_generations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("topic_id", sa.String(36), sa.ForeignKey("safety_training_topics.id"), nullable=False),
        sa.Column("schedule_id", sa.String(36), sa.ForeignKey("tenant_training_schedules.id"), nullable=True),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("month_number", sa.Integer, nullable=False),
        # OSHA scraper
        sa.Column("osha_standard_code", sa.String(100), nullable=True),
        sa.Column("osha_scraped_text", sa.Text, nullable=True),
        sa.Column("osha_scrape_url", sa.String(500), nullable=True),
        sa.Column("osha_scrape_status", sa.String(20), server_default="pending"),
        sa.Column("osha_scraped_at", sa.DateTime(timezone=True), nullable=True),
        # Generation
        sa.Column("generated_content", sa.Text, nullable=True),
        sa.Column("generated_html", sa.Text, nullable=True),
        sa.Column("generation_status", sa.String(20), server_default="pending"),
        sa.Column("generation_model", sa.String(100), nullable=True),
        sa.Column("generation_token_usage", sa.JSON, nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        # PDF
        sa.Column("pdf_document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("pdf_generated_at", sa.DateTime(timezone=True), nullable=True),
        # Approval
        sa.Column("status", sa.String(20), server_default="draft"),
        sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text, nullable=True),
        # Posting
        sa.Column("safety_program_id", sa.String(36), sa.ForeignKey("safety_programs.id"), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        # Metadata
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_safety_program_gen_tenant_year_month",
        "safety_program_generations",
        ["tenant_id", "year", "month_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_safety_program_gen_tenant_year_month")
    op.drop_table("safety_program_generations")
