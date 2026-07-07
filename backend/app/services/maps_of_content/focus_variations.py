"""Focus variations — the guided flow's orchestration (Focus Variations V-1).

ONE service call materializes the operator's whole gesture: name → verticals
(multi) → task wiring → the Tier 2 variation, refs auto-authored onto each
chosen vertical's map (the keystone: CREATION LIGHTS THE MAPS — a variation
never exists off-map).

Steps, in order:
  1. Create the Tier 2 template (scope=vertical_default, home vertical =
     first chosen; `inherits_from_core_version` pinned from the live core by
     create_template — the r96 column earning its keep). rows=[] — a
     core-derived variation starts fully-inheriting.
  2. Write the slug-keyed multi-vertical join rows (home included — uniform
     reads; r120).
  3. Wire tasks (the focus join from the FOCUS side): append the variation to
     each task's focus set — read-modify-write via patch_task's replace
     semantics, append-if-absent so re-runs are no-ops.
  4. Auto-author a ref row onto each chosen vertical's MoC page (find-or-
     create the 'focus-defaults' section; append-if-absent by artifact).

NOT atomic across steps: the underlying services commit per-step (their
shipped contract). Steps 3 + 4 are append-if-absent, so a retry after a
mid-flow failure converges rather than duplicating. A failure surfaces as
FocusVariationError with the step named — never silent.
"""

from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy.orm import Session

from app.models.focus_template_vertical import FocusTemplateVertical
from app.models.moc_page import MoCPage
from app.models.moc_task_catalog import MoCTaskCatalog
from app.services.focus_template_inheritance import (
    create_template,
    get_core_by_id,
    get_template_by_slug,
)
from app.services.maps_of_content import service as moc_service
from app.services.maps_of_content.task_catalog import patch_task

logger = logging.getLogger(__name__)


class FocusVariationError(Exception):
    """A guided-flow step failed — message names the step."""


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:80] or f"variation-{uuid.uuid4().hex[:8]}"


def _unique_slug(db: Session, base: str, *, vertical: str) -> str:
    """create_template VERSION-BUMPS on a (scope, vertical, slug) collision —
    a name collision must mint a fresh lineage, never hijack an existing one."""
    slug = base
    n = 2
    while (
        get_template_by_slug(
            db, slug, scope="vertical_default", vertical=vertical
        )
        is not None
    ):
        slug = f"{base}-{n}"
        n += 1
    return slug


def create_focus_variation(
    db: Session,
    *,
    core_id: str,
    display_name: str,
    verticals: list[str],
    task_ids: list[str] | None = None,
    actor_id: str | None = None,
) -> dict:
    if not display_name or not display_name.strip():
        raise FocusVariationError("display_name is required")
    if not verticals:
        raise FocusVariationError("at least one vertical is required")
    core = get_core_by_id(db, core_id)
    if core is None or not core.is_active:
        raise FocusVariationError(f"core {core_id!r} not found or inactive")

    display_name = display_name.strip()
    home = verticals[0]
    slug = _unique_slug(db, _slugify(display_name), vertical=home)

    # 1. The Tier 2 variation (create_template pins inherits_from_core_version
    #    from the live active core row + commits).
    template = create_template(
        db,
        scope="vertical_default",
        vertical=home,
        template_slug=slug,
        display_name=display_name,
        description=f"Variation of {core.display_name}.",
        inherits_from_core_id=core.id,
        rows=[],
        canvas_config={},
        created_by=actor_id,
    )

    # 2. The multi-vertical join (slug-keyed, home included). Append-if-
    #    absent like steps 3+4 — a retry after a mid-flow failure (or a
    #    recreated lineage whose slug-keyed joins outlived a deleted
    #    template) converges instead of tripping the unique pair.
    existing_joins = {
        j.vertical
        for j in db.query(FocusTemplateVertical).filter(
            FocusTemplateVertical.template_slug == slug
        )
    }
    for v in verticals:
        if v in existing_joins:
            continue
        db.add(
            FocusTemplateVertical(
                template_slug=slug, vertical=v, created_by=actor_id
            )
        )
    db.commit()

    # 3. Task wiring — append-if-absent through patch_task's replace
    #    semantics (validates refs; caller commits).
    wired: list[str] = []
    for task_id in task_ids or []:
        task = db.get(MoCTaskCatalog, task_id)
        if task is None or not task.is_active:
            raise FocusVariationError(f"task {task_id!r} not found (wiring)")
        current = [f.focus_template_id for f in task.focuses]
        if template.id in current:
            continue
        patch_task(
            db,
            task_id=task_id,
            focus_template_ids=[*current, template.id],
            actor_id=actor_id,
        )
        wired.append(task_id)
    db.commit()

    # 4. Auto-author the map refs (the keystone).
    authored: list[str] = []
    for v in verticals:
        if _author_ref_on_vertical_page(
            db,
            vertical=v,
            artifact_id=template.id,
            label=display_name,
            actor_id=actor_id,
        ):
            authored.append(v)

    return {
        "template_id": template.id,
        "template_slug": slug,
        "display_name": display_name,
        "home_vertical": home,
        "verticals": verticals,
        "wired_task_ids": wired,
        "authored_verticals": authored,
    }


def _author_ref_on_vertical_page(
    db: Session,
    *,
    vertical: str,
    artifact_id: str,
    label: str,
    actor_id: str | None,
) -> bool:
    """Append a focuses ref to the vertical's map — find-or-create the
    'focus-defaults' section; append-if-absent by artifact_id. Returns True
    when the page now carries the ref (False = no map page for the vertical
    yet; logged, not fatal — the ref appears when the vertical's map is
    seeded and the operator re-runs the flow or authors by hand)."""
    page = (
        db.query(MoCPage)
        .filter(
            MoCPage.scope == "vertical_default",
            MoCPage.vertical == vertical,
            MoCPage.is_active.is_(True),
        )
        .first()
    )
    if page is None:
        logger.warning(
            "focus variation: vertical %r has no MoC page — ref not authored",
            vertical,
        )
        return False
    sections = [dict(s) for s in (page.sections or [])]
    target = None
    for s in sections:
        if s.get("section_id") == "focus-defaults" or s.get("title") == "Focuses":
            target = s
            break
    if target is None:
        target = {
            "section_id": "focus-defaults",
            "title": "Focuses",
            "description": "This vertical's Focus variations.",
            "rows": [],
        }
        sections.append(target)
    rows = list(target.get("rows") or [])
    if any(r.get("artifact_id") == artifact_id for r in rows):
        return True  # already authored — append-if-absent
    rows.append(
        {
            "row_id": f"fvar-{uuid.uuid4().hex[:8]}",
            "builder": "focuses",
            "artifact_id": artifact_id,
            "label": label,
            "icon": "focus",
        }
    )
    target["rows"] = rows
    moc_service.update_page(
        db, page.id, sections=sections, actor_id=actor_id
    )
    return True
