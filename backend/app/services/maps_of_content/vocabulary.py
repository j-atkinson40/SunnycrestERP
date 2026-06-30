"""MoC task vocabulary service (Task Editing 2a) — the constrained-editable store.

A task's frequency/type must be a value that EXISTS here (referential), but the
store is editable: `add_value` inserts a row (configuration, not code). Scope is
read three-tier — for vertical V the picker sees platform values + V's values.
Deactivation is soft (is_active=False) so tasks referencing a value don't orphan.
"""
from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.moc_task_vocabulary import MoCTaskVocabulary

KINDS = ("frequency", "type")


class VocabularyError(ValueError):
    """Invalid vocabulary write (bad kind/scope) — surfaces as HTTP 400."""


def _check_kind(kind: str) -> None:
    if kind not in KINDS:
        raise VocabularyError(f"kind must be one of {KINDS} (got {kind!r})")


def list_values(
    db: Session,
    *,
    kind: str | None = None,
    vertical: str | None = None,
    active_only: bool = True,
) -> list[MoCTaskVocabulary]:
    """Platform values + (if given) the vertical's values, ordered for display."""
    stmt = select(MoCTaskVocabulary)
    if kind is not None:
        _check_kind(kind)
        stmt = stmt.where(MoCTaskVocabulary.kind == kind)
    if active_only:
        stmt = stmt.where(MoCTaskVocabulary.is_active.is_(True))
    # platform_default (vertical NULL) is always visible; vertical_default only for
    # the requested vertical.
    if vertical is not None:
        stmt = stmt.where(
            (MoCTaskVocabulary.scope == "platform_default")
            | (
                (MoCTaskVocabulary.scope == "vertical_default")
                & (MoCTaskVocabulary.vertical == vertical)
            )
        )
    rows = list(db.execute(stmt).scalars())
    rows.sort(key=lambda v: (v.kind, v.display_order, v.value.lower()))
    return rows


def value_exists(db: Session, *, kind: str, value: str, vertical: str | None) -> bool:
    """The referential check: an ACTIVE value of this kind visible to `vertical`
    (platform-wide or vertical-specific)."""
    _check_kind(kind)
    stmt = (
        select(MoCTaskVocabulary.id)
        .where(MoCTaskVocabulary.kind == kind)
        .where(MoCTaskVocabulary.value == value)
        .where(MoCTaskVocabulary.is_active.is_(True))
        .where(
            (MoCTaskVocabulary.scope == "platform_default")
            | (
                (MoCTaskVocabulary.scope == "vertical_default")
                & (MoCTaskVocabulary.vertical == vertical)
            )
        )
    )
    return db.execute(stmt).first() is not None


def add_value(
    db: Session,
    *,
    kind: str,
    value: str,
    scope: str = "platform_default",
    vertical: str | None = None,
    display_order: int = 0,
    actor_id: str | None = None,
) -> MoCTaskVocabulary:
    """Find-or-create (reactivates a soft-deleted match). Caller commits."""
    _check_kind(kind)
    value = value.strip()
    if not value:
        raise VocabularyError("value must be non-empty")
    if scope not in ("platform_default", "vertical_default", "tenant_override"):
        raise VocabularyError(f"invalid scope {scope!r}")
    if scope == "vertical_default" and not vertical:
        raise VocabularyError("vertical_default scope requires a vertical")

    existing = db.execute(
        select(MoCTaskVocabulary)
        .where(MoCTaskVocabulary.kind == kind)
        .where(MoCTaskVocabulary.value == value)
        .where(MoCTaskVocabulary.scope == scope)
        .where(MoCTaskVocabulary.vertical.is_(None) if vertical is None
               else MoCTaskVocabulary.vertical == vertical)
    ).scalar_one_or_none()
    if existing is not None:
        existing.is_active = True
        if display_order:
            existing.display_order = display_order
        if actor_id:
            existing.updated_by = actor_id
        return existing

    row = MoCTaskVocabulary(
        id=str(uuid.uuid4()), kind=kind, value=value, scope=scope,
        vertical=vertical, display_order=display_order,
        created_by=actor_id, updated_by=actor_id,
    )
    db.add(row)
    return row


def deactivate_value(db: Session, *, value_id: str, actor_id: str | None = None) -> MoCTaskVocabulary:
    """Soft-delete: is_active=False. Tasks referencing the value keep it
    (referential validation only fires on writes)."""
    row = db.get(MoCTaskVocabulary, value_id)
    if row is None:
        raise VocabularyError(f"vocabulary value {value_id!r} not found")
    row.is_active = False
    if actor_id:
        row.updated_by = actor_id
    return row


# Minimal seed — the values in use by the 2 demo tasks, platform-scoped (shared
# across every MoC). Adding more is an add_value (a row), not a code change.
_SEED: Sequence[tuple[str, str, int]] = (
    ("frequency", "End of Month", 0),
    ("frequency", "On demand", 1),
    ("type", "Accounting", 0),
    ("type", "Funeral Service Operations", 1),
)


def seed_minimal(db: Session) -> int:
    """Idempotent platform-scope seed. Commits. Returns count seeded/ensured."""
    for kind, value, order in _SEED:
        add_value(db, kind=kind, value=value, scope="platform_default",
                  vertical=None, display_order=order)
    db.commit()
    return len(_SEED)
