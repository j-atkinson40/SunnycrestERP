"""VerticalInventoryService — counts + recent edits for Studio overview.

Counts strategy:
    For each section that maps to a backend table, count active rows
    (`is_active=True`, plus `deleted_at IS NULL` for document_templates).
    Vertical-scoped requests filter by `vertical = :slug` where the
    table carries that column. Tables WITHOUT a `vertical` column
    (component_class_configurations) return their full count under
    platform scope and ZERO under vertical scope (per spec).
    Sections without a backend table (Registry, Plugin Registry under
    vertical scope) return count=None.

Recent-edits strategy (Path A — per-table updated_at pivot per
Studio 1a-ii locked decision 6):
    Per editor table, SELECT entity_id, display_field, updated_at,
    updated_by (where present) WHERE updated_at >= now() - 7 days.
    Vertical-scoped: filter by vertical column where present.
    UNION across all editor tables; ORDER BY updated_at DESC LIMIT 10.
    Editor email resolved by looking up User by id; falls through to
    None on miss (no PlatformUser join attempted — the FK constraint
    only resolves to `users.id`, and the route layer passes
    `actor_user_id=None` for PlatformUser writes per the canonical
    audit-attribution limitation).

Display-name column choice (documented per table):
    - platform_themes               → "Theme — {mode} ({scope})"
    - focus_compositions (focus)    → "{focus_type}"
    - focus_compositions (edge_pnl) → "{focus_type} (edge panel)"
    - component_configurations      → "{component_kind}:{component_name}"
    - component_class_configurations→ "{component_class} class"
    - workflow_templates            → "{display_name}"
    - document_templates            → "{template_key}"

Deep-link convention:
    `/studio[/{vertical}]/{editor}?{entity-param}={entity_id}`
    Platform-only editors (classes/registry/plugin-registry) drop
    the vertical segment. The entity-param key per editor:
        themes        → ?theme_id=
        focuses       → ?composition_id=    (kind=focus)
        edge-panels   → ?composition_id=    (kind=edge_panel)
        widgets       → ?config_id=
        classes       → ?config_id=
        workflows     → ?template_id=
        documents     → ?template=

Implemented inline rather than wired to per-editor canonical helpers
to keep the service self-contained; if/when an editor changes its
deep-link param, update this module's `_DEEP_LINK_PARAM` map.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.component_class_configuration import ComponentClassConfiguration
from app.models.component_configuration import ComponentConfiguration
from app.models.document_template import DocumentTemplate
from app.models.focus_composition import FocusComposition
from app.models.platform_theme import PlatformTheme
from app.models.user import User
from app.models.workflow_template import WorkflowTemplate
from app.services.plugin_registry import list_category_keys
from app.services.vertical_inventory.schemas import (
    InventoryResponse,
    RecentEditEntry,
    SectionInventoryEntry,
)


logger = logging.getLogger(__name__)


# Mirror of A1's section list in StudioOverviewPage. Order is the
# display order (must stay in sync with the frontend SECTIONS list).
_SECTION_LABELS: list[tuple[str, str]] = [
    ("themes", "Themes"),
    ("focuses", "Focus Editor"),
    ("widgets", "Widget Editor"),
    ("documents", "Documents"),
    ("classes", "Classes"),
    ("workflows", "Workflows"),
    ("edge-panels", "Edge Panels"),
    ("registry", "Registry inspector"),
    ("plugin-registry", "Plugin Registry"),
]


# Sections that are platform-only in the Studio shell. Vertical
# segment is dropped from deep links for these editors.
_PLATFORM_ONLY_EDITORS = {"classes", "registry", "plugin-registry"}


# Entity-query-param convention per editor. Studio 1a-ii spec.
_DEEP_LINK_PARAM: dict[str, str] = {
    "themes": "theme_id",
    "focuses": "composition_id",
    "edge-panels": "composition_id",
    "widgets": "config_id",
    "classes": "config_id",
    "workflows": "template_id",
    "documents": "template",
}


_RECENT_EDITS_WINDOW_DAYS = 7
_RECENT_EDITS_LIMIT = 10


# ─── Public API ──────────────────────────────────────────────────


def get_inventory(
    db: Session,
    vertical_slug: str | None,
) -> InventoryResponse:
    """Compute the Studio overview inventory.

    vertical_slug=None       → Platform-wide scope.
    vertical_slug="<slug>"   → Vertical-scoped (caller should
                                  have validated the slug exists).
    """
    sections = _build_sections(db, vertical_slug)
    recent = _build_recent_edits(db, vertical_slug)
    return InventoryResponse(
        scope="vertical" if vertical_slug else "platform",
        vertical_slug=vertical_slug,
        sections=sections,
        recent_edits=recent,
    )


# ─── Section counts ──────────────────────────────────────────────


def _build_sections(
    db: Session,
    vertical_slug: str | None,
) -> list[SectionInventoryEntry]:
    counts: dict[str, int | None] = {}

    # themes — platform_themes (has vertical column)
    counts["themes"] = _count_with_vertical(
        db, PlatformTheme, vertical_slug, has_vertical=True
    )

    # focuses — focus_compositions WHERE kind='focus'
    counts["focuses"] = _count_focus_compositions(
        db, vertical_slug, kind="focus"
    )

    # widgets — component_configurations WHERE component_kind='widget'
    q_widgets = select(func.count()).select_from(ComponentConfiguration).where(
        ComponentConfiguration.is_active.is_(True),
        ComponentConfiguration.component_kind == "widget",
    )
    if vertical_slug:
        q_widgets = q_widgets.where(
            ComponentConfiguration.vertical == vertical_slug
        )
    counts["widgets"] = int(db.execute(q_widgets).scalar_one())

    # documents — document_templates (soft-delete via deleted_at)
    q_docs = select(func.count()).select_from(DocumentTemplate).where(
        DocumentTemplate.is_active.is_(True),
        DocumentTemplate.deleted_at.is_(None),
    )
    if vertical_slug:
        q_docs = q_docs.where(DocumentTemplate.vertical == vertical_slug)
    counts["documents"] = int(db.execute(q_docs).scalar_one())

    # classes — component_class_configurations (NO vertical column)
    # Platform scope → full count. Vertical scope → 0.
    if vertical_slug:
        counts["classes"] = 0
    else:
        q_classes = (
            select(func.count())
            .select_from(ComponentClassConfiguration)
            .where(ComponentClassConfiguration.is_active.is_(True))
        )
        counts["classes"] = int(db.execute(q_classes).scalar_one())

    # workflows — workflow_templates (has vertical column)
    counts["workflows"] = _count_with_vertical(
        db, WorkflowTemplate, vertical_slug, has_vertical=True
    )

    # edge-panels — focus_compositions WHERE kind='edge_panel'
    counts["edge-panels"] = _count_focus_compositions(
        db, vertical_slug, kind="edge_panel"
    )

    # registry — frontend in-memory; no backend source → None
    counts["registry"] = None

    # plugin-registry — static CATEGORY_CATALOG, platform-global.
    # Vertical scope: catalog is not vertical-scoped → None (per
    # locked decision 7).
    if vertical_slug:
        counts["plugin-registry"] = None
    else:
        counts["plugin-registry"] = len(list_category_keys())

    return [
        SectionInventoryEntry(key=key, label=label, count=counts[key])
        for key, label in _SECTION_LABELS
    ]


def _count_with_vertical(
    db: Session,
    model,
    vertical_slug: str | None,
    *,
    has_vertical: bool,
) -> int:
    q = select(func.count()).select_from(model).where(model.is_active.is_(True))
    if vertical_slug:
        if not has_vertical:
            return 0
        q = q.where(model.vertical == vertical_slug)
    return int(db.execute(q).scalar_one())


def _count_focus_compositions(
    db: Session,
    vertical_slug: str | None,
    *,
    kind: str,
) -> int:
    q = (
        select(func.count())
        .select_from(FocusComposition)
        .where(
            FocusComposition.is_active.is_(True),
            FocusComposition.kind == kind,
        )
    )
    if vertical_slug:
        q = q.where(FocusComposition.vertical == vertical_slug)
    return int(db.execute(q).scalar_one())


# ─── Recent edits ────────────────────────────────────────────────


def _build_recent_edits(
    db: Session,
    vertical_slug: str | None,
) -> list[RecentEditEntry]:
    """UNION across the seven editor tables that carry `updated_at`.

    Implemented as 7 small SELECTs + in-Python merge rather than a
    single SQL UNION. Each editor table has different display-name
    composition rules; pushing the formatting into SQL CASE
    expressions would clutter the query. Each individual SELECT is
    indexed on `updated_at DESC` via the underlying table indexes;
    the in-Python sort + slice is O(n log n) over ~70 candidate rows
    (10 per table × 7 tables).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(
        days=_RECENT_EDITS_WINDOW_DAYS
    )
    candidates: list[RecentEditEntry] = []

    # themes
    q = (
        select(
            PlatformTheme.id,
            PlatformTheme.mode,
            PlatformTheme.scope,
            PlatformTheme.updated_at,
            PlatformTheme.updated_by,
        )
        .where(PlatformTheme.is_active.is_(True))
        .where(PlatformTheme.updated_at >= cutoff)
    )
    if vertical_slug:
        q = q.where(PlatformTheme.vertical == vertical_slug)
    q = q.order_by(PlatformTheme.updated_at.desc()).limit(_RECENT_EDITS_LIMIT)
    for row in db.execute(q).all():
        candidates.append(
            RecentEditEntry(
                section="themes",
                entity_name=f"Theme — {row.mode} ({row.scope})",
                entity_id=row.id,
                editor_email=None,  # resolved below in bulk
                edited_at=row.updated_at,
                deep_link_path=_build_deep_link(
                    "themes", vertical_slug, row.id
                ),
            )
        )

    # focuses + edge-panels (one query, branch by kind)
    q = (
        select(
            FocusComposition.id,
            FocusComposition.focus_type,
            FocusComposition.kind,
            FocusComposition.updated_at,
            FocusComposition.updated_by,
        )
        .where(FocusComposition.is_active.is_(True))
        .where(FocusComposition.updated_at >= cutoff)
    )
    if vertical_slug:
        q = q.where(FocusComposition.vertical == vertical_slug)
    q = q.order_by(FocusComposition.updated_at.desc()).limit(
        _RECENT_EDITS_LIMIT * 2
    )
    for row in db.execute(q).all():
        if row.kind == "edge_panel":
            section = "edge-panels"
            name = f"{row.focus_type} (edge panel)"
        else:
            section = "focuses"
            name = row.focus_type
        candidates.append(
            RecentEditEntry(
                section=section,
                entity_name=name,
                entity_id=row.id,
                editor_email=None,
                edited_at=row.updated_at,
                deep_link_path=_build_deep_link(
                    section, vertical_slug, row.id
                ),
            )
        )

    # widgets (component_configurations WHERE component_kind='widget')
    q = (
        select(
            ComponentConfiguration.id,
            ComponentConfiguration.component_kind,
            ComponentConfiguration.component_name,
            ComponentConfiguration.updated_at,
            ComponentConfiguration.updated_by,
        )
        .where(ComponentConfiguration.is_active.is_(True))
        .where(ComponentConfiguration.component_kind == "widget")
        .where(ComponentConfiguration.updated_at >= cutoff)
    )
    if vertical_slug:
        q = q.where(ComponentConfiguration.vertical == vertical_slug)
    q = q.order_by(ComponentConfiguration.updated_at.desc()).limit(
        _RECENT_EDITS_LIMIT
    )
    for row in db.execute(q).all():
        candidates.append(
            RecentEditEntry(
                section="widgets",
                entity_name=f"{row.component_kind}:{row.component_name}",
                entity_id=row.id,
                editor_email=None,
                edited_at=row.updated_at,
                deep_link_path=_build_deep_link(
                    "widgets", vertical_slug, row.id
                ),
            )
        )

    # documents — no updated_by column. Vertical filter via vertical col.
    q = (
        select(
            DocumentTemplate.id,
            DocumentTemplate.template_key,
            DocumentTemplate.updated_at,
        )
        .where(DocumentTemplate.is_active.is_(True))
        .where(DocumentTemplate.deleted_at.is_(None))
        .where(DocumentTemplate.updated_at >= cutoff)
    )
    if vertical_slug:
        q = q.where(DocumentTemplate.vertical == vertical_slug)
    q = q.order_by(DocumentTemplate.updated_at.desc()).limit(
        _RECENT_EDITS_LIMIT
    )
    for row in db.execute(q).all():
        candidates.append(
            RecentEditEntry(
                section="documents",
                entity_name=row.template_key,
                entity_id=row.id,
                editor_email=None,  # column doesn't exist on this table
                edited_at=row.updated_at,
                deep_link_path=_build_deep_link(
                    "documents", vertical_slug, row.id
                ),
            )
        )

    # classes — no vertical column. Suppressed entirely under
    # vertical scope (mirrors the count: 0 → no edits surface).
    if not vertical_slug:
        q = (
            select(
                ComponentClassConfiguration.id,
                ComponentClassConfiguration.component_class,
                ComponentClassConfiguration.updated_at,
                ComponentClassConfiguration.updated_by,
            )
            .where(ComponentClassConfiguration.is_active.is_(True))
            .where(ComponentClassConfiguration.updated_at >= cutoff)
            .order_by(ComponentClassConfiguration.updated_at.desc())
            .limit(_RECENT_EDITS_LIMIT)
        )
        for row in db.execute(q).all():
            candidates.append(
                RecentEditEntry(
                    section="classes",
                    entity_name=f"{row.component_class} class",
                    entity_id=row.id,
                    editor_email=None,
                    edited_at=row.updated_at,
                    deep_link_path=_build_deep_link(
                        "classes", None, row.id
                    ),
                )
            )

    # workflows
    q = (
        select(
            WorkflowTemplate.id,
            WorkflowTemplate.display_name,
            WorkflowTemplate.updated_at,
            WorkflowTemplate.updated_by,
        )
        .where(WorkflowTemplate.is_active.is_(True))
        .where(WorkflowTemplate.updated_at >= cutoff)
    )
    if vertical_slug:
        q = q.where(WorkflowTemplate.vertical == vertical_slug)
    q = q.order_by(WorkflowTemplate.updated_at.desc()).limit(
        _RECENT_EDITS_LIMIT
    )
    for row in db.execute(q).all():
        candidates.append(
            RecentEditEntry(
                section="workflows",
                entity_name=row.display_name,
                entity_id=row.id,
                editor_email=None,
                edited_at=row.updated_at,
                deep_link_path=_build_deep_link(
                    "workflows", vertical_slug, row.id
                ),
            )
        )

    # Sort merged candidates + truncate to 10.
    candidates.sort(key=lambda r: r.edited_at, reverse=True)
    top = candidates[:_RECENT_EDITS_LIMIT]

    # Resolve editor_email in one batch query. We have to track the
    # source updated_by per candidate — re-collect by re-running the
    # relevant SELECTs would be wasteful. We held updated_by in-row
    # but didn't capture it on the RecentEditEntry (which intentionally
    # exposes editor_email, not user_id, to the API surface).
    # Re-query just the chosen 10 rows to fetch updated_by, then
    # bulk-resolve users.
    if top:
        _resolve_editor_emails(db, top)

    return top


# ─── Editor-email resolution ─────────────────────────────────────


def _resolve_editor_emails(
    db: Session,
    entries: list[RecentEditEntry],
) -> None:
    """Populate `editor_email` on the entries in-place.

    Re-query the source tables for the chosen entries' updated_by
    user_ids, then batch-resolve those user_ids to email addresses
    via a single User SELECT. Entries whose source table lacks
    `updated_by` (documents) or whose updated_by is NULL or
    unresolvable stay at editor_email=None.
    """
    # Build a map from (section, entity_id) → updated_by user_id.
    by_section: dict[str, list[str]] = {}
    for e in entries:
        by_section.setdefault(e.section, []).append(e.entity_id)

    user_id_by_entry: dict[tuple[str, str], str | None] = {}

    if "themes" in by_section:
        ids = by_section["themes"]
        rows = db.execute(
            select(PlatformTheme.id, PlatformTheme.updated_by).where(
                PlatformTheme.id.in_(ids)
            )
        ).all()
        for r in rows:
            user_id_by_entry[("themes", r.id)] = r.updated_by

    if "focuses" in by_section or "edge-panels" in by_section:
        ids = by_section.get("focuses", []) + by_section.get(
            "edge-panels", []
        )
        rows = db.execute(
            select(
                FocusComposition.id,
                FocusComposition.kind,
                FocusComposition.updated_by,
            ).where(FocusComposition.id.in_(ids))
        ).all()
        for r in rows:
            section = "edge-panels" if r.kind == "edge_panel" else "focuses"
            user_id_by_entry[(section, r.id)] = r.updated_by

    if "widgets" in by_section:
        ids = by_section["widgets"]
        rows = db.execute(
            select(
                ComponentConfiguration.id,
                ComponentConfiguration.updated_by,
            ).where(ComponentConfiguration.id.in_(ids))
        ).all()
        for r in rows:
            user_id_by_entry[("widgets", r.id)] = r.updated_by

    if "classes" in by_section:
        ids = by_section["classes"]
        rows = db.execute(
            select(
                ComponentClassConfiguration.id,
                ComponentClassConfiguration.updated_by,
            ).where(ComponentClassConfiguration.id.in_(ids))
        ).all()
        for r in rows:
            user_id_by_entry[("classes", r.id)] = r.updated_by

    if "workflows" in by_section:
        ids = by_section["workflows"]
        rows = db.execute(
            select(
                WorkflowTemplate.id,
                WorkflowTemplate.updated_by,
            ).where(WorkflowTemplate.id.in_(ids))
        ).all()
        for r in rows:
            user_id_by_entry[("workflows", r.id)] = r.updated_by

    # documents has no updated_by — entries stay at None.

    # Batch-resolve user_ids → emails.
    user_ids = {uid for uid in user_id_by_entry.values() if uid}
    email_by_user: dict[str, str] = {}
    if user_ids:
        rows = db.execute(
            select(User.id, User.email).where(User.id.in_(user_ids))
        ).all()
        for r in rows:
            email_by_user[r.id] = r.email

    # Write back into the entries.
    for entry in entries:
        uid = user_id_by_entry.get((entry.section, entry.entity_id))
        if uid and uid in email_by_user:
            entry.editor_email = email_by_user[uid]
        # else: leave None per decision 6.


# ─── Deep-link construction ──────────────────────────────────────


def _build_deep_link(
    section: str,
    vertical_slug: str | None,
    entity_id: str,
) -> str:
    """Construct the Studio URL the entity opens at.

    Platform-only editors drop the vertical segment regardless of
    request scope (matches the frontend's `studioPath()` shape).
    """
    if section in _PLATFORM_ONLY_EDITORS:
        path = f"/studio/{section}"
    elif vertical_slug:
        path = f"/studio/{vertical_slug}/{section}"
    else:
        path = f"/studio/{section}"

    param = _DEEP_LINK_PARAM.get(section)
    if param is None:
        return path
    return f"{path}?{param}={entity_id}"
