"""Pre-tenant onboarding self-repair validation.

Run manually before each new tenant is onboarded.
NOT in the CI suite — this is a pre-flight check.

Usage:
    cd backend && source .venv/bin/activate
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev \
        pytest tests/test_self_repair_complete.py -v
"""

import hashlib
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.company import Company
from app.models.platform_incident import PlatformIncident
from app.models.platform_notification import PlatformNotification
from app.models.tenant_health_score import TenantHealthScore


@pytest.fixture(scope="module")
def db():
    """Shared DB session for the test module — cleaned up at the end."""
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


def _unique_msg(base: str) -> str:
    return f"{base} [{uuid.uuid4().hex[:8]}]"


def _make_fingerprint(category: str, message: str) -> str:
    normalized = f"{category}:{message[:200]}"
    return hashlib.sha256(normalized.encode()).hexdigest()[:64]


# ── Test 1: All responders registered ──────────────────────────────────────


def test_all_responders_registered():
    """RESPONDER_REGISTRY has 6 entries covering all expected categories."""
    from app.services.platform.responders.registry import RESPONDER_REGISTRY

    assert len(RESPONDER_REGISTRY) == 6

    categories = {r.category for r in RESPONDER_REGISTRY}
    expected = {
        "background_job",
        "auth",
        "infra",
        "config",
        "migration",
        "api_contract",
    }
    assert categories == expected, f"Missing: {expected - categories}"


# ── Test 2: Dispatcher runs without error ──────────────────────────────────


def test_dispatcher_runs_clean(db: Session):
    """dispatch_pending_incidents succeeds with no pending incidents."""
    from app.services.platform.responders.dispatcher import (
        dispatch_pending_incidents,
    )

    result = dispatch_pending_incidents(db)
    assert isinstance(result, dict)
    assert "total" in result
    assert "resolved" in result
    assert "errors" in result
    # No exceptions raised — that's the main assertion


# ── Test 3: Full auto-fix loop ─────────────────────────────────────────────


def test_full_auto_fix_loop(db: Session):
    """Create a background_job incident, dispatch, verify resolved."""
    from app.services.platform.responders.dispatcher import (
        dispatch_pending_incidents,
    )

    msg = _unique_msg("platform_health_recalculate failed")
    inc = PlatformIncident(
        id=str(uuid.uuid4()),
        category="background_job",
        severity="medium",
        resolution_tier="auto_fix",
        resolution_status="pending",
        source="background_job",
        error_message=msg,
        context={"job_name": "platform_health_recalculate"},
        fingerprint=_make_fingerprint("background_job", msg),
        created_at=datetime.now(timezone.utc),
    )
    db.add(inc)
    db.flush()

    result = dispatch_pending_incidents(db)
    assert result["resolved"] >= 1

    db.refresh(inc)
    assert inc.resolution_status == "resolved"


# ── Test 4: Notification system works ──────────────────────────────────────


def test_notification_lifecycle(db: Session):
    """Create a notification, verify it exists, dismiss it."""
    from app.services.platform.platform_health_service import (
        create_notification,
    )

    notif = create_notification(
        db,
        title=f"Test notification [{uuid.uuid4().hex[:8]}]",
        body="Pre-onboarding validation",
        level="info",
    )
    db.flush()

    # Verify it exists undismissed
    fetched = (
        db.query(PlatformNotification)
        .filter(PlatformNotification.id == notif.id)
        .first()
    )
    assert fetched is not None
    assert fetched.is_dismissed is False

    # Dismiss it
    fetched.is_dismissed = True
    fetched.dismissed_at = datetime.now(timezone.utc)
    db.flush()

    db.refresh(fetched)
    assert fetched.is_dismissed is True


# ── Test 5: Health score created for new tenant ────────────────────────────


def test_health_score_for_new_tenant(db: Session):
    """Simulate tenant creation → TenantHealthScore row exists."""
    from app.services.platform.platform_health_service import (
        calculate_tenant_health,
    )

    # Create a test company
    test_slug = f"test-{uuid.uuid4().hex[:8]}"
    company = Company(
        name=f"Test Co {test_slug}",
        slug=test_slug,
        is_active=True,
    )
    db.add(company)
    db.flush()

    # Simulate the onboarding hook — create TenantHealthScore
    health_row = TenantHealthScore(
        id=str(uuid.uuid4()),
        tenant_id=str(company.id),
        score="unknown",
    )
    db.add(health_row)
    db.flush()

    # Verify row exists
    found = (
        db.query(TenantHealthScore)
        .filter(TenantHealthScore.tenant_id == str(company.id))
        .first()
    )
    assert found is not None
    assert found.score == "unknown"

    # Calculate health — should move from unknown to a real score
    result = calculate_tenant_health(db, str(company.id))
    assert result.score != "unknown"
    assert result.score in ("healthy", "watch", "degraded", "critical")


# ── Test 6: System health endpoint returns operational ─────────────────────


def test_system_health_endpoint(db: Session):
    """GET /api/platform/health/system returns valid status."""
    from app.api.routes.platform_health import get_system_health

    # Call the endpoint function directly with a mock auth
    response = get_system_health(_auth=None, db=db)

    assert response.status in ("operational", "degraded", "down")
    assert response.checks.responders_registered == 6
    assert response.checks.total_tenants_monitored >= 0
    assert response.checks.open_critical_incidents >= 0
    assert response.checks.undismissed_notifications >= 0


# ── Test 7: All operator dashboard endpoints return valid data ─────────────


def test_operator_dashboard_endpoints(db: Session):
    """All 4 operator dashboard endpoints return valid responses."""
    from app.api.routes.platform_health import (
        get_health_incidents,
        get_health_summary,
        get_repeat_patterns,
        get_system_health,
    )

    # Summary
    summary_res = get_health_summary(_auth=None, db=db)
    assert summary_res.summary is not None
    assert summary_res.summary.total_tenants >= 0

    # Incidents — pass explicit defaults since Query() objects don't resolve outside FastAPI
    incident_res = get_health_incidents(
        tenant_id=None, status=None, category=None,
        limit=20, offset=0, _auth=None, db=db,
    )
    assert incident_res.total >= 0
    assert isinstance(incident_res.incidents, list)

    # Patterns
    pattern_res = get_repeat_patterns(_auth=None, db=db)
    assert isinstance(pattern_res.patterns, list)

    # System health
    system_res = get_system_health(_auth=None, db=db)
    assert system_res.status in ("operational", "degraded", "down")
