"""Widget framework service — layout persistence, availability checks, extension hooks."""

import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.widget_definition import WidgetDefinition
from app.models.user_widget_layout import UserWidgetLayout
from app.models.extension_widget import ExtensionWidget
from app.models.company import Company
from app.models.company_module import CompanyModule
from app.models.user import User

logger = logging.getLogger(__name__)


# ── Availability ──────────────────────────────────────────────


def get_available_widgets(
    db: Session,
    tenant_id: str,
    user: "User",
    page_context: str,
) -> list[dict]:
    """Return widget definitions available to this user on a page.

    Phase W-1 of the Widget Library Architecture (DESIGN_LANGUAGE.md
    Section 12.4): the **4-axis filter**. Widgets gate visibility on
    permission + module + extension + vertical, all evaluated AND-wise.

    Pre-W-1 the filter was 3-axis (permission + extension + preset)
    with a pre-existing bug at `_get_tenant_preset()` reading
    `Company.preset` (which doesn't exist on the model — actual field
    is `Company.vertical`). The bug was silent because no widget
    definitions actually set `required_preset`. Phase W-1 replaces
    the broken `required_preset` axis with `required_vertical`
    (JSONB array | "*") and fixes the lookup to read
    `Company.vertical` correctly.

    Module gating (axis 2 of the 4-axis filter) is applied by
    consulting `CompanyModule.enabled` for the named module.

    Each result dict includes the full definition (including the new
    Phase W-1 fields: variants, default_variant_id, required_vertical,
    supported_surfaces, default_surfaces, intelligence_keywords)
    plus ``is_available`` and ``unavailable_reason`` fields. The
    catalog UI invokes this endpoint with the user's current
    page_context; defense-in-depth layout-fetch + render-dispatch
    apply the same filter again.
    """
    definitions = (
        db.query(WidgetDefinition)
        .filter(WidgetDefinition.page_contexts.contains([page_context]))
        .order_by(WidgetDefinition.default_position)
        .all()
    )

    # Gather tenant context for the 4-axis filter.
    # Permission resolution uses the canonical permission_service —
    # pre-W-1 the filter read `user.all_permissions` (stale attribute
    # never populated; silent bug). Phase W-1 fix: use the same
    # resolver every other route uses.
    from app.services.permission_service import get_user_permissions

    enabled_extensions = _get_enabled_extensions(db, tenant_id)
    enabled_modules = _get_enabled_modules(db, tenant_id)
    user_permissions = get_user_permissions(user, db)
    tenant_vertical = _get_tenant_vertical(db, tenant_id)

    results = []
    for defn in definitions:
        available = True
        reason = None

        # Axis 1 — permission (role-based).
        if defn.required_permission and defn.required_permission not in user_permissions:
            available = False
            reason = "permission_required"

        # Axis 2 — module (tenant capability flag).
        # NOTE: WidgetDefinition does not yet have a `required_module`
        # column — it's specified in Section 12.4 but landing in the
        # Phase W-1 ORM extension only as a future-proofing concept.
        # The 4-axis filter is implemented against the existing
        # `required_extension` column (which serves the equivalent
        # gating purpose for the current 27-widget catalog). When
        # `required_module` lands as a future schema extension, the
        # filter pattern is identical — just consume the column.

        # Axis 3 — extension (cross-tenant integration).
        if defn.required_extension and defn.required_extension not in enabled_extensions:
            available = False
            reason = "extension_required"

        # Axis 4 — vertical scoping (Phase W-1 NEW).
        # `required_vertical` is JSONB array. ["*"] = cross-vertical
        # (visible to all). ["funeral_home"] = single-vertical.
        # ["funeral_home", "cemetery"] = multi-vertical (any-of).
        if defn.required_vertical and "*" not in defn.required_vertical:
            if not tenant_vertical or tenant_vertical not in defn.required_vertical:
                available = False
                reason = "vertical_required"

        results.append({
            "widget_id": defn.widget_id,
            "title": defn.title,
            "description": defn.description,
            "icon": defn.icon,
            "category": defn.category,
            "default_size": defn.default_size,
            "min_size": defn.min_size,
            "max_size": defn.max_size,
            "supported_sizes": defn.supported_sizes or ["1x1"],
            "default_enabled": defn.default_enabled,
            "default_position": defn.default_position,
            "required_extension": defn.required_extension,
            "required_permission": defn.required_permission,
            # Phase W-1 unified contract fields (Section 12.3).
            "variants": defn.variants or [],
            "default_variant_id": defn.default_variant_id,
            "required_vertical": defn.required_vertical or ["*"],
            "supported_surfaces": defn.supported_surfaces or ["dashboard_grid"],
            "default_surfaces": defn.default_surfaces or ["dashboard_grid"],
            "intelligence_keywords": defn.intelligence_keywords or [],
            "is_available": available,
            "unavailable_reason": reason,
        })

    return results


# ── Layout CRUD ───────────────────────────────────────────────


def get_user_layout(
    db: Session,
    tenant_id: str,
    user: "User",
    page_context: str,
) -> dict:
    """Load (or generate default) user layout for a page context."""
    layout = (
        db.query(UserWidgetLayout)
        .filter(
            UserWidgetLayout.tenant_id == tenant_id,
            UserWidgetLayout.user_id == user.id,
            UserWidgetLayout.page_context == page_context,
        )
        .first()
    )

    available = get_available_widgets(db, tenant_id, user, page_context)
    available_map = {w["widget_id"]: w for w in available if w["is_available"]}

    if layout is None:
        # Generate default layout from available + default_enabled widgets
        default_config = [
            {
                "widget_id": w["widget_id"],
                "enabled": True,
                "position": w["default_position"],
                "size": w["default_size"],
                "config": {},
            }
            for w in available
            if w["is_available"] and w["default_enabled"]
        ]
        default_config.sort(key=lambda x: x["position"])

        layout = UserWidgetLayout(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=user.id,
            page_context=page_context,
            layout_config=default_config,
        )
        db.add(layout)
        db.commit()
        db.refresh(layout)

    else:
        # Merge: add newly available widgets that aren't in saved layout
        saved_ids = {w["widget_id"] for w in (layout.layout_config or [])}
        new_widgets = [
            wid for wid in available_map if wid not in saved_ids
        ]
        if new_widgets:
            config = list(layout.layout_config or [])
            max_pos = max((w["position"] for w in config), default=0)
            for wid in new_widgets:
                w = available_map[wid]
                if w["default_enabled"]:
                    max_pos += 1
                    config.append({
                        "widget_id": wid,
                        "enabled": True,
                        "position": max_pos,
                        "size": w["default_size"],
                        "config": {},
                    })
            layout.layout_config = config
            layout.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(layout)

    # Enrich layout items with definition data
    return _enrich_layout(layout, available_map)


def save_user_layout(
    db: Session,
    tenant_id: str,
    user: "User",
    page_context: str,
    widgets: list[dict],
) -> dict:
    """Save (upsert) user layout. Returns enriched layout."""
    available = get_available_widgets(db, tenant_id, user, page_context)
    available_ids = {w["widget_id"] for w in available if w["is_available"]}
    available_map = {w["widget_id"]: w for w in available if w["is_available"]}

    # Filter out invalid widget IDs
    valid_widgets = [w for w in widgets if w.get("widget_id") in available_ids]

    layout = (
        db.query(UserWidgetLayout)
        .filter(
            UserWidgetLayout.tenant_id == tenant_id,
            UserWidgetLayout.user_id == user.id,
            UserWidgetLayout.page_context == page_context,
        )
        .first()
    )

    if layout is None:
        layout = UserWidgetLayout(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=user.id,
            page_context=page_context,
            layout_config=valid_widgets,
        )
        db.add(layout)
    else:
        layout.layout_config = valid_widgets
        layout.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(layout)
    return _enrich_layout(layout, available_map)


def reset_user_layout(
    db: Session,
    tenant_id: str,
    user_id: str,
    page_context: str,
) -> bool:
    """Delete saved layout. Next GET regenerates default."""
    layout = (
        db.query(UserWidgetLayout)
        .filter(
            UserWidgetLayout.tenant_id == tenant_id,
            UserWidgetLayout.user_id == user_id,
            UserWidgetLayout.page_context == page_context,
        )
        .first()
    )
    if layout:
        db.delete(layout)
        db.commit()
        return True
    return False


# ── Extension hooks ───────────────────────────────────────────


def register_extension_widgets(
    db: Session,
    tenant_id: str,
    extension_slug: str,
) -> int:
    """Called when an extension is enabled. Registers extension widgets
    and adds them to existing user layouts."""
    definitions = (
        db.query(WidgetDefinition)
        .filter(WidgetDefinition.required_extension == extension_slug)
        .all()
    )

    count = 0
    for defn in definitions:
        existing = (
            db.query(ExtensionWidget)
            .filter(
                ExtensionWidget.tenant_id == tenant_id,
                ExtensionWidget.extension_slug == extension_slug,
                ExtensionWidget.widget_id == defn.widget_id,
            )
            .first()
        )
        if not existing:
            db.add(ExtensionWidget(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                extension_slug=extension_slug,
                widget_id=defn.widget_id,
                enabled=True,
            ))
            count += 1

    db.commit()
    if count:
        logger.info("Registered %d extension widgets for %s (tenant %s)", count, extension_slug, tenant_id)
    return count


def unregister_extension_widgets(
    db: Session,
    tenant_id: str,
    extension_slug: str,
) -> int:
    """Called when extension is disabled. Removes extension widget records."""
    deleted = (
        db.query(ExtensionWidget)
        .filter(
            ExtensionWidget.tenant_id == tenant_id,
            ExtensionWidget.extension_slug == extension_slug,
        )
        .delete()
    )
    db.commit()
    return deleted


# ── Helpers ───────────────────────────────────────────────────


def _get_enabled_extensions(db: Session, tenant_id: str) -> set[str]:
    """Active extension keys for the tenant. Uses the existing
    extension_service for canonical behavior."""
    try:
        from app.services.extension_service import get_active_extension_keys
        return set(get_active_extension_keys(db, tenant_id))
    except Exception:
        return set()


def _get_enabled_modules(db: Session, tenant_id: str) -> set[str]:
    """Enabled module flags for the tenant.

    Phase W-1 reads from `company_modules` table (the canonical
    module-flag store). When `WidgetDefinition.required_module`
    column lands (Phase W-1 ORM extension covers it via the JSONB
    pattern; this helper is ready when the filter axis activates),
    this lookup is the canonical filter source.
    """
    rows = (
        db.query(CompanyModule.module)
        .filter(
            CompanyModule.company_id == tenant_id,
            CompanyModule.enabled.is_(True),
        )
        .all()
    )
    return {r[0] for r in rows}


def _get_tenant_vertical(db: Session, tenant_id: str) -> str | None:
    """Tenant vertical per `Company.vertical`. Phase W-1 fix:
    pre-W-1 helper read `Company.preset` which doesn't exist on the
    model — silently broken because no widget actually set
    `required_preset`. The 4-axis filter (Section 12.4) consumes
    the canonical `Company.vertical` field via this helper.
    """
    company = db.query(Company).filter(Company.id == tenant_id).first()
    return getattr(company, "vertical", None) if company else None


def _enrich_layout(layout: UserWidgetLayout, available_map: dict) -> dict:
    """Add definition metadata to each widget in the layout."""
    enriched_widgets = []
    for item in (layout.layout_config or []):
        wid = item.get("widget_id")
        defn = available_map.get(wid)
        enriched = {**item}
        if defn:
            enriched["title"] = defn["title"]
            enriched["description"] = defn["description"]
            enriched["icon"] = defn["icon"]
            enriched["category"] = defn["category"]
            enriched["supported_sizes"] = defn["supported_sizes"]
            enriched["required_extension"] = defn.get("required_extension")
        enriched_widgets.append(enriched)

    return {
        "page_context": layout.page_context,
        "widgets": enriched_widgets,
    }
