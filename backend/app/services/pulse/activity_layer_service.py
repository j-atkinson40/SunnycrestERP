"""Activity layer composition — recent context.

Per BRIDGEABLE_MASTER §3.26.2.3 Activity Layer surfaces:
  • What changed while you were away ✅ (V-1c recent_activity locked)
  • Recent customer communications — Phase W-4b STUB (depends on
    email native primitive)
  • Recent system events (Workflow Engine + AgentJob completions) ✅
    partial — ad-hoc query for W-4a; richer wiring post-W-4b
  • Recent cross-tenant communications — Phase W-4b STUB
  • Updates to entities you're watching — Post-arc STUB (no watch
    system today)

For Phase W-4a Commit 2, the layer composes:
  • Recent activity widget (Brief variant per Phase W-3a) — surfaces
    top events with actor_name + entity + timestamp via the V-1c
    `recent_activity` widget.
  • System events stream (ad-hoc) — recent AgentJob completions in
    last 24h. Surfaces "what the system did overnight" per
    §3.26.2.3 Activity Layer ambient context.

**Tenant isolation:** the V-1c `get_tenant_feed` enforces tenant
isolation via `ActivityLog.tenant_id`. AgentJob queries explicitly
filter by `tenant_id`. Cross-tenant leakage is prevented at the
data source.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.pulse.types import LayerContent, LayerItem


# Component keys
RECENT_ACTIVITY_WIDGET_KEY = "recent_activity"  # the existing widget
SYSTEM_EVENTS_STREAM_KEY = "system_events_stream"


def _build_recent_activity_widget_item(
    db: Session, *, user: User
) -> LayerItem | None:
    """Surface the existing Phase W-3a `recent_activity` widget at
    Brief variant in the Activity layer.

    The widget self-fetches via `/api/v1/vault/activity/recent`,
    which delegates to `activity_log_service.get_tenant_feed` — the
    canonical tenant-scoped feed. We only emit the LayerItem when
    there's recent activity to show; otherwise the layer's
    advisory carries a quiet "Quiet day so far" message.

    Probe whether to surface by counting recent activity in the last
    7 days. If empty, suppress the widget. (The widget itself
    handles its own empty state, but suppressing at the Pulse
    composition level prevents an empty card from taking layout
    space when the user genuinely has no activity to surface.)
    """
    from app.services.crm.activity_log_service import get_tenant_feed

    try:
        feed = get_tenant_feed(
            db,
            user.company_id,
            limit=1,
            since=datetime.now(timezone.utc) - timedelta(days=7),
        )
    except Exception:
        # Defensive — activity feed errors must not blank the
        # entire layer. Skip the widget on error; system events
        # stream may still surface.
        return None

    if not feed:
        return None

    return LayerItem(
        item_id="widget:recent_activity",
        kind="widget",
        component_key=RECENT_ACTIVITY_WIDGET_KEY,
        variant_id="brief",
        cols=2,
        rows=1,
        # Activity layer is ambient/peripheral per §3.26.2.4 — lower
        # priority than Personal/Operational/Anomaly layers.
        priority=50,
    )


def _build_system_events_item(
    db: Session, *, user: User
) -> LayerItem | None:
    """Surface a stream of recent AgentJob completions.

    Phase 8b accounting agents + Phase 8c-d migrations + Phase 8e+
    workflow engine all complete via `AgentJob` rows. Pulse Activity
    layer surfaces "what the system did" in the trailing 24h —
    agent completions, workflow runs, etc.

    For Phase W-4a we surface AgentJob completions. WorkflowRun
    completions could also surface but the WorkflowRun feed isn't
    yet wired up cleanly; defer to W-4b.
    """
    from app.models.agent import AgentJob

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    rows: list[AgentJob] = (
        db.query(AgentJob)
        .filter(
            AgentJob.tenant_id == user.company_id,
            AgentJob.status.in_(
                ["complete", "approved", "rejected", "failed"]
            ),
            AgentJob.completed_at.isnot(None),
            AgentJob.completed_at >= since,
        )
        .order_by(AgentJob.completed_at.desc())
        .limit(5)
        .all()
    )
    if not rows:
        return None
    return LayerItem(
        item_id="stream:system_events",
        kind="stream",
        component_key=SYSTEM_EVENTS_STREAM_KEY,
        variant_id="brief",
        cols=2,
        rows=1,
        # Lower priority than recent_activity — system events are
        # ambient context that user can ignore most days.
        priority=40,
        payload={
            "total_count": len(rows),
            "top_items": [
                {
                    "id": j.id,
                    "job_type": j.job_type,
                    "status": j.status,
                    "completed_at": (
                        j.completed_at.isoformat()
                        if j.completed_at
                        else None
                    ),
                }
                for j in rows
            ],
            "navigation_target": "/agents",
        },
    )


# ── Public API ──────────────────────────────────────────────────────


def compose_for_user(
    db: Session,
    *,
    user: User,
) -> LayerContent:
    """Build the Activity layer for the given user.

    Returns recent_activity (Brief widget) + system events stream
    (when populated). Per §3.26.2.4 "Activity layer ambient at
    periphery" — lower priorities than Personal/Operational/Anomaly.

    Empty state: when nothing surfaces, returns advisory "Quiet day
    so far." which the frontend may render as a small italic note
    or suppress entirely.
    """
    items: list[LayerItem] = []

    activity_item = _build_recent_activity_widget_item(db, user=user)
    if activity_item:
        items.append(activity_item)

    events_item = _build_system_events_item(db, user=user)
    if events_item:
        items.append(events_item)

    advisory: str | None = None
    if not items:
        advisory = "Quiet day so far."

    items.sort(key=lambda it: (-it.priority, it.component_key))

    return LayerContent(layer="activity", items=items, advisory=advisory)
