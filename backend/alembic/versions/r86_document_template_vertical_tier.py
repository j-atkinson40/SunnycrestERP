"""Document template vertical tier (Phase D-11, June 2026).

Extends `document_templates` from two-tier (platform → tenant) to
three-tier (platform → vertical → tenant) scope, matching the rest
of the visual editor's content types (themes, component_configurations,
focus_compositions all use three-tier).

Adds:
  - `vertical` String(32) nullable column on document_templates
  - CHECK constraint: `vertical IS NULL OR company_id IS NULL`
    (vertical-scoped templates are platform-level; tenant-scoped
    templates inherit the tenant's vertical at resolution time and
    don't carry a vertical attribute themselves)
  - Replaces `uq_document_templates_company_key` partial unique index
    with `uq_document_templates_company_vertical_key` covering all
    three discriminators

Resolution chain at READ time:
    platform_default(company_id=NULL, vertical=NULL)
        + vertical_default(company_id=NULL, vertical=<X>)
            + tenant_override(company_id=<Y>, vertical=NULL)

template_loader._resolve_version walks tenant → vertical → platform,
returning the first match. Existing two-tier rows (vertical=NULL)
behave exactly as before — no data migration needed for the 18
seeded platform templates.

Migration head: r85_document_template_blocks → r86_document_template_vertical_tier.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r86_document_template_vertical_tier"
down_revision = "r85_document_template_blocks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("document_templates")}

    # Add the vertical column if not already present.
    if "vertical" not in cols:
        op.add_column(
            "document_templates",
            sa.Column("vertical", sa.String(32), nullable=True),
        )

    # CHECK constraint: vertical and company_id are mutually exclusive
    # at the non-null position. Either:
    #   - both NULL          → platform_default
    #   - vertical set       → vertical_default (company_id NULL)
    #   - company_id set     → tenant_override (vertical NULL)
    # Postgres-only; SQLite (test fixtures) silently no-ops the CHECK.
    existing_checks = {
        c["name"] for c in inspector.get_check_constraints("document_templates")
    }
    if "ck_document_templates_scope_disjoint" not in existing_checks:
        op.create_check_constraint(
            "ck_document_templates_scope_disjoint",
            "document_templates",
            "vertical IS NULL OR company_id IS NULL",
        )

    # Replace the two-column partial unique with a three-column one.
    existing_indexes = {
        ix["name"] for ix in inspector.get_indexes("document_templates")
    }
    if "uq_document_templates_company_key" in existing_indexes:
        op.execute(
            "DROP INDEX IF EXISTS uq_document_templates_company_key"
        )
    if "uq_document_templates_company_vertical_key" not in existing_indexes:
        # Use IS NOT DISTINCT FROM semantics by including all three
        # columns; partial-unique on the canonical disjoint shape.
        op.execute(
            "CREATE UNIQUE INDEX uq_document_templates_company_vertical_key "
            "ON document_templates (company_id, vertical, template_key) "
            "WHERE deleted_at IS NULL"
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_indexes = {
        ix["name"] for ix in inspector.get_indexes("document_templates")
    }
    if "uq_document_templates_company_vertical_key" in existing_indexes:
        op.execute(
            "DROP INDEX IF EXISTS uq_document_templates_company_vertical_key"
        )
    # Restore the two-column partial unique index.
    if "uq_document_templates_company_key" not in existing_indexes:
        op.execute(
            "CREATE UNIQUE INDEX uq_document_templates_company_key "
            "ON document_templates (company_id, template_key) "
            "WHERE deleted_at IS NULL"
        )

    existing_checks = {
        c["name"] for c in inspector.get_check_constraints("document_templates")
    }
    if "ck_document_templates_scope_disjoint" in existing_checks:
        op.drop_constraint(
            "ck_document_templates_scope_disjoint",
            "document_templates",
            type_="check",
        )

    cols = {c["name"] for c in inspector.get_columns("document_templates")}
    if "vertical" in cols:
        op.drop_column("document_templates", "vertical")
