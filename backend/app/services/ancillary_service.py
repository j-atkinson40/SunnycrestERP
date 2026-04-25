"""Phase 4.3.3 — ancillary three-state machine service.

PRODUCT_PRINCIPLES §Domain-Specific Operational Semantics canon (as
amended in this commit) names three ancillary states:

  - **pool** — `attached_to_delivery_id IS NULL` AND
    `primary_assignee_id IS NULL` AND `requested_date IS NULL`.
    Waiting for pairing or assignment. Lives in the Scheduling
    Focus pool pin (Phase 4.3b).

  - **paired/attached** — `attached_to_delivery_id IS NOT NULL`.
    Rides with a primary kanban delivery. driver/date inherit from
    parent at attach time (denormalized snapshot, not a relationship
    join, so detach can preserve those fields if desired).

  - **standalone** — `attached_to_delivery_id IS NULL` AND
    `primary_assignee_id IS NOT NULL` AND `requested_date IS NOT
    NULL`. Independent stop on a driver's day — e.g., slow-day
    driver covering an ancillary-only drop-off, or office staff
    covering when drivers unavailable.

Four transitions:

    pool         → paired:     attach_ancillary
    standalone   → paired:     attach_ancillary  (driver/date
                                                  overwritten by
                                                  parent's)
    paired       → standalone: detach_ancillary  (clear FK only;
                                                  driver/date
                                                  preserved)
    pool         → standalone: assign_ancillary_standalone
    paired       → pool:       detach_ancillary then
                               return_ancillary_to_pool
                               (or call return_ancillary_to_pool
                               directly — it handles all cases)
    standalone   → pool:       return_ancillary_to_pool
    pool         → pool:       no-op (return_ancillary_to_pool is
                                      idempotent)

Each transition validates tenant scope + ancillary scheduling_type +
returns the updated row. Errors surface as ``ValueError`` (caller
maps to HTTP 400) or ``LookupError`` (caller maps to 404).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.models.delivery import Delivery


# ── Errors ─────────────────────────────────────────────────────────


class AncillaryNotFound(LookupError):
    """Ancillary delivery does not exist within the caller's tenant."""


class ParentNotFound(LookupError):
    """Parent delivery does not exist within the caller's tenant."""


class InvalidAncillaryTransition(ValueError):
    """The current state of the ancillary does not allow the
    requested transition. Carries a structured `code` for the route
    layer to translate into operator-friendly copy."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


# ── Helpers ────────────────────────────────────────────────────────


def _load_ancillary(
    db: Session, ancillary_id: str, company_id: str
) -> Delivery:
    """Load + tenant-scope. Raises AncillaryNotFound if missing."""
    d = (
        db.query(Delivery)
        .filter(
            Delivery.id == ancillary_id,
            Delivery.company_id == company_id,
        )
        .first()
    )
    if d is None:
        raise AncillaryNotFound(f"Ancillary {ancillary_id!r} not found")
    if d.scheduling_type != "ancillary":
        # Phase 4.3.3 routes are explicitly for the ancillary state
        # machine. Non-ancillary deliveries route through the
        # primary delivery PATCH endpoint instead.
        raise InvalidAncillaryTransition(
            f"Delivery {ancillary_id!r} has scheduling_type"
            f"={d.scheduling_type!r}, not 'ancillary'.",
            code="not_ancillary",
        )
    return d


def _load_kanban_parent(
    db: Session, parent_id: str, company_id: str
) -> Delivery:
    """Load + tenant-scope a parent kanban delivery. Raises
    ParentNotFound if missing OR if not scheduling_type='kanban'."""
    p = (
        db.query(Delivery)
        .filter(
            Delivery.id == parent_id,
            Delivery.company_id == company_id,
        )
        .first()
    )
    if p is None:
        raise ParentNotFound(f"Parent delivery {parent_id!r} not found")
    if p.scheduling_type != "kanban":
        raise InvalidAncillaryTransition(
            f"Parent {parent_id!r} is not a kanban delivery "
            f"(scheduling_type={p.scheduling_type!r}).",
            code="parent_not_kanban",
        )
    return p


def _stamp_modified(d: Delivery) -> None:
    d.modified_at = datetime.now(timezone.utc)


# ── State transitions ──────────────────────────────────────────────


def attach_ancillary(
    db: Session, ancillary_id: str, parent_delivery_id: str, company_id: str
) -> Delivery:
    """Attach an ancillary to a parent kanban delivery.

    Inheritance: driver + date copied from parent. Ancillary's
    fulfillment status flips to ``assigned_to_driver`` so it
    surfaces correctly in Phase 8e portal driver-mobile views.
    """
    a = _load_ancillary(db, ancillary_id, company_id)
    p = _load_kanban_parent(db, parent_delivery_id, company_id)
    if a.id == p.id:
        raise InvalidAncillaryTransition(
            "Cannot attach an ancillary to itself.",
            code="self_attach",
        )

    a.attached_to_delivery_id = p.id
    a.primary_assignee_id = p.primary_assignee_id
    a.requested_date = p.requested_date
    a.ancillary_is_floating = False
    a.ancillary_fulfillment_status = (
        "assigned_to_driver"
        if p.primary_assignee_id is not None
        else "unassigned"
    )
    _stamp_modified(a)
    db.commit()
    db.refresh(a)
    return a


def detach_ancillary(
    db: Session, ancillary_id: str, company_id: str
) -> Delivery:
    """Detach an ancillary from its parent.

    Default: transition to **standalone** (preserve driver + date,
    clear FK only). Per Phase 4.3.3 spec — single-path detach;
    callers wanting pool state instead chain
    ``return_ancillary_to_pool``.
    """
    a = _load_ancillary(db, ancillary_id, company_id)
    if a.attached_to_delivery_id is None:
        raise InvalidAncillaryTransition(
            "Ancillary is not currently attached.",
            code="not_attached",
        )

    a.attached_to_delivery_id = None
    # primary_assignee_id + requested_date PRESERVED — that's the
    # standalone state. ancillary_fulfillment_status follows the
    # assignee: assigned_to_driver if a driver remains, else
    # unassigned.
    if a.primary_assignee_id is not None:
        a.ancillary_fulfillment_status = "assigned_to_driver"
    else:
        a.ancillary_fulfillment_status = "unassigned"
    _stamp_modified(a)
    db.commit()
    db.refresh(a)
    return a


def assign_ancillary_standalone(
    db: Session,
    ancillary_id: str,
    primary_assignee_id: str,
    scheduled_date: date,
    company_id: str,
) -> Delivery:
    """Assign an ancillary as a standalone stop on a driver's day.

    Sets driver + date, ensures `attached_to_delivery_id` is null
    (standalone is mutually exclusive with paired). Caller is
    responsible for resolving `primary_assignee_id` from a
    Driver.id via `delivery_service.resolve_primary_assignee_id`
    when the frontend passes a Driver.id (Phase 4.3.2 transitional
    helper still in use).
    """
    a = _load_ancillary(db, ancillary_id, company_id)

    a.attached_to_delivery_id = None
    a.primary_assignee_id = primary_assignee_id
    a.requested_date = scheduled_date
    a.ancillary_is_floating = False
    a.ancillary_soft_target_date = None
    a.ancillary_fulfillment_status = "assigned_to_driver"
    _stamp_modified(a)
    db.commit()
    db.refresh(a)
    return a


def return_ancillary_to_pool(
    db: Session, ancillary_id: str, company_id: str
) -> Delivery:
    """Return an ancillary to the unassigned pool.

    Idempotent: pool→pool is a no-op (just stamps modified_at).
    Clears every assignment field — driver, date, attachment FK.
    Sets `ancillary_is_floating=True` so it surfaces in the
    Phase 4.3b pin widget. Floating soft target date cleared too —
    pool means truly waiting, not "soft-targeted for some day."
    """
    a = _load_ancillary(db, ancillary_id, company_id)

    a.attached_to_delivery_id = None
    a.primary_assignee_id = None
    a.requested_date = None
    a.ancillary_is_floating = True
    a.ancillary_soft_target_date = None
    a.ancillary_fulfillment_status = "unassigned"
    _stamp_modified(a)
    db.commit()
    db.refresh(a)
    return a
