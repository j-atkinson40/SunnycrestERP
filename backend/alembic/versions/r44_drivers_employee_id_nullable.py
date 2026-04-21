"""Workflow Arc Phase 8e.2.1 — make drivers.employee_id nullable.

Part 1 of the employee_id retirement. Per the Phase 8e.2.1 audit
(Option b): rather than drop the column in one phase, we relax
nullability + rewrite code consumers to use `portal_user_id` as the
canonical driver-identity path. The actual column drop lands in the
dedicated latent-bug cleanup session after verifying zero production
consumers.

Why nullable-not-dropped:
  - Audit found real code consumers (delivery_service, widget_data,
    schemas, frontend types) that break if the column vanishes.
    Phase 8e.2.1 rewrites those consumers to `portal_user_id`.
  - Dev DB at audit time had 8 driver rows with employee_id set —
    production status unknown. Nullable keeps the data; a future
    cleanup migration drops the column once production is verified
    empty.
  - Business-logic invariant (NOT DB CHECK) after 8e.2.1:
    `portal_user_id` is required for NEW drivers; existing
    employee_id-only drivers are treated as legacy during the
    transition window.

Revision ID: r44_drivers_employee_id_nullable
Down Revision: r43_portal_password_email_template
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "r44_drivers_employee_id_nullable"
down_revision = "r43_portal_password_email_template"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Report current population for operator awareness.
    conn = op.get_bind()
    populated_count = conn.execute(
        sa.text("SELECT COUNT(*) FROM drivers WHERE employee_id IS NOT NULL")
    ).scalar() or 0
    portal_count = conn.execute(
        sa.text("SELECT COUNT(*) FROM drivers WHERE portal_user_id IS NOT NULL")
    ).scalar() or 0
    total = conn.execute(sa.text("SELECT COUNT(*) FROM drivers")).scalar() or 0
    print(
        f"[r44] drivers table: total={total} "
        f"with_employee_id={populated_count} "
        f"with_portal_user_id={portal_count}"
    )

    # Relax nullability. Data unchanged.
    op.alter_column(
        "drivers",
        "employee_id",
        existing_type=sa.String(36),
        nullable=True,
    )


def downgrade() -> None:
    # Re-tighten to NOT NULL. Will fail if any rows have NULL
    # employee_id — by design (downgrade safety).
    op.alter_column(
        "drivers",
        "employee_id",
        existing_type=sa.String(36),
        nullable=False,
    )
