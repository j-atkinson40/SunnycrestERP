"""Add disinterment_management extension to the extension catalog.

Moves disinterment from the module system to the extension catalog so it
appears in the Extension Library UI for tenant self-service install.

Revision ID: r8_disinterment_ext
Revises: r7_create_missing
Create Date: 2026-04-08
"""

import json
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "r8_disinterment_ext"
down_revision = "r7_create_missing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # Check if extension already exists
    existing = bind.execute(
        sa.text(
            "SELECT id FROM extension_definitions WHERE extension_key = :key"
        ),
        {"key": "disinterment_management"},
    ).fetchone()

    if existing:
        return  # Already seeded

    now = datetime.now(timezone.utc)

    bind.execute(
        sa.text("""
            INSERT INTO extension_definitions (
                id, extension_key, module_key, display_name, description,
                tagline, section, category, publisher,
                applicable_verticals, default_enabled_for,
                access_model, status, version,
                feature_bullets, setup_required,
                setup_config_schema, sort_order, is_active,
                created_at, updated_at
            ) VALUES (
                :id, :key, :mod, :name, :desc,
                :tagline, :section, :category, :publisher,
                :verticals, :default_for,
                :access, :status, :version,
                :bullets, :setup,
                :schema, :sort, true,
                :now, :now
            )
        """),
        {
            "id": str(uuid.uuid4()),
            "key": "disinterment_management",
            "mod": "core",
            "name": "Disinterment Management",
            "desc": (
                "End-to-end disinterment case management with a 5-stage pipeline: "
                "intake form, quote acceptance, DocuSign 4-party signatures, scheduling "
                "with union rotation assignment, and automatic invoice generation on "
                "completion. Includes a public intake form that funeral directors fill "
                "out on their phone."
            ),
            "tagline": "5-stage disinterment pipeline with DocuSign signatures and union rotation assignment",
            "section": "core",
            "category": "workflow",
            "publisher": "first_party",
            "verticals": json.dumps(["manufacturing"]),
            "default_for": json.dumps([]),
            "access": "included",
            "status": "active",
            "version": "1.0.0",
            "bullets": json.dumps([
                "Public intake form — funeral directors submit from their phone",
                "5-stage pipeline: Intake → Quote → Signatures → Schedule → Complete",
                "DocuSign integration with 4-party signatures (FH, cemetery, NOK, manufacturer)",
                "Union rotation auto-assignment for hazard pay jobs",
                "Automatic invoice generation on case completion",
                "Configurable charge types with hazard pay tracking",
            ]),
            "setup": True,
            "schema": json.dumps({
                "type": "object",
                "properties": {
                    "docusign_manufacturer_signer_email": {
                        "type": "string",
                        "title": "Manufacturer Signer Email",
                        "description": "Email address of the person who signs disinterment release forms on behalf of your company",
                    },
                },
            }),
            "sort": 5,
            "now": now,
        },
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "DELETE FROM extension_definitions WHERE extension_key = :key"
        ),
        {"key": "disinterment_management"},
    )
