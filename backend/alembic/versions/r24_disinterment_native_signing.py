"""Bridgeable Documents Phase D-5 — disinterment on native signing.

Changes:
  - Adds `disinterment_cases.signature_envelope_id` FK to
    `signature_envelopes` (nullable — existing cases use DocuSign).
  - Partial index on that FK WHERE NOT NULL.
  - Extends `signature_fields` with `anchor_x_offset`, `anchor_y_offset`,
    `anchor_units` for tuning inline signature placement without
    re-rendering the source template.

Nothing is dropped — `docusign_envelope_id` + `sig_*` columns stay for
backward compatibility with in-flight DocuSign envelopes.

Revision ID: r24_disinterment_native_signing
Revises: r23_native_signing
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r24_disinterment_native_signing"
down_revision = "r23_native_signing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── disinterment_cases.signature_envelope_id ────────────────────
    op.add_column(
        "disinterment_cases",
        sa.Column(
            "signature_envelope_id",
            sa.String(36),
            sa.ForeignKey(
                "signature_envelopes.id", ondelete="SET NULL"
            ),
            nullable=True,
        ),
    )
    op.execute(
        "CREATE INDEX ix_disinterment_cases_signature_envelope "
        "ON disinterment_cases (signature_envelope_id) "
        "WHERE signature_envelope_id IS NOT NULL"
    )

    # ── signature_fields anchor offsets ─────────────────────────────
    op.add_column(
        "signature_fields",
        sa.Column(
            "anchor_x_offset",
            sa.Float(),
            nullable=True,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "signature_fields",
        sa.Column(
            "anchor_y_offset",
            sa.Float(),
            nullable=True,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "signature_fields",
        sa.Column(
            "anchor_units",
            sa.String(16),
            nullable=True,
            server_default=sa.text("'points'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("signature_fields", "anchor_units")
    op.drop_column("signature_fields", "anchor_y_offset")
    op.drop_column("signature_fields", "anchor_x_offset")

    op.execute(
        "DROP INDEX IF EXISTS ix_disinterment_cases_signature_envelope"
    )
    op.drop_column("disinterment_cases", "signature_envelope_id")
