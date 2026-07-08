"""Maps of Content service implementation.

Reference resolution touches the four wired builders' owning tables via
raw SQL (light-touch, no ORM coupling to four substrates). Each resolver
returns the artifact's CURRENT label + the routing fields the frontend
deep-link helper needs, plus exists/available flags. A missing artifact
yields exists=False (orphan-tolerant); an inactive one yields
available=False — neither raises.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.models.moc_page import MoCPage

# The four wired builders. Keys match the Studio route segments
# (/studio/workflows, /studio/focuses, /studio/widgets, /studio/documents)
# so the frontend deep-link helper maps key → builder directly.
_WORKFLOWS = "workflows"
_FOCUSES = "focuses"
_WIDGETS = "widgets"
_DOCUMENTS = "documents"
# Focus Variations V-1: Tier 1 focus cores as first-class refs — the platform
# map's Focuses card shows the canonical default shapes (the fork-menu
# targets). Deep-links to the Focus Builder's tier-1 view (?tier=1&core=<id>).
_FOCUS_CORES = "focus-cores"


class InvalidReference(Exception):
    """A row references an unknown builder, or a section/row is malformed.
    Raised at WRITE time only — read is orphan-tolerant."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Reference resolvers (one per wired builder) ─────────────────────
#
# Each returns: {exists, available, label, routing}. `label` is the
# artifact's CURRENT name (the authored label is used only as a fallback
# when the artifact is gone). `routing` carries the builder-specific
# fields the deep-link helper assembles into a Studio URL.


def _resolve_workflow(db: Session, artifact_id: str, authored: str) -> dict:
    row = db.execute(
        sql_text(
            "SELECT display_name, is_active, workflow_type, scope, vertical "
            "FROM workflow_templates WHERE id = :id"
        ),
        {"id": artifact_id},
    ).first()
    if row is None:
        return _gone(authored)
    return {
        "exists": True,
        "available": bool(row.is_active),
        "label": row.display_name or authored,
        "routing": {
            "workflow_type": row.workflow_type,
            "scope": row.scope,
            "vertical": row.vertical,
        },
    }


def _family_icon_for_template(db: Session, template_id: str) -> str | None:
    """Focus family icons (r122): the lineage ROOT core's CURRENT icon —
    inherited at read, never copied, not overridable downstream. The
    template's stored core id may point at a retained snapshot; the
    slug self-join lands on the ACTIVE core (the C-2.1.2 canon), so an
    icon change propagates to every variation immediately."""
    row = db.execute(
        sql_text(
            "SELECT c2.icon FROM focus_templates ft "
            "JOIN focus_cores c1 ON c1.id = ft.inherits_from_core_id "
            "JOIN focus_cores c2 ON c2.core_slug = c1.core_slug "
            "  AND c2.is_active = true "
            "WHERE ft.id = :id"
        ),
        {"id": template_id},
    ).first()
    return row.icon if row else None


def _resolve_focus(db: Session, artifact_id: str, authored: str) -> dict:
    row = db.execute(
        sql_text(
            "SELECT id, display_name, is_active, template_slug, scope, vertical "
            "FROM focus_templates WHERE id = :id"
        ),
        {"id": artifact_id},
    ).first()
    if row is None:
        return _gone(authored)
    if not row.is_active:
        # Slug-translation rebind (the C-2.1.2 pattern applied to MoC refs):
        # focus_template version bumps mint NEW row ids, so an authored ref's
        # stored id goes inactive on the template's next edit. The slug tuple
        # (scope, vertical, template_slug) is the stable identity — re-bind to
        # the lineage's ACTIVE row so refs survive version rotation. The
        # rebound id rides back in `artifact_id` so deep-links open the live
        # version, not the retained snapshot.
        active = db.execute(
            sql_text(
                "SELECT id, display_name, template_slug, scope, vertical "
                "FROM focus_templates WHERE scope = :scope "
                "AND vertical IS NOT DISTINCT FROM :vertical "
                "AND template_slug = :slug AND is_active = true"
            ),
            {"scope": row.scope, "vertical": row.vertical,
             "slug": row.template_slug},
        ).first()
        if active is not None:
            return {
                "exists": True,
                "available": True,
                "label": active.display_name or authored,
                "artifact_id": active.id,
                "icon": _family_icon_for_template(db, active.id),
                "routing": {
                    "template_slug": active.template_slug,
                    "scope": active.scope,
                    "vertical": active.vertical,
                },
            }
    return {
        "exists": True,
        "available": bool(row.is_active),
        "label": row.display_name or authored,
        "icon": _family_icon_for_template(db, row.id),
        "routing": {
            "template_slug": row.template_slug,
            "scope": row.scope,
            "vertical": row.vertical,
        },
    }


def _resolve_focus_core(db: Session, artifact_id: str, authored: str) -> dict:
    """Tier 1 core refs. Same rebind semantics as _resolve_focus: core
    version bumps mint new row ids; core_slug is the stable identity."""
    row = db.execute(
        sql_text(
            "SELECT id, display_name, is_active, core_slug, icon "
            "FROM focus_cores WHERE id = :id"
        ),
        {"id": artifact_id},
    ).first()
    if row is None:
        return _gone(authored)
    if not row.is_active:
        active = db.execute(
            sql_text(
                "SELECT id, display_name, core_slug, icon FROM focus_cores "
                "WHERE core_slug = :slug AND is_active = true"
            ),
            {"slug": row.core_slug},
        ).first()
        if active is not None:
            return {
                "exists": True,
                "available": True,
                "label": active.display_name or authored,
                "artifact_id": active.id,
                "icon": active.icon,
                "routing": {"core_slug": active.core_slug},
            }
    return {
        "exists": True,
        "available": bool(row.is_active),
        "label": row.display_name or authored,
        "icon": row.icon,
        "routing": {"core_slug": row.core_slug},
    }


def _resolve_widget(db: Session, artifact_id: str, authored: str) -> dict:
    # widget_definitions has no is_active — presence is liveness.
    row = db.execute(
        sql_text(
            "SELECT title, widget_id FROM widget_definitions WHERE id = :id"
        ),
        {"id": artifact_id},
    ).first()
    if row is None:
        return _gone(authored)
    return {
        "exists": True,
        "available": True,
        "label": row.title or authored,
        "routing": {"widget_id": row.widget_id},
    }


def _resolve_document(db: Session, artifact_id: str, authored: str) -> dict:
    row = db.execute(
        sql_text(
            "SELECT template_key, is_active, vertical "
            "FROM document_templates WHERE id = :id"
        ),
        {"id": artifact_id},
    ).first()
    if row is None:
        return _gone(authored)
    return {
        "exists": True,
        "available": bool(row.is_active),
        # document_templates carries no display_name — template_key is the
        # stable human-facing identifier; authored label still wins for UX.
        "label": authored or row.template_key,
        "routing": {"template_key": row.template_key, "vertical": row.vertical},
    }


def _gone(authored: str) -> dict:
    return {
        "exists": False,
        "available": False,
        "label": authored,
        "routing": {},
    }


BUILDERS: dict[str, Callable[[Session, str, str], dict]] = {
    _WORKFLOWS: _resolve_workflow,
    _FOCUSES: _resolve_focus,
    _FOCUS_CORES: _resolve_focus_core,
    _WIDGETS: _resolve_widget,
    _DOCUMENTS: _resolve_document,
}


# ── Section / row shaping + validation (write-side) ─────────────────


def _validate_and_normalize_sections(sections: Any) -> list[dict]:
    """Validate the authored shape + stamp ids/order. Rejects an unknown
    builder key (the only write-side existence guard — artifact existence
    is a read-time concern, kept orphan-tolerant)."""
    if not isinstance(sections, list):
        raise InvalidReference("sections must be a list")
    out: list[dict] = []
    for s_idx, section in enumerate(sections):
        if not isinstance(section, dict):
            raise InvalidReference("each section must be an object")
        title = section.get("title")
        if not title or not isinstance(title, str):
            raise InvalidReference("each section needs a title")
        rows_in = section.get("rows", [])
        if not isinstance(rows_in, list):
            raise InvalidReference("section.rows must be a list")
        rows_out: list[dict] = []
        for r_idx, row in enumerate(rows_in):
            if not isinstance(row, dict):
                raise InvalidReference("each row must be an object")
            builder = row.get("builder")
            if builder not in BUILDERS:
                raise InvalidReference(
                    f"unknown builder {builder!r} "
                    f"(wired: {sorted(BUILDERS)})"
                )
            artifact_id = row.get("artifact_id")
            if not artifact_id or not isinstance(artifact_id, str):
                raise InvalidReference("each row needs an artifact_id")
            label = row.get("label")
            if not label or not isinstance(label, str):
                raise InvalidReference("each row needs a label")
            rows_out.append(
                {
                    "row_id": row.get("row_id") or str(uuid.uuid4()),
                    "builder": builder,
                    "artifact_id": artifact_id,
                    "label": label,
                    "icon": row.get("icon"),
                    "order": r_idx,
                }
            )
        out.append(
            {
                "section_id": section.get("section_id") or str(uuid.uuid4()),
                "title": title,
                "description": section.get("description"),
                "order": s_idx,
                "rows": rows_out,
            }
        )
    return out


# ── CRUD ────────────────────────────────────────────────────────────


def create_page(
    db: Session,
    *,
    scope: str = "vertical_default",
    vertical: str | None,
    tenant_id: str | None = None,
    slug: str,
    title: str,
    description: str | None = None,
    sections: Any = None,
    actor_id: str | None = None,
) -> MoCPage:
    if scope not in (
        "platform_default",
        "vertical_default",
        "tenant_override",
    ):
        raise InvalidReference(f"invalid scope {scope!r}")
    page = MoCPage(
        scope=scope,
        vertical=vertical,
        tenant_id=tenant_id,
        slug=slug,
        title=title,
        description=description,
        sections=_validate_and_normalize_sections(sections or []),
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(page)
    db.commit()
    db.refresh(page)
    return page


def get_page(db: Session, page_id: str) -> MoCPage | None:
    return db.query(MoCPage).filter(MoCPage.id == page_id).first()


def list_pages(
    db: Session,
    *,
    scope: str | None = None,
    vertical: str | None = None,
    tenant_id: str | None = None,
    include_inactive: bool = False,
) -> list[MoCPage]:
    q = db.query(MoCPage)
    if scope is not None:
        q = q.filter(MoCPage.scope == scope)
    if vertical is not None:
        q = q.filter(MoCPage.vertical == vertical)
    if tenant_id is not None:
        q = q.filter(MoCPage.tenant_id == tenant_id)
    if not include_inactive:
        q = q.filter(MoCPage.is_active.is_(True))
    return q.order_by(MoCPage.vertical, MoCPage.slug).all()


def update_page(
    db: Session,
    page_id: str,
    *,
    actor_id: str | None = None,
    title: str | None = None,
    description: str | None = None,
    slug: str | None = None,
    sections: Any = None,
) -> MoCPage | None:
    page = get_page(db, page_id)
    if page is None:
        return None
    if title is not None:
        page.title = title
    if description is not None:
        page.description = description
    if slug is not None:
        page.slug = slug
    if sections is not None:
        page.sections = _validate_and_normalize_sections(sections)
    page.updated_by = actor_id
    db.commit()
    db.refresh(page)
    return page


def delete_page(
    db: Session, page_id: str, *, actor_id: str | None = None
) -> bool:
    """Soft-delete (is_active=False). Frees the identity tuple for a fresh
    active page at the same (scope, vertical, tenant, slug)."""
    page = get_page(db, page_id)
    if page is None:
        return False
    page.is_active = False
    page.updated_by = actor_id
    db.commit()
    return True


# ── Resolution (read-side) ──────────────────────────────────────────


def resolve_for_context(
    db: Session, *, vertical: str | None, tenant_id: str | None = None
) -> MoCPage | None:
    """Three-tier first-match walk: tenant_override(tenant,vertical) →
    vertical_default(vertical) → platform_default. Returns the most
    specific active page for the context, or None."""
    if tenant_id is not None:
        hit = (
            db.query(MoCPage)
            .filter(
                MoCPage.scope == "tenant_override",
                MoCPage.tenant_id == tenant_id,
                MoCPage.vertical == vertical,
                MoCPage.is_active.is_(True),
            )
            .first()
        )
        if hit:
            return hit
    if vertical is not None:
        hit = (
            db.query(MoCPage)
            .filter(
                MoCPage.scope == "vertical_default",
                MoCPage.vertical == vertical,
                MoCPage.is_active.is_(True),
            )
            .first()
        )
        if hit:
            return hit
    return (
        db.query(MoCPage)
        .filter(
            MoCPage.scope == "platform_default",
            MoCPage.is_active.is_(True),
        )
        .first()
    )


def resolve_references(db: Session, sections: list[dict]) -> list[dict]:
    """Enrich each row with a `resolution` block from its builder's owning
    table. Orphan-tolerant: a vanished artifact → exists=False; an inactive
    one → available=False. Never raises on a bad reference at read."""
    resolved_sections: list[dict] = []
    for section in sections or []:
        rows_out: list[dict] = []
        for row in section.get("rows", []):
            builder = row.get("builder")
            resolver = BUILDERS.get(builder)
            authored = row.get("label", "")
            if resolver is None:
                resolution = _gone(authored)
            else:
                try:
                    resolution = resolver(
                        db, row.get("artifact_id", ""), authored
                    )
                except Exception:  # noqa: BLE001 — read must never error
                    resolution = _gone(authored)
            rows_out.append({**row, "resolution": resolution})
        resolved_sections.append({**section, "rows": rows_out})
    return resolved_sections


def read_page(db: Session, page_id: str) -> dict | None:
    """A page with its references resolved for rendering."""
    page = get_page(db, page_id)
    if page is None:
        return None
    return _to_read_dict(db, page)


def read_for_context(
    db: Session, *, vertical: str | None, tenant_id: str | None = None
) -> dict | None:
    page = resolve_for_context(db, vertical=vertical, tenant_id=tenant_id)
    if page is None:
        return None
    return _to_read_dict(db, page)


def _to_read_dict(db: Session, page: MoCPage) -> dict:
    return {
        "id": page.id,
        "scope": page.scope,
        "vertical": page.vertical,
        "tenant_id": page.tenant_id,
        "slug": page.slug,
        "title": page.title,
        "description": page.description,
        "sections": resolve_references(db, page.sections or []),
    }
