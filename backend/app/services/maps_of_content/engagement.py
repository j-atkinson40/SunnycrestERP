"""The engagement substrate + the suggestions rail rules (The Map Home
campaign, commit sets 3 + 4).

ENGAGEMENT: one row per (user, ponder_key); ONE keyspace across
task/area/onboarding ponders. Written QUIETLY — a single upsert per event,
timestamps only ever SET (first view wins; a re-view doesn't rewrite
history), nothing else. Company-scoped reads.

SUGGESTIONS (rule-based v1, honesty visible): rules in priority, each
carrying its WHY on the card — the why-line is LOAD-BEARING (a suggestion
without an honest reason doesn't ship):
  1. ONBOARDING — an admin with unviewed onboarding compositions IS new;
     the first unviewed (by sequence) surfaces first.
  2. ROLE-RELEVANT AREAS unexplored — a small honest role→area map; only
     areas that actually exist on their map.
  3. RECENCY — a task the user HAS walked whose row changed since
     (updated_at > viewed_at).
THE RESTRAINT PINS: at most `_MAX_SUGGESTIONS` cards, no feed; DISMISSAL
RESPECTED (dismissed_at ends that suggestion — no resurrection);
empty-honest when no rule genuinely fires.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.moc_composition import PonderEngagement

_MAX_SUGGESTIONS = 4
_EVENTS = ("viewed", "completed", "dismissed")

# The honest role→area map (rule 2). Small on purpose — a row here is a
# claim we can put in a why-line. Extend as roles earn areas.
ROLE_AREAS: dict[str, list[str]] = {
    "admin": ["Accounting"],
    "accountant": ["Accounting"],
}


class EngagementError(ValueError):
    pass


def record(
    db: Session, *, user_id: str, company_id: str, ponder_key: str, event: str
) -> PonderEngagement:
    """The quiet write — upsert the row, set the event's timestamp IF UNSET
    (history is written once; a re-view is not a new first view). Commits."""
    if event not in _EVENTS:
        raise EngagementError(f"event must be one of {_EVENTS}")
    row = (
        db.query(PonderEngagement)
        .filter(
            PonderEngagement.user_id == user_id,
            PonderEngagement.ponder_key == ponder_key,
        )
        .first()
    )
    if row is None:
        row = PonderEngagement(
            id=str(uuid.uuid4()), user_id=user_id, company_id=company_id,
            ponder_key=ponder_key,
        )
        db.add(row)
    field = f"{event}_at"
    if getattr(row, field) is None:
        setattr(row, field, datetime.now(timezone.utc))
    db.commit()
    return row


def _rows_for_user(db: Session, user_id: str) -> dict[str, PonderEngagement]:
    return {
        r.ponder_key: r
        for r in db.query(PonderEngagement)
        .filter(PonderEngagement.user_id == user_id)
        .all()
    }


def build_suggestions(
    db: Session, *, user_id: str, company_id: str, vertical: str | None,
    role_slug: str | None, is_admin: bool,
) -> list[dict[str, Any]]:
    """The rail's content — rules in priority, each with its why. Returns
    [] honestly when nothing genuinely fires."""
    from app.services.maps_of_content.area_ponder import list_onboarding
    from app.services.maps_of_content.task_catalog import resolve_task_catalog

    seen = _rows_for_user(db, user_id)

    def _dismissed(key: str) -> bool:
        r = seen.get(key)
        return bool(r and r.dismissed_at)

    def _viewed(key: str) -> bool:
        r = seen.get(key)
        return bool(r and r.viewed_at)

    out: list[dict[str, Any]] = []

    # RULE 1 — ONBOARDING (admins; the first unviewed by sequence).
    if is_admin:
        for comp in list_onboarding(db):
            key = f"onboarding:{comp.key}"
            if _viewed(key) or _dismissed(key):
                continue
            out.append({
                "id": key,
                "rule": "onboarding",
                "title": comp.title or "Get set up",
                "why": "Get set up — you haven't walked this yet.",
                "ponder_key": key,
            })
            break  # one at a time — the sequence advances on completion

    # The merged map (their view) grounds rules 2 + 3.
    tasks = resolve_task_catalog(db, vertical=vertical, tenant_id=company_id)
    areas_with_tasks = {(t.get("task_type") or "General") for t in tasks}

    # RULE 2 — ROLE-RELEVANT AREAS unexplored.
    for area in ROLE_AREAS.get(role_slug or "", []):
        if area not in areas_with_tasks:
            continue
        key = f"area:{vertical}:{area}"
        if _viewed(key) or _dismissed(key):
            continue
        out.append({
            "id": key,
            "rule": "role_area",
            "title": f"How {area} thinks",
            "why": f"You work in {area} — see how it thinks.",
            "ponder_key": key,
        })

    # RULE 3 — RECENCY: a task they walked that changed since.
    for t in tasks:
        key = f"task:{t['id']}"
        r = seen.get(key)
        if not r or not r.viewed_at or r.dismissed_at:
            continue
        updated = t.get("updated_at")
        if not updated:
            continue
        updated_dt = (
            datetime.fromisoformat(updated) if isinstance(updated, str) else updated
        )
        if updated_dt and updated_dt > r.viewed_at:
            out.append({
                "id": key,
                "rule": "recency",
                "title": t["name"],
                "why": f"This changed {updated_dt.strftime('%A')} — see what's new.",
                "ponder_key": key,
            })

    return out[:_MAX_SUGGESTIONS]
