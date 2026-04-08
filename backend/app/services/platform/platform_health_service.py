"""Platform health service — incident logging, resolution, and tenant health scoring.

Core of the Bridgeable self-repair system. Provides:
- log_incident(): record a new platform incident with fingerprint dedup
- resolve_incident(): mark an incident resolved with timing
- calculate_tenant_health(): score a single tenant based on open incidents
- calculate_all_tenant_health(): nightly job entry point for all tenants
"""

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.constants.platform_incidents import INCIDENT_CATEGORIES
from app.models.platform_incident import PlatformIncident
from app.models.platform_notification import PlatformNotification
from app.models.tenant_health_score import TenantHealthScore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Incident logging
# ---------------------------------------------------------------------------


def log_incident(
    db: Session,
    category: str,
    error_message: str,
    tenant_id: str | None = None,
    severity: str = "medium",
    source: str = "manual",
    stack_trace: str | None = None,
    context: dict | None = None,
) -> PlatformIncident:
    """Record a new platform incident.

    Computes a fingerprint from category + error message to detect repeat
    incidents. Sets resolution_tier from the category's default_tier.
    """
    if category not in INCIDENT_CATEGORIES:
        raise ValueError(
            f"Invalid category '{category}'. "
            f"Must be one of: {list(INCIDENT_CATEGORIES.keys())}"
        )

    # Compute fingerprint
    normalized = f"{category}:{error_message[:200]}"
    fingerprint = hashlib.sha256(normalized.encode()).hexdigest()[:64]

    # Check for repeat within last 30 days
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    recent_match = (
        db.query(PlatformIncident)
        .filter(
            PlatformIncident.fingerprint == fingerprint,
            PlatformIncident.created_at >= thirty_days_ago,
        )
        .order_by(PlatformIncident.created_at.desc())
        .first()
    )

    was_repeat = recent_match is not None
    previous_incident_id = recent_match.id if recent_match else None

    # Get default resolution tier
    resolution_tier = INCIDENT_CATEGORIES[category]["default_tier"]

    incident = PlatformIncident(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        category=category,
        severity=severity,
        fingerprint=fingerprint,
        source=source,
        error_message=error_message,
        stack_trace=stack_trace,
        context=context or {},
        resolution_tier=resolution_tier,
        resolution_status="pending",
        was_repeat=was_repeat,
        previous_incident_id=previous_incident_id,
    )
    db.add(incident)
    db.flush()

    logger.info(
        f"Logged incident {incident.id[:8]} "
        f"category={category} severity={severity} "
        f"repeat={was_repeat} tier={resolution_tier}"
    )
    return incident


# ---------------------------------------------------------------------------
# Incident resolution
# ---------------------------------------------------------------------------


def resolve_incident(
    db: Session,
    incident_id: str,
    resolution_action: str,
    status: str = "resolved",
) -> PlatformIncident:
    """Mark an incident as resolved (or escalated/ignored)."""
    incident = (
        db.query(PlatformIncident)
        .filter(PlatformIncident.id == incident_id)
        .first()
    )
    if not incident:
        raise ValueError(f"Incident {incident_id} not found")

    now = datetime.now(timezone.utc)
    incident.resolution_status = status
    incident.resolution_action = resolution_action
    incident.resolved_at = now
    incident.resolution_duration_seconds = int(
        (now - incident.created_at).total_seconds()
    )
    incident.updated_at = now
    db.flush()

    logger.info(
        f"Resolved incident {incident.id[:8]} "
        f"status={status} duration={incident.resolution_duration_seconds}s"
    )
    return incident


# ---------------------------------------------------------------------------
# Tenant health scoring
# ---------------------------------------------------------------------------


def calculate_tenant_health(
    db: Session,
    tenant_id: str,
) -> TenantHealthScore:
    """Calculate and persist a health score for a single tenant."""

    # Load or create health score record
    health = (
        db.query(TenantHealthScore)
        .filter(TenantHealthScore.tenant_id == tenant_id)
        .first()
    )
    if not health:
        health = TenantHealthScore(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
        )
        db.add(health)

    # Query open incidents for this tenant
    open_statuses = ("pending", "in_progress")
    open_incidents = (
        db.query(PlatformIncident)
        .filter(
            PlatformIncident.tenant_id == tenant_id,
            PlatformIncident.resolution_status.in_(open_statuses),
        )
        .all()
    )

    # Count by resolution tier
    escalate_open = sum(
        1 for i in open_incidents if i.resolution_tier == "escalate"
    )
    remediate_open = sum(
        1 for i in open_incidents if i.resolution_tier == "auto_remediate"
    )
    fix_open = sum(
        1 for i in open_incidents if i.resolution_tier == "auto_fix"
    )
    has_high_severity = any(
        i.severity in ("high", "critical") for i in open_incidents
    )

    # Determine overall score
    if escalate_open >= 1:
        score = "critical"
    elif remediate_open >= 2:
        score = "degraded"
    elif remediate_open == 1 or fix_open >= 3:
        score = "watch"
    elif fix_open <= 2 and not has_high_severity:
        score = "healthy"
    else:
        score = "watch"

    # Count by category for component scores
    open_categories = {i.category for i in open_incidents}

    health.api_health = (
        "degraded"
        if ("api_contract" in open_categories or "infra" in open_categories)
        else "healthy"
    )
    health.auth_health = (
        "degraded" if "auth" in open_categories else "healthy"
    )
    health.data_health = (
        "critical" if "data_integrity" in open_categories else "healthy"
    )
    health.background_job_health = (
        "watch" if "background_job" in open_categories else "healthy"
    )

    # Build reasons
    reasons: list[str] = []
    category_counts: dict[str, int] = {}
    for i in open_incidents:
        category_counts[i.category] = category_counts.get(i.category, 0) + 1
    for cat, count in sorted(category_counts.items()):
        reasons.append(f"{count} open {cat} incident(s)")
    if any(i.severity == "critical" for i in open_incidents):
        reasons.append("critical severity incident requires attention")

    # Update stats
    now = datetime.now(timezone.utc)
    health.score = score
    health.open_incident_count = len(open_incidents)
    health.reasons = reasons

    if open_incidents:
        health.last_incident_at = max(i.created_at for i in open_incidents)

    if score == "healthy":
        health.last_healthy_at = now

    health.last_calculated = now
    health.updated_at = now
    db.flush()

    return health


def calculate_all_tenant_health(db: Session) -> list[TenantHealthScore]:
    """Recalculate health scores for all active tenants. Nightly job entry point."""
    from app.models.company import Company

    tenant_ids = [
        t.id
        for t in db.query(Company.id).filter(Company.is_active.is_(True)).all()
    ]

    logger.info(f"Calculating health scores for {len(tenant_ids)} tenants")
    results = []
    for tid in tenant_ids:
        try:
            health = calculate_tenant_health(db, tid)
            results.append(health)
        except Exception as e:
            logger.error(f"Health score failed for tenant {tid}: {e}")
    db.commit()
    logger.info(
        f"Health scores updated: "
        f"{sum(1 for r in results if r.score == 'healthy')} healthy, "
        f"{sum(1 for r in results if r.score != 'healthy')} non-healthy"
    )
    return results


# ---------------------------------------------------------------------------
# Platform notifications
# ---------------------------------------------------------------------------


def create_notification(
    db: Session,
    title: str,
    body: str,
    level: str = "info",
    tenant_id: str | None = None,
    incident_id: str | None = None,
) -> PlatformNotification:
    """Create a platform notification for the operator dashboard."""
    notif = PlatformNotification(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        incident_id=incident_id,
        level=level,
        title=title,
        body=body,
    )
    db.add(notif)
    db.flush()
    logger.info(f"Notification created: [{level}] {title}")
    return notif
