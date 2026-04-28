"""Phase W-4a Commit 3 — Composition engine + Pulse API tests.

Verifies the composition engine assembles layers correctly, the V1
anomaly intelligence stream synthesizes meaningful prose, the
work_areas-aware cache invalidates correctly, the Pulse API endpoint
enforces tenant isolation, and the legacy
`spaces/pulse_compositions.py` is fully retired.

Test classes:
  • TestCompositionEngine — engine orchestration + layer ordering
  • TestAnomalyIntelligenceStreamV1 — synthesis quality + edge cases
  • TestPulseAPIEndpoint — auth + tenant isolation + response shape
  • TestCacheBehavior — work_areas-aware invalidation + TTL + bypass
  • TestPulseCompositionsRetirement — D7 grep verification
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _seeded() -> Iterator[None]:
    from app.database import SessionLocal
    from app.services.widgets.widget_registry import seed_widget_definitions
    from app.services.pulse import composition_cache

    db = SessionLocal()
    try:
        seed_widget_definitions(db)
        # Reset in-memory cache between tests so test isolation holds.
        composition_cache._test_clear()
        yield
    finally:
        db.close()


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


def _make_tenant_user_token(
    *,
    vertical: str = "manufacturing",
    work_areas: list[str] | None = None,
    permissions: list[str] | None = None,
    product_lines: list[tuple[str, str]] | None = None,
) -> dict:
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.role_permission import RolePermission
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"PulseAPI-{suffix}",
            slug=f"pa-{suffix}",
            is_active=True,
            vertical=vertical,
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
        for p in permissions or []:
            db.add(RolePermission(role_id=role.id, permission_key=p))
        if permissions:
            db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@example.com",
            first_name="Pulse",
            last_name="API",
            hashed_password="x",
            is_active=True,
            role_id=role.id,
            work_areas=work_areas,
        )
        db.add(user)
        db.commit()
        if product_lines:
            from app.services import product_line_service

            for line_key, mode in product_lines:
                product_line_service.enable_line(
                    db,
                    company_id=co.id,
                    line_key=line_key,
                    operating_mode=mode,
                )
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


def _make_anomaly(
    db_session,
    *,
    tenant_id: str,
    severity: str = "critical",
    anomaly_type: str = "balance_mismatch",
    description: str = "Hopkins invoice balance mismatch",
):
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly

    j = AgentJob(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        job_type="month_end_close",
        status="complete",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(j)
    db_session.flush()
    a = AgentAnomaly(
        id=str(uuid.uuid4()),
        agent_job_id=j.id,
        severity=severity,
        anomaly_type=anomaly_type,
        description=description,
        resolved=False,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(a)
    db_session.commit()
    return a


# ── Composition engine ─────────────────────────────────────────────


class TestCompositionEngine:
    def test_composes_for_user_with_work_areas(self, db_session):
        from app.models.user import User
        from app.services.pulse.composition_engine import compose_for_user

        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            work_areas=["Production Scheduling", "Delivery Scheduling"],
            permissions=["delivery.view"],
            product_lines=[("vault", "production")],
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        # Layer ordering per §3.26.2.4
        layers = [lc.layer for lc in result.layers]
        assert layers == ["personal", "operational", "anomaly", "activity"]
        # Sunnycrest dispatcher composition
        op_keys = {
            it.component_key
            for it in result.layers[1].items  # operational layer
        }
        assert "vault_schedule" in op_keys
        assert "scheduling.ancillary-pool" in op_keys
        assert result.metadata.work_areas_used == [
            "Production Scheduling",
            "Delivery Scheduling",
        ]
        assert result.metadata.vertical_default_applied is False

    def test_vertical_default_fallback_for_user_without_work_areas(
        self, db_session
    ):
        from app.models.user import User
        from app.services.pulse.composition_engine import compose_for_user

        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            work_areas=None,  # not set
            permissions=["delivery.view"],
            product_lines=[("vault", "production")],
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        assert result.metadata.vertical_default_applied is True
        assert result.metadata.work_areas_used == []
        # Sunnycrest manufacturing default surfaces vault_schedule etc.
        op_keys = {
            it.component_key for it in result.layers[1].items
        }
        assert "vault_schedule" in op_keys

    def test_sizing_rules_per_d5_demo_composition(self, db_session):
        """vault_schedule renders Detail (2x2) as primary work
        surface per D5 + §3.26.2.4."""
        from app.models.user import User
        from app.services.pulse.composition_engine import compose_for_user

        ctx = _make_tenant_user_token(
            work_areas=["Production Scheduling", "Delivery Scheduling"],
            permissions=["delivery.view"],
            product_lines=[("vault", "production")],
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        op_layer = result.layers[1]
        vs = next(
            it for it in op_layer.items if it.component_key == "vault_schedule"
        )
        assert vs.variant_id == "detail"
        assert vs.cols == 2 and vs.rows == 2
        # line_status Brief (2x1)
        ls = next(
            it for it in op_layer.items if it.component_key == "line_status"
        )
        assert ls.variant_id == "brief"
        # today Glance (1x1)
        td = next(
            it for it in op_layer.items if it.component_key == "today"
        )
        assert td.variant_id == "glance"

    def test_dedupe_across_overlapping_work_areas(self, db_session):
        from app.models.user import User
        from app.services.pulse.composition_engine import compose_for_user

        ctx = _make_tenant_user_token(
            # Both Production Scheduling + Delivery Scheduling list
            # vault_schedule. Engine must de-dupe.
            work_areas=["Production Scheduling", "Delivery Scheduling"],
            permissions=["delivery.view"],
            product_lines=[("vault", "production")],
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        op_layer = result.layers[1]
        vs_count = sum(
            1 for it in op_layer.items if it.component_key == "vault_schedule"
        )
        assert vs_count == 1

    def test_time_of_day_signal_recorded_in_metadata(self, db_session):
        from app.models.user import User
        from app.services.pulse.composition_engine import compose_for_user

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        # Signal must be one of the canonical 4 values
        assert result.metadata.time_of_day_signal in {
            "morning",
            "midday",
            "end_of_day",
            "off_hours",
        }

    def test_intelligence_stream_emitted_when_anomalies_present(
        self, db_session
    ):
        from app.models.user import User
        from app.services.pulse.composition_engine import compose_for_user

        ctx = _make_tenant_user_token(
            work_areas=["Accounting"],
        )
        _make_anomaly(db_session, tenant_id=ctx["company_id"])
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        assert len(result.intelligence_streams) == 1
        stream = result.intelligence_streams[0]
        assert stream.stream_id == "anomaly_intelligence"
        assert stream.layer == "anomaly"
        assert "Hopkins" in stream.synthesized_text  # entity surfaced

    def test_intelligence_stream_empty_when_no_anomalies(self, db_session):
        from app.models.user import User
        from app.services.pulse.composition_engine import compose_for_user

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        assert result.intelligence_streams == []


# ── Anomaly Intelligence Stream V1 ─────────────────────────────────


class TestAnomalyIntelligenceStreamV1:
    def test_synthesizes_text_with_count_and_most_urgent(self):
        from app.services.pulse.anomaly_intelligence_v1 import synthesize

        payload = {
            "total_unresolved": 3,
            "critical_count": 2,
            "warning_count": 1,
            "info_count": 0,
            "top_anomalies": [
                {
                    "id": "a1",
                    "severity": "critical",
                    "anomaly_type": "balance_mismatch",
                    "description": "Hopkins invoice balance mismatch",
                },
                {
                    "id": "a2",
                    "severity": "critical",
                    "anomaly_type": "duplicate_payment",
                    "description": "Duplicate payment from Smith FH",
                },
                {
                    "id": "a3",
                    "severity": "warning",
                    "anomaly_type": "overdue_ar_90plus",
                    "description": "Jones FH 95 days overdue",
                },
            ],
            "work_areas": [],
        }
        stream = synthesize(payload=payload)
        assert stream is not None
        assert stream.stream_id == "anomaly_intelligence"
        assert stream.title == "Today's watch list"
        # Severity count phrase included
        assert "2 critical" in stream.synthesized_text
        assert "1 warning" in stream.synthesized_text
        # Most urgent named
        assert "Hopkins" in stream.synthesized_text
        # Watch list mentions secondary items
        assert "Smith" in stream.synthesized_text or "Jones" in stream.synthesized_text

    def test_returns_none_for_zero_anomalies(self):
        from app.services.pulse.anomaly_intelligence_v1 import synthesize

        payload = {
            "total_unresolved": 0,
            "critical_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "top_anomalies": [],
            "work_areas": [],
        }
        assert synthesize(payload=payload) is None

    def test_referenced_items_built_from_top_anomalies(self):
        from app.services.pulse.anomaly_intelligence_v1 import synthesize

        payload = {
            "total_unresolved": 1,
            "critical_count": 1,
            "warning_count": 0,
            "info_count": 0,
            "top_anomalies": [
                {
                    "id": "a1",
                    "severity": "critical",
                    "anomaly_type": "balance_mismatch",
                    "description": "Test description",
                }
            ],
            "work_areas": [],
        }
        stream = synthesize(payload=payload)
        assert stream is not None
        assert len(stream.referenced_items) == 1
        ref = stream.referenced_items[0]
        assert ref.kind == "anomaly"
        assert ref.entity_id == "a1"

    def test_work_area_relevance_filter(self):
        """Anomalies relevant to the user's work_areas surface first."""
        from app.services.pulse.anomaly_intelligence_v1 import synthesize

        payload = {
            "total_unresolved": 2,
            "critical_count": 2,
            "warning_count": 0,
            "info_count": 0,
            "top_anomalies": [
                {
                    "id": "a-acct",
                    "severity": "critical",
                    "anomaly_type": "balance_mismatch",  # → Accounting
                    "description": "Accounting issue",
                },
                {
                    "id": "a-delivery",
                    "severity": "critical",
                    "anomaly_type": "delivery_sla_risk",  # → Delivery Scheduling
                    "description": "Delivery SLA at risk",
                },
            ],
            # User cares about Delivery Scheduling — that anomaly
            # should be the "most urgent" mentioned by name.
            "work_areas": ["Delivery Scheduling"],
        }
        stream = synthesize(payload=payload)
        assert stream is not None
        # First anomaly mentioned = the relevant one.
        assert "Delivery SLA" in stream.synthesized_text

    def test_critical_count_priority_signal(self):
        """When only critical anomalies exist, the synthesis carries
        the critical-count phrasing, not ambiguous totals."""
        from app.services.pulse.anomaly_intelligence_v1 import synthesize

        payload = {
            "total_unresolved": 1,
            "critical_count": 1,
            "warning_count": 0,
            "info_count": 0,
            "top_anomalies": [
                {
                    "id": "a1",
                    "severity": "critical",
                    "anomaly_type": "balance_mismatch",
                    "description": "Critical issue",
                }
            ],
            "work_areas": [],
        }
        stream = synthesize(payload=payload)
        assert stream is not None
        assert (
            "critical" in stream.synthesized_text.lower()
            or "needs attention" in stream.synthesized_text.lower()
        )


# ── Pulse API endpoint ─────────────────────────────────────────────


class TestPulseAPIEndpoint:
    def test_authenticated_user_gets_composition(self, client):
        ctx = _make_tenant_user_token(
            work_areas=["Production Scheduling"],
            permissions=["delivery.view"],
            product_lines=[("vault", "production")],
        )
        r = client.get(
            "/api/v1/pulse/composition", headers=_auth_headers(ctx)
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # Response shape per Commit 3 spec
        assert body["user_id"] == ctx["user_id"]
        assert "composed_at" in body
        assert isinstance(body["layers"], list)
        assert len(body["layers"]) == 4
        assert {lc["layer"] for lc in body["layers"]} == {
            "personal",
            "operational",
            "anomaly",
            "activity",
        }
        assert "intelligence_streams" in body
        assert body["metadata"]["vertical_default_applied"] is False
        assert "Production Scheduling" in body["metadata"]["work_areas_used"]

    def test_unauthenticated_returns_401_or_403(self, client):
        r = client.get("/api/v1/pulse/composition")
        assert r.status_code in (401, 403)

    def test_response_serialization_includes_layer_items(self, client):
        ctx = _make_tenant_user_token(
            work_areas=["Production Scheduling"],
            permissions=["delivery.view"],
            product_lines=[("vault", "production")],
        )
        r = client.get(
            "/api/v1/pulse/composition", headers=_auth_headers(ctx)
        )
        body = r.json()
        op_layer = next(
            lc for lc in body["layers"] if lc["layer"] == "operational"
        )
        # Layer items serialize as dicts with the canonical shape
        for item in op_layer["items"]:
            assert "item_id" in item
            assert "kind" in item
            assert "component_key" in item
            assert "variant_id" in item
            assert "cols" in item
            assert "rows" in item
            assert "priority" in item

    def test_tenant_isolation_no_cross_tenant_anomalies(self, client, db_session):
        """User A's Pulse must not surface tenant B's anomalies."""
        ctx_a = _make_tenant_user_token(
            work_areas=["Accounting"],
        )
        ctx_b = _make_tenant_user_token()
        # Anomaly seeded in tenant B; A must not see it.
        _make_anomaly(db_session, tenant_id=ctx_b["company_id"])
        r = client.get(
            "/api/v1/pulse/composition",
            headers=_auth_headers(ctx_a),
        )
        body = r.json()
        # No intelligence stream for A (B's anomaly should not surface)
        assert body["intelligence_streams"] == []

    def test_refresh_query_param_bypasses_cache(self, client):
        """?refresh=true forces re-composition even if cache is warm."""
        ctx = _make_tenant_user_token(
            work_areas=["Production Scheduling"],
            permissions=["delivery.view"],
            product_lines=[("vault", "production")],
        )
        # Warm the cache
        r1 = client.get(
            "/api/v1/pulse/composition", headers=_auth_headers(ctx)
        )
        composed_at_1 = r1.json()["composed_at"]
        # Manual refresh — different composed_at proves bypass
        time.sleep(0.05)
        r2 = client.get(
            "/api/v1/pulse/composition?refresh=true",
            headers=_auth_headers(ctx),
        )
        composed_at_2 = r2.json()["composed_at"]
        assert composed_at_1 != composed_at_2


# ── Cache behavior ─────────────────────────────────────────────────


class TestCacheBehavior:
    def test_first_request_misses_then_second_hits(self, client):
        from app.services.pulse import composition_cache

        ctx = _make_tenant_user_token(
            work_areas=["Production Scheduling"]
        )
        composition_cache._test_clear()
        r1 = client.get(
            "/api/v1/pulse/composition", headers=_auth_headers(ctx)
        )
        composed_at_1 = r1.json()["composed_at"]
        # Second request inside the same minute window — cache hit
        r2 = client.get(
            "/api/v1/pulse/composition", headers=_auth_headers(ctx)
        )
        composed_at_2 = r2.json()["composed_at"]
        # Same cached composition → same composed_at
        assert composed_at_1 == composed_at_2

    def test_updating_work_areas_invalidates_cache_via_hash_change(
        self, client, db_session
    ):
        """User updates work_areas → cache key includes new hash →
        next request misses → re-composes."""
        from app.models.user import User

        ctx = _make_tenant_user_token(
            work_areas=["Production Scheduling"]
        )
        # Warm cache
        r1 = client.get(
            "/api/v1/pulse/composition", headers=_auth_headers(ctx)
        )
        composed_at_1 = r1.json()["composed_at"]

        # Update work_areas via the operator-profile API (canonical path)
        r_patch = client.patch(
            "/api/v1/operator-profile",
            headers=_auth_headers(ctx),
            json={"work_areas": ["Customer Service"]},
        )
        assert r_patch.status_code == 200

        # Refetch — cache key contains different work_areas hash, so
        # this is a miss and re-composes
        time.sleep(0.05)
        r2 = client.get(
            "/api/v1/pulse/composition", headers=_auth_headers(ctx)
        )
        body2 = r2.json()
        composed_at_2 = body2["composed_at"]
        # Different composition → different timestamp (proves miss)
        assert composed_at_1 != composed_at_2
        # Metadata reflects new work_areas
        assert body2["metadata"]["work_areas_used"] == ["Customer Service"]

    def test_updating_responsibilities_does_not_invalidate_cache(
        self, client, db_session
    ):
        """Per spec: responsibilities don't affect Tier 1 composition,
        so updating responsibilities shouldn't invalidate the cache.
        Cache key only includes work_areas hash, not responsibilities,
        so an update to responsibilities should produce a cache hit
        on the next request."""
        ctx = _make_tenant_user_token(
            work_areas=["Production Scheduling"]
        )
        r1 = client.get(
            "/api/v1/pulse/composition", headers=_auth_headers(ctx)
        )
        composed_at_1 = r1.json()["composed_at"]

        # Update responsibilities only
        r_patch = client.patch(
            "/api/v1/operator-profile",
            headers=_auth_headers(ctx),
            json={"responsibilities_description": "I dispatch deliveries."},
        )
        assert r_patch.status_code == 200

        time.sleep(0.05)
        r2 = client.get(
            "/api/v1/pulse/composition", headers=_auth_headers(ctx)
        )
        composed_at_2 = r2.json()["composed_at"]
        # Same cache key → cache hit → same composed_at
        assert composed_at_1 == composed_at_2

    def test_cache_key_stability_under_work_area_reorder(self):
        """Sorting work_areas in the hash means selection order
        doesn't change the key — UI can present cards in any order."""
        from app.services.pulse import composition_cache

        k1 = composition_cache.cache_key(
            user_id="u1",
            work_areas=["Production Scheduling", "Delivery Scheduling"],
        )
        k2 = composition_cache.cache_key(
            user_id="u1",
            work_areas=["Delivery Scheduling", "Production Scheduling"],
        )
        assert k1 == k2

    def test_cache_key_differs_per_user(self):
        from app.services.pulse import composition_cache

        k_a = composition_cache.cache_key(
            user_id="user-a", work_areas=["Accounting"]
        )
        k_b = composition_cache.cache_key(
            user_id="user-b", work_areas=["Accounting"]
        )
        assert k_a != k_b

    def test_cache_key_differs_per_work_areas(self):
        from app.services.pulse import composition_cache

        k_a = composition_cache.cache_key(
            user_id="u1", work_areas=["Accounting"]
        )
        k_b = composition_cache.cache_key(
            user_id="u1", work_areas=["Inventory Management"]
        )
        assert k_a != k_b

    def test_invalidate_for_user_drops_all_keys(self):
        """invalidate_for_user evicts all cached compositions for a
        user across all work_areas hashes + minute windows."""
        from datetime import datetime, timedelta, timezone

        from app.services.pulse import composition_cache
        from app.services.pulse.types import (
            PulseComposition,
            PulseCompositionMetadata,
        )

        composition_cache._test_clear()
        now = datetime.now(timezone.utc)
        # Two different work_areas hashes for the same user
        for areas in [["Accounting"], ["Inventory Management"]]:
            comp = PulseComposition(
                user_id="user-x",
                composed_at=now,
                layers=[],
                intelligence_streams=[],
                metadata=PulseCompositionMetadata(
                    work_areas_used=areas,
                    vertical_default_applied=False,
                    time_of_day_signal="morning",
                ),
            )
            key = composition_cache.cache_key(
                user_id="user-x", work_areas=areas, now=now
            )
            composition_cache.put(key, comp)

        evicted = composition_cache.invalidate_for_user("user-x")
        assert evicted >= 2
        # Subsequent reads miss
        for areas in [["Accounting"], ["Inventory Management"]]:
            key = composition_cache.cache_key(
                user_id="user-x", work_areas=areas, now=now
            )
            assert composition_cache.get(key) is None


# ── Pulse compositions retirement (D7) ─────────────────────────────


class TestPulseCompositionsRetirement:
    def test_pulse_compositions_module_no_longer_importable(self):
        """Per D7: legacy module deleted in Commit 3.6 with grep-
        verified zero consumers. Import must fail."""
        with pytest.raises(ModuleNotFoundError):
            __import__("app.services.spaces.pulse_compositions")

    def test_new_composition_engine_importable(self):
        from app.services.pulse import composition_engine

        assert hasattr(composition_engine, "compose_for_user")

    def test_pulse_composition_dataclass_in_new_location(self):
        """The PulseComposition name is preserved but lives in the
        new package — `app.services.pulse.types`, not the old
        `app.services.spaces.pulse_compositions`."""
        from app.services.pulse.types import PulseComposition

        assert PulseComposition is not None
        # Sanity — the new dataclass keys on user, not (vertical, role)
        from dataclasses import fields

        field_names = {f.name for f in fields(PulseComposition)}
        assert "user_id" in field_names
        assert "intelligence_streams" in field_names
        assert "metadata" in field_names
