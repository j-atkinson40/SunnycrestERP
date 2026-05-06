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

    Phase W-1 + W-3a of the Widget Library Architecture
    ([DESIGN_LANGUAGE.md §12.4](../../../DESIGN_LANGUAGE.md)): the **5-axis
    filter**. Widgets gate visibility on permission + module + extension
    + vertical + product_line, all evaluated AND-wise.

    Pre-W-1 the filter was 3-axis (permission + extension + preset)
    with a pre-existing bug at `_get_tenant_preset()` reading
    `Company.preset` (which doesn't exist on the model — actual field
    is `Company.vertical`). Phase W-1 replaced `required_preset` with
    `required_vertical` (JSONB array | "*") and fixed the lookup.

    Phase W-3a (April 2026) added the 5th axis (`required_product_line`)
    per Product Line + Operating Mode canon. Per
    [BRIDGEABLE_MASTER §5.2.1](../../../BRIDGEABLE_MASTER.md):
    **Extension = how a line gets installed (or not — vault is built-in).
    Product line = the operational reality once installed.** The two
    axes are intentionally distinct because vault is a baseline product
    line that is NOT extension-gated, but vault widgets need to scope
    to "vault product line activated for this tenant".

    Module gating (axis 2) is applied via `CompanyModule.enabled`.

    Each result dict includes the full definition + ``is_available`` +
    ``unavailable_reason`` fields. The catalog UI invokes this endpoint
    with the user's current page_context; defense-in-depth layout-fetch
    + render-dispatch apply the same filter again.
    """
    definitions = (
        db.query(WidgetDefinition)
        .filter(WidgetDefinition.page_contexts.contains([page_context]))
        .order_by(WidgetDefinition.default_position)
        .all()
    )

    # Gather tenant context for the 5-axis filter.
    # Permission resolution uses the canonical permission_service —
    # pre-W-1 the filter read `user.all_permissions` (stale attribute
    # never populated; silent bug). Phase W-1 fix: use the same
    # resolver every other route uses.
    from app.services.permission_service import get_user_permissions

    enabled_extensions = _get_enabled_extensions(db, tenant_id)
    enabled_modules = _get_enabled_modules(db, tenant_id)
    user_permissions = get_user_permissions(user, db)
    tenant_vertical = _get_tenant_vertical(db, tenant_id)
    enabled_product_lines = _get_enabled_product_lines(db, tenant_id)

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

        # Axis 4 — vertical scoping (Phase W-1).
        # `required_vertical` is JSONB array. ["*"] = cross-vertical
        # (visible to all). ["funeral_home"] = single-vertical.
        # ["funeral_home", "cemetery"] = multi-vertical (any-of).
        if defn.required_vertical and "*" not in defn.required_vertical:
            if not tenant_vertical or tenant_vertical not in defn.required_vertical:
                available = False
                reason = "vertical_required"

        # Axis 5 — product line scoping (Phase W-3a NEW).
        # `required_product_line` is JSONB array. ["*"] = cross-line
        # (visible regardless of which lines the tenant runs).
        # ["vault"] = vault-line-only (e.g., vault_schedule widget).
        # ["vault", "redi_rock"] = multi-line (any-of). Per Section
        # 12.4: defaults to ["*"] when absent or empty (defensive).
        # Resolved against TenantProductLine.line_key with is_enabled=True.
        required_lines = defn.required_product_line or ["*"]
        if "*" not in required_lines:
            if not any(line in enabled_product_lines for line in required_lines):
                available = False
                reason = "product_line_required"

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
            # Phase W-1 + W-3a unified contract fields (Section 12.3).
            "variants": defn.variants or [],
            "default_variant_id": defn.default_variant_id,
            "required_vertical": defn.required_vertical or ["*"],
            "required_product_line": required_lines,
            "supported_surfaces": defn.supported_surfaces or ["dashboard_grid"],
            "default_surfaces": defn.default_surfaces or ["dashboard_grid"],
            "intelligence_keywords": defn.intelligence_keywords or [],
            "is_available": available,
            "unavailable_reason": reason,
        })

    return results


def get_widgets_for_surface(
    db: Session,
    tenant_id: str,
    user: "User",
    surface: str,
) -> list[dict]:
    """Return widget definitions that declare ``surface`` in their
    supported_surfaces, filtered by the 4-axis filter against the
    union of their declared page_contexts.

    Widget Library Phase W-2 — surface-scoped catalog endpoint.
    Sidebar pinning (`surface="spaces_pin"`) is page-context-
    independent: the pin follows the user across pages, not a
    specific dashboard. To preserve the 4-axis filter (permission +
    module + extension + vertical) we evaluate visibility against
    each declared page_context and consider the widget available iff
    the user passes the filter for AT LEAST ONE of them. This
    matches the defense-in-depth check at `add_pin()` time per
    DESIGN_LANGUAGE.md §12.4.

    Surface check uses JSONB containment so dropdown / selection of
    valid sidebar widgets is consistent with crud.py's `add_pin`
    surface gate.

    Returns the same shape as :func:`get_available_widgets` so the
    frontend WidgetPicker (`destination="sidebar"`) can consume both
    interchangeably.
    """
    definitions = (
        db.query(WidgetDefinition)
        .filter(WidgetDefinition.supported_surfaces.contains([surface]))
        .order_by(WidgetDefinition.default_position)
        .all()
    )

    if not definitions:
        return []

    # Compute available-per-context lookup ONCE per page_context.
    # Most widgets declare 1-2 contexts; this avoids re-running the
    # 4-axis filter for every widget × every context combination.
    contexts_seen: dict[str, dict[str, dict]] = {}

    def _is_widget_available_in_context(widget_id: str, ctx: str) -> tuple[bool, str | None]:
        if ctx not in contexts_seen:
            available = get_available_widgets(db, tenant_id, user, ctx)
            contexts_seen[ctx] = {w["widget_id"]: w for w in available}
        widget = contexts_seen[ctx].get(widget_id)
        if widget is None:
            return False, "unknown_in_context"
        return widget["is_available"], widget.get("unavailable_reason")

    results = []
    for defn in definitions:
        contexts = defn.page_contexts or []
        is_available = False
        first_reason: str | None = None
        for ctx in contexts:
            ok, reason = _is_widget_available_in_context(defn.widget_id, ctx)
            if ok:
                is_available = True
                break
            if first_reason is None:
                first_reason = reason

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
            "variants": defn.variants or [],
            "default_variant_id": defn.default_variant_id,
            "required_vertical": defn.required_vertical or ["*"],
            "required_product_line": defn.required_product_line or ["*"],
            "supported_surfaces": defn.supported_surfaces or ["dashboard_grid"],
            "default_surfaces": defn.default_surfaces or ["dashboard_grid"],
            "intelligence_keywords": defn.intelligence_keywords or [],
            "is_available": is_available,
            "unavailable_reason": first_reason if not is_available else None,
        })

    return results


# ── Layout CRUD ───────────────────────────────────────────────


def _resolve_default_layout_config(
    db: Session,
    tenant_id: str,
    page_context: str,
    available: list[dict],
) -> list[dict]:
    """Compute the default layout for a tenant + page_context by
    walking the 3-tier inheritance chain shipped Phase R-0.

    Resolution chain:
        platform_default
            ← vertical_default(tenant.vertical)
                ← tenant_default(tenant_id)

    Returns the deepest non-empty resolved layout, or — if no row
    exists at any scope — falls back to the in-code WIDGET_DEFINITIONS
    `default_position` defaults (the pre-R-0 behavior).
    """
    # Lazy import — dashboard_layouts service is a sibling, but this
    # keeps the dependency direction clean.
    from app.services.dashboard_layouts import resolve_layout

    tenant_vertical = _get_tenant_vertical(db, tenant_id)

    resolved = resolve_layout(
        db,
        page_context=page_context,
        vertical=tenant_vertical,
        tenant_id=tenant_id,
    )
    layout_config = resolved.get("layout_config") or []
    if layout_config:
        return list(layout_config)

    # No row at any scope — pre-R-0 fallback to in-code defaults.
    fallback = [
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
    fallback.sort(key=lambda x: x["position"])
    return fallback


def get_user_layout(
    db: Session,
    tenant_id: str,
    user: "User",
    page_context: str,
) -> dict:
    """Load (or generate default) user layout for a page context.

    Phase R-0 of the Runtime-Aware Editor extends default-layout
    generation to consume the new `dashboard_layouts` 3-tier
    inheritance chain (`platform_default → vertical_default →
    tenant_default`) before falling back to in-code WIDGET_DEFINITIONS
    defaults. Per-user overrides via `user_widget_layouts` continue to
    win when present — this method is the user-override tier of the
    resolution chain.
    """
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
        # Generate default layout — walks dashboard_layouts inheritance
        # chain (Phase R-0), falls back to in-code defaults if no row
        # exists at any scope.
        default_config = _resolve_default_layout_config(
            db, tenant_id, page_context, available
        )

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


def _get_enabled_product_lines(db: Session, tenant_id: str) -> set[str]:
    """Enabled product line keys for the tenant. Phase W-3a — 5th axis.

    Reads `tenant_product_lines.line_key` for rows with `is_enabled=True`.
    Returns the set of canonical line_keys (e.g. {"vault", "urn_sales"}).
    Used by axis 5 of the 5-axis filter to evaluate
    `WidgetDefinition.required_product_line`.

    Per [BRIDGEABLE_MASTER §5.2.1](../../../BRIDGEABLE_MASTER.md): a
    tenant runs N product lines, each in its own operating mode. The
    visibility axis cares only about activation state (which lines are
    on); the operating mode (production / purchase / hybrid) is read at
    render time by mode-aware widgets, NOT here.

    Defensive on import — `TenantProductLine` model is in the codebase
    pre-canon but the migration backfilling existing manufacturing
    tenants with vault rows ships in r60. If the table is empty for a
    tenant (e.g. the migration hasn't run, or a non-manufacturing
    tenant), this returns an empty set — line-scoped widgets become
    invisible to that tenant. Cross-line widgets ("*") remain visible.
    """
    try:
        from app.models.tenant_product_line import TenantProductLine

        rows = (
            db.query(TenantProductLine.line_key)
            .filter(
                TenantProductLine.company_id == tenant_id,
                TenantProductLine.is_enabled.is_(True),
            )
            .all()
        )
        return {r[0] for r in rows}
    except Exception:
        # Defensive — if the model isn't importable (mid-migration or
        # tests with stale schema), behave as if no lines are activated.
        # Cross-line widgets ("*") remain visible; line-scoped widgets
        # become invisible. Better than crashing the catalog endpoint.
        return set()


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
