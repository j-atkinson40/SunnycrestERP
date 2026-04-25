"""Phase B Session 4 Phase 4.3.3 — tenant default driver start time.

Revision ID: r57_delivery_settings_default_start_time
Revises: r56_ancillary_and_helper_assignment

Adds ``delivery_settings.default_driver_start_time`` (TEXT, default
``'07:00'``). Each tenant has one DeliverySettings row; this column
holds the tenant-wide weekday default driver start time used when a
delivery's own ``driver_start_time`` is NULL.

Phase 4.3.2 added ``deliveries.driver_start_time`` (per-delivery
override). Phase 4.3.3 adds the tenant-default fallback so the
QuickEditDialog's "Use default" toggle has a real backing value.

**Semantic** (mirrored in DeliverySettings model docstring):
    Default start time for weekday deliveries. Weekend deliveries
    (Saturday especially) typically specify explicit start times
    per delivery due to overtime rules. NULL
    delivery.driver_start_time = use this default.

**Format**: TEXT 'HH:MM' (e.g. '07:00', '06:30'). Stored as string,
not TIME, because the value is interpreted as tenant-local time
when a delivery is dispatched, not as a UTC instant.

**Backfill**: every existing DeliverySettings row gets '07:00' by
the column default. Idempotent — re-running adds the column once
(env.py monkey-patches add_column for idempotency).

**Downgrade**: drops the column. No data preserved (default is
recoverable from the spec).
"""

from alembic import op
import sqlalchemy as sa


revision = "r57_delivery_settings_default_start_time"
down_revision = "r56_ancillary_and_helper_assignment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "delivery_settings",
        sa.Column(
            "default_driver_start_time",
            sa.String(length=5),
            nullable=False,
            server_default="07:00",
        ),
    )


def downgrade() -> None:
    op.drop_column("delivery_settings", "default_driver_start_time")
