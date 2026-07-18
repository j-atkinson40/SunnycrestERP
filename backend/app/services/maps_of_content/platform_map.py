"""The map completes itself (2026-07-18) — the Platform area, the
Onboarding journey, tips, and the showroom.

THE GRAMMAR: platform areas are AUTHORED rooms beside the derived
business areas — the spine absorbs both; business derivation is
untouched (pinned). Everything here is a composition on the same table
(the list-not-engine STOP holds): 'platform' cards teach Bridgeable's
primitives, 'onboarding' rows sequence the journey, 'tip' rows are the
stage's smallest stories, 'module' rows are the showroom's never-faces.

AUTHORING IS THE OPERATOR'S: exemplar-grade beats ship; his voice
replaces them through the same authoring surface.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.modules import AVAILABLE_MODULES
from app.models.company_module import CompanyModule
from app.models.moc_composition import MoCComposition
from app.models.moc_composition import PonderEngagement

# The platform rooms, in spine order (after the business areas — stable,
# never personalized). Visibility: Platform teaches everyone; the journey
# and the showroom are admin-led.
PLATFORM_AREAS = (
    {"area": "Platform", "admin_only": False},
    {"area": "Onboarding & Setup", "admin_only": True},
    {"area": "Additional features", "admin_only": True},
)


def _script(row: MoCComposition, task_id: str,
            extra_beats: list[dict] | None = None) -> dict[str, Any]:
    beats = [
        {
            "key": b.get("key", f"beat:{i}"),
            "kind": b.get("kind", "opening"),
            "text": b["text"],
            "derived_text": b["text"],
            "authored": True,
            **({"link": b["link"]} if b.get("link") else {}),
            **({"artifact": b["artifact"]} if b.get("artifact") else {}),
        }
        for i, b in enumerate(row.beats or [])
    ]
    if extra_beats:
        beats = beats[:-1] + extra_beats + beats[-1:] if beats else extra_beats
    return {
        "task_id": task_id, "task_name": row.title or row.key,
        "workflow_name": "", "beats": beats,
        "orphaned_captions": {}, "mirror_drift": [],
        "is_live": False, "vertical": None, "workflow_id": None,
        "fires": None,
    }


def _get_comp(db: Session, kind: str, key: str) -> MoCComposition | None:
    return (
        db.query(MoCComposition)
        .filter(MoCComposition.kind == kind, MoCComposition.key == key,
                MoCComposition.is_active.is_(True))
        .first()
    )


# ── The Platform area's three cards ─────────────────────────────────────

PLATFORM_CARDS = ("pulse", "command-bar", "focuses")


def build_platform_ponder(db: Session, *, key: str,
                          vertical: str | None) -> dict[str, Any]:
    row = _get_comp(db, "platform", key)
    if row is None:
        raise ValueError("Unknown platform card")
    extra: list[dict] = []
    if key == "focuses":
        # THE EXHIBIT GRAMMAR — a REAL focus miniature, resolved live.
        from app.services.maps_of_content.ponder import focus_miniature
        from app.models.focus_template import FocusTemplate
        tmpl = (
            db.query(FocusTemplate)
            .filter(FocusTemplate.is_active.is_(True))
            .order_by(FocusTemplate.template_slug)
            .first()
        )
        if tmpl is not None:
            art = focus_miniature(
                db, template_slug=tmpl.template_slug,
                vertical=vertical or "manufacturing",
                display_name=getattr(tmpl, "display_name", None) or tmpl.template_slug,
            )
            if art:
                extra.append({
                    "key": "exhibit", "kind": "focus",
                    "text": "Here's a real one — exactly as it opens on this "
                            "map today.",
                    "derived_text": "A real focus, resolved live.",
                    "authored": False, "artifact": art,
                })
    return _script(row, f"platform:{key}", extra_beats=extra)


# ── The journey (the relaxing guided path) ──────────────────────────────

def _reality_connect_bank(db: Session, tenant_id: str) -> bool:
    from app.models.plaid import PlaidItem
    return db.query(PlaidItem).filter(
        PlaidItem.tenant_id == tenant_id, PlaidItem.is_active.is_(True)
    ).first() is not None


def _reality_invite_users(db: Session, tenant_id: str) -> bool:
    from app.models.user import User
    return db.query(User).filter(
        User.company_id == tenant_id, User.is_active.is_(True)
    ).count() > 1


def _reality_company_details(db: Session, tenant_id: str) -> bool:
    from app.models.company import Company
    co = db.get(Company, tenant_id)
    return bool(co and (getattr(co, "phone", None) or getattr(co, "address", None)))


# COMPLETION BY REALITY where reality is checkable; by engagement where
# not. A step with no checker completes when any user in the tenant
# finished its walkthrough.
REALITY_CHECKS = {
    "connect-your-bank": _reality_connect_bank,
    "invite-your-users": _reality_invite_users,
    "company-details": _reality_company_details,
}


def build_journey(db: Session, *, tenant_id: str) -> dict[str, Any]:
    """The whole sequence, visible — done quietly marked, current gently,
    ahead open (a journey, not a gate)."""
    comps = (
        db.query(MoCComposition)
        .filter(MoCComposition.kind == "onboarding",
                MoCComposition.is_active.is_(True))
        .order_by(MoCComposition.sequence, MoCComposition.key)
        .all()
    )
    walked_keys = {
        r.ponder_key for r in db.query(PonderEngagement)
        .filter(PonderEngagement.company_id == tenant_id,
                PonderEngagement.completed_at.isnot(None),
                PonderEngagement.ponder_key.like("onboarding:%"))
    }
    steps = []
    current_marked = False
    for c in comps:
        checker = REALITY_CHECKS.get(c.key)
        if checker is not None:
            done = checker(db, tenant_id)
            completion = "reality"
        else:
            done = f"onboarding:{c.key}" in walked_keys
            completion = "engagement"
        state = "done" if done else ("current" if not current_marked else "ahead")
        if not done and not current_marked:
            current_marked = True
        steps.append({
            "key": c.key, "title": c.title or c.key,
            "state": state, "completion": completion,
            "ponder_key": f"onboarding:{c.key}",
        })
    done_count = sum(1 for s in steps if s["state"] == "done")
    return {
        "steps": steps,
        "walked": done_count,
        "total": len(steps),
        "prose": f"{done_count} of {len(steps)} walked",
    }


# ── Tips (the stage's smallest stories) ─────────────────────────────────

def list_tips(db: Session, *, area: str) -> list[dict[str, Any]]:
    """Tips key convention: '<Area>|<slug>'. Empty-honest."""
    rows = (
        db.query(MoCComposition)
        .filter(MoCComposition.kind == "tip",
                MoCComposition.key.like(f"{area}|%"),
                MoCComposition.is_active.is_(True))
        .order_by(MoCComposition.sequence, MoCComposition.key)
        .all()
    )
    return [{"key": r.key, "title": r.title or r.key,
             "ponder_key": f"tip:{r.key}"} for r in rows]


def build_tip_ponder(db: Session, *, key: str) -> dict[str, Any]:
    row = _get_comp(db, "tip", key)
    if row is None:
        raise ValueError("Unknown tip")
    return _script(row, f"tip:{key}")


# ── The showroom (toggle-with-terms) ────────────────────────────────────

# Not-yet cards: authored 'module' compositions whose key isn't in
# AVAILABLE_MODULES — they carry "I'm interested" instead of a toggle.
def showroom(db: Session, *, tenant_id: str) -> dict[str, Any]:
    enabled = {
        m.module for m in db.query(CompanyModule)
        .filter(CompanyModule.company_id == tenant_id,
                CompanyModule.enabled.is_(True))
    }
    cards = []
    for key, meta in AVAILABLE_MODULES.items():
        if meta.get("locked") or key in enabled:
            continue  # the showroom shows what ISN'T on — honest inventory
        cards.append({
            "key": key, "title": meta["label"],
            "description": meta["description"],
            "toggleable": True,
            "ponder_key": f"module:{key}",
        })
    # Authored not-yet cards (payroll et al.) join from compositions.
    for row in (
        db.query(MoCComposition)
        .filter(MoCComposition.kind == "module",
                MoCComposition.is_active.is_(True))
        .all()
    ):
        if row.key in AVAILABLE_MODULES:
            continue  # the catalog card already stands; the comp is its ponder
        cards.append({
            "key": row.key, "title": row.title or row.key,
            "description": (row.beats or [{}])[0].get("text", "")[:140],
            "toggleable": False,
            "ponder_key": f"module:{row.key}",
        })
    return {"cards": sorted(cards, key=lambda c: (not c["toggleable"], c["title"]))}


def build_module_ponder(db: Session, *, key: str,
                        tenant_id: str | None) -> dict[str, Any]:
    """The never-face: authored beats where they exist; derived honest
    teaching from the catalog where not."""
    row = _get_comp(db, "module", key)
    if row is not None:
        return _script(row, f"module:{key}")
    meta = AVAILABLE_MODULES.get(key)
    if meta is None:
        raise ValueError("Unknown module")
    beats = [
        {"key": "opening", "kind": "opening", "text": meta["description"],
         "derived_text": meta["description"], "authored": False},
        {"key": "terms", "kind": "setup",
         "text": "Turn it on and its surfaces light up for your whole "
                 "team — billing per your agreement; turn it off any time "
                 "(surfaces hide; your data remains).",
         "derived_text": "Toggle-with-terms.", "authored": False},
    ]
    return {
        "task_id": f"module:{key}", "task_name": meta["label"],
        "workflow_name": "", "beats": beats,
        "orphaned_captions": {}, "mirror_drift": [],
        "is_live": False, "vertical": None, "workflow_id": None,
        "fires": None,
    }


def set_module_enabled(db: Session, *, tenant_id: str, module_key: str,
                       enabled: bool, actor_user_id: str) -> dict[str, Any]:
    """THE TOGGLE: recorded + the operator notified + the terms stated.
    Locked modules refuse; unknown keys refuse. Disable semantics are the
    gating's own (surfaces hide via hasModule; data untouched) — modules
    with richer disable semantics would be surfaced, not guessed; today's
    toggleables all gate uniformly."""
    meta = AVAILABLE_MODULES.get(module_key)
    if meta is None:
        raise ValueError("Unknown module")
    if meta.get("locked"):
        raise ValueError("This module is part of the core and can't be toggled")
    row = (
        db.query(CompanyModule)
        .filter(CompanyModule.company_id == tenant_id,
                CompanyModule.module == module_key)
        .first()
    )
    if row is None:
        row = CompanyModule(company_id=tenant_id, module=module_key,
                            enabled=enabled)
        db.add(row)
    else:
        row.enabled = enabled
    # THE RECORD — audit-queryable forever.
    from app.services.audit_service import log_action
    log_action(
        db, tenant_id,
        action="module_enabled" if enabled else "module_disabled",
        entity_type="company_module", entity_id=module_key,
        user_id=actor_user_id,
        changes={"module": module_key, "enabled": enabled,
                 "terms": "billing per your agreement"},
    )
    # THE NOTIFY — tenant admins see it (the operator's channel).
    from app.services.notification_service import notify_tenant_admins
    verb = "enabled" if enabled else "disabled"
    notify_tenant_admins(
        db, company_id=tenant_id,
        title=f"{meta['label']} {verb}",
        message=(f"{meta['label']} was {verb} from the map's showroom. "
                 + ("Billing per your agreement." if enabled
                    else "Surfaces are hidden; data remains.")),
        category="modules",
    )
    db.commit()
    return {"module": module_key, "enabled": enabled,
            "terms": "billing per your agreement"}


def record_interest(db: Session, *, tenant_id: str, module_key: str,
                    actor_user_id: str) -> dict[str, Any]:
    """The not-yet card's honest path — interest recorded, never a dead
    toggle."""
    from app.services.audit_service import log_action
    log_action(
        db, tenant_id,
        action="module_interest", entity_type="company_module",
        entity_id=module_key, user_id=actor_user_id,
        changes={"module": module_key},
    )
    from app.services.notification_service import notify_tenant_admins
    notify_tenant_admins(
        db, company_id=tenant_id,
        title="Interest noted",
        message=f"Interest in {module_key} was recorded — it counts toward "
                "when it gets built.",
        category="modules",
    )
    db.commit()
    return {"module": module_key, "interested": True}
