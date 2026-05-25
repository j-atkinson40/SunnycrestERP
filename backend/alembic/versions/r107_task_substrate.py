"""Task substrate v1.0 — VaultItem 12th item_type 'task' + task_details.

Ships the v1.0 substrate phase of the task substrate v1 build arc
(state doc §5.1; phasing §1.1; build prompt §5.1).

Schema changes:

1. **VaultItem.item_type enum extension.** Adds 'task' as the 12th value.
   The column is `String(30)` with NO DB CHECK constraint — enum values
   are validated at the Python layer only (`vault_item.py:28-30` comment
   is the documentation surface). This migration adds nothing at the
   column-type level; the value extension is documented + tested.

2. **New `task_details` table.** 1:1 join with VaultItem rows where
   `item_type='task'`. Operator Lock 1 (Shape A): the existing `tasks`
   table stays as-is; new task_details table holds the substrate-shape
   columns; Task façade reads through join. Existing 8 Task consumers
   continue working via service-layer + façade.

   Columns: id, vault_item_id (UNIQUE), assignee_realm, assignee_user_id,
   assignee_portal_user_id (forward-compat for v2 portal), lifecycle_shape,
   current_state, provenance_kind (12 values), provenance_ref_type,
   provenance_ref_id, event_kind, visibility (5 values), priority,
   due_date, due_datetime, assigned_at, completed_at, resolution_outcome,
   suppression_key, created_at, updated_at.

3. **Six indexes** per state doc §5.1:
   - assignee_state (assignee_user_id, current_state) partial
   - due_date partial
   - provenance composite partial
   - PARTIAL UNIQUE idempotency on (provenance_kind, provenance_ref_type,
     provenance_ref_id, event_kind) WHERE provenance_ref_id IS NOT NULL
   - vault_item_id (explicit; UNIQUE constraint creates implicit but
     explicit name is helpful for diagnostics)
   - lifecycle_state (lifecycle_shape, current_state)

FK semantics (operator Lock 2):
- task_details.vault_item_id → vault_items.id ON DELETE CASCADE
- task_details.assignee_user_id → users.id ON DELETE SET NULL
- task_details.assignee_portal_user_id → portal_users.id ON DELETE SET NULL

Idempotent: each DDL step gated on inspector-reported state. Matches the
r103/r105/r106 precedent.

Reversible: downgrade drops indexes + table.

Migration head: r106_widget_definitions_published_blob → r107.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "r107_task_substrate"
down_revision = "r106_widget_definitions_published_blob"
branch_labels = None
depends_on = None


_TABLE = "task_details"


def _table_exists(bind, table_name: str) -> bool:
    insp = sa.inspect(bind)
    return table_name in insp.get_table_names()


def _existing_indexes(bind, table_name: str) -> set[str]:
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return set()
    return {idx["name"] for idx in insp.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. Create task_details table ─────────────────────────────────
    if not _table_exists(bind, _TABLE):
        op.create_table(
            _TABLE,
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "vault_item_id",
                sa.String(length=36),
                sa.ForeignKey("vault_items.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column(
                "assignee_realm",
                sa.String(length=20),
                nullable=False,
                server_default="user",
            ),
            sa.Column(
                "assignee_user_id",
                sa.String(length=36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "assignee_portal_user_id",
                sa.String(length=36),
                # Forward-compat: portal_users table exists from r42.
                # FK declared so the column carries semantic intent.
                sa.ForeignKey("portal_users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("lifecycle_shape", sa.String(length=16), nullable=False),
            sa.Column("current_state", sa.String(length=32), nullable=False),
            sa.Column("provenance_kind", sa.String(length=32), nullable=False),
            sa.Column("provenance_ref_type", sa.String(length=64), nullable=True),
            sa.Column("provenance_ref_id", sa.String(length=36), nullable=True),
            sa.Column(
                "event_kind",
                sa.String(length=64),
                nullable=False,
                server_default="manual",
            ),
            sa.Column(
                "visibility",
                sa.String(length=24),
                nullable=False,
                server_default="operator_internal",
            ),
            sa.Column(
                "priority",
                sa.String(length=16),
                nullable=False,
                server_default="normal",
            ),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column(
                "due_datetime", sa.DateTime(timezone=True), nullable=True
            ),
            sa.Column(
                "assigned_at", sa.DateTime(timezone=True), nullable=True
            ),
            sa.Column(
                "completed_at", sa.DateTime(timezone=True), nullable=True
            ),
            sa.Column(
                "resolution_outcome", sa.String(length=64), nullable=True
            ),
            sa.Column("suppression_key", sa.String(length=128), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            # CHECK constraints documenting enum vocabularies. Values
            # validated at service layer too; DB-level CHECK gives a
            # secondary safety net.
            sa.CheckConstraint(
                "assignee_realm IN ('user', 'portal_user')",
                name="ck_task_details_assignee_realm",
            ),
            sa.CheckConstraint(
                "lifecycle_shape IN ('action', 'reminder')",
                name="ck_task_details_lifecycle_shape",
            ),
            sa.CheckConstraint(
                "visibility IN ('operator_internal', 'operator_assigned', "
                "'portal_family', 'portal_contractor', 'portal_partner')",
                name="ck_task_details_visibility",
            ),
            sa.CheckConstraint(
                "priority IN ('low', 'normal', 'high', 'urgent')",
                name="ck_task_details_priority",
            ),
            sa.CheckConstraint(
                "provenance_kind IN ("
                "'workflow_step', 'intelligence_observation', "
                "'manual_creation', 'communication_inbound', "
                "'integration_event', 'shelf_parking', "
                "'coaching_observation', 'scheduled_recurring', "
                "'triage_event', 'focus_completion', "
                "'anomaly_detection', 'system_internal'"
                ")",
                name="ck_task_details_provenance_kind",
            ),
        )

    # ── 2. Indexes ───────────────────────────────────────────────────
    existing = _existing_indexes(bind, _TABLE)

    if "ix_task_details_vault_item_id" not in existing:
        op.create_index(
            "ix_task_details_vault_item_id",
            _TABLE,
            ["vault_item_id"],
        )

    if "ix_task_details_assignee_state" not in existing:
        op.create_index(
            "ix_task_details_assignee_state",
            _TABLE,
            ["assignee_user_id", "current_state"],
            postgresql_where=sa.text("assignee_user_id IS NOT NULL"),
        )

    if "ix_task_details_due_date" not in existing:
        op.create_index(
            "ix_task_details_due_date",
            _TABLE,
            ["due_date"],
            postgresql_where=sa.text("due_date IS NOT NULL"),
        )

    if "ix_task_details_provenance" not in existing:
        op.create_index(
            "ix_task_details_provenance",
            _TABLE,
            ["provenance_kind", "provenance_ref_type", "provenance_ref_id"],
            postgresql_where=sa.text("provenance_ref_id IS NOT NULL"),
        )

    if "ix_task_details_lifecycle_state" not in existing:
        op.create_index(
            "ix_task_details_lifecycle_state",
            _TABLE,
            ["lifecycle_shape", "current_state"],
        )

    # Load-bearing idempotency partial unique (state doc §5.3) —
    # prevents duplicate task creation on producer retry.
    if "uq_task_details_idempotency" not in existing:
        op.create_index(
            "uq_task_details_idempotency",
            _TABLE,
            [
                "provenance_kind",
                "provenance_ref_type",
                "provenance_ref_id",
                "event_kind",
            ],
            unique=True,
            postgresql_where=sa.text("provenance_ref_id IS NOT NULL"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing = _existing_indexes(bind, _TABLE)

    for ix in (
        "uq_task_details_idempotency",
        "ix_task_details_lifecycle_state",
        "ix_task_details_provenance",
        "ix_task_details_due_date",
        "ix_task_details_assignee_state",
        "ix_task_details_vault_item_id",
    ):
        if ix in existing:
            op.drop_index(ix, table_name=_TABLE)

    if _table_exists(bind, _TABLE):
        op.drop_table(_TABLE)
