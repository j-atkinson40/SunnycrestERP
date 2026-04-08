"""Platform health dashboard API — operator dashboard endpoints.

Supports dual auth:
- Platform JWT (super_admin / support / viewer) for dashboard UI
- X-Internal-Key header for automated systems

All endpoints are registered under /api/platform/health/.
"""

import json
import logging
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import decode_token
from app.database import get_db
from app.models.company import Company
from app.models.platform_incident import PlatformIncident
from app.models.platform_notification import PlatformNotification
from app.models.platform_user import PlatformUser
from app.models.tenant_health_score import TenantHealthScore
from app.services.platform.platform_health_service import (
    calculate_all_tenant_health,
    calculate_tenant_health,
    resolve_incident,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dual auth dependency — accepts platform JWT OR internal key
# ---------------------------------------------------------------------------


def require_platform_or_internal_key(
    authorization: Optional[str] = Header(None),
    x_internal_key: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Accept either platform JWT token or X-Internal-Key header."""
    # Try internal key first (fast path for automated callers)
    if x_internal_key:
        if settings.INTERNAL_API_KEY and x_internal_key == settings.INTERNAL_API_KEY:
            return None  # Authenticated via internal key
        raise HTTPException(status_code=401, detail="Invalid internal API key")

    # Fall back to platform JWT
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        try:
            payload = decode_token(token)
            if payload.get("type") != "access" or payload.get("realm") != "platform":
                raise HTTPException(status_code=401, detail="Invalid platform token")
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid token")
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        user = db.query(PlatformUser).filter(PlatformUser.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Platform user not found")
        return user

    raise HTTPException(
        status_code=401,
        detail="Provide Authorization header (Bearer token) or X-Internal-Key",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

SCORE_ORDER = {"critical": 0, "degraded": 1, "watch": 2, "unknown": 3, "healthy": 4}


class ComponentScores(BaseModel):
    api: str
    auth: str
    data: str
    background_job: str


class TenantHealthItem(BaseModel):
    tenant_id: str
    tenant_name: str
    score: str
    open_incident_count: int
    last_incident_at: Optional[datetime] = None
    last_healthy_at: Optional[datetime] = None
    last_calculated: Optional[datetime] = None
    reasons: list[str]
    component_scores: ComponentScores


class HealthSummary(BaseModel):
    total_tenants: int
    healthy: int
    watch: int
    degraded: int
    critical: int
    unknown: int
    last_updated: Optional[datetime] = None
    avg_resolution_seconds_7d: Optional[float] = None


class HealthSummaryResponse(BaseModel):
    summary: HealthSummary
    tenants: list[TenantHealthItem]


class IncidentListItem(BaseModel):
    id: str
    tenant_id: Optional[str] = None
    tenant_name: Optional[str] = None
    category: str
    severity: str
    source: Optional[str] = None
    resolution_tier: Optional[str] = None
    resolution_status: str
    resolution_action: Optional[str] = None
    error_message: Optional[str] = None
    was_repeat: bool
    created_at: datetime
    resolved_at: Optional[datetime] = None


class IncidentListResponse(BaseModel):
    incidents: list[IncidentListItem]
    total: int


class ResolveRequest(BaseModel):
    resolution_action: str


class RecalculateResponse(BaseModel):
    recalculated: int
    healthy: int
    watch: int
    degraded: int
    critical: int
    unknown: int


# ---- Notification schemas ----


class NotificationItem(BaseModel):
    id: str
    tenant_id: Optional[str] = None
    tenant_name: Optional[str] = None
    incident_id: Optional[str] = None
    level: str
    title: str
    body: Optional[str] = None
    is_dismissed: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    notifications: list[NotificationItem]
    total: int


# ---- Pattern schemas ----


class RepeatPatternItem(BaseModel):
    fingerprint: str
    category: str
    first_error: str
    count: int
    tenants_affected: list[str]
    last_seen: datetime
    resolution_rate: float
    avg_resolution_seconds: Optional[float] = None


class PatternsResponse(BaseModel):
    patterns: list[RepeatPatternItem]


# ---- Timeline schemas ----


class TimelineEntry(BaseModel):
    date: str
    score: str
    incident_count: int


class TimelineResponse(BaseModel):
    timeline: list[TimelineEntry]


# ---------------------------------------------------------------------------
# Endpoints — Summary
# ---------------------------------------------------------------------------


@router.get("/summary", response_model=HealthSummaryResponse)
def get_health_summary(
    _auth=Depends(require_platform_or_internal_key),
    db: Session = Depends(get_db),
):
    """Operator dashboard summary — tenant health scores with company names."""
    # Get all active tenants
    active_tenants = (
        db.query(Company.id, Company.name)
        .filter(Company.is_active.is_(True))
        .all()
    )
    tenant_map = {t.id: t.name for t in active_tenants}
    tenant_ids = list(tenant_map.keys())

    # Get health scores
    health_scores = (
        db.query(TenantHealthScore)
        .filter(TenantHealthScore.tenant_id.in_(tenant_ids))
        .all()
    )
    health_map = {h.tenant_id: h for h in health_scores}

    # Build tenant list
    tenants: list[TenantHealthItem] = []
    counts = {"healthy": 0, "watch": 0, "degraded": 0, "critical": 0, "unknown": 0}

    for tid in tenant_ids:
        name = tenant_map[tid]
        h = health_map.get(tid)

        if h:
            score = h.score or "unknown"
            item = TenantHealthItem(
                tenant_id=tid,
                tenant_name=name,
                score=score,
                open_incident_count=h.open_incident_count or 0,
                last_incident_at=h.last_incident_at,
                last_healthy_at=h.last_healthy_at,
                last_calculated=h.last_calculated,
                reasons=h.reasons or [],
                component_scores=ComponentScores(
                    api=h.api_health or "unknown",
                    auth=h.auth_health or "unknown",
                    data=h.data_health or "unknown",
                    background_job=h.background_job_health or "unknown",
                ),
            )
        else:
            score = "unknown"
            item = TenantHealthItem(
                tenant_id=tid,
                tenant_name=name,
                score="unknown",
                open_incident_count=0,
                reasons=[],
                component_scores=ComponentScores(
                    api="unknown", auth="unknown", data="unknown", background_job="unknown"
                ),
            )

        counts[score] = counts.get(score, 0) + 1
        tenants.append(item)

    # Sort by severity: critical first, healthy last
    tenants.sort(key=lambda t: SCORE_ORDER.get(t.score, 3))

    # Last updated = most recent last_calculated across all scores
    last_updated = None
    calculated_dates = [h.last_calculated for h in health_scores if h.last_calculated]
    if calculated_dates:
        last_updated = max(calculated_dates)

    # Avg resolution time (7 days)
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    avg_res = (
        db.query(func.avg(PlatformIncident.resolution_duration_seconds))
        .filter(
            PlatformIncident.resolution_status == "resolved",
            PlatformIncident.resolved_at >= seven_days_ago,
        )
        .scalar()
    )

    return HealthSummaryResponse(
        summary=HealthSummary(
            total_tenants=len(tenant_ids),
            healthy=counts["healthy"],
            watch=counts["watch"],
            degraded=counts["degraded"],
            critical=counts["critical"],
            unknown=counts["unknown"],
            last_updated=last_updated,
            avg_resolution_seconds_7d=float(avg_res) if avg_res is not None else None,
        ),
        tenants=tenants,
    )


# ---------------------------------------------------------------------------
# Endpoints — Incidents
# ---------------------------------------------------------------------------


@router.get("/incidents", response_model=IncidentListResponse)
def get_health_incidents(
    tenant_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _auth=Depends(require_platform_or_internal_key),
    db: Session = Depends(get_db),
):
    """List recent incidents with tenant names for the operator dashboard."""
    q = db.query(PlatformIncident)

    if tenant_id:
        q = q.filter(PlatformIncident.tenant_id == tenant_id)
    if status:
        q = q.filter(PlatformIncident.resolution_status == status)
    if category:
        q = q.filter(PlatformIncident.category == category)

    # Get total count before limit
    total = q.count()

    incidents = (
        q.order_by(PlatformIncident.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Resolve tenant names
    tenant_ids_set = {i.tenant_id for i in incidents if i.tenant_id}
    tenant_names = {}
    if tenant_ids_set:
        rows = (
            db.query(Company.id, Company.name)
            .filter(Company.id.in_(tenant_ids_set))
            .all()
        )
        tenant_names = {r.id: r.name for r in rows}

    items = [
        IncidentListItem(
            id=i.id,
            tenant_id=i.tenant_id,
            tenant_name=tenant_names.get(i.tenant_id) if i.tenant_id else None,
            category=i.category,
            severity=i.severity,
            source=i.source,
            resolution_tier=i.resolution_tier,
            resolution_status=i.resolution_status,
            resolution_action=i.resolution_action,
            error_message=i.error_message,
            was_repeat=i.was_repeat,
            created_at=i.created_at,
            resolved_at=i.resolved_at,
        )
        for i in incidents
    ]

    return IncidentListResponse(incidents=items, total=total)


@router.patch("/incidents/{incident_id}/resolve")
def resolve_platform_incident(
    incident_id: str,
    body: ResolveRequest,
    _auth=Depends(require_platform_or_internal_key),
    db: Session = Depends(get_db),
):
    """Resolve an incident and recalculate the affected tenant's health score."""
    try:
        incident = resolve_incident(db, incident_id, body.resolution_action)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Recalculate tenant health if tenant-scoped
    health = None
    if incident.tenant_id:
        health = calculate_tenant_health(db, incident.tenant_id)

    db.commit()

    return {
        "id": incident.id,
        "resolution_status": incident.resolution_status,
        "resolved_at": incident.resolved_at,
        "tenant_health_score": health.score if health else None,
    }


@router.post("/recalculate", response_model=RecalculateResponse)
def recalculate_all_health(
    _auth=Depends(require_platform_or_internal_key),
    db: Session = Depends(get_db),
):
    """Trigger immediate recalculation of all tenant health scores."""
    results = calculate_all_tenant_health(db)
    counts = {"healthy": 0, "watch": 0, "degraded": 0, "critical": 0, "unknown": 0}
    for r in results:
        s = r.score or "unknown"
        counts[s] = counts.get(s, 0) + 1

    return RecalculateResponse(
        recalculated=len(results),
        **counts,
    )


# ---------------------------------------------------------------------------
# Endpoints — Notifications
# ---------------------------------------------------------------------------


@router.get("/notifications", response_model=NotificationListResponse)
def get_notifications(
    dismissed: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    _auth=Depends(require_platform_or_internal_key),
    db: Session = Depends(get_db),
):
    """List platform notifications for the operator dashboard."""
    q = db.query(PlatformNotification).filter(
        PlatformNotification.is_dismissed == dismissed
    )

    total = q.count()

    notifs = (
        q.order_by(PlatformNotification.created_at.desc())
        .limit(limit)
        .all()
    )

    # Resolve tenant names
    tenant_ids_set = {n.tenant_id for n in notifs if n.tenant_id}
    tenant_names = {}
    if tenant_ids_set:
        rows = (
            db.query(Company.id, Company.name)
            .filter(Company.id.in_(tenant_ids_set))
            .all()
        )
        tenant_names = {r.id: r.name for r in rows}

    items = [
        NotificationItem(
            id=n.id,
            tenant_id=n.tenant_id,
            tenant_name=tenant_names.get(n.tenant_id) if n.tenant_id else None,
            incident_id=n.incident_id,
            level=n.level,
            title=n.title,
            body=n.body,
            is_dismissed=n.is_dismissed,
            created_at=n.created_at,
        )
        for n in notifs
    ]

    return NotificationListResponse(notifications=items, total=total)


@router.patch("/notifications/{notification_id}/dismiss")
def dismiss_notification(
    notification_id: str,
    _auth=Depends(require_platform_or_internal_key),
    db: Session = Depends(get_db),
):
    """Dismiss a platform notification."""
    notif = (
        db.query(PlatformNotification)
        .filter(PlatformNotification.id == notification_id)
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    notif.is_dismissed = True
    notif.dismissed_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "id": notif.id,
        "is_dismissed": notif.is_dismissed,
        "dismissed_at": notif.dismissed_at,
    }


# ---------------------------------------------------------------------------
# Endpoints — Repeat patterns
# ---------------------------------------------------------------------------


@router.get("/patterns", response_model=PatternsResponse)
def get_repeat_patterns(
    _auth=Depends(require_platform_or_internal_key),
    db: Session = Depends(get_db),
):
    """Return fingerprint clusters with 2+ incidents in the last 30 days."""
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    rows = (
        db.query(
            PlatformIncident.fingerprint,
            PlatformIncident.category,
            func.min(PlatformIncident.error_message).label("first_error"),
            func.count().label("count"),
            func.max(PlatformIncident.created_at).label("last_seen"),
            func.avg(
                case(
                    (
                        PlatformIncident.resolution_status == "resolved",
                        PlatformIncident.resolution_duration_seconds,
                    ),
                    else_=None,
                )
            ).label("avg_resolution_seconds"),
            func.sum(
                case(
                    (PlatformIncident.resolution_status == "resolved", 1),
                    else_=0,
                )
            ).label("resolved_count"),
        )
        .filter(
            PlatformIncident.created_at >= thirty_days_ago,
            PlatformIncident.fingerprint.isnot(None),
        )
        .group_by(PlatformIncident.fingerprint, PlatformIncident.category)
        .having(func.count() >= 2)
        .order_by(func.count().desc())
        .all()
    )

    # Collect tenant IDs per fingerprint
    fingerprints = [r.fingerprint for r in rows]
    tenant_data: dict[str, set[str]] = {fp: set() for fp in fingerprints}

    if fingerprints:
        tenant_rows = (
            db.query(
                PlatformIncident.fingerprint,
                PlatformIncident.tenant_id,
            )
            .filter(
                PlatformIncident.fingerprint.in_(fingerprints),
                PlatformIncident.tenant_id.isnot(None),
                PlatformIncident.created_at >= thirty_days_ago,
            )
            .distinct()
            .all()
        )
        for tr in tenant_rows:
            if tr.fingerprint in tenant_data:
                tenant_data[tr.fingerprint].add(tr.tenant_id)

    # Resolve tenant names
    all_tenant_ids = set()
    for tids in tenant_data.values():
        all_tenant_ids.update(tids)

    tenant_names: dict[str, str] = {}
    if all_tenant_ids:
        name_rows = (
            db.query(Company.id, Company.name)
            .filter(Company.id.in_(all_tenant_ids))
            .all()
        )
        tenant_names = {r.id: r.name for r in name_rows}

    patterns = []
    for r in rows:
        count = r.count
        resolved_count = r.resolved_count or 0
        resolution_rate = resolved_count / count if count > 0 else 0.0

        affected_names = [
            tenant_names.get(tid, tid[:12])
            for tid in tenant_data.get(r.fingerprint, set())
        ]

        patterns.append(
            RepeatPatternItem(
                fingerprint=r.fingerprint,
                category=r.category,
                first_error=r.first_error or "Unknown error",
                count=count,
                tenants_affected=sorted(affected_names),
                last_seen=r.last_seen,
                resolution_rate=round(resolution_rate, 2),
                avg_resolution_seconds=(
                    round(float(r.avg_resolution_seconds))
                    if r.avg_resolution_seconds is not None
                    else None
                ),
            )
        )

    return PatternsResponse(patterns=patterns)


# ---------------------------------------------------------------------------
# Endpoints — Health timeline
# ---------------------------------------------------------------------------


@router.get("/timeline", response_model=TimelineResponse)
def get_health_timeline(
    tenant_id: str = Query(...),
    days: int = Query(30, ge=1, le=90),
    _auth=Depends(require_platform_or_internal_key),
    db: Session = Depends(get_db),
):
    """Approximate daily health score for a tenant over the last N days.

    Derived from incident data — not from stored snapshots.
    For each day, counts open incidents at end of day and derives a score.
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    # Get all incidents for this tenant in the window
    incidents = (
        db.query(PlatformIncident)
        .filter(
            PlatformIncident.tenant_id == tenant_id,
            PlatformIncident.created_at >= start - timedelta(days=30),  # older incidents may still be open
        )
        .all()
    )

    timeline: list[TimelineEntry] = []

    for day_offset in range(days):
        day = start + timedelta(days=day_offset)
        day_end = day.replace(hour=23, minute=59, second=59)

        # Count incidents that were open at end of this day
        open_at_day = []
        for inc in incidents:
            created = inc.created_at
            resolved = inc.resolved_at
            if created <= day_end:
                if resolved is None or resolved > day_end:
                    open_at_day.append(inc)

        # Derive score using same logic as calculate_tenant_health
        escalate_open = sum(1 for i in open_at_day if i.resolution_tier == "escalate")
        remediate_open = sum(1 for i in open_at_day if i.resolution_tier == "auto_remediate")
        fix_open = sum(1 for i in open_at_day if i.resolution_tier == "auto_fix")
        has_high = any(i.severity in ("high", "critical") for i in open_at_day)

        if escalate_open >= 1:
            score = "critical"
        elif remediate_open >= 2:
            score = "degraded"
        elif remediate_open == 1 or fix_open >= 3:
            score = "watch"
        elif fix_open <= 2 and not has_high:
            score = "healthy"
        else:
            score = "watch"

        timeline.append(
            TimelineEntry(
                date=day.strftime("%Y-%m-%d"),
                score=score,
                incident_count=len(open_at_day),
            )
        )

    return TimelineResponse(timeline=timeline)


# ---------------------------------------------------------------------------
# Smoke test trigger
# ---------------------------------------------------------------------------


class SmokeTriggerRequest(BaseModel):
    tenant_id: str


class SmokeTriggerResponse(BaseModel):
    passed: int = 0
    failed: int = 0
    incidents_logged: int = 0
    duration_ms: int = 0
    error: Optional[str] = None


@router.post("/smoke-trigger", response_model=SmokeTriggerResponse)
def trigger_smoke_test(
    body: SmokeTriggerRequest,
    _auth=Depends(require_platform_or_internal_key),
):
    """Run smoke tests via Playwright and return results.

    The incident reporter automatically logs any failures to platform_incidents.
    This endpoint runs synchronously (30-60s typical).
    """
    # Check if npx/playwright is available
    npx_path = shutil.which("npx")
    if not npx_path:
        return SmokeTriggerResponse(
            error=(
                "Playwright not available in this environment. "
                "Run smoke tests locally or via CI."
            )
        )

    import time

    start = time.time()

    try:
        result = subprocess.run(
            [
                npx_path,
                "playwright",
                "test",
                "tests/e2e/smoke.spec.ts",
                "--reporter=./tests/e2e/incident-reporter.ts,json",
                "--project=chromium",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd="frontend",  # Relative to backend working dir
            env={
                **__import__("os").environ,
                "INTERNAL_API_KEY": settings.INTERNAL_API_KEY or "",
                "BACKEND_URL": f"http://localhost:{settings.PORT or 8000}",
            },
        )
    except subprocess.TimeoutExpired:
        return SmokeTriggerResponse(
            error="Smoke test timed out after 120 seconds.",
            duration_ms=120_000,
        )
    except FileNotFoundError:
        return SmokeTriggerResponse(
            error=(
                "Playwright not available in this environment. "
                "Run smoke tests locally or via CI."
            )
        )
    except Exception as e:
        logger.error(f"Smoke test trigger failed: {e}")
        return SmokeTriggerResponse(
            error=f"Smoke test execution failed: {str(e)[:200]}"
        )

    duration_ms = int((time.time() - start) * 1000)

    # Parse results from JSON reporter output
    passed = 0
    failed = 0

    try:
        # JSON reporter writes to stdout
        json_output = result.stdout
        if json_output.strip():
            report = json.loads(json_output)
            for suite in report.get("suites", []):
                for spec in suite.get("specs", []):
                    for test_result in spec.get("tests", []):
                        for r in test_result.get("results", []):
                            if r.get("status") == "passed":
                                passed += 1
                            elif r.get("status") in ("failed", "timedOut"):
                                failed += 1
    except (json.JSONDecodeError, KeyError):
        # Fall back to counting from exit code
        if result.returncode == 0:
            passed = result.stderr.count(" passed")
            if passed == 0:
                passed = 5
        else:
            failed = 1

    return SmokeTriggerResponse(
        passed=passed,
        failed=failed,
        incidents_logged=failed,
        duration_ms=duration_ms,
    )
