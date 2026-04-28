"""Phase W-4a Commit 4 — Signal tracking endpoints + service + aggregation tests.

Verifies:
  • POST /pulse/signals/dismiss + /pulse/signals/navigate endpoints
    persist correctly with standardized JSONB metadata shapes (per
    r61 migration docstring)
  • signal_service write paths + validation
  • Aggregation helpers (dismiss_counts_per_component,
    navigation_targets, engagement_score) — ready for Tier 2
    algorithms post-September
  • Tenant isolation (canonical W-3 pattern) — A's signals don't
    leak to B's aggregations; cross-user writes structurally
    impossible
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest.fixture
def db_session() -> Iterator:
    from app.database import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _make_tenant_user_token() -> dict:
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"PulseSig-{suffix}",
            slug=f"ps-{suffix}",
            is_active=True,
            vertical="manufacturing",
            timezone="America/New_York",
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Test",
            slug="test",
            is_system=False,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@example.com",
            first_name="Sig",
            last_name="Test",
            hashed_password="x",
            is_active=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        token = create_access_token(
            {"sub": user.id, "company_id": co.id, "realm": "tenant"}
        )
        return {
            "company_id": co.id,
            "slug": co.slug,
            "user_id": user.id,
            "token": token,
        }
    finally:
        db.close()


def _auth_headers(ctx: dict) -> dict:
    return {
        "Authorization": f"Bearer {ctx['token']}",
        "X-Company-Slug": ctx["slug"],
    }


def _seed_signal(
    db_session,
    *,
    user_id: str,
    company_id: str,
    signal_type: str = "dismiss",
    component_key: str = "anomalies",
    layer: str = "anomaly",
    metadata: dict | None = None,
    timestamp_offset_hours: int = 0,
):
    """Direct DB seed for aggregation tests — bypasses the service
    layer to set arbitrary timestamps for time-window testing."""
    from app.models.pulse_signal import PulseSignal

    sig = PulseSignal(
        id=str(uuid.uuid4()),
        user_id=user_id,
        company_id=company_id,
        signal_type=signal_type,
        layer=layer,
        component_key=component_key,
        timestamp=datetime.now(timezone.utc)
        + timedelta(hours=timestamp_offset_hours),
        signal_metadata=metadata or {},
    )
    db_session.add(sig)
    db_session.commit()
    return sig


# ── Signal endpoints ───────────────────────────────────────────────


class TestSignalEndpoints:
    def test_dismiss_endpoint_requires_auth(self, client):
        r = client.post(
            "/api/v1/pulse/signals/dismiss",
            json={
                "component_key": "anomalies",
                "layer": "anomaly",
                "time_of_day": "morning",
            },
        )
        assert r.status_code in (401, 403)

    def test_navigate_endpoint_requires_auth(self, client):
        r = client.post(
            "/api/v1/pulse/signals/navigate",
            json={
                "from_component_key": "anomalies",
                "to_route": "/agents",
                "dwell_time_seconds": 12,
                "layer": "anomaly",
            },
        )
        assert r.status_code in (401, 403)

    def test_dismiss_persists_with_standardized_metadata(
        self, client, db_session
    ):
        from app.models.pulse_signal import PulseSignal

        ctx = _make_tenant_user_token()
        r = client.post(
            "/api/v1/pulse/signals/dismiss",
            headers=_auth_headers(ctx),
            json={
                "component_key": "vault_schedule",
                "layer": "operational",
                "time_of_day": "morning",
                "work_areas_at_dismiss": [
                    "Production Scheduling",
                    "Delivery Scheduling",
                ],
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["signal_type"] == "dismiss"
        assert body["component_key"] == "vault_schedule"
        assert body["layer"] == "operational"
        # Standardized JSONB metadata shape per r61 migration docstring
        assert body["metadata"]["component_key"] == "vault_schedule"
        assert body["metadata"]["time_of_day"] == "morning"
        assert body["metadata"]["work_areas_at_dismiss"] == [
            "Production Scheduling",
            "Delivery Scheduling",
        ]

        # Verify DB row
        row = (
            db_session.query(PulseSignal)
            .filter(PulseSignal.id == body["id"])
            .one()
        )
        assert row.user_id == ctx["user_id"]
        assert row.company_id == ctx["company_id"]
        assert row.signal_type == "dismiss"

    def test_navigate_persists_with_standardized_metadata(
        self, client, db_session
    ):
        from app.models.pulse_signal import PulseSignal

        ctx = _make_tenant_user_token()
        r = client.post(
            "/api/v1/pulse/signals/navigate",
            headers=_auth_headers(ctx),
            json={
                "from_component_key": "anomalies",
                "to_route": "/agents",
                "dwell_time_seconds": 8,
                "layer": "anomaly",
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["signal_type"] == "navigate"
        assert body["component_key"] == "anomalies"
        # Standardized metadata shape per r61
        assert body["metadata"]["from_component_key"] == "anomalies"
        assert body["metadata"]["to_route"] == "/agents"
        assert body["metadata"]["dwell_time_seconds"] == 8

    def test_dismiss_rejects_malformed_body(self, client):
        ctx = _make_tenant_user_token()
        # Missing required component_key
        r = client.post(
            "/api/v1/pulse/signals/dismiss",
            headers=_auth_headers(ctx),
            json={"layer": "anomaly", "time_of_day": "morning"},
        )
        assert r.status_code == 422

    def test_dismiss_rejects_invalid_layer(self, client):
        ctx = _make_tenant_user_token()
        r = client.post(
            "/api/v1/pulse/signals/dismiss",
            headers=_auth_headers(ctx),
            json={
                "component_key": "anomalies",
                "layer": "bogus_layer",
                "time_of_day": "morning",
            },
        )
        # Service-layer validation — 400 Bad Request
        assert r.status_code == 400

    def test_dismiss_rejects_invalid_time_of_day(self, client):
        ctx = _make_tenant_user_token()
        r = client.post(
            "/api/v1/pulse/signals/dismiss",
            headers=_auth_headers(ctx),
            json={
                "component_key": "anomalies",
                "layer": "anomaly",
                "time_of_day": "midnight",  # not canonical
            },
        )
        assert r.status_code == 400

    def test_navigate_rejects_negative_dwell(self, client):
        ctx = _make_tenant_user_token()
        r = client.post(
            "/api/v1/pulse/signals/navigate",
            headers=_auth_headers(ctx),
            json={
                "from_component_key": "anomalies",
                "to_route": "/agents",
                "dwell_time_seconds": -5,
                "layer": "anomaly",
            },
        )
        # Pydantic ge=0 → 422
        assert r.status_code == 422

    def test_navigate_caps_pathological_dwell_time(
        self, client, db_session
    ):
        """24h+ dwell_time gets capped, not rejected — defends
        against pathological client clocks without forcing 400 on
        legitimate-but-sleepy users."""
        from app.models.pulse_signal import PulseSignal

        ctx = _make_tenant_user_token()
        r = client.post(
            "/api/v1/pulse/signals/navigate",
            headers=_auth_headers(ctx),
            json={
                "from_component_key": "anomalies",
                "to_route": "/agents",
                "dwell_time_seconds": 999999,  # ~11 days
                "layer": "anomaly",
            },
        )
        assert r.status_code == 201
        # Capped at 24h = 86400
        body = r.json()
        assert body["metadata"]["dwell_time_seconds"] == 86400

    def test_signal_user_id_forced_from_token_not_body(
        self, client, db_session
    ):
        """Cross-user write rejected — the body has no user_id field
        at all, so Pydantic strips any caller-supplied user_id and
        the service forces user_id from the auth token."""
        from app.models.pulse_signal import PulseSignal

        ctx_a = _make_tenant_user_token()
        ctx_b = _make_tenant_user_token()
        # User A authenticates; tries to inject user_id=B in body
        r = client.post(
            "/api/v1/pulse/signals/dismiss",
            headers=_auth_headers(ctx_a),
            json={
                "component_key": "anomalies",
                "layer": "anomaly",
                "time_of_day": "morning",
                # Pydantic schema doesn't define user_id; this field
                # is silently ignored. The service forces user_id
                # from current_user.id.
                "user_id": ctx_b["user_id"],
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        # Verify in DB the row belongs to A, not B
        row = (
            db_session.query(PulseSignal)
            .filter(PulseSignal.id == body["id"])
            .one()
        )
        assert row.user_id == ctx_a["user_id"]
        assert row.company_id == ctx_a["company_id"]
        # NOT B
        assert row.user_id != ctx_b["user_id"]


# ── Signal service ─────────────────────────────────────────────────


class TestSignalService:
    def test_record_dismiss_writes_correctly(self, db_session):
        from app.models.user import User
        from app.services.pulse.signal_service import record_dismiss

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        sig = record_dismiss(
            db_session,
            user=user,
            component_key="vault_schedule",
            layer="operational",
            time_of_day="morning",
            work_areas_at_dismiss=["Production Scheduling"],
        )
        assert sig.signal_type == "dismiss"
        assert sig.component_key == "vault_schedule"
        assert sig.user_id == user.id
        assert sig.company_id == user.company_id
        assert sig.signal_metadata == {
            "component_key": "vault_schedule",
            "time_of_day": "morning",
            "work_areas_at_dismiss": ["Production Scheduling"],
        }

    def test_record_navigation_writes_correctly(self, db_session):
        from app.models.user import User
        from app.services.pulse.signal_service import record_navigation

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        sig = record_navigation(
            db_session,
            user=user,
            from_component_key="anomalies",
            to_route="/agents",
            dwell_time_seconds=12,
            layer="anomaly",
        )
        assert sig.signal_type == "navigate"
        assert sig.component_key == "anomalies"
        assert sig.signal_metadata == {
            "from_component_key": "anomalies",
            "to_route": "/agents",
            "dwell_time_seconds": 12,
        }

    def test_unknown_layer_rejected(self, db_session):
        from app.models.user import User
        from app.services.pulse.signal_service import (
            SignalValidationError,
            record_dismiss,
        )

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        with pytest.raises(SignalValidationError):
            record_dismiss(
                db_session,
                user=user,
                component_key="x",
                layer="bogus",
                time_of_day="morning",
            )

    def test_empty_component_key_rejected(self, db_session):
        from app.models.user import User
        from app.services.pulse.signal_service import (
            SignalValidationError,
            record_dismiss,
        )

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        with pytest.raises(SignalValidationError):
            record_dismiss(
                db_session,
                user=user,
                component_key="   ",  # whitespace-only
                layer="anomaly",
                time_of_day="morning",
            )

    def test_dismiss_without_time_of_day_rejected(self, db_session):
        """time_of_day required — Tier 2 algorithms need it for
        time-of-day adaptation patterns."""
        from app.models.user import User
        from app.services.pulse.signal_service import (
            SignalValidationError,
            record_dismiss,
        )

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        with pytest.raises(SignalValidationError):
            record_dismiss(
                db_session,
                user=user,
                component_key="anomalies",
                layer="anomaly",
                time_of_day=None,  # type: ignore[arg-type]
            )


# ── Aggregation helpers ────────────────────────────────────────────


class TestAggregationHelpers:
    def test_dismiss_counts_per_component(self, db_session):
        from app.models.user import User
        from app.services.pulse.signal_service import (
            get_dismiss_counts_per_component,
        )

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        # 3 dismisses of vault_schedule, 1 of anomalies, 0 of today
        for _ in range(3):
            _seed_signal(
                db_session,
                user_id=user.id,
                company_id=user.company_id,
                signal_type="dismiss",
                component_key="vault_schedule",
                layer="operational",
            )
        _seed_signal(
            db_session,
            user_id=user.id,
            company_id=user.company_id,
            signal_type="dismiss",
            component_key="anomalies",
            layer="anomaly",
        )
        # A navigation should NOT count toward dismiss counts
        _seed_signal(
            db_session,
            user_id=user.id,
            company_id=user.company_id,
            signal_type="navigate",
            component_key="vault_schedule",
            layer="operational",
        )
        counts = get_dismiss_counts_per_component(
            db_session, user=user, days=30
        )
        assert counts == {"vault_schedule": 3, "anomalies": 1}

    def test_dismiss_counts_time_window_filter(self, db_session):
        """Signals older than `days` window are excluded."""
        from app.models.user import User
        from app.services.pulse.signal_service import (
            get_dismiss_counts_per_component,
        )

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        # Recent dismiss
        _seed_signal(
            db_session,
            user_id=user.id,
            company_id=user.company_id,
            signal_type="dismiss",
            component_key="vault_schedule",
            timestamp_offset_hours=0,
        )
        # 60 days ago — outside the 30-day window
        _seed_signal(
            db_session,
            user_id=user.id,
            company_id=user.company_id,
            signal_type="dismiss",
            component_key="vault_schedule",
            timestamp_offset_hours=-60 * 24,
        )
        counts = get_dismiss_counts_per_component(
            db_session, user=user, days=30
        )
        # Only the recent one
        assert counts == {"vault_schedule": 1}

    def test_navigation_targets_ordered_by_frequency_then_recency(
        self, db_session
    ):
        from app.models.user import User
        from app.services.pulse.signal_service import (
            get_navigation_targets,
        )

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        # /agents: 3 nav events
        for _ in range(3):
            _seed_signal(
                db_session,
                user_id=user.id,
                company_id=user.company_id,
                signal_type="navigate",
                component_key="anomalies",
                layer="anomaly",
                metadata={
                    "from_component_key": "anomalies",
                    "to_route": "/agents",
                    "dwell_time_seconds": 5,
                },
            )
        # /tasks: 1 nav event
        _seed_signal(
            db_session,
            user_id=user.id,
            company_id=user.company_id,
            signal_type="navigate",
            component_key="anomalies",
            layer="anomaly",
            metadata={
                "from_component_key": "anomalies",
                "to_route": "/tasks",
                "dwell_time_seconds": 3,
            },
        )
        targets = get_navigation_targets(
            db_session, user=user, from_component_key="anomalies", days=30
        )
        # /agents first (count=3), then /tasks (count=1)
        assert len(targets) == 2
        assert targets[0]["to_route"] == "/agents"
        assert targets[0]["count"] == 3
        assert targets[1]["to_route"] == "/tasks"
        assert targets[1]["count"] == 1

    def test_navigation_targets_empty_when_no_signals(self, db_session):
        from app.models.user import User
        from app.services.pulse.signal_service import (
            get_navigation_targets,
        )

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        targets = get_navigation_targets(
            db_session,
            user=user,
            from_component_key="anomalies",
            days=30,
        )
        assert targets == []

    def test_engagement_score_navigation_minus_weighted_dismisses(
        self, db_session
    ):
        from app.models.user import User
        from app.services.pulse.signal_service import get_engagement_score

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        # 5 navigations + 1 dismiss = 5 - (2.0 × 1) = 3.0
        for _ in range(5):
            _seed_signal(
                db_session,
                user_id=user.id,
                company_id=user.company_id,
                signal_type="navigate",
                component_key="vault_schedule",
                layer="operational",
            )
        _seed_signal(
            db_session,
            user_id=user.id,
            company_id=user.company_id,
            signal_type="dismiss",
            component_key="vault_schedule",
            layer="operational",
        )
        score = get_engagement_score(
            db_session, user=user, component_key="vault_schedule", days=30
        )
        assert score == 3.0

    def test_engagement_score_no_signals_zero(self, db_session):
        from app.models.user import User
        from app.services.pulse.signal_service import get_engagement_score

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        score = get_engagement_score(
            db_session, user=user, component_key="vault_schedule", days=30
        )
        assert score == 0.0

    def test_engagement_score_negative_for_net_disengagement(
        self, db_session
    ):
        """Heavy dismisses + few navigations → negative score (signal
        of net disengagement)."""
        from app.models.user import User
        from app.services.pulse.signal_service import get_engagement_score

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        # 10 dismisses, 2 navigations → 2 - (2.0 × 10) = -18
        for _ in range(10):
            _seed_signal(
                db_session,
                user_id=user.id,
                company_id=user.company_id,
                signal_type="dismiss",
                component_key="anomalies",
                layer="anomaly",
            )
        for _ in range(2):
            _seed_signal(
                db_session,
                user_id=user.id,
                company_id=user.company_id,
                signal_type="navigate",
                component_key="anomalies",
                layer="anomaly",
            )
        score = get_engagement_score(
            db_session, user=user, component_key="anomalies", days=30
        )
        assert score < 0
        assert score == -18.0


# ── Tenant isolation ───────────────────────────────────────────────


class TestTenantIsolation:
    def test_dismiss_counts_scoped_to_caller_user(self, db_session):
        """User A's signals don't appear in user B's aggregations."""
        from app.models.user import User
        from app.services.pulse.signal_service import (
            get_dismiss_counts_per_component,
        )

        ctx_a = _make_tenant_user_token()
        ctx_b = _make_tenant_user_token()
        # B has 5 dismisses; A has 0
        for _ in range(5):
            _seed_signal(
                db_session,
                user_id=ctx_b["user_id"],
                company_id=ctx_b["company_id"],
                signal_type="dismiss",
                component_key="vault_schedule",
                layer="operational",
            )
        user_a = (
            db_session.query(User).filter(User.id == ctx_a["user_id"]).one()
        )
        counts = get_dismiss_counts_per_component(
            db_session, user=user_a, days=30
        )
        # A sees nothing
        assert counts == {}

    def test_navigation_targets_scoped_to_caller_user(self, db_session):
        from app.models.user import User
        from app.services.pulse.signal_service import (
            get_navigation_targets,
        )

        ctx_a = _make_tenant_user_token()
        ctx_b = _make_tenant_user_token()
        # B has 3 nav signals; A has 0
        for _ in range(3):
            _seed_signal(
                db_session,
                user_id=ctx_b["user_id"],
                company_id=ctx_b["company_id"],
                signal_type="navigate",
                component_key="anomalies",
                layer="anomaly",
                metadata={
                    "from_component_key": "anomalies",
                    "to_route": "/agents",
                    "dwell_time_seconds": 5,
                },
            )
        user_a = (
            db_session.query(User).filter(User.id == ctx_a["user_id"]).one()
        )
        targets = get_navigation_targets(
            db_session,
            user=user_a,
            from_component_key="anomalies",
            days=30,
        )
        assert targets == []

    def test_engagement_score_scoped_to_caller_user(self, db_session):
        from app.models.user import User
        from app.services.pulse.signal_service import get_engagement_score

        ctx_a = _make_tenant_user_token()
        ctx_b = _make_tenant_user_token()
        # B has heavy engagement on vault_schedule; A's score
        # should be 0.0 (sees nothing).
        for _ in range(10):
            _seed_signal(
                db_session,
                user_id=ctx_b["user_id"],
                company_id=ctx_b["company_id"],
                signal_type="navigate",
                component_key="vault_schedule",
                layer="operational",
            )
        user_a = (
            db_session.query(User).filter(User.id == ctx_a["user_id"]).one()
        )
        score = get_engagement_score(
            db_session,
            user=user_a,
            component_key="vault_schedule",
            days=30,
        )
        assert score == 0.0

    def test_endpoint_writes_use_caller_company_id(
        self, client, db_session
    ):
        """Direct verification: endpoint POST persists with caller's
        company_id, not anything from the request body."""
        from app.models.pulse_signal import PulseSignal

        ctx = _make_tenant_user_token()
        r = client.post(
            "/api/v1/pulse/signals/dismiss",
            headers=_auth_headers(ctx),
            json={
                "component_key": "anomalies",
                "layer": "anomaly",
                "time_of_day": "morning",
                # Even if a malicious client tries to inject company_id,
                # Pydantic schema doesn't define it; service forces
                # company_id from auth.
                "company_id": "evil-tenant-id",
            },
        )
        assert r.status_code == 201
        body = r.json()
        row = (
            db_session.query(PulseSignal)
            .filter(PulseSignal.id == body["id"])
            .one()
        )
        assert row.company_id == ctx["company_id"]
        assert row.company_id != "evil-tenant-id"
