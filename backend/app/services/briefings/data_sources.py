"""Phase 6 — briefing data assembly.

Reads-only orchestrator that collects every piece of context needed to
generate a narrative briefing. Delegates to:

  - `briefing_service.py` legacy context builders (REUSED VERBATIM —
    months of customer ground-truth tuning; not rewriting)
  - Phase 5 triage `queue_count` + `list_queues_for_user`
  - Phase 3 `space-context` via user.preferences.active_space_id
  - Phase 2 saved-view executor (used selectively when we need row data
    beyond what legacy builders already compute)
  - Call Intelligence `_build_call_summary` legacy path

Returns a `BriefingDataContext` that `generator.py` flattens into prompt
variables. The context is JSON-serializable so it can also be persisted
on the `briefings.generation_context` column for audit / replay.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.user import User
from app.services.briefings.types import BriefingDataContext

logger = logging.getLogger(__name__)


# ── Public entry points ─────────────────────────────────────────────


def collect_data_for_morning_briefing(
    db: Session, user: User, *, requested_sections: list[str] | None = None
) -> BriefingDataContext:
    """Assemble the morning briefing data context.

    Morning orients forward: today's events, overnight changes, pending
    decisions, queue summaries, things flagged for attention.
    """
    return _collect(
        db,
        user,
        requested_sections=requested_sections or [],
        lens="morning",
    )


def collect_data_for_evening_briefing(
    db: Session, user: User, *, requested_sections: list[str] | None = None
) -> BriefingDataContext:
    """Assemble the evening briefing data context.

    Evening closes backward: what got done today, what remains pending,
    tomorrow preview, loose threads.
    """
    return _collect(
        db,
        user,
        requested_sections=requested_sections or [],
        lens="evening",
    )


# ── Implementation ──────────────────────────────────────────────────


def _collect(
    db: Session,
    user: User,
    *,
    requested_sections: list[str],
    lens: str,
) -> BriefingDataContext:
    now = datetime.now(timezone.utc)
    today = date.today()
    day_of_week = today.strftime("%A")

    # Tenant + role context
    company = (
        db.query(Company).filter(Company.id == user.company_id).first()
    )
    company_name = company.name if company else None
    vertical = getattr(company, "preset", None) or "manufacturing"

    role_slug = None
    try:
        if user.role_id:
            from app.models.role import Role

            role = db.query(Role).filter(Role.id == user.role_id).first()
            role_slug = role.slug if role else None
    except Exception:  # pragma: no cover — defensive
        role_slug = None

    # Active space (Phase 3 integration)
    active_space_id = None
    active_space_name = None
    try:
        prefs = user.preferences or {}
        active_space_id = prefs.get("active_space_id")
        if active_space_id:
            for space in prefs.get("spaces") or []:
                if space.get("id") == active_space_id:
                    active_space_name = space.get("name")
                    break
    except Exception:
        pass

    # Narrative tone (existing ai_settings_service integration)
    narrative_tone = "concise"
    try:
        from app.services import ai_settings_service

        settings = ai_settings_service.get_effective_settings(
            db, user.company_id, user.id
        )
        narrative_tone = settings.get("briefing_narrative_tone", "concise")
    except Exception:
        pass

    # Legacy context builders — reuse verbatim per approved coexist strategy.
    legacy_context = _collect_legacy_context(db, user, lens=lens)

    # Triage queues (Phase 5 integration)
    queue_summaries = _collect_queue_summaries(db, user)

    # Call Intelligence (Phase 6 preserves legacy path)
    overnight_calls = None
    try:
        from app.services.briefing_service import _build_call_summary

        call_summary = _build_call_summary(db, user.company_id)
        # Legacy returns {"calls_yesterday": {...}} — unwrap to match our shape
        if call_summary and "calls_yesterday" in call_summary:
            overnight_calls = call_summary["calls_yesterday"]
    except Exception as e:  # pragma: no cover — defensive
        logger.debug("Call Intelligence summary failed: %s", e)

    # Calendar events (today for morning; today + tomorrow for evening)
    today_events, tomorrow_events = _collect_events(db, user, today=today)

    return BriefingDataContext(
        user_id=user.id,
        user_first_name=user.first_name or "there",
        user_last_name=user.last_name,
        company_id=user.company_id,
        company_name=company_name,
        role_slug=role_slug,
        vertical=vertical,
        today_iso=today.isoformat(),
        day_of_week=day_of_week,
        now_iso=now.isoformat(),
        since_last_briefing_iso=None,  # filled in by caller if known
        active_space_id=active_space_id,
        active_space_name=active_space_name,
        legacy_context=legacy_context,
        queue_summaries=queue_summaries,
        overnight_calls=overnight_calls,
        today_events=today_events,
        tomorrow_events=tomorrow_events,
        requested_sections=list(requested_sections),
        narrative_tone=narrative_tone,
    )


def _collect_legacy_context(
    db: Session, user: User, *, lens: str
) -> dict[str, Any]:
    """Call the legacy `briefing_service.py` context builders.

    Each builder is defensive (try/except internal) so a single failure
    yields an empty dict rather than breaking the whole briefing.
    """
    out: dict[str, Any] = {}
    try:
        from app.services.briefing_service import (
            _build_draft_invoice_context,
            _build_executive_context,
            _build_funeral_scheduling_context,
            _build_invoicing_ar_context,
            _build_precast_scheduling_context,
            _build_safety_compliance_context,
        )
    except ImportError as e:
        logger.warning("Legacy briefing context builders unavailable: %s", e)
        return out

    company_id = user.company_id

    # Always pull the executive overview — it's the richest cross-area
    # summary and contains call_summary + revenue + AR + ops KPIs.
    try:
        out["executive"] = _build_executive_context(db, company_id)
    except Exception as e:
        logger.debug("executive context failed: %s", e)

    # Area-specific builders — best-effort; Phase 6 narrative prompt
    # gracefully degrades when a given area returns empty.
    for key, builder in (
        ("funeral_scheduling", _build_funeral_scheduling_context),
        ("precast_scheduling", _build_precast_scheduling_context),
        ("invoicing_ar", _build_invoicing_ar_context),
        ("safety_compliance", _build_safety_compliance_context),
        ("draft_invoices", _build_draft_invoice_context),
    ):
        try:
            out[key] = builder(db, company_id)
        except Exception as e:  # pragma: no cover — defensive
            logger.debug("%s context failed: %s", key, e)
            out[key] = {}

    return out


def _collect_queue_summaries(
    db: Session, user: User
) -> list[dict[str, Any]]:
    """Triage-queue pending counts per Phase 5 integration.

    Iterates every queue visible to the user, calls `queue_count` on each.
    Each summary: {queue_id, queue_name, pending_count, estimated_time_minutes}.
    """
    out: list[dict[str, Any]] = []
    try:
        from app.services.triage import (
            list_queues_for_user,
            queue_count,
        )
    except ImportError:
        return out

    try:
        configs = list_queues_for_user(db, user=user)
    except Exception as e:
        logger.debug("list_queues_for_user failed: %s", e)
        return out

    # Seeded default — 30 sec/item. Refined via telemetry post-arc.
    seconds_per_item = 30.0

    for cfg in configs:
        try:
            n = queue_count(db, user=user, queue_id=cfg.queue_id)
        except Exception:
            n = 0
        if n <= 0:
            # Empty queues still surface so users see "all clear" context,
            # but we filter the zeros to keep the prompt compact.
            continue
        est_minutes = max(1, round((n * seconds_per_item) / 60.0))
        out.append(
            {
                "queue_id": cfg.queue_id,
                "queue_name": cfg.queue_name,
                "pending_count": n,
                "estimated_time_minutes": est_minutes,
            }
        )
    return out


def _collect_events(
    db: Session, user: User, *, today: date
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Pull today + tomorrow VaultItem events for the tenant.

    Returns (today_events, tomorrow_events). Events with company_id
    scoped to the user's tenant; ordered by start time.
    """
    try:
        from app.models.vault_item import VaultItem
    except ImportError:
        return [], []

    tomorrow = today + timedelta(days=1)
    day_after = tomorrow + timedelta(days=1)

    start_today = datetime.combine(today, datetime.min.time()).replace(
        tzinfo=timezone.utc
    )
    start_tomorrow = datetime.combine(tomorrow, datetime.min.time()).replace(
        tzinfo=timezone.utc
    )
    end_tomorrow = datetime.combine(day_after, datetime.min.time()).replace(
        tzinfo=timezone.utc
    )

    try:
        rows = (
            db.query(VaultItem)
            .filter(
                VaultItem.company_id == user.company_id,
                VaultItem.item_type == "event",
                VaultItem.event_start >= start_today,
                VaultItem.event_start < end_tomorrow,
            )
            .order_by(VaultItem.event_start.asc())
            .limit(50)
            .all()
        )
    except Exception as e:
        logger.debug("event query failed: %s", e)
        return [], []

    today_evts: list[dict[str, Any]] = []
    tomorrow_evts: list[dict[str, Any]] = []
    for r in rows:
        entry = {
            "id": r.id,
            "title": r.title,
            "event_type": r.event_type,
            "event_type_sub": r.event_type_sub,
            "event_start": (
                r.event_start.isoformat() if r.event_start else None
            ),
        }
        if r.event_start and r.event_start < start_tomorrow:
            today_evts.append(entry)
        else:
            tomorrow_evts.append(entry)
    return today_evts, tomorrow_evts


__all__ = [
    "collect_data_for_morning_briefing",
    "collect_data_for_evening_briefing",
]
