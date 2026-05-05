"""Calendar Step 4.1 — PTR consent metadata columns.

Per Q3 confirmed pre-build: add `calendar_freebusy_consent_updated_at`
+ `calendar_freebusy_consent_updated_by` nullable columns on
`platform_tenant_relationships` for settings-page rendering ergonomics
("Last updated 3 days ago by Jane") without dipping into audit log on
every list-view query.

**Storage shape canonical (Q1 confirmed)**: existing
`calendar_freebusy_consent` column shipped at Step 3 (Calendar Step 3
read-side enforcement) is canonically complete for the bilateral
state machine. PTR's existing per-direction-row architecture already
encodes per-side intent without additional columns — Step 4.1 ships
service-layer state machine + audit trail + UI without schema rework
of the consent column itself.

These two metadata columns are bounded ergonomic affordances.
NULL when consent has never been changed (Step 4.1 doesn't backfill
prior Step 3 default-state rows; only stamps on first state flip).

Revision ID: r72_ptr_consent_metadata
Revises: r71_calendar_step4_actions
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r72_ptr_consent_metadata"
down_revision = "r71_calendar_step4_actions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {
        col["name"]
        for col in inspector.get_columns("platform_tenant_relationships")
    }

    if "calendar_freebusy_consent_updated_at" not in columns:
        op.add_column(
            "platform_tenant_relationships",
            sa.Column(
                "calendar_freebusy_consent_updated_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )

    if "calendar_freebusy_consent_updated_by" not in columns:
        op.add_column(
            "platform_tenant_relationships",
            sa.Column(
                "calendar_freebusy_consent_updated_by",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {
        col["name"]
        for col in inspector.get_columns("platform_tenant_relationships")
    }

    if "calendar_freebusy_consent_updated_by" in columns:
        op.drop_column(
            "platform_tenant_relationships",
            "calendar_freebusy_consent_updated_by",
        )

    if "calendar_freebusy_consent_updated_at" in columns:
        op.drop_column(
            "platform_tenant_relationships",
            "calendar_freebusy_consent_updated_at",
        )
