"""C-10 heal, round 2 — re-assert three missing tables named by the drift gate.

The boot-time schema-drift gate's FIRST production-tier run (staging,
2026-07-09, deploy 40bd7556) named exactly three model-mapped tables missing
from staging's live schema:

    company_migration_reviews   (from r44_master_company_entities)
    legacy_email_settings       (from r42_legacy_email_settings)
    legacy_fh_email_config      (from r42_legacy_email_settings)

Same class as r124's quotes columns (stamped-past / edited-after-applied —
alembic records the revisions as applied, so it will never re-run them).
Note the r44 fingerprint matches f1g2's exactly: the SAME migration's
company_entities table EXISTS on staging while its company_migration_reviews
sibling is missing — partial application, not a missing revision.

Table definitions copied VERBATIM from r42 + r44, each behind an
if-table-not-present guard: NO-OP on healthy DBs, heals staging.

DOWNGRADE IS A DELIBERATE NO-OP (r124 rationale): a heal cannot distinguish
tables it created on a stale DB from tables a healthy DB got from the
originals; dropping would destroy healthy databases' data.

Revision ID: r125_heal_missing_tables
Revises: r124_heal_quotes_quick_quote_columns
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = "r125_heal_missing_tables"
down_revision = "r124_heal_quotes_quick_quote_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    tables = set(sa_inspect(conn).get_table_names())

    # ── r42 block, verbatim ──────────────────────────────────────────────
    if "legacy_email_settings" not in tables:
        op.create_table(
            "legacy_email_settings",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, unique=True),
            sa.Column("sender_tier", sa.String(20), server_default="bridgeable"),
            sa.Column("reply_to_email", sa.String(500), nullable=True),
            sa.Column("custom_from_email", sa.String(500), nullable=True),
            sa.Column("custom_from_name", sa.String(200), nullable=True),
            sa.Column("domain_verified", sa.Boolean, server_default="false"),
            sa.Column("resend_domain_id", sa.String(200), nullable=True),
            sa.Column("proof_email_subject", sa.String(500), server_default="'Legacy Proof — {name}'"),
            sa.Column("proof_email_body", sa.Text, nullable=True),
            sa.Column("proof_email_reply_to", sa.String(500), nullable=True),
            sa.Column("print_email_subject", sa.String(500), server_default="'Legacy Ready — {name}, needed by {deadline}'"),
            sa.Column("print_email_body", sa.Text, nullable=True),
            sa.Column("use_invoice_branding", sa.Boolean, server_default="true"),
            sa.Column("header_color", sa.String(7), nullable=True),
            sa.Column("logo_url", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        )

    if "legacy_fh_email_config" not in tables:
        op.create_table(
            "legacy_fh_email_config",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=False),
            sa.Column("recipients", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("custom_subject", sa.String(500), nullable=True),
            sa.Column("custom_notes", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.UniqueConstraint("company_id", "customer_id", name="uq_legacy_fh_email_config"),
        )

    # ── r44 block, verbatim ──────────────────────────────────────────────
    if "company_migration_reviews" not in tables:
        op.create_table(
            "company_migration_reviews",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False),
            sa.Column("source_type", sa.String(20), nullable=False),
            sa.Column("source_id", sa.String(36), nullable=False),
            sa.Column("source_name", sa.String(500), nullable=True),
            sa.Column("suggested_company_id", sa.String(36), sa.ForeignKey("company_entities.id"), nullable=True),
            sa.Column("suggested_company_name", sa.String(500), nullable=True),
            sa.Column("similarity_score", sa.Numeric(4, 3), nullable=True),
            sa.Column("current_company_id", sa.String(36), sa.ForeignKey("company_entities.id"), nullable=True),
            sa.Column("status", sa.String(20), server_default="pending"),
            sa.Column("resolved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        )


def downgrade() -> None:
    # Deliberate no-op — see module docstring / r124 rationale.
    pass
