"""Network intelligence — cross-tenant analytics, gap detection, onboarding patterns.

PRIVACY: All cross-tenant queries are anonymized. Minimum 3 tenants for any aggregate.
No tenant ever sees another tenant's specific financial data.
"""

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import desc, distinct, func
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.network_intelligence import (
    NetworkAnalyticsSnapshot,
    NetworkConnectionSuggestion,
    NetworkCoverageGap,
    OnboardingPatternData,
)

logger = logging.getLogger(__name__)

MIN_TENANT_THRESHOLD = 3  # Non-negotiable privacy threshold


# ---------------------------------------------------------------------------
# Platform Health Snapshot
# ---------------------------------------------------------------------------


def build_platform_health_snapshot(db: Session) -> dict | None:
    """Build anonymized platform health snapshot."""
    today = date.today()
    snapshot_date = today.replace(day=1)

    # Count active tenants
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    total_tenants = db.query(func.count(Company.id)).filter(Company.is_active.is_(True)).scalar() or 0

    if total_tenants < MIN_TENANT_THRESHOLD:
        return None

    data = {
        "active_tenants": total_tenants,
        "tenant_breakdown": {
            "manufacturer": db.query(func.count(Company.id)).filter(Company.is_active.is_(True), Company.preset == "manufacturing").scalar() or 0,
            "funeral_home": db.query(func.count(Company.id)).filter(Company.is_active.is_(True), Company.preset == "funeral_home").scalar() or 0,
        },
        "platform_growth": {
            "new_tenants_this_month": db.query(func.count(Company.id)).filter(Company.created_at >= snapshot_date).scalar() or 0,
        },
    }

    # Upsert snapshot
    existing = db.query(NetworkAnalyticsSnapshot).filter(
        NetworkAnalyticsSnapshot.snapshot_type == "platform_health",
        NetworkAnalyticsSnapshot.snapshot_date == snapshot_date,
    ).first()

    if existing:
        existing.data = data
        existing.tenant_count_included = total_tenants
    else:
        db.add(NetworkAnalyticsSnapshot(
            id=str(uuid.uuid4()),
            snapshot_type="platform_health",
            snapshot_date=snapshot_date,
            data=data,
            tenant_count_included=total_tenants,
        ))
    db.commit()
    return data


# ---------------------------------------------------------------------------
# Network Gap Detection
# ---------------------------------------------------------------------------


def detect_and_update_gaps(db: Session) -> dict:
    """Detect coverage gaps based on transfer demand and funeral home locations."""
    results = {"new_gaps": 0, "resolved": 0}

    # Would query licensee_transfers grouped by cemetery_state/county
    # and compare against manufacturer_service_territories
    # Simplified stub for initial deployment

    return results


def get_top_gaps(db: Session, limit: int = 10, state_filter: str | None = None) -> list[dict]:
    """Get top network coverage gaps by opportunity score."""
    query = db.query(NetworkCoverageGap).filter(NetworkCoverageGap.resolved.is_(False))
    if state_filter:
        query = query.filter(NetworkCoverageGap.state == state_filter.upper())
    gaps = query.order_by(desc(NetworkCoverageGap.opportunity_score)).limit(limit).all()
    return [
        {
            "id": g.id,
            "state": g.state,
            "county": g.county,
            "gap_type": g.gap_type,
            "transfer_request_count": g.transfer_request_count,
            "funeral_home_count": g.funeral_home_count,
            "platform_licensee_count": g.platform_licensee_count,
            "nearest_licensee_miles": float(g.nearest_licensee_miles) if g.nearest_licensee_miles else None,
            "opportunity_score": float(g.opportunity_score) if g.opportunity_score else None,
            "first_detected_at": g.first_detected_at.isoformat() if g.first_detected_at else None,
        }
        for g in gaps
    ]


# ---------------------------------------------------------------------------
# Onboarding Intelligence
# ---------------------------------------------------------------------------


def predict_onboarding_timeline(db: Session, tenant_id: str, tenant_type: str) -> list[dict]:
    """Predict timeline for remaining onboarding steps based on aggregate patterns."""
    current_month = date.today().replace(day=1)

    # Get latest pattern data
    patterns = (
        db.query(OnboardingPatternData)
        .filter(OnboardingPatternData.tenant_type == tenant_type)
        .order_by(desc(OnboardingPatternData.snapshot_month))
        .all()
    )

    # Deduplicate — keep most recent snapshot per item_key
    seen_keys = set()
    latest_patterns = {}
    for p in patterns:
        if p.checklist_item_key not in seen_keys:
            seen_keys.add(p.checklist_item_key)
            latest_patterns[p.checklist_item_key] = p

    results = []
    for key, pattern in latest_patterns.items():
        if pattern.tenant_count_sample and pattern.tenant_count_sample < MIN_TENANT_THRESHOLD:
            continue  # Insufficient data

        avg_days = float(pattern.avg_days_to_complete) if pattern.avg_days_to_complete else None
        difficulty = None
        if avg_days is not None:
            if avg_days < 1:
                difficulty = "easy"
            elif avg_days <= 3:
                difficulty = "moderate"
            else:
                difficulty = "hard"

        results.append({
            "step_key": pattern.checklist_item_key,
            "predicted_days": avg_days,
            "difficulty": difficulty,
            "completion_rate": float(pattern.completion_rate) if pattern.completion_rate else None,
            "tenant_count_sample": pattern.tenant_count_sample,
        })

    return results


def get_onboarding_warnings(db: Session, tenant_id: str, tenant_type: str) -> list[dict]:
    """Check if tenant is stuck on any onboarding step beyond average time."""
    from app.models.onboarding import OnboardingChecklistItem

    warnings = []
    incomplete = (
        db.query(OnboardingChecklistItem)
        .filter(
            OnboardingChecklistItem.company_id == tenant_id,
            OnboardingChecklistItem.status.in_(["not_started", "in_progress"]),
        )
        .all()
    )

    for item in incomplete:
        pattern = (
            db.query(OnboardingPatternData)
            .filter(
                OnboardingPatternData.tenant_type == tenant_type,
                OnboardingPatternData.checklist_item_key == item.item_key,
                OnboardingPatternData.tenant_count_sample >= MIN_TENANT_THRESHOLD,
            )
            .order_by(desc(OnboardingPatternData.snapshot_month))
            .first()
        )

        if not pattern or not pattern.avg_days_to_complete:
            continue

        days_stuck = (datetime.now(timezone.utc) - item.created_at).days if item.created_at else 0
        threshold = float(pattern.avg_days_to_complete) * 1.5

        if days_stuck > threshold:
            warnings.append({
                "step_key": item.item_key,
                "step_title": item.title,
                "days_stuck": days_stuck,
                "avg_days": float(pattern.avg_days_to_complete),
                "message": f"Most businesses complete this step in {int(pattern.avg_days_to_complete)} days. You've been on this step for {days_stuck} days.",
            })

    return warnings


# ---------------------------------------------------------------------------
# Connection Suggestions
# ---------------------------------------------------------------------------


def get_connection_suggestions(db: Session, tenant_id: str) -> list[dict]:
    """Get pending connection suggestions for a tenant."""
    suggestions = (
        db.query(NetworkConnectionSuggestion)
        .filter(
            NetworkConnectionSuggestion.tenant_id == tenant_id,
            NetworkConnectionSuggestion.status == "pending",
        )
        .order_by(desc(NetworkConnectionSuggestion.created_at))
        .all()
    )

    # Get suggested tenant names
    tenant_ids = [s.suggested_tenant_id for s in suggestions]
    tenants = {c.id: c for c in db.query(Company).filter(Company.id.in_(tenant_ids)).all()} if tenant_ids else {}

    return [
        {
            "id": s.id,
            "suggested_tenant_id": s.suggested_tenant_id,
            "suggested_tenant_name": tenants[s.suggested_tenant_id].company_name if s.suggested_tenant_id in tenants else "Unknown",
            "suggested_tenant_type": tenants[s.suggested_tenant_id].preset if s.suggested_tenant_id in tenants else None,
            "connection_type": s.connection_type,
            "reason": s.reason,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in suggestions
    ]


def dismiss_suggestion(db: Session, suggestion_id: str) -> bool:
    s = db.query(NetworkConnectionSuggestion).filter(NetworkConnectionSuggestion.id == suggestion_id).first()
    if not s:
        return False
    s.status = "dismissed"
    s.dismissed_at = datetime.now(timezone.utc)
    db.commit()
    return True


def accept_suggestion(db: Session, suggestion_id: str) -> bool:
    s = db.query(NetworkConnectionSuggestion).filter(NetworkConnectionSuggestion.id == suggestion_id).first()
    if not s:
        return False
    s.status = "connected"
    s.connected_at = datetime.now(timezone.utc)
    db.commit()
    # Would create platform_tenant_relationships record here
    return True


# ---------------------------------------------------------------------------
# Cemetery Network Readiness — suggest connections for new cemetery tenants
# ---------------------------------------------------------------------------


def suggest_cemetery_connections_for_new_tenants(db: Session) -> dict:
    """Find recently-joined cemetery tenants and create NetworkConnectionSuggestions
    for manufacturer tenants within 100 miles.

    Called weekly by job_network_readiness(). Idempotent — uses ON CONFLICT DO NOTHING
    logic (checks for existing suggestion before inserting).
    """
    from decimal import Decimal

    RADIUS_MILES = 100

    cutoff = datetime.now(timezone.utc) - timedelta(days=14)

    # Cemetery tenants created in the last 14 days with known location
    new_cemeteries = (
        db.query(Company)
        .filter(
            Company.vertical == "cemetery",
            Company.is_active.is_(True),
            Company.created_at >= cutoff,
            Company.facility_latitude.isnot(None),
            Company.facility_longitude.isnot(None),
        )
        .all()
    )

    created = 0
    skipped = 0

    for cemetery in new_cemeteries:
        c_lat = float(cemetery.facility_latitude)
        c_lng = float(cemetery.facility_longitude)
        lat_range = RADIUS_MILES / 69.0
        lng_range = RADIUS_MILES / 54.6

        # Manufacturer tenants within bounding box
        manufacturers = (
            db.query(Company)
            .filter(
                Company.vertical == "manufacturing",
                Company.is_active.is_(True),
                Company.id != cemetery.id,
                Company.facility_latitude.between(
                    Decimal(str(c_lat - lat_range)),
                    Decimal(str(c_lat + lat_range)),
                ),
                Company.facility_longitude.between(
                    Decimal(str(c_lng - lng_range)),
                    Decimal(str(c_lng + lng_range)),
                ),
            )
            .all()
        )

        for mfr in manufacturers:
            # Idempotent — skip if suggestion already exists
            existing = (
                db.query(NetworkConnectionSuggestion)
                .filter(
                    NetworkConnectionSuggestion.tenant_id == mfr.id,
                    NetworkConnectionSuggestion.suggested_tenant_id == cemetery.id,
                    NetworkConnectionSuggestion.connection_type == "cemetery_network",
                )
                .first()
            )
            if existing:
                skipped += 1
                continue

            db.add(
                NetworkConnectionSuggestion(
                    tenant_id=mfr.id,
                    suggested_tenant_id=cemetery.id,
                    connection_type="cemetery_network",
                    reason=f"{cemetery.name} recently joined the platform and is in your area",
                    status="pending",
                )
            )
            created += 1

    db.commit()
    logger.info(
        "suggest_cemetery_connections: %d created, %d skipped (existing)", created, skipped
    )
    return {"created": created, "skipped": skipped}


# ---------------------------------------------------------------------------
# Admin Network Health
# ---------------------------------------------------------------------------


def get_latest_snapshot(db: Session, snapshot_type: str) -> dict | None:
    """Get most recent network analytics snapshot."""
    snapshot = (
        db.query(NetworkAnalyticsSnapshot)
        .filter(NetworkAnalyticsSnapshot.snapshot_type == snapshot_type)
        .order_by(desc(NetworkAnalyticsSnapshot.snapshot_date))
        .first()
    )
    if not snapshot:
        return None
    if snapshot.tenant_count_included < MIN_TENANT_THRESHOLD:
        return None  # Privacy threshold
    return {
        "snapshot_type": snapshot.snapshot_type,
        "snapshot_date": str(snapshot.snapshot_date),
        "data": snapshot.data,
        "tenant_count_included": snapshot.tenant_count_included,
    }


def get_snapshot_history(db: Session, snapshot_type: str, periods: int = 12) -> list[dict]:
    """Get snapshot history for trend charts."""
    snapshots = (
        db.query(NetworkAnalyticsSnapshot)
        .filter(
            NetworkAnalyticsSnapshot.snapshot_type == snapshot_type,
            NetworkAnalyticsSnapshot.tenant_count_included >= MIN_TENANT_THRESHOLD,
        )
        .order_by(desc(NetworkAnalyticsSnapshot.snapshot_date))
        .limit(periods)
        .all()
    )
    return [
        {
            "snapshot_date": str(s.snapshot_date),
            "data": s.data,
            "tenant_count": s.tenant_count_included,
        }
        for s in reversed(snapshots)
    ]
