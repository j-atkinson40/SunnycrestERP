"""Tests for the incident responder system.

Verifies:
1.  Background job responder resolves known job failures
2.  Unknown job name escalates
3.  Retry limit (3 in 24h) escalates
4.  Responder failure is self-reported
5.  Non-handled escalate-tier incidents stay pending
6.  Auth transient failure auto-resolves
7.  Auth breach threshold escalates + notifies
8.  Infra probe passes → auto-resolves
9.  Infra repeated failures → escalates
10. Config drift → preset reapplied
11. Migration rollback success
12. Migration rollback failure → escalates
13. Migration no double-rollback
14. API contract → structured escalation + notification
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.platform_incident import PlatformIncident
from app.models.platform_notification import PlatformNotification
from app.services.platform.responders.dispatcher import dispatch_pending_incidents


def _make_fingerprint(category: str, message: str) -> str:
    normalized = f"{category}:{message[:200]}"
    return hashlib.sha256(normalized.encode()).hexdigest()[:64]


def _unique_msg(base: str) -> str:
    """Append a UUID fragment to make error messages unique across test runs."""
    return f"{base} [{uuid.uuid4().hex[:8]}]"


def _create_incident(
    db: Session,
    *,
    category: str = "background_job",
    tier: str = "auto_fix",
    status: str = "pending",
    error_message: str = "platform_health_recalculate failed",
    context: dict | None = None,
    fingerprint: str | None = None,
    created_at: datetime | None = None,
    tenant_id: str | None = None,
    resolution_action: str | None = None,
) -> PlatformIncident:
    if fingerprint is None:
        fingerprint = _make_fingerprint(category, error_message)
    inc = PlatformIncident(
        id=str(uuid.uuid4()),
        category=category,
        severity="medium",
        resolution_tier=tier,
        resolution_status=status,
        source="background_job",
        error_message=error_message,
        context=context or {},
        fingerprint=fingerprint,
        created_at=created_at or datetime.now(timezone.utc),
        tenant_id=tenant_id,
        resolution_action=resolution_action,
    )
    db.add(inc)
    db.flush()
    return inc


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ── Test 1: known job resolves ────────────────────────────────────────────


def test_background_job_responder_resolves_known_job(db: Session):
    """A pending background_job incident with a valid job_name is auto-fixed."""
    msg = _unique_msg("platform_health_recalculate failed")
    incident = _create_incident(
        db,
        error_message=msg,
        context={"job_name": "platform_health_recalculate"},
    )
    db.flush()

    result = dispatch_pending_incidents(db)

    db.refresh(incident)
    assert incident.resolution_status == "resolved"
    assert "Auto-fix" in (incident.resolution_action or "")
    assert incident.resolved_at is not None
    assert (incident.resolution_duration_seconds or 0) >= 0
    assert result["resolved"] >= 1


# ── Test 2: unknown job escalates ─────────────────────────────────────────


def test_unknown_job_name_escalates(db: Session):
    """An incident with an unidentifiable job name is escalated."""
    msg = _unique_msg("some unknown job failed completely")
    incident = _create_incident(
        db,
        error_message=msg,
        context={},
    )
    db.flush()

    result = dispatch_pending_incidents(db)

    db.refresh(incident)
    assert incident.resolution_status == "escalated"
    assert "Could not identify" in (incident.resolution_action or "")
    assert result["escalated"] >= 1


# ── Test 3: retry limit escalates ─────────────────────────────────────────


def test_retry_limit_escalates_after_3_attempts(db: Session):
    """After 3 prior failures with the same fingerprint, the 4th is escalated."""
    msg = _unique_msg("platform_health_recalculate failed")
    fp = _make_fingerprint("background_job", msg)

    # Create 3 prior incidents in last 24h
    for i in range(3):
        _create_incident(
            db,
            error_message=msg,
            context={"job_name": "platform_health_recalculate"},
            fingerprint=fp,
            status="resolved",
            created_at=datetime.now(timezone.utc) - timedelta(hours=i + 1),
        )

    # 4th pending incident
    incident = _create_incident(
        db,
        error_message=msg,
        context={"job_name": "platform_health_recalculate"},
        fingerprint=fp,
    )
    db.flush()

    result = dispatch_pending_incidents(db)

    db.refresh(incident)
    assert incident.resolution_status == "escalated"
    assert "auto-retry limit reached" in (incident.resolution_action or "")
    assert result["escalated"] >= 1


# ── Test 4: responder failure is self-reported ────────────────────────────


def test_responder_failure_self_reports(db: Session):
    """If the job re-run raises, a new incident is created and original is not resolved."""
    msg = _unique_msg("platform_health_recalculate failed")
    incident = _create_incident(
        db,
        error_message=msg,
        context={"job_name": "platform_health_recalculate"},
    )
    db.flush()

    # Mock the job to raise
    def boom():
        raise RuntimeError("Simulated job explosion")

    with patch.dict(
        "app.scheduler.JOB_REGISTRY",
        {"platform_health_recalculate": boom},
    ):
        result = dispatch_pending_incidents(db)

    # Original incident should NOT be resolved (responder crashed before resolve)
    db.refresh(incident)
    assert incident.resolution_status == "pending"

    # A new self-report incident should exist
    self_report = (
        db.query(PlatformIncident)
        .filter(
            PlatformIncident.error_message.contains(
                "Responder BackgroundJobResponder failed"
            ),
        )
        .first()
    )
    assert self_report is not None
    assert result["errors"] >= 1


# ── Test 5: non-handled escalate-tier stays pending ───────────────────────


def test_escalate_tier_no_handler_stays_pending(db: Session):
    """data_integrity incidents (escalate, no handler) stay pending."""
    msg = _unique_msg("FK violation detected")
    incident = _create_incident(
        db,
        category="data_integrity",
        tier="escalate",
        error_message=msg,
    )
    db.flush()

    result = dispatch_pending_incidents(db)

    db.refresh(incident)
    assert incident.resolution_status == "pending"  # Unchanged
    assert result["no_handler"] >= 1


# ── Test 6: auth transient failure auto-resolves ──────────────────────────


def test_auth_transient_resolves(db: Session):
    """A single auth failure is treated as transient and resolved."""
    msg = _unique_msg("JWT expired during request")
    tenant_id = f"tenant-auth-{uuid.uuid4().hex[:8]}"
    incident = _create_incident(
        db,
        category="auth",
        tier="auto_fix",
        error_message=msg,
        tenant_id=tenant_id,
    )
    db.flush()

    result = dispatch_pending_incidents(db)

    db.refresh(incident)
    assert incident.resolution_status == "resolved"
    assert "transient auth failure" in (incident.resolution_action or "")
    assert result["resolved"] >= 1


# ── Test 7: auth breach threshold escalates + notifies ────────────────────


def test_auth_breach_escalates(db: Session):
    """5+ auth failures for the same tenant in 1 hour triggers breach escalation."""
    tenant_id = f"tenant-breach-{uuid.uuid4().hex[:8]}"

    # Create 5 prior auth failures in the last hour
    for i in range(5):
        _create_incident(
            db,
            category="auth",
            tier="auto_fix",
            error_message=_unique_msg(f"JWT expired #{i}"),
            status="pending",
            tenant_id=tenant_id,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=i + 1),
        )

    # The incident that will be dispatched (6th total, all pending)
    msg = _unique_msg("JWT expired #5")
    incident = _create_incident(
        db,
        category="auth",
        tier="auto_fix",
        error_message=msg,
        tenant_id=tenant_id,
    )
    db.flush()

    result = dispatch_pending_incidents(db)

    db.refresh(incident)
    assert incident.resolution_status == "escalated"
    assert "auth failures" in (incident.resolution_action or "").lower()

    # A notification should have been created
    notif = (
        db.query(PlatformNotification)
        .filter(PlatformNotification.incident_id == str(incident.id))
        .first()
    )
    assert notif is not None
    assert notif.level == "critical"
    assert "auth anomaly" in notif.title.lower()


# ── Test 8: infra probe passes → auto-resolves ───────────────────────────


def test_infra_probe_resolves(db: Session):
    """A single infra failure with passing DB probe is auto-resolved."""
    msg = _unique_msg("DB connection pool exhausted")
    incident = _create_incident(
        db,
        category="infra",
        tier="auto_fix",
        error_message=msg,
        tenant_id=f"tenant-infra-{uuid.uuid4().hex[:8]}",
    )
    db.flush()

    result = dispatch_pending_incidents(db)

    db.refresh(incident)
    assert incident.resolution_status == "resolved"
    assert "DB probe passed" in (incident.resolution_action or "")
    assert result["resolved"] >= 1


# ── Test 9: infra repeated failures → escalates ──────────────────────────


def test_infra_repeated_escalates(db: Session):
    """3+ infra failures in 2 hours triggers escalation."""
    # Create 3 prior infra incidents in last 2h
    for i in range(3):
        _create_incident(
            db,
            category="infra",
            tier="auto_fix",
            error_message=_unique_msg(f"DB connection dropped #{i}"),
            status="resolved",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=30 * (i + 1)),
        )

    # New pending incident
    msg = _unique_msg("DB connection dropped #3")
    incident = _create_incident(
        db,
        category="infra",
        tier="auto_fix",
        error_message=msg,
    )
    db.flush()

    result = dispatch_pending_incidents(db)

    db.refresh(incident)
    assert incident.resolution_status == "escalated"
    assert "infra failures" in (incident.resolution_action or "").lower()

    notif = (
        db.query(PlatformNotification)
        .filter(PlatformNotification.incident_id == str(incident.id))
        .first()
    )
    assert notif is not None
    assert notif.level == "critical"


# ── Test 10: config drift → preset reapplied ─────────────────────────────


def test_config_preset_reapplied(db: Session):
    """Config drift incident triggers preset reapplication."""
    tenant_id = f"tenant-config-{uuid.uuid4().hex[:8]}"
    msg = _unique_msg("Module config drifted from manufacturing preset")
    incident = _create_incident(
        db,
        category="config",
        tier="auto_remediate",
        error_message=msg,
        tenant_id=tenant_id,
    )
    db.flush()

    # Mock Company lookup and apply_preset_to_tenant
    mock_company = MagicMock()
    mock_company.vertical = "manufacturing"

    from app.services.platform.responders.config_responder import ConfigResponder

    responder = ConfigResponder()

    # Patch Company query to return our mock
    original_query = db.query

    def patched_query(model):
        from app.models.company import Company

        if model is Company:
            mock_q = MagicMock()
            mock_q.filter.return_value.first.return_value = mock_company
            return mock_q
        return original_query(model)

    with (
        patch.object(db, "query", side_effect=patched_query),
        patch(
            "app.services.tenant_module_service.apply_preset_to_tenant",
            return_value={"modules_enabled": 5},
        ),
        patch(
            "app.services.platform.platform_health_service.calculate_tenant_health",
        ),
    ):
        success = responder.handle(db, incident)

    db.refresh(incident)
    assert incident.resolution_status == "resolved"
    assert "preset" in (incident.resolution_action or "").lower()
    assert "manufacturing" in (incident.resolution_action or "")
    assert success is True

    # Check notification was created
    notif = (
        db.query(PlatformNotification)
        .filter(PlatformNotification.incident_id == str(incident.id))
        .first()
    )
    assert notif is not None
    assert notif.level == "warning"


# ── Test 11: migration rollback success ───────────────────────────────────


def test_migration_rollback_success(db: Session):
    """Successful alembic downgrade resolves the incident."""
    msg = _unique_msg("Migration z9x failed to apply")
    incident = _create_incident(
        db,
        category="migration",
        tier="auto_remediate",
        error_message=msg,
    )
    db.flush()

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Downgrade to z9w successful"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        from app.services.platform.responders.migration_responder import (
            MigrationResponder,
        )

        responder = MigrationResponder()
        success = responder.handle(db, incident)

    db.refresh(incident)
    assert incident.resolution_status == "resolved"
    assert "downgrade" in (incident.resolution_action or "").lower()
    assert success is True

    notif = (
        db.query(PlatformNotification)
        .filter(PlatformNotification.incident_id == str(incident.id))
        .first()
    )
    assert notif is not None
    assert notif.level == "warning"
    assert "rolled back" in notif.title.lower()


# ── Test 12: migration rollback failure → escalates ───────────────────────


def test_migration_rollback_failure(db: Session):
    """Failed alembic downgrade escalates the incident."""
    msg = _unique_msg("Migration z9y rollback-fail test")
    incident = _create_incident(
        db,
        category="migration",
        tier="auto_remediate",
        error_message=msg,
    )
    db.flush()

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "ERROR: relation does not exist"

    with patch("subprocess.run", return_value=mock_result):
        from app.services.platform.responders.migration_responder import (
            MigrationResponder,
        )

        responder = MigrationResponder()
        success = responder.handle(db, incident)

    db.refresh(incident)
    assert incident.resolution_status == "escalated"
    assert "downgrade" in (incident.resolution_action or "").lower()
    assert success is False

    notif = (
        db.query(PlatformNotification)
        .filter(PlatformNotification.incident_id == str(incident.id))
        .first()
    )
    assert notif is not None
    assert notif.level == "critical"


# ── Test 13: migration no double-rollback ─────────────────────────────────


def test_migration_no_double_rollback(db: Session):
    """If a prior rollback was already attempted for same fingerprint, refuse."""
    msg = _unique_msg("Migration z9x no-double test")
    fp = _make_fingerprint("migration", msg)

    # Prior incident with a downgrade already attempted
    _create_incident(
        db,
        category="migration",
        tier="auto_remediate",
        error_message=msg,
        fingerprint=fp,
        status="resolved",
        resolution_action="Auto-remediate: alembic downgrade -1 completed.",
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )

    # New pending incident with same fingerprint
    incident = _create_incident(
        db,
        category="migration",
        tier="auto_remediate",
        error_message=msg,
        fingerprint=fp,
    )
    db.flush()

    from app.services.platform.responders.migration_responder import (
        MigrationResponder,
    )

    responder = MigrationResponder()
    success = responder.handle(db, incident)

    db.refresh(incident)
    assert incident.resolution_status == "escalated"
    assert "already attempted" in (incident.resolution_action or "").lower()
    assert success is False

    notif = (
        db.query(PlatformNotification)
        .filter(PlatformNotification.incident_id == str(incident.id))
        .first()
    )
    assert notif is not None
    assert notif.level == "critical"


# ── Test 14: API contract → structured escalation + notification ──────────


def test_api_contract_escalation_with_notification(db: Session):
    """API contract incidents are structured-escalated with notifications."""
    msg = _unique_msg("GET /api/v1/orders returned 500")
    incident = _create_incident(
        db,
        category="api_contract",
        tier="escalate",
        error_message=msg,
        context={
            "route": "/api/v1/orders",
            "method": "GET",
            "status_code": 500,
        },
    )
    db.flush()

    result = dispatch_pending_incidents(db)

    db.refresh(incident)
    assert incident.resolution_status == "escalated"
    assert "API contract violation" in (incident.resolution_action or "")
    assert "/api/v1/orders" in (incident.resolution_action or "")

    notif = (
        db.query(PlatformNotification)
        .filter(PlatformNotification.incident_id == str(incident.id))
        .first()
    )
    assert notif is not None
    assert notif.level == "critical"
    assert "api contract" in notif.title.lower()
    assert result["escalated"] >= 1
