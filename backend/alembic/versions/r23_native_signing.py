"""Bridgeable Documents Phase D-4 — native signing infrastructure.

Four tables:
  signature_envelopes  — a signing request (the "envelope")
  signature_parties    — the people who need to sign (with signer_token)
  signature_fields     — the fields each party fills (signature, initial, etc.)
  signature_events     — append-only audit log of every envelope/party event

Also seeds 5 new platform templates:
  pdf.signature_certificate  — Certificate of Completion (ESIGN-compliant)
  email.signing_invite
  email.signing_completed
  email.signing_declined
  email.signing_voided

Runs in parallel with the existing DocuSign integration — no existing
flows are migrated in D-4. D-5 handles disinterment migration.

Revision ID: r23_native_signing
Revises: r22_document_template_editing
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision = "r23_native_signing"
down_revision = "r22_document_template_editing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. signature_envelopes ──────────────────────────────────────
    op.create_table(
        "signature_envelopes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "routing_type",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'sequential'"),
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("document_hash", sa.String(64), nullable=False),
        sa.Column(
            "expires_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "voided_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "voided_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column(
            "certificate_document_id",
            sa.String(36),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_sig_env_company_status_created",
        "signature_envelopes",
        ["company_id", "status", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_sig_env_document_id",
        "signature_envelopes",
        ["document_id"],
    )
    op.execute(
        "CREATE INDEX ix_sig_env_status_active "
        "ON signature_envelopes (status) "
        "WHERE status IN ('sent','in_progress')"
    )
    op.execute(
        "CREATE INDEX ix_sig_env_expires_at_active "
        "ON signature_envelopes (expires_at) "
        "WHERE status IN ('sent','in_progress')"
    )

    # ── 2. signature_parties ────────────────────────────────────────
    op.create_table(
        "signature_parties",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "envelope_id",
            sa.String(36),
            sa.ForeignKey("signature_envelopes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("signing_order", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("signer_token", sa.String(128), nullable=False, unique=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("declined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decline_reason", sa.Text(), nullable=True),
        sa.Column("signing_ip_address", sa.String(45), nullable=True),
        sa.Column("signing_user_agent", sa.Text(), nullable=True),
        sa.Column("signature_type", sa.String(16), nullable=True),
        sa.Column("signature_data", sa.Text(), nullable=True),
        sa.Column("typed_signature_name", sa.String(255), nullable=True),
        sa.Column(
            "notification_sent_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "last_notification_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_sig_party_envelope_order",
        "signature_parties",
        ["envelope_id", "signing_order"],
    )
    op.create_index(
        "ix_sig_party_envelope_status",
        "signature_parties",
        ["envelope_id", "status"],
    )
    # signer_token unique constraint covers the token lookup index

    # ── 3. signature_fields ─────────────────────────────────────────
    op.create_table(
        "signature_fields",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "envelope_id",
            sa.String(36),
            sa.ForeignKey("signature_envelopes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "party_id",
            sa.String(36),
            sa.ForeignKey("signature_parties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field_type", sa.String(16), nullable=False),
        sa.Column("anchor_string", sa.String(255), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("position_x", sa.Float(), nullable=True),
        sa.Column("position_y", sa.Float(), nullable=True),
        sa.Column("width", sa.Float(), nullable=True),
        sa.Column("height", sa.Float(), nullable=True),
        sa.Column(
            "required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("default_value", sa.Text(), nullable=True),
        sa.Column("value", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_sig_field_envelope",
        "signature_fields",
        ["envelope_id"],
    )
    op.create_index(
        "ix_sig_field_party",
        "signature_fields",
        ["party_id"],
    )

    # ── 4. signature_events ─────────────────────────────────────────
    op.create_table(
        "signature_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "envelope_id",
            sa.String(36),
            sa.ForeignKey("signature_envelopes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "party_id",
            sa.String(36),
            sa.ForeignKey("signature_parties.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column(
            "actor_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "actor_party_id",
            sa.String(36),
            sa.ForeignKey("signature_parties.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "meta_json",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_sig_event_envelope_seq",
        "signature_events",
        ["envelope_id", "sequence_number"],
        unique=True,
    )
    op.create_index(
        "ix_sig_event_envelope_created",
        "signature_events",
        ["envelope_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_sig_event_event_type",
        "signature_events",
        ["event_type"],
    )

    # ── 5. Seed the 5 new signing-related platform templates ────────
    from app.services.documents._template_seeds import _signing_seeds

    now = datetime.now(timezone.utc)
    conn = op.get_bind()
    for seed in _signing_seeds():
        template_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        conn.execute(
            sa.text(
                """
                INSERT INTO document_templates (
                    id, company_id, template_key, document_type,
                    output_format, description, supports_variants,
                    current_version_id, is_active, created_at, updated_at
                ) VALUES (
                    :id, NULL, :template_key, :document_type,
                    :output_format, :description, :supports_variants,
                    NULL, TRUE, :now, :now
                )
                """
            ),
            {
                "id": template_id,
                "template_key": seed["template_key"],
                "document_type": seed["document_type"],
                "output_format": seed["output_format"],
                "description": seed.get("description"),
                "supports_variants": seed.get("supports_variants", False),
                "now": now,
            },
        )
        conn.execute(
            sa.text(
                """
                INSERT INTO document_template_versions (
                    id, template_id, version_number, status,
                    body_template, subject_template,
                    variable_schema, css_variables,
                    changelog, activated_at, created_at
                ) VALUES (
                    :id, :template_id, 1, 'active',
                    :body_template, :subject_template,
                    CAST(:variable_schema AS jsonb),
                    CAST(:css_variables AS jsonb),
                    :changelog, :now, :now
                )
                """
            ),
            {
                "id": version_id,
                "template_id": template_id,
                "body_template": seed["body_template"],
                "subject_template": seed.get("subject_template"),
                "variable_schema": None,
                "css_variables": None,
                "changelog": "Phase D-4 initial platform seed.",
                "now": now,
            },
        )
        conn.execute(
            sa.text(
                "UPDATE document_templates SET current_version_id = :v "
                "WHERE id = :t"
            ),
            {"v": version_id, "t": template_id},
        )


def downgrade() -> None:
    # Remove seeded platform templates first (referenced by nothing)
    conn = op.get_bind()
    for key in (
        "pdf.signature_certificate",
        "email.signing_invite",
        "email.signing_completed",
        "email.signing_declined",
        "email.signing_voided",
    ):
        conn.execute(
            sa.text(
                "DELETE FROM document_template_versions "
                "WHERE template_id IN ("
                "SELECT id FROM document_templates "
                "WHERE template_key = :k AND company_id IS NULL)"
            ),
            {"k": key},
        )
        conn.execute(
            sa.text(
                "DELETE FROM document_templates "
                "WHERE template_key = :k AND company_id IS NULL"
            ),
            {"k": key},
        )

    # Drop signing tables in reverse order (children first)
    op.drop_index(
        "ix_sig_event_event_type", table_name="signature_events"
    )
    op.drop_index(
        "ix_sig_event_envelope_created", table_name="signature_events"
    )
    op.drop_index(
        "ix_sig_event_envelope_seq", table_name="signature_events"
    )
    op.drop_table("signature_events")

    op.drop_index("ix_sig_field_party", table_name="signature_fields")
    op.drop_index("ix_sig_field_envelope", table_name="signature_fields")
    op.drop_table("signature_fields")

    op.drop_index(
        "ix_sig_party_envelope_status", table_name="signature_parties"
    )
    op.drop_index(
        "ix_sig_party_envelope_order", table_name="signature_parties"
    )
    op.drop_table("signature_parties")

    op.execute("DROP INDEX IF EXISTS ix_sig_env_expires_at_active")
    op.execute("DROP INDEX IF EXISTS ix_sig_env_status_active")
    op.drop_index(
        "ix_sig_env_document_id", table_name="signature_envelopes"
    )
    op.drop_index(
        "ix_sig_env_company_status_created",
        table_name="signature_envelopes",
    )
    op.drop_table("signature_envelopes")
