"""Phase B Session 4 Phase 4.3.2 — ancillary three-state model + helper FK.

Revision ID: r56_ancillary_and_helper_assignment
Revises: r50_dispatch_hole_dug_default

Phase 4.3 adds the ancillary three-state model (pool / standalone /
attached) and the helper-user concept. This migration makes the
schema changes; application-layer rename + service methods + UI
ship alongside.

**What this migration does:**

1. **Renames `deliveries.assigned_driver_id` → `deliveries.primary_assignee_id`,
   adds FK to `users.id` (was: bare String(36), no FK).**

   Pre-4.3 the column name implied a Driver (domain: licensed driver
   doing vault routes). Phase 4.3 operational reality includes
   office staff and any tenant user occasionally covering deliveries
   — "any tenant user is a primary assignee." The existing values
   stored `drivers.id`, not `users.id`, so this migration translates
   every value via the `drivers.employee_id` link (employee_id FKs
   to users.id; it's the canonical tenant-user identity for a
   Driver record).

   Data translation:
     - Resolvable: `drivers.employee_id IS NOT NULL AND user exists`
       → primary_assignee_id = drivers.employee_id
     - Unresolvable: seed-data Drivers with `employee_id=NULL` AND
       `portal_user_id=NULL` → primary_assignee_id = NULL. Admins
       reassign post-migration via the Scheduling Focus drag UI.

   Dev-DB audit at author time: 25 deliveries with assignment,
   16 resolvable, 9 unresolvable (bare seed-data drivers).

   **Portal-driver gap (known, tracked):** Phase 8e.2 Drivers with
   `portal_user_id` set but `employee_id=NULL` cannot be assigned
   via this new FK — their identity lives in `portal_users`, not
   `users`. Zero such deliveries in dev DB; production Sunnycrest
   uses Phase 8e.2's non-destructive migration (all Drivers still
   `employee_id`-backed). Portal-only driver kanban-assignment is a
   post-September follow-up.

2. **Adds `attached_to_delivery_id`** — self-referential FK to
   `deliveries.id`, ON DELETE SET NULL. Nullable. Indexed (partial
   on non-null). Represents the Phase 4.3 three-state model:
     - NULL + primary_assignee_id=NULL + requested_date=NULL → pool
     - NULL + primary_assignee_id set + requested_date set → standalone
     - set → attached (parent is another kanban Delivery)

   No auto-backfill. Audit: 0 ambiguous order_id rows (1:N), 0
   resolvable 1:1 rows, 3 pure-ancillary orders (no kanban parent).
   All existing ancillaries start in the pool state; dispatchers
   establish pairings via drag in Phase 4.3b.

3. **Adds `helper_user_id`** — FK to `users.id`, ON DELETE SET NULL.
   Nullable. Indexed (partial on non-null). Optional second person
   accompanying a delivery. Shown as icon+tooltip in card status
   row per Phase 4.3.4 spec. Populated via PATCH /deliveries/{id}.

4. **Adds `driver_start_time`** — TIME NULL. Per-delivery start-of-
   day target (when the assignee should start this delivery). Not
   the ETA or service time; an assignee-facing scheduling hint.

**Migration style notes:**

- Uses `with op.batch_alter_table("deliveries")` so downgrade is
  clean on SQLite (test env).
- Data translation runs as a DB-side UPDATE (no Python row-by-row).
- FK constraint names explicit per existing convention
  (`fk_<table>_<column>`).
- Partial indexes (WHERE ... IS NOT NULL) for sparse fields.

**Downgrade:**

Reverses in the opposite order. Data translation is LOSSY at
downgrade: `primary_assignee_id` values map back to the Driver.id
whose employee_id equals the user_id (if any). Rows that went NULL
on the forward migration stay NULL on reverse. Rows that had
valid drivers.employee_id on forward (16 in dev) can round-trip.

**Filename collision note:** orphaned chain files r51_ai_settings.py
through r55_name_suggestions.py exist in alembic/versions/ but
trace back to a dead `r47_activity_log` base. Live alembic head is
`r50_dispatch_hole_dug_default`. Skipping to r56 avoids
the visual confusion of a dual-r51 directory and sidesteps any
future re-use concerns if the orphan chain is ever revived.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "r56_ancillary_and_helper_assignment"
down_revision = "r50_dispatch_hole_dug_default"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Rename assigned_driver_id → primary_assignee_id +
    #       add FK to users.id.
    #
    # Strategy: add the new column first, populate it via translation,
    # then drop the old column. Not a single ALTER COLUMN RENAME
    # because we need the type translation (driver.id → user.id) to
    # happen atomically with the rename. Add-then-drop is also safer
    # for rollback rehearsal.

    op.add_column(
        "deliveries",
        sa.Column("primary_assignee_id", sa.String(length=36), nullable=True),
    )

    # Translate data: deliveries.assigned_driver_id stored driver.id
    # values. Resolve via drivers.employee_id (which FKs to users.id).
    # Rows where employee_id is NULL (portal-only drivers or bare
    # seed-data drivers with neither linkage) fall through to NULL.
    op.execute(
        """
        UPDATE deliveries d
        SET primary_assignee_id = drv.employee_id
        FROM drivers drv
        INNER JOIN users u ON u.id = drv.employee_id
        WHERE d.assigned_driver_id IS NOT NULL
          AND drv.id = d.assigned_driver_id
          AND drv.employee_id IS NOT NULL
        """
    )

    # FK constraint + index for the new column. Partial index because
    # the majority of rows are NULL (unassigned) — sparse FK.
    op.create_foreign_key(
        "fk_deliveries_primary_assignee_id",
        "deliveries",
        "users",
        ["primary_assignee_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_deliveries_primary_assignee_id",
        "deliveries",
        ["primary_assignee_id"],
        postgresql_where=sa.text("primary_assignee_id IS NOT NULL"),
    )

    # Drop the legacy column. Any lingering application-layer
    # references will fail loudly post-deploy; the Phase 4.3.2
    # application-layer rename sweeps them all.
    op.drop_column("deliveries", "assigned_driver_id")

    # ── 2. Add attached_to_delivery_id (self-referential FK) ──

    op.add_column(
        "deliveries",
        sa.Column(
            "attached_to_delivery_id",
            sa.String(length=36),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_deliveries_attached_to_delivery_id",
        "deliveries",
        "deliveries",
        ["attached_to_delivery_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_deliveries_attached_to_delivery_id",
        "deliveries",
        ["attached_to_delivery_id"],
        postgresql_where=sa.text("attached_to_delivery_id IS NOT NULL"),
    )

    # ── 3. Add helper_user_id (FK users.id) ──

    op.add_column(
        "deliveries",
        sa.Column("helper_user_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_deliveries_helper_user_id",
        "deliveries",
        "users",
        ["helper_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_deliveries_helper_user_id",
        "deliveries",
        ["helper_user_id"],
        postgresql_where=sa.text("helper_user_id IS NOT NULL"),
    )

    # ── 4. Add driver_start_time (TIME) ──

    op.add_column(
        "deliveries",
        sa.Column("driver_start_time", sa.Time(), nullable=True),
    )


def downgrade() -> None:
    # Reverse order — constraints + indexes before columns.

    # 4. driver_start_time
    op.drop_column("deliveries", "driver_start_time")

    # 3. helper_user_id
    op.drop_index("ix_deliveries_helper_user_id", table_name="deliveries")
    op.drop_constraint(
        "fk_deliveries_helper_user_id", "deliveries", type_="foreignkey"
    )
    op.drop_column("deliveries", "helper_user_id")

    # 2. attached_to_delivery_id
    op.drop_index(
        "ix_deliveries_attached_to_delivery_id", table_name="deliveries"
    )
    op.drop_constraint(
        "fk_deliveries_attached_to_delivery_id",
        "deliveries",
        type_="foreignkey",
    )
    op.drop_column("deliveries", "attached_to_delivery_id")

    # 1. primary_assignee_id → assigned_driver_id reverse translation.
    # Re-add the old column first so we can populate it.
    op.add_column(
        "deliveries",
        sa.Column(
            "assigned_driver_id", sa.String(length=36), nullable=True
        ),
    )

    # Reverse-translate: user_id → driver.id via drivers.employee_id.
    # Rows where primary_assignee_id is NULL (including those that
    # were made NULL by forward migration's unresolvable cases) stay
    # NULL — no way to recover the original driver.id from nothing.
    op.execute(
        """
        UPDATE deliveries d
        SET assigned_driver_id = drv.id
        FROM drivers drv
        WHERE d.primary_assignee_id IS NOT NULL
          AND drv.employee_id = d.primary_assignee_id
        """
    )

    op.drop_index(
        "ix_deliveries_primary_assignee_id", table_name="deliveries"
    )
    op.drop_constraint(
        "fk_deliveries_primary_assignee_id",
        "deliveries",
        type_="foreignkey",
    )
    op.drop_column("deliveries", "primary_assignee_id")
