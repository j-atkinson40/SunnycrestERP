"""Tests for the incident responder system.

Verifies:
1. Background job responder resolves known job failures
2. Unknown job name escalates
3. Retry limit (3 in 24h) escalates
4. Responder failure is self-reported
5. Escalate-tier incidents are skipped
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.platform_incident import PlatformIncident
from app.services.platform.responders.dispatcher import dispatch_pending_incidents


def _make_fingerprint(category: str, message: str) -> str:
    normalized = f"{category}:{message[:200]}"
    return hashlib.sha256(normalized.encode()).hexdigest()[:64]


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
    incident = _create_incident(
        db,
        error_message="platform_health_recalculate failed",
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
    incident = _create_incident(
        db,
        error_message="some unknown job failed completely",
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
    fp = _make_fingerprint("background_job", "platform_health_recalculate failed")

    # Create 3 prior incidents in last 24h
    for i in range(3):
        _create_incident(
            db,
            error_message="platform_health_recalculate failed",
            context={"job_name": "platform_health_recalculate"},
            fingerprint=fp,
            status="resolved",
            created_at=datetime.now(timezone.utc) - timedelta(hours=i + 1),
        )

    # 4th pending incident
    incident = _create_incident(
        db,
        error_message="platform_health_recalculate failed",
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
    incident = _create_incident(
        db,
        error_message="platform_health_recalculate failed",
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


# ── Test 5: escalate-tier incidents are skipped ───────────────────────────


def test_escalate_tier_skipped(db: Session):
    """Incidents with resolution_tier='escalate' are never auto-handled."""
    incident = _create_incident(
        db,
        category="data_integrity",
        tier="escalate",
        error_message="FK violation detected",
    )
    db.flush()

    result = dispatch_pending_incidents(db)

    db.refresh(incident)
    assert incident.resolution_status == "pending"  # Unchanged
    assert result["total"] == 0  # Dispatcher doesn't even fetch escalate-tier
