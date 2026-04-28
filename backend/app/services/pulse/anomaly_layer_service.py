"""Anomaly layer composition — things needing user attention.

Per BRIDGEABLE_MASTER §3.26.2.3 Anomaly Layer surfaces:
  • Raw agent_anomalies (Phase 1+ accounting agent infrastructure) ✅
  • Blockers and exceptions (computed) ✅ partial
  • SLA risks (computed from delivery data) — STUB for W-4a (no
    SLAAnomaly persistence today; flagged for W-4b agent-job)
  • Compliance flags (Notification.category=safety_alert) ✅
  • Inventory risks (computed from urn_inventory low-stock) ✅
  • Schedule conflicts (computed from Delivery overlap) — STUB for
    W-4a (vault_schedule_service detects but doesn't persist)

**Tenant isolation (load-bearing — same canon as Phase W-3a anomalies
widget):** `agent_anomalies` has no direct `company_id`; tenant
scoping flows through `agent_job_id` FK → `AgentJob.tenant_id`. This
service composes anomalies into Pulse and MUST preserve the same
explicit-tenant-isolation discipline. We delegate raw anomaly fetch
to `anomalies_widget_service.get_anomalies` which already enforces
tenant isolation correctly.

**Anomaly Intelligence Stream (Tier 3 V1) — Commit 5 build:** This
service prepares the raw inputs (anomaly count + severity dist +
top items + work_areas relevance). The Tier 3 rule-based synthesis
("what to watch today" — D6 V1) lives in Commit 5 inside the
frontend AnomalyIntelligenceStream component because the
synthesized prose is presentation-layer concern, not data-layer.
This service surfaces the structured signal; the synthesis is
rendered.

For Phase W-4a Commit 2, the layer composes:
  • Raw `anomalies` widget (Brief variant) — surfaces top critical
    items inline.
  • Anomaly intelligence stream item — synthesis-input payload
    consumed by Commit 5's frontend rule-based template.
  • Compliance flags surfaced as a separate stream (top safety
    alerts) when present.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.pulse.types import LayerContent, LayerItem


# Component keys
ANOMALIES_WIDGET_KEY = "anomalies"  # the existing widget
ANOMALY_INTELLIGENCE_STREAM_KEY = "anomaly_intelligence_stream"
COMPLIANCE_FLAGS_STREAM_KEY = "compliance_flags_stream"


def _build_anomaly_intelligence_stream_item(
    db: Session, *, user: User
) -> LayerItem | None:
    """Compose the Tier 3 V1 anomaly intelligence stream input.

    Reads `agent_anomalies` for the tenant via the canonical
    anomalies_widget_service (which enforces tenant isolation through
    the AgentJob.tenant_id join). Aggregates into a synthesis-ready
    payload:
      • total_unresolved
      • critical_count / warning_count / info_count
      • top_anomalies (top 5 by severity then created_at desc)
      • work_areas (relayed for the frontend template to filter on
        relevance)

    The frontend AnomalyIntelligenceStream component (Commit 5)
    renders this payload via a rule-based template per D6 V1:
      "{N} critical anomalies. Most urgent: {anomaly_type} on
       {entity}. Watch: {top by severity}."

    Returns None when no anomalies are unresolved (suppresses the
    intelligence stream entirely; the layer's empty-state path
    surfaces "All clear").
    """
    from app.services.widgets.anomalies_widget_service import get_anomalies

    response = get_anomalies(
        db,
        user=user,
        severity_filter=None,
        limit=20,
        include_resolved=False,
    )
    total = response.get("total_unresolved", 0)
    if total == 0:
        return None

    anomalies = response.get("anomalies", [])
    return LayerItem(
        item_id="stream:anomaly_intelligence",
        kind="stream",
        component_key=ANOMALY_INTELLIGENCE_STREAM_KEY,
        # Brief variant carries the synthesized intelligence;
        # rendering details handled by the frontend component.
        variant_id="brief",
        cols=2,
        rows=1,
        # High priority within the layer — the synthesized "what to
        # watch today" surfaces above the raw anomalies widget so
        # users see the synthesis first.
        priority=95,
        payload={
            "total_unresolved": total,
            "critical_count": response.get("critical_count", 0),
            "warning_count": response.get("warning_count", 0),
            "info_count": response.get("info_count", 0),
            # Top 5 for the synthesis; frontend template picks the
            # most-urgent N to mention by name.
            "top_anomalies": anomalies[:5],
            # Relay user work_areas so the frontend template can
            # filter for relevance (D6 V1 includes a work-area-
            # relevance filter pass).
            "work_areas": user.work_areas or [],
        },
    )


def _build_anomalies_widget_item(
    db: Session, *, user: User
) -> LayerItem | None:
    """Surface the existing Phase W-3a `anomalies` widget at Brief
    variant inline in the Anomaly layer.

    The widget renders the raw severity-sorted list with the
    Acknowledge action — bounded state-flip per §12.6a. This is
    distinct from the intelligence stream above: the stream
    synthesizes "what to watch"; the widget is the actionable
    inventory of unresolved items.
    """
    from app.services.widgets.anomalies_widget_service import get_anomalies

    response = get_anomalies(
        db, user=user, severity_filter=None, limit=1
    )
    if response.get("total_unresolved", 0) == 0:
        # No anomalies → suppress the widget entirely; the layer
        # advisory will carry "All clear" instead.
        return None

    return LayerItem(
        item_id="widget:anomalies",
        kind="widget",
        component_key=ANOMALIES_WIDGET_KEY,
        variant_id="brief",
        cols=2,
        rows=1,
        # Lower than the intelligence stream — synthesis surfaces
        # first, raw inventory second.
        priority=80,
    )


def _build_compliance_flags_item(
    db: Session, *, user: User
) -> LayerItem | None:
    """Surface critical compliance flags from the notifications table.

    Phase V-1d Notifications absorbed SafetyAlert. Compliance
    breaches surface as `Notification.category='safety_alert'` rows
    with `severity in ('critical', 'high')`. We surface a stream
    item with count + top flags; full list lives at /safety.

    Tenant isolation: Notifications are user-scoped by virtue of the
    fan-out to admin users; we filter by `company_id == user.company_id`
    AND `user_id == user.id` (per-user notifications). For W-4a we
    surface only items addressed to THIS user — fan-out semantics
    already routed safety_alert to admin users per Phase V-1d.
    """
    from app.models.notification import Notification

    rows = (
        db.query(Notification)
        .filter(
            Notification.company_id == user.company_id,
            Notification.user_id == user.id,
            Notification.category == "safety_alert",
            Notification.is_read.is_(False),
            Notification.severity.in_(["critical", "high"]),
        )
        .order_by(Notification.created_at.desc())
        .limit(5)
        .all()
    )
    if not rows:
        return None

    return LayerItem(
        item_id="stream:compliance_flags",
        kind="stream",
        component_key=COMPLIANCE_FLAGS_STREAM_KEY,
        variant_id="brief",
        cols=2,
        rows=1,
        priority=85,
        payload={
            "total_count": len(rows),
            "top_items": [
                {
                    "id": n.id,
                    "title": n.title,
                    "severity": n.severity,
                    "due_date": (
                        n.due_date.isoformat() if n.due_date else None
                    ),
                    "link": n.link,
                }
                for n in rows
            ],
            "navigation_target": "/safety",
        },
    )


# ── Public API ──────────────────────────────────────────────────────


def compose_for_user(
    db: Session,
    *,
    user: User,
) -> LayerContent:
    """Build the Anomaly layer for the given user.

    Composes (in priority order):
      1. Anomaly intelligence stream (synthesized "what to watch")
      2. Compliance flags stream (safety alerts, critical/high)
      3. Raw anomalies widget (Brief variant, per Phase W-3a)

    Empty state: when no anomalies + no compliance flags, returns
    `LayerContent(items=[], advisory="All clear — nothing needs
    attention right now.")` so the frontend renders the canonical
    operational good-state signal.

    Per §3.26.2.4: "Anomaly layer surfaces above standard operational
    content when severity warrants" — the composition engine (Commit
    3) consumes this layer and decides whether to render anomalies
    inline with operational layer based on severity distribution.
    """
    items: list[LayerItem] = []

    intel_item = _build_anomaly_intelligence_stream_item(db, user=user)
    if intel_item:
        items.append(intel_item)

    flags_item = _build_compliance_flags_item(db, user=user)
    if flags_item:
        items.append(flags_item)

    widget_item = _build_anomalies_widget_item(db, user=user)
    if widget_item:
        items.append(widget_item)

    advisory: str | None = None
    if not items:
        # First-class operational signal per §12.10 reference 9
        # (anomalies widget empty state) + Phase W-4a §13.4.2 design.
        advisory = "All clear — nothing needs attention right now."

    # Sort within layer by priority desc; preserves intelligence
    # stream above raw widget.
    items.sort(key=lambda it: (-it.priority, it.component_key))

    return LayerContent(layer="anomaly", items=items, advisory=advisory)
