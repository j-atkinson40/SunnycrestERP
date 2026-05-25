"""TaskDetails — task substrate v1.0 join table.

1:1 with VaultItem rows where `item_type='task'`. Holds the substrate-
shape columns the task substrate v1 build arc adds. Existing `tasks`
table preserved (operator Lock 1, Shape A — see r107).

FK semantics (operator Lock 2):
- vault_item_id → vault_items.id ON DELETE CASCADE
- assignee_user_id → users.id ON DELETE SET NULL
- assignee_portal_user_id → portal_users.id ON DELETE SET NULL

Idempotency: see partial-unique on (provenance_kind, provenance_ref_type,
provenance_ref_id, event_kind) WHERE provenance_ref_id IS NOT NULL —
load-bearing for producer-site retry safety per state doc §5.3.

Lifecycle: dual-shape per state doc §5.2 — `action` shape (created /
assigned / in_progress / blocked / done / cancelled) + `reminder` shape
(informational / acknowledged / dismissed). State machine + transition
guards live in `app/services/tasks/lifecycle.py`.

Visibility: 5 values per state doc §5.5. v1 operator-only filter applied
at service + API layers; `portal_*` values are schema forward-compat for
v2/v3 portal extensions.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TaskDetails(Base):
    __tablename__ = "task_details"
    __table_args__ = (
        CheckConstraint(
            "assignee_realm IN ('user', 'portal_user')",
            name="ck_task_details_assignee_realm",
        ),
        CheckConstraint(
            "lifecycle_shape IN ('action', 'reminder')",
            name="ck_task_details_lifecycle_shape",
        ),
        CheckConstraint(
            "visibility IN ('operator_internal', 'operator_assigned', "
            "'portal_family', 'portal_contractor', 'portal_partner')",
            name="ck_task_details_visibility",
        ),
        CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name="ck_task_details_priority",
        ),
        CheckConstraint(
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

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    vault_item_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("vault_items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Assignee — dual-realm (tenant User vs PortalUser). v1 writes only
    # the 'user' realm; v2 portal arc enables 'portal_user'.
    assignee_realm: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user"
    )
    assignee_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    assignee_portal_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("portal_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Dual-shape lifecycle (state doc §5.2).
    lifecycle_shape: Mapped[str] = mapped_column(
        String(16), nullable=False
    )
    current_state: Mapped[str] = mapped_column(
        String(32), nullable=False
    )

    # Provenance — 12 values per state doc §5.3.
    provenance_kind: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    provenance_ref_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    provenance_ref_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    event_kind: Mapped[str] = mapped_column(
        String(64), nullable=False, default="manual"
    )

    # Visibility — 5 values per state doc §5.5; operator-only filter v1.
    visibility: Mapped[str] = mapped_column(
        String(24), nullable=False, default="operator_internal"
    )
    priority: Mapped[str] = mapped_column(
        String(16), nullable=False, default="normal"
    )

    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_datetime: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_outcome: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    suppression_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships.
    vault_item = relationship("VaultItem", foreign_keys=[vault_item_id])
    assignee_user = relationship("User", foreign_keys=[assignee_user_id])


# ── Frozen enum vocabularies ────────────────────────────────────────────

ASSIGNEE_REALMS: tuple[str, ...] = ("user", "portal_user")

LIFECYCLE_SHAPES: tuple[str, ...] = ("action", "reminder")

ACTION_STATES: tuple[str, ...] = (
    "created",
    "assigned",
    "in_progress",
    "blocked",
    "done",
    "cancelled",
)

REMINDER_STATES: tuple[str, ...] = (
    "informational",
    "acknowledged",
    "dismissed",
)

PROVENANCE_KINDS: tuple[str, ...] = (
    "workflow_step",
    "intelligence_observation",
    "manual_creation",
    "communication_inbound",
    "integration_event",
    "shelf_parking",
    "coaching_observation",
    "scheduled_recurring",
    "triage_event",
    "focus_completion",
    "anomaly_detection",
    "system_internal",
)

VISIBILITY_VALUES: tuple[str, ...] = (
    "operator_internal",
    "operator_assigned",
    "portal_family",
    "portal_contractor",
    "portal_partner",
)

TASK_DETAILS_PRIORITIES: tuple[str, ...] = (
    "low",
    "normal",
    "high",
    "urgent",
)


__all__ = [
    "TaskDetails",
    "ASSIGNEE_REALMS",
    "LIFECYCLE_SHAPES",
    "ACTION_STATES",
    "REMINDER_STATES",
    "PROVENANCE_KINDS",
    "VISIBILITY_VALUES",
    "TASK_DETAILS_PRIORITIES",
]
