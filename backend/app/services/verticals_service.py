"""Verticals service — list / get / update for the `verticals` table.

Verticals-lite precursor arc. Backs the admin-only
`/api/platform/admin/verticals/*` endpoints. Slug is immutable
(part of the primary key); create + delete are intentionally NOT
in scope at this arc — the 4 canonical seeds (manufacturing,
funeral_home, cemetery, crematory) ship via migration r92_verticals_table
and full lifecycle CRUD lands when Studio shell needs it.

See migration `r92_verticals_table` for schema + canonical seeds.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.vertical import VALID_STATUSES, Vertical


class VerticalServiceError(Exception):
    """Base exception for the verticals service."""


class VerticalNotFound(VerticalServiceError):
    """Raised when a `slug` does not resolve to a row."""


def list_verticals(
    db: Session, *, include_archived: bool = False
) -> list[Vertical]:
    """Return verticals ordered by `sort_order ASC, slug ASC`.

    Archived rows are excluded by default. Set `include_archived=True`
    to include them (admin surfaces use this for the full history
    view).
    """
    query = db.query(Vertical)
    if not include_archived:
        query = query.filter(Vertical.status != "archived")
    return query.order_by(Vertical.sort_order.asc(), Vertical.slug.asc()).all()


def get_vertical(db: Session, slug: str) -> Vertical:
    """Return a single vertical by slug.

    Raises `VerticalNotFound` if the slug does not resolve.
    """
    row = db.query(Vertical).filter(Vertical.slug == slug).first()
    if row is None:
        raise VerticalNotFound(f"vertical not found: slug={slug!r}")
    return row


def update_vertical(
    db: Session,
    slug: str,
    *,
    display_name: str | None = None,
    description: str | None = None,
    status: str | None = None,
    icon: str | None = None,
    sort_order: int | None = None,
) -> Vertical:
    """Partial-update a vertical by slug.

    None values are no-ops (leaves existing column value). Slug is
    intentionally NOT in the signature — the column is immutable
    (primary key). Raises `ValueError` on invalid status; raises
    `VerticalNotFound` when slug doesn't resolve.

    Updates `updated_at` whenever any mutation lands.
    """
    row = get_vertical(db, slug)

    mutated = False

    if display_name is not None:
        row.display_name = display_name
        mutated = True
    if description is not None:
        # NULL is a valid description (explicit clear). Callers
        # wanting "clear description" pass description="" or use a
        # PATCH semantic; the column is nullable so empty-string
        # round-trips honestly. We do not distinguish "absent" from
        # "explicit None" at this signature level — the API layer
        # passes None to mean "no change", and an explicit clear
        # would pass description="" which lands here as a value.
        row.description = description
        mutated = True
    if status is not None:
        if status not in VALID_STATUSES:
            raise ValueError(
                f"status must be one of {VALID_STATUSES}, got {status!r}"
            )
        row.status = status
        mutated = True
    if icon is not None:
        row.icon = icon
        mutated = True
    if sort_order is not None:
        row.sort_order = sort_order
        mutated = True

    if mutated:
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)

    return row
