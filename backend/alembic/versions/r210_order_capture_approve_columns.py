"""The six captured fields with no home, plus the capture session's order link.

⚠️ EXPAND-ONLY, EVERY COLUMN NULLABLE, NO SERVER DEFAULT AND NO MODEL-SIDE
`default=`. These columns are added to POPULATED tables — production holds 37
`sales_orders` rows — so any non-null value would assert something about every
existing row that nothing has measured. CLAUDE.md §5: "not established" must stay
distinguishable from a measured value, and the literal form of that mistake is the
one a default-focused review cannot see. NULL here means "this order predates typed
capture", which is a different fact from "this order has no burial date".

⚠️ `cemetery_city` IS DELIBERATELY ABSENT, and that is Q5 from the investigation
answered. The capture captures a typed cemetery town and raises a pick when it
disagrees with the record; once `cemetery_id` is set the record's city is
authoritative and a second copy on the order is a second source of truth for one
fact. The typed value survives where it belongs — in `capture_sessions.full_text`,
which is the order's own words.

⚠️ `nameplate_date_format` GOES ON THE TASK, NOT THE ORDER. It describes how the
nameplate renders its dates, which is a property of the personalization work, and
`order_personalization_tasks` is the table the personalization flow reads. The
closest precedent in the codebase agrees: `case_merchandise.monument_dates_format`
sits with the monument, not with the case.

⚠️ `capture_sessions.sales_order_id` IS WHAT MAKES APPROVE IDEMPOTENT. A second
click, a replayed request or a repeated "approve" finds the link already set and
returns the same order instead of minting another. The uniqueness is enforced by
reading that column inside the approving transaction, not by a constraint — a
UNIQUE index would also forbid two sessions legitimately pointing at one order,
which is what a re-open would do.

Revision ID: r210_order_capture_approve_columns
Revises: r209_capture_session_switches
"""
import sqlalchemy as sa
from alembic import op

# ⚠️ IMPORTED EXPLICITLY. `sa.dialects.postgresql` does not resolve on a bare
# interpreter — measured 2026-10-13 — and relying on alembic's env.py having
# imported it first is relying on an import order inside someone else's module, on
# the one code path that writes production.
from sqlalchemy.dialects import postgresql  # noqa: F401

revision = "r210_order_capture_approve_columns"
down_revision = "r209_capture_session_switches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sales_orders", sa.Column("burial_date", sa.Date(), nullable=True))
    op.add_column(
        "sales_orders", sa.Column("grave_location", sa.String(length=120), nullable=True)
    )
    op.add_column("sales_orders", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("sales_orders", sa.Column("date_of_death", sa.Date(), nullable=True))
    op.add_column(
        "order_personalization_tasks",
        sa.Column("nameplate_date_format", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "capture_sessions",
        sa.Column("sales_order_id", sa.String(length=36), nullable=True),
    )
    # ⚠️ `ON DELETE SET NULL`, STATED RATHER THAN DEFAULTED. CLAUDE.md §5: a foreign
    # key specifies DELETE behaviour too, and its default is NO ACTION — which would
    # make deleting a sales order raise for any session that had approved it. A
    # capture session outliving its order is a real state (the order was deleted);
    # a delete that fails is not.
    op.create_foreign_key(
        "fk_capture_sessions_sales_order_id",
        "capture_sessions",
        "sales_orders",
        ["sales_order_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # ⚠️ THE STATUS CHECK HAS TO LEARN THE NEW VALUE, AND THE DATABASE IS WHAT TOLD
    # ME. `ck_capture_sessions_status` (r203) enumerates
    # ('capturing','review','abandoned'); writing `approved` raised CheckViolation on
    # the first run of the approve tests. A constraint doing its job — and a reminder
    # that a status vocabulary living in two places (the model's tuple and this
    # CHECK) only stays honest if both move together.
    #
    # ⚠️ DROP-THEN-CREATE RATHER THAN ALTER, because Postgres has no ALTER for a
    # check's expression. The new constraint is the old one plus `approved`; nothing
    # is loosened.
    op.drop_constraint("ck_capture_sessions_status", "capture_sessions", type_="check")
    op.create_check_constraint(
        "ck_capture_sessions_status",
        "capture_sessions",
        "status IN ('capturing', 'review', 'abandoned', 'approved')",
    )


def downgrade() -> None:
    # ⚠️ ROWS CARRYING THE NEW VALUE WOULD BREAK THE OLD CHECK, so they are moved
    # back to `review` — which is where they were a moment before being approved —
    # BEFORE the narrower constraint goes back on. A downgrade that recreated the
    # constraint first would fail on exactly the rows this migration made possible.
    op.execute(
        "UPDATE capture_sessions SET status = 'review' WHERE status = 'approved'"
    )
    op.drop_constraint("ck_capture_sessions_status", "capture_sessions", type_="check")
    op.create_check_constraint(
        "ck_capture_sessions_status",
        "capture_sessions",
        "status IN ('capturing', 'review', 'abandoned')",
    )
    op.drop_constraint(
        "fk_capture_sessions_sales_order_id", "capture_sessions", type_="foreignkey"
    )
    op.drop_column("capture_sessions", "sales_order_id")
    op.drop_column("order_personalization_tasks", "nameplate_date_format")
    op.drop_column("sales_orders", "date_of_death")
    op.drop_column("sales_orders", "date_of_birth")
    op.drop_column("sales_orders", "grave_location")
    op.drop_column("sales_orders", "burial_date")
