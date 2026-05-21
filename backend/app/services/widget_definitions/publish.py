"""Widget definition draft + publish service (WB-4a).

Backs the three API endpoints the Widget Builder shell needs:

  • PUT  /api/v1/widget-definitions/{slug}/draft    → upsert draft
        (auto-save; permissive Pydantic on the wire; updates
        `composition_blob` + edit-session columns; preserves
        `published_composition_blob` untouched).
  • POST /api/v1/widget-definitions/{slug}/publish  → promote draft
        to live (full validator pass; copies composition_blob →
        published_composition_blob; bumps composition_version).
  • POST /api/v1/widget-definitions                 → create new
        composed widget with a default empty flex-stack root container
        (tier_scope='vertical' by default; composition_version=1;
        published_composition_blob=NULL).

Per the Area 2 lock at
`docs/investigations/2026-05-21-widget-builder.md`: composition_blob
is the DRAFT authoring surface; published_composition_blob is the
LIVE render surface. Tenant render paths read published first; fall
back to draft only for pre-r106 legacy rows.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.widget_definition import WidgetDefinition
from app.services.widget_definitions.validators import (
    CompositionBlobValidationError,
    validate_composition_blob,
)


# ── exceptions ────────────────────────────────────────────────────────


class WidgetDefinitionNotFoundError(Exception):
    """Raised when a slug doesn't map to an existing widget."""


class WidgetDefinitionConflictError(Exception):
    """Raised when a slug collides on create."""


class CannotPublishWithoutDraftError(Exception):
    """Raised on publish when composition_blob is NULL.

    This shouldn't happen via the editor (every publish lands after a
    draft save), but defensive on the API boundary.
    """


# ── helpers ───────────────────────────────────────────────────────────


_DEFAULT_TIER_SCOPE = "vertical"


def _empty_flex_stack_composition() -> dict[str, Any]:
    """Default composition_blob for a freshly created widget.

    Phase 1 flex-stack canvas: the canvas root is implicit (canvas
    chrome carries direction/spacing/alignment per WB-4a). The blob
    needs a `root_atom_id` per the Pydantic schema; we ship an empty
    conditional_container as the synthetic root + no children. Canvas
    renders nothing until the operator drops atoms.
    """
    root_id = str(uuid.uuid4())
    return {
        "schema_version": 1,
        "root_atom_id": root_id,
        "atom_tree": {
            root_id: {
                "atom_id": root_id,
                "atom_type": "conditional_container",
                # Phase 1 conditional_container config carries
                # `direction` + `gap_token`. The WB-4a canvas-root flex
                # chrome (direction/spacing/alignment selects in the
                # top bar) writes through to these fields — direction
                # maps directly; spacing maps to gap_token (sm/md/lg);
                # alignment is exposed in the chrome but stored as
                # widget-level state (deferred to WB-4b inspector
                # work). Until then, the default config stays minimal.
                "config": {
                    "direction": "column",
                    "gap_token": "sm",
                },
                "children": [],
            }
        },
        "variants": [],
        "bindings_catalog": {},
    }


def _resolve_widget(db: Session, slug: str) -> WidgetDefinition:
    row = (
        db.query(WidgetDefinition)
        .filter(WidgetDefinition.widget_id == slug)
        .first()
    )
    if row is None:
        raise WidgetDefinitionNotFoundError(slug)
    return row


def _make_unique_slug(db: Session, base: str) -> str:
    """Return ``base`` if unused, else ``base-2`` / ``base-3`` / ...

    Matches Area 7 slug-collision convention.
    """
    candidate = base
    n = 2
    while (
        db.query(WidgetDefinition)
        .filter(WidgetDefinition.widget_id == candidate)
        .first()
        is not None
    ):
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def serialize_widget(row: WidgetDefinition) -> dict[str, Any]:
    """Canonical Widget Builder response shape.

    Augments the WB-3 composed-definitions shape with the WB-4a
    additions: `published_composition_blob` + edit-session metadata.
    """
    return {
        "widget_id": row.widget_id,
        "title": row.title,
        "description": row.description,
        "icon": row.icon,
        "category": row.category,
        "composition_blob": row.composition_blob,
        "composition_version": row.composition_version,
        "published_composition_blob": row.published_composition_blob,
        "tier_scope": row.tier_scope,
        "supported_surfaces": row.supported_surfaces or ["dashboard_grid"],
        "default_size": row.default_size,
        "supported_sizes": row.supported_sizes or ["1x1"],
        "last_edit_session_id": row.last_edit_session_id,
        "last_edit_session_at": (
            row.last_edit_session_at.isoformat()
            if row.last_edit_session_at is not None
            else None
        ),
    }


# ── service operations ────────────────────────────────────────────────


def create_widget_definition(
    db: Session,
    *,
    title: Optional[str] = None,
    slug: Optional[str] = None,
    tier_scope: str = _DEFAULT_TIER_SCOPE,
    category: Optional[str] = None,
) -> WidgetDefinition:
    """Create a brand-new composed widget with a default empty root.

    composition_version=1, published_composition_blob=NULL. The
    operator names the widget at first Publish (per Area 7 — naming
    happens in the editor; we ship a placeholder title until then).
    """
    safe_title = (title or "Untitled widget").strip() or "Untitled widget"
    base_slug = (slug or "untitled-widget").strip() or "untitled-widget"
    unique_slug = _make_unique_slug(db, base_slug)

    row = WidgetDefinition(
        widget_id=unique_slug,
        title=safe_title,
        description=None,
        page_contexts=[],
        composition_blob=_empty_flex_stack_composition(),
        composition_version=1,
        tier_scope=tier_scope,
        category=category,
        is_system=False,
    )
    db.add(row)
    db.flush()
    return row


def save_draft(
    db: Session,
    *,
    slug: str,
    composition_blob: Any,
    edit_session_id: Optional[str],
    actor_user_id: Optional[str] = None,
    title: Optional[str] = None,
) -> WidgetDefinition:
    """Auto-save the draft.

    PERMISSIVE — accepts any dict-shaped blob; full validation runs on
    Publish. This lets the operator's mid-edit intermediate states
    (orphan children, missing bindings) persist for resumability
    without blocking each keystroke. Per Area 5 lock.
    """
    row = _resolve_widget(db, slug)
    row.composition_blob = composition_blob
    if row.composition_version is None:
        row.composition_version = 1
    row.last_edit_session_id = edit_session_id
    row.last_edit_session_at = datetime.now(timezone.utc)
    if actor_user_id is not None:
        row.last_edit_session_actor_id = actor_user_id
    if title is not None:
        safe_title = title.strip()
        if safe_title:
            row.title = safe_title
    db.flush()
    return row


def publish_draft(db: Session, *, slug: str) -> WidgetDefinition:
    """Promote the draft to live.

    Full validator pass (raises CompositionBlobValidationError on
    invalid; the route layer surfaces as HTTP 422). On success: copies
    composition_blob → published_composition_blob, bumps version.
    """
    row = _resolve_widget(db, slug)
    if row.composition_blob is None:
        raise CannotPublishWithoutDraftError(slug)

    # Full validation. Raises on any error.
    validate_composition_blob(row.composition_blob)

    row.published_composition_blob = row.composition_blob
    # composition_version bump — every Publish increments. Phase 1
    # stamp stays at 1 for schema_version (inside the blob); the row
    # field tracks publish iteration.
    row.composition_version = (row.composition_version or 1) + 1
    db.flush()
    return row
