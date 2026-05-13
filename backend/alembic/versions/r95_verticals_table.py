"""Verticals-lite precursor — `verticals` table + 4 canonical seeds.

Precursor to the Studio shell arc. Establishes the `verticals` table
as the canonical first-class registry for platform verticals (today
expressed as scattered `vertical` String(32) columns across 16+
tables). Going forward, any migration introducing a column referring
to a vertical must reference `verticals.slug` as a foreign key.

The existing String(32) nullable `vertical` columns on
`platform_themes`, `focus_compositions`, `workflow_templates`,
`document_templates`, `component_configurations`, `dashboard_layouts`,
`companies`, and others are preserved for backward compatibility. A
future cleanup arc may migrate these to FKs; new tables should not
perpetuate the String-not-FK pattern.

This migration:
  - Creates `verticals` table with slug PK + display_name + description
    + status enum (draft|published|archived) + icon + sort_order +
    created_at / updated_at timestamps.
  - Seeds 4 canonical verticals at status='published':
      manufacturing (sort_order=10)
      funeral_home  (sort_order=20)
      cemetery      (sort_order=30)
      crematory     (sort_order=40)

Spec-Override Discipline note (CLAUDE.md §12): build spec named the
revision `r92_verticals_table` revising `r91_compositions_kind_and_pages`,
but `r92_workflow_review_items` (R-6.0a), `r93_workflow_email_classification`
(R-6.1a), and `r94_intake_adapter_configurations` (R-6.2a) had
already landed since STATE.md last refreshed. Renamed to
`r95_verticals_table` revising the actual current head
`r94_intake_adapter_configurations`. Schema + seeds identical to spec.

Pattern mirrors r87_dashboard_layouts (canonical migration precedent
with seed inserts) and existing idempotency op-wrapper convention.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r95_verticals_table"
down_revision = "r94_intake_adapter_configurations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "verticals" in set(inspector.get_table_names()):
        return

    op.create_table(
        "verticals",
        sa.Column("slug", sa.String(32), primary_key=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'published'"),
        ),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_verticals_status",
        ),
    )

    # Seed 4 canonical verticals. Idempotent at the migration boundary
    # via the table-exists short-circuit at the top of upgrade().
    op.execute(
        sa.text(
            """
            INSERT INTO verticals (slug, display_name, status, sort_order)
            VALUES
                ('manufacturing', 'Manufacturing', 'published', 10),
                ('funeral_home', 'Funeral Home', 'published', 20),
                ('cemetery', 'Cemetery', 'published', 30),
                ('crematory', 'Crematory', 'published', 40)
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "verticals" not in set(inspector.get_table_names()):
        return
    op.drop_table("verticals")
