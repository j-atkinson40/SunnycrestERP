"""Dashboard Layouts service — CRUD + 3-tier inheritance resolution.

Mirrors `platform_themes.theme_service` shape:
  - Inheritance computed at READ time (`resolve_layout`).
  - Write-side versioning: each save deactivates the prior active row
    at the same (scope, vertical, tenant_id, page_context) tuple and
    inserts a new active row with version+1.
  - Inactive rows accumulate as a versioned audit trail.

Resolution order:
    platform_default(page_context)
        ←  vertical_default(vertical, page_context) if vertical given
            ←  tenant_default(tenant_id, page_context) if tenant_id given

Deeper scope wins. The widget_service.get_user_layout consumer
layers the per-user override (UserWidgetLayout) on top of the
deepest resolved layer.

Layout config is a list of widget config entries (same shape as
UserWidgetLayout.layout_config); validation here is structural only,
the widget framework's availability/permission filter still runs at
fetch time.
"""

from __future__ import annotations

from typing import Iterable, Literal, Sequence
from sqlalchemy.orm import Session

from app.models.dashboard_layout import (
    DashboardLayout,
    SCOPE_PLATFORM_DEFAULT,
    SCOPE_TENANT_DEFAULT,
    SCOPE_VERTICAL_DEFAULT,
)


Scope = Literal["platform_default", "vertical_default", "tenant_default"]

_VALID_SCOPES: tuple[str, ...] = (
    SCOPE_PLATFORM_DEFAULT,
    SCOPE_VERTICAL_DEFAULT,
    SCOPE_TENANT_DEFAULT,
)


class DashboardLayoutServiceError(Exception):
    """Base exception for the dashboard layout service."""


class DashboardLayoutNotFound(DashboardLayoutServiceError):
    pass


class DashboardLayoutScopeMismatch(DashboardLayoutServiceError):
    """Scope/vertical/tenant_id triple violates the canonical shape."""


class InvalidDashboardLayoutShape(DashboardLayoutServiceError):
    """page_context invalid, or layout_config not a list of dicts."""


# ─── Validation helpers ──────────────────────────────────────────


def _validate_scope_keys(
    scope: str,
    vertical: str | None,
    tenant_id: str | None,
) -> None:
    """Mirror the DB CHECK constraint at the application boundary so
    we 400-out cleanly instead of relying on Postgres to barf."""
    if scope not in _VALID_SCOPES:
        raise InvalidDashboardLayoutShape(
            f"scope must be one of {_VALID_SCOPES}, got {scope!r}"
        )
    if scope == SCOPE_PLATFORM_DEFAULT and (vertical is not None or tenant_id is not None):
        raise DashboardLayoutScopeMismatch(
            "platform_default rows must have vertical=None and tenant_id=None"
        )
    if scope == SCOPE_VERTICAL_DEFAULT and (vertical is None or tenant_id is not None):
        raise DashboardLayoutScopeMismatch(
            "vertical_default rows must have vertical set and tenant_id=None"
        )
    if scope == SCOPE_TENANT_DEFAULT and (tenant_id is None or vertical is not None):
        raise DashboardLayoutScopeMismatch(
            "tenant_default rows must have tenant_id set and vertical=None"
        )


def _validate_page_context(page_context: str) -> None:
    if not isinstance(page_context, str) or not page_context.strip():
        raise InvalidDashboardLayoutShape(
            "page_context must be a non-empty string"
        )


def _validate_layout_config(layout_config: Sequence[object]) -> list[dict]:
    """Structural validation — each entry must be a dict carrying
    `widget_id` (str). Other fields (enabled, position, size, config)
    are passed through; the widget framework re-validates them at
    fetch time when resolving against WIDGET_DEFINITIONS."""
    if not isinstance(layout_config, (list, tuple)):
        raise InvalidDashboardLayoutShape(
            "layout_config must be a list of widget config dicts"
        )
    cleaned: list[dict] = []
    seen_widget_ids: set[str] = set()
    for idx, entry in enumerate(layout_config):
        if not isinstance(entry, dict):
            raise InvalidDashboardLayoutShape(
                f"layout_config[{idx}] must be a dict, got {type(entry).__name__}"
            )
        widget_id = entry.get("widget_id")
        if not isinstance(widget_id, str) or not widget_id:
            raise InvalidDashboardLayoutShape(
                f"layout_config[{idx}].widget_id must be a non-empty string"
            )
        if widget_id in seen_widget_ids:
            raise InvalidDashboardLayoutShape(
                f"layout_config[{idx}].widget_id '{widget_id}' is duplicated"
            )
        seen_widget_ids.add(widget_id)
        cleaned.append(dict(entry))
    return cleaned


# ─── Internal lookup ─────────────────────────────────────────────


def _find_active(
    db: Session,
    *,
    scope: str,
    vertical: str | None,
    tenant_id: str | None,
    page_context: str,
) -> DashboardLayout | None:
    """Return the currently active row for the canonical tuple, or
    None. Active = `is_active=True`."""
    q = db.query(DashboardLayout).filter(
        DashboardLayout.scope == scope,
        DashboardLayout.page_context == page_context,
        DashboardLayout.is_active.is_(True),
    )
    # vertical / tenant_id may be None depending on scope; filter both
    # explicitly to avoid SQLAlchemy's `.is_(None)` vs `== None` quirk.
    if vertical is None:
        q = q.filter(DashboardLayout.vertical.is_(None))
    else:
        q = q.filter(DashboardLayout.vertical == vertical)
    if tenant_id is None:
        q = q.filter(DashboardLayout.tenant_id.is_(None))
    else:
        q = q.filter(DashboardLayout.tenant_id == tenant_id)
    return q.first()


# ─── CRUD ────────────────────────────────────────────────────────


def list_layouts(
    db: Session,
    *,
    scope: str | None = None,
    vertical: str | None = None,
    tenant_id: str | None = None,
    page_context: str | None = None,
    include_inactive: bool = False,
) -> list[DashboardLayout]:
    """Return layout rows matching filters. Active-only by default."""
    q = db.query(DashboardLayout)
    if scope is not None:
        if scope not in _VALID_SCOPES:
            raise InvalidDashboardLayoutShape(f"scope filter invalid: {scope!r}")
        q = q.filter(DashboardLayout.scope == scope)
    if vertical is not None:
        q = q.filter(DashboardLayout.vertical == vertical)
    if tenant_id is not None:
        q = q.filter(DashboardLayout.tenant_id == tenant_id)
    if page_context is not None:
        q = q.filter(DashboardLayout.page_context == page_context)
    if not include_inactive:
        q = q.filter(DashboardLayout.is_active.is_(True))
    return q.order_by(DashboardLayout.created_at.desc()).all()


def get_layout_by_id(db: Session, layout_id: str) -> DashboardLayout:
    row = (
        db.query(DashboardLayout)
        .filter(DashboardLayout.id == layout_id)
        .first()
    )
    if not row:
        raise DashboardLayoutNotFound(layout_id)
    return row


def create_layout(
    db: Session,
    *,
    scope: str,
    vertical: str | None = None,
    tenant_id: str | None = None,
    page_context: str,
    layout_config: Sequence[dict] | None = None,
    actor_user_id: str | None = None,
) -> DashboardLayout:
    """Create a new active layout row.

    If an active row already exists at the same tuple, it is
    deactivated first (write-side versioning); the new row's version
    is `prior.version + 1`.
    """
    _validate_scope_keys(scope, vertical, tenant_id)
    _validate_page_context(page_context)
    cleaned = _validate_layout_config(layout_config or [])

    existing = _find_active(
        db,
        scope=scope,
        vertical=vertical,
        tenant_id=tenant_id,
        page_context=page_context,
    )

    next_version = 1
    if existing is not None:
        existing.is_active = False
        next_version = existing.version + 1
        # flush so the partial unique index doesn't see two active rows
        # mid-transaction.
        db.flush()

    row = DashboardLayout(
        scope=scope,
        vertical=vertical,
        tenant_id=tenant_id,
        page_context=page_context,
        layout_config=cleaned,
        version=next_version,
        is_active=True,
        created_by=actor_user_id,
        updated_by=actor_user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_layout(
    db: Session,
    layout_id: str,
    *,
    layout_config: Sequence[dict],
    actor_user_id: str | None = None,
) -> DashboardLayout:
    """Replace `layout_config` on the active layout identified by id
    and bump version. Pattern mirrors `theme_service.update_theme` —
    deactivate prior + insert new active row with version+1.
    """
    prior = get_layout_by_id(db, layout_id)
    if not prior.is_active:
        raise DashboardLayoutServiceError(
            f"cannot update inactive dashboard layout {layout_id!r} — fetch "
            f"the active row at the same tuple instead"
        )

    cleaned = _validate_layout_config(layout_config)
    prior.is_active = False
    db.flush()
    new_row = DashboardLayout(
        scope=prior.scope,
        vertical=prior.vertical,
        tenant_id=prior.tenant_id,
        page_context=prior.page_context,
        layout_config=cleaned,
        version=prior.version + 1,
        is_active=True,
        created_by=actor_user_id,
        updated_by=actor_user_id,
    )
    db.add(new_row)
    db.commit()
    db.refresh(new_row)
    return new_row


# ─── Inheritance resolution ──────────────────────────────────────


def resolve_layout(
    db: Session,
    *,
    page_context: str,
    vertical: str | None = None,
    tenant_id: str | None = None,
) -> dict:
    """Walk the 3-tier inheritance chain.

    Resolution order (deeper-scope wins; first non-empty wins for the
    layout_config because layouts are complete arrangements, not
    partial overlays):

        platform_default(page_context)
            ←  vertical_default(vertical, page_context)
                ←  tenant_default(tenant_id, page_context)

    Returns dict with keys:
        - `layout_config`: the resolved list of widget config entries
            (or empty list if no row exists at any scope).
        - `source`: the scope that supplied the resolved layout, or
            None if no row exists at any scope ("inherits from in-code
            WIDGET_DEFINITIONS defaults" — caller decides fallback).
        - `source_id`: the row id if any.
        - `source_version`: the row version if any.
        - `sources`: full chain of rows visited (for the editor's
            inheritance indicator), each with `{scope, id, version,
            page_context}`.

    Note: layouts are first-match-wins, NOT layered. A tenant_default
    row's layout_config REPLACES the vertical_default. This mirrors
    `focus_compositions` semantics — a complete arrangement at scope X
    is the source of truth, not a partial overlay over scope X-1.
    Per-widget property merging across scopes happens in
    `component_configurations`, not here.
    """
    _validate_page_context(page_context)

    sources: list[dict] = []
    resolved: dict[str, object] = {
        "layout_config": [],
        "source": None,
        "source_id": None,
        "source_version": None,
    }

    # Walk in canonical order; first-match-wins (deepest non-empty wins).
    candidates: list[tuple[str, str | None, str | None]] = [
        (SCOPE_PLATFORM_DEFAULT, None, None),
    ]
    if vertical is not None:
        candidates.append((SCOPE_VERTICAL_DEFAULT, vertical, None))
    if tenant_id is not None:
        candidates.append((SCOPE_TENANT_DEFAULT, None, tenant_id))

    # Walk every candidate so `sources` always shows the full visit
    # trail; deepest non-empty wins for the resolved value.
    for scope, v, t in candidates:
        row = _find_active(
            db,
            scope=scope,
            vertical=v,
            tenant_id=t,
            page_context=page_context,
        )
        if row is None:
            continue
        sources.append(
            {
                "scope": scope,
                "id": row.id,
                "version": row.version,
                "page_context": page_context,
                "vertical": v,
                "tenant_id": t,
            }
        )
        # Deeper scope wins; overwrite resolved.
        resolved["layout_config"] = list(row.layout_config or [])
        resolved["source"] = scope
        resolved["source_id"] = row.id
        resolved["source_version"] = row.version

    return {
        **resolved,
        "sources": sources,
        "page_context": page_context,
        "vertical": vertical,
        "tenant_id": tenant_id,
    }
