"""Pulse composition engine — Phase W-4a Commit 3.

Orchestrates the four layer services (personal / operational /
anomaly / activity) into a single `PulseComposition` response per
BRIDGEABLE_MASTER §3.26.2. Consumed by the
`GET /api/v1/pulse/composition` endpoint.

**Responsibilities:**
  • Resolve time-of-day signal in tenant timezone
  • Call each layer service (sequential — per-layer queries are
    each modest; orchestrator stays simple)
  • Generate V1 anomaly intelligence stream from anomaly layer's
    payload
  • Assemble layers in canonical order (Personal → Operational →
    Anomaly → Activity per §3.26.2.4)
  • Apply work_areas-aware caching per D1 (5-min TTL,
    work_areas-hash invalidation)

**Replaces** the legacy `app.services.spaces.pulse_compositions`
infrastructure shell (D7). The legacy module keyed on
`(vertical, role_slug)`; this engine keys on `user.work_areas`
per the canon shipped April 27. Legacy module is retired in Commit
3.7 with grep verification.

**Sizing rules (per the user's Commit 3 spec section 2):**
  • Layer services already emit per-item sizing in their
    `LayerItem.cols/rows`. The engine respects layer-service-emitted
    sizing — it's the layer's responsibility to know what variant
    each widget should render at per the work_areas mapping +
    vertical defaults.
  • The engine adds NO additional sizing pass for Phase W-4a; the
    layer services have the necessary context (work_areas, primary
    vs secondary widgets per the WORK_AREA_WIDGET_MAPPING) to make
    sizing decisions.
  • Future iterations (post-W-4a) may add a global priority cascade
    if viewport hints become available, but for now sizing is a
    layer-service concern.

**Tenant isolation:** every layer service enforces tenant scoping
on its own queries; the engine doesn't add another filter pass.
The User passed in is the authoritative scope.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.user import User
from app.services.pulse import (
    activity_layer_service,
    anomaly_intelligence_v1,
    anomaly_layer_service,
    composition_cache,
    operational_layer_service,
    personal_layer_service,
)
from app.services.pulse.types import (
    IntelligenceStream,
    LayerContent,
    PulseComposition,
    PulseCompositionMetadata,
    TimeOfDaySignal,
)

logger = logging.getLogger(__name__)


# ── Time-of-day resolution ──────────────────────────────────────────


# Boundaries (24h clock in tenant local time):
#   off_hours   : 0:00 - 5:59
#   morning     : 6:00 - 11:59
#   midday      : 12:00 - 16:59
#   end_of_day  : 17:00 - 20:59
#   off_hours   : 21:00 - 23:59 (wraps via prefix branch)
def _resolve_time_of_day(
    db: Session, tenant_id: str
) -> TimeOfDaySignal:
    """Resolve the time-of-day signal in the tenant's timezone.

    Used for Tier 1 rule-based composition adjustments per
    §3.26.2.5 ("Time-of-day adaptation"). For Phase W-4a Commit 3
    the engine surfaces the signal in metadata so the frontend can
    apply subtle UX cues; no layer-service composition currently
    branches on time_of_day.
    """
    company = (
        db.query(Company).filter(Company.id == tenant_id).first()
    )
    tz_name = (
        getattr(company, "timezone", None) or "America/New_York"
        if company
        else "America/New_York"
    )
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("America/New_York")
    hour = datetime.now(tz).hour
    if 6 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "midday"
    if 17 <= hour < 21:
        return "end_of_day"
    return "off_hours"


# ── Engine ─────────────────────────────────────────────────────────


def _compose_uncached(db: Session, *, user: User) -> PulseComposition:
    """The actual composition path — runs every layer service and
    synthesizes the intelligence streams. Cache layer wraps this.
    """
    work_areas = list(user.work_areas or [])
    vertical_default_applied = not work_areas

    # ── Call each layer service. Sequential is fine for W-4a; per-
    # layer queries are each modest and total < 100ms typical.
    personal = personal_layer_service.compose_for_user(db, user=user)
    operational = operational_layer_service.compose_for_user(db, user=user)
    anomaly = anomaly_layer_service.compose_for_user(db, user=user)
    activity = activity_layer_service.compose_for_user(db, user=user)

    layers: list[LayerContent] = [personal, operational, anomaly, activity]

    # ── Generate V1 anomaly intelligence stream from the anomaly
    # layer's intelligence-stream item payload. The layer service
    # already emits a LayerItem with the synthesis-input payload;
    # we extract its payload and synthesize the IntelligenceStream
    # content here at the engine level so the API response carries
    # both the structural piece (LayerItem) AND the synthesized
    # content (IntelligenceStream) without an extra round trip.
    intelligence_streams: list[IntelligenceStream] = []
    intel_layer_item = next(
        (
            it
            for it in anomaly.items
            if it.component_key
            == anomaly_layer_service.ANOMALY_INTELLIGENCE_STREAM_KEY
        ),
        None,
    )
    if intel_layer_item is not None:
        synth = anomaly_intelligence_v1.synthesize(
            payload=intel_layer_item.payload
        )
        if synth is not None:
            intelligence_streams.append(synth)

    # ── Time-of-day signal (recorded in metadata for frontend use).
    time_of_day = _resolve_time_of_day(db, user.company_id)

    metadata = PulseCompositionMetadata(
        work_areas_used=work_areas,
        vertical_default_applied=vertical_default_applied,
        time_of_day_signal=time_of_day,
    )

    return PulseComposition(
        user_id=user.id,
        composed_at=datetime.now(timezone.utc),
        layers=layers,
        intelligence_streams=intelligence_streams,
        metadata=metadata,
    )


def compose_for_user(
    db: Session,
    *,
    user: User,
    bypass_cache: bool = False,
) -> PulseComposition:
    """Public entry point for Pulse composition.

    Returns a fresh or cached `PulseComposition` for the given user.

    Cache semantics per D1:
      • Key = `pulse:{user_id}:{work_areas_hash}:{minute_window}`
      • TTL = 5 minutes
      • Active invalidation via work_areas hash change (user updates
        work_areas → key changes → next request misses → re-composes)
      • `bypass_cache=True` skips the read but still writes the
        result, so a manual refresh warms the cache for subsequent
        requests within the window.

    Tenant isolation: layer services enforce per-query tenant
    scoping. The User object passed in is the authoritative scope.
    """
    work_areas = list(user.work_areas or [])
    key = composition_cache.cache_key(
        user_id=user.id, work_areas=work_areas
    )

    if not bypass_cache:
        cached = composition_cache.get(key)
        if cached is not None:
            return cached

    composition = _compose_uncached(db, user=user)

    # Best-effort cache write — failures don't block the response.
    try:
        composition_cache.put(key, composition)
    except Exception as exc:
        logger.warning("pulse cache put failed: %s", exc)

    return composition
