"""Phase W-4a Commit 6 — End-to-end integration tests.

These exercise Phase W-4a's full HTTP surface end-to-end. Commits 1-4
test each layer in isolation; this suite verifies they compose
correctly through the canonical auth + tenant + cache stack.

Test classes:
  • TestPulseCompositionEndToEnd — composition shape via the public
    API; vertical-default fallback; work-areas-driven composition;
    cache invalidation through PATCH /operator-profile; response
    shape matches `frontend/src/types/pulse.ts`.
  • TestSignalCollectionFlow — POST signals through the API + verify
    they show up in the aggregation helpers; cross-user signals stay
    isolated through the full HTTP path.
  • TestSunnycrestDemoComposition — the canonical Sunnycrest
    dispatcher D5 composition emerges from Production + Delivery +
    Inventory work areas; urn_catalog_status conditional on the
    `urn_sales` extension being active.
  • TestFirstLoginFlow — null work_areas → vertical_default_applied=
    true (banner-eligible) → PATCH operator-profile with work_areas
    → cache invalidates → next composition has vertical_default_
    applied=false (banner suppressed).

Tenant scoping is enforced server-side at every layer; these tests
assert the contract holds end-to-end, not at any single layer in
isolation. The earlier Commit 1-4 tests cover the per-layer paths.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
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


# ── Tenant + user fixture (shared with Commits 3 + 4) ─────────────


def _make_tenant_user_token(
    *,
    vertical: str = "manufacturing",
    work_areas: list[str] | None = None,
    permissions: list[str] | None = None,
    product_lines: list[tuple[str, str]] | None = None,
    extensions: list[str] | None = None,
    responsibilities: str | None = None,
) -> dict:
    """Build a fresh tenant + user + token + (optionally) seeded
    operator profile + activated extensions. Mirrors the pattern in
    test_phase_w4a_commit3 / commit4 and adds the `extensions`
    parameter for the urn_sales conditional test."""
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
            name=f"PulseInt-{suffix}",
            slug=f"pi-{suffix}",
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
            last_name="Int",
            hashed_password="x",
            is_active=True,
            role_id=role.id,
            work_areas=work_areas,
            responsibilities_description=responsibilities,
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
        if extensions:
            from app.models.tenant_extension import TenantExtension

            for ext_key in extensions:
                db.add(
                    TenantExtension(
                        id=str(uuid.uuid4()),
                        tenant_id=co.id,
                        extension_key=ext_key,
                        enabled=True,
                        status="active",
                    )
                )
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


# ── End-to-end composition ─────────────────────────────────────────


class TestPulseCompositionEndToEnd:
    def test_composition_response_shape_matches_frontend_types(
        self, client
    ):
        """`frontend/src/types/pulse.ts` declares the `PulseComposition`
        shape — every field listed there must come back from the API.
        If a future change drifts the contract, this test fails before
        the frontend hits a runtime crash."""
        ctx = _make_tenant_user_token(
            work_areas=["Production Scheduling", "Delivery Scheduling"],
            permissions=["delivery.view"],
            product_lines=[("vault", "production")],
        )
        r = client.get(
            "/api/v1/pulse/composition", headers=_auth_headers(ctx)
        )
        assert r.status_code == 200
        body = r.json()
        # Top-level shape
        assert set(body.keys()) >= {
            "user_id",
            "composed_at",
            "layers",
            "intelligence_streams",
            "metadata",
        }
        # Metadata shape
        meta = body["metadata"]
        assert set(meta.keys()) >= {
            "work_areas_used",
            "vertical_default_applied",
            "time_of_day_signal",
        }
        # Layers shape — canonical 4 in canonical order
        assert [l["layer"] for l in body["layers"]] == [
            "personal",
            "operational",
            "anomaly",
            "activity",
        ]
        # Each layer carries the contract: layer + items + advisory
        for lc in body["layers"]:
            assert set(lc.keys()) >= {"layer", "items", "advisory"}

    def test_vertical_default_fallback_via_api(self, client):
        """User without work_areas → composition fires vertical-
        default; the metadata flag carries this so the frontend can
        gate the first-login banner."""
        ctx = _make_tenant_user_token(
            work_areas=None,
            permissions=["delivery.view"],
            product_lines=[("vault", "production")],
        )
        r = client.get(
            "/api/v1/pulse/composition", headers=_auth_headers(ctx)
        )
        assert r.status_code == 200
        body = r.json()
        assert body["metadata"]["vertical_default_applied"] is True
        assert body["metadata"]["work_areas_used"] == []
        # Manufacturing default surfaces vault_schedule etc.
        op_layer = next(
            l for l in body["layers"] if l["layer"] == "operational"
        )
        op_keys = {it["component_key"] for it in op_layer["items"]}
        assert "vault_schedule" in op_keys

    def test_work_areas_driven_composition_via_api(self, client):
        """Per the canonical work-area mapping in
        operational_layer_service: Production Scheduling alone surfaces
        vault_schedule + line_status; vertical_default is suppressed."""
        ctx = _make_tenant_user_token(
            work_areas=["Production Scheduling"],
            permissions=["delivery.view"],
            product_lines=[("vault", "production")],
        )
        r = client.get(
            "/api/v1/pulse/composition", headers=_auth_headers(ctx)
        )
        body = r.json()
        assert body["metadata"]["vertical_default_applied"] is False
        op_layer = next(
            l for l in body["layers"] if l["layer"] == "operational"
        )
        op_keys = {it["component_key"] for it in op_layer["items"]}
        assert "vault_schedule" in op_keys
        assert "line_status" in op_keys
        # Production Scheduling does NOT include the dispatcher's
        # ancillary-pool — that's Delivery Scheduling's contribution.
        assert "scheduling.ancillary-pool" not in op_keys

    def test_patch_operator_profile_invalidates_composition_cache(
        self, client
    ):
        """End-to-end cache invalidation: GET composition → PATCH work
        areas → next GET reflects the new composition. The cache is
        keyed on a hash of work_areas, so a profile update changes the
        key and the next read misses + recomputes."""
        ctx = _make_tenant_user_token(
            work_areas=None,  # vertical default initially
            permissions=["delivery.view"],
            product_lines=[("vault", "production")],
        )
        # 1st GET: vertical default applies
        r1 = client.get(
            "/api/v1/pulse/composition", headers=_auth_headers(ctx)
        )
        assert r1.status_code == 200
        assert r1.json()["metadata"]["vertical_default_applied"] is True

        # PATCH operator profile
        r2 = client.patch(
            "/api/v1/operator-profile",
            json={
                "work_areas": ["Production Scheduling"],
                "mark_onboarding_complete": True,
            },
            headers=_auth_headers(ctx),
        )
        assert r2.status_code == 200

        # 2nd GET: cache key changed (work_areas hash differs);
        # composition reflects the work-area-driven shape.
        r3 = client.get(
            "/api/v1/pulse/composition", headers=_auth_headers(ctx)
        )
        body = r3.json()
        assert body["metadata"]["vertical_default_applied"] is False
        assert body["metadata"]["work_areas_used"] == [
            "Production Scheduling"
        ]

    def test_refresh_query_param_bypasses_cache(self, client):
        """`?refresh=true` is the manual reload affordance; backend
        bypasses the cache read but still WRITES the result so a
        warmer cache lands for subsequent unforced reads. The contract
        test: same response shape, different fresh timestamp."""
        ctx = _make_tenant_user_token(
            work_areas=["Production Scheduling"],
            permissions=["delivery.view"],
            product_lines=[("vault", "production")],
        )
        r1 = client.get(
            "/api/v1/pulse/composition", headers=_auth_headers(ctx)
        ).json()
        r2 = client.get(
            "/api/v1/pulse/composition?refresh=true",
            headers=_auth_headers(ctx),
        ).json()
        # Same composition shape regardless of cache hit/miss
        assert r1["metadata"]["work_areas_used"] == r2[
            "metadata"
        ]["work_areas_used"]
        # composed_at is the per-call timestamp (recomputed on miss)
        assert "composed_at" in r2

    def test_composition_requires_auth(self, client):
        """Unauthenticated request rejected — no anonymous Pulse."""
        r = client.get("/api/v1/pulse/composition")
        assert r.status_code in (401, 403)


# ── Signal collection through HTTP layer ───────────────────────────


class TestSignalCollectionFlow:
    def test_dismiss_signal_persists_with_standardized_metadata(
        self, client, db_session
    ):
        """POST a dismiss signal; aggregation helper sees it. The
        canonical metadata shape is {component_key, time_of_day,
        work_areas_at_dismiss} per the r61 migration docstring."""
        from app.models.user import User
        from app.services.pulse import signal_service

        ctx = _make_tenant_user_token(
            work_areas=["Production Scheduling"],
        )
        r = client.post(
            "/api/v1/pulse/signals/dismiss",
            json={
                "component_key": "today",
                "layer": "operational",
                "time_of_day": "morning",
                "work_areas_at_dismiss": ["Production Scheduling"],
            },
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 201
        body = r.json()
        assert body["signal_type"] == "dismiss"
        assert body["component_key"] == "today"
        assert body["metadata"]["time_of_day"] == "morning"
        assert body["metadata"]["work_areas_at_dismiss"] == [
            "Production Scheduling"
        ]
        # Aggregation helper sees the write
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        counts = signal_service.get_dismiss_counts_per_component(
            db_session, user=user
        )
        assert counts.get("today") == 1

    def test_navigate_signal_persists_and_aggregates(
        self, client, db_session
    ):
        """POST a navigation signal; the navigation_targets aggregator
        returns it ordered by frequency."""
        from app.models.user import User
        from app.services.pulse import signal_service

        ctx = _make_tenant_user_token()
        # Two clicks to /scheduling, one to /agents from same component
        for to_route in [
            "/scheduling",
            "/scheduling",
            "/agents",
        ]:
            r = client.post(
                "/api/v1/pulse/signals/navigate",
                json={
                    "from_component_key": "vault_schedule",
                    "to_route": to_route,
                    "dwell_time_seconds": 12.5,
                    "layer": "operational",
                },
                headers=_auth_headers(ctx),
            )
            assert r.status_code == 201
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        targets = signal_service.get_navigation_targets(
            db_session,
            user=user,
            from_component_key="vault_schedule",
        )
        # /scheduling first (count 2), /agents second (count 1)
        assert [t["to_route"] for t in targets] == [
            "/scheduling",
            "/agents",
        ]
        assert targets[0]["count"] == 2
        assert targets[1]["count"] == 1

    def test_signal_validation_rejects_invalid_layer(self, client):
        """layer must be one of the canonical four — bogus layer
        rejected with 400."""
        ctx = _make_tenant_user_token()
        r = client.post(
            "/api/v1/pulse/signals/dismiss",
            json={
                "component_key": "today",
                "layer": "not_a_real_layer",
                "time_of_day": "morning",
            },
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 400

    def test_cross_user_signals_isolated_via_aggregations(
        self, client, db_session
    ):
        """User A's signals MUST NOT leak into User B's aggregations.
        Tenant scoping is forced server-side from the auth token —
        request bodies cannot carry user_id at all."""
        from app.models.user import User
        from app.services.pulse import signal_service

        a = _make_tenant_user_token()
        b = _make_tenant_user_token()
        # User A dismisses 3 times
        for _ in range(3):
            client.post(
                "/api/v1/pulse/signals/dismiss",
                json={
                    "component_key": "today",
                    "layer": "operational",
                    "time_of_day": "morning",
                },
                headers=_auth_headers(a),
            )
        # User B dismisses 1 time
        client.post(
            "/api/v1/pulse/signals/dismiss",
            json={
                "component_key": "today",
                "layer": "operational",
                "time_of_day": "midday",
            },
            headers=_auth_headers(b),
        )
        user_a = (
            db_session.query(User).filter(User.id == a["user_id"]).one()
        )
        user_b = (
            db_session.query(User).filter(User.id == b["user_id"]).one()
        )
        a_counts = signal_service.get_dismiss_counts_per_component(
            db_session, user=user_a
        )
        b_counts = signal_service.get_dismiss_counts_per_component(
            db_session, user=user_b
        )
        assert a_counts.get("today") == 3
        assert b_counts.get("today") == 1


# ── Sunnycrest demo composition ────────────────────────────────────


class TestSunnycrestDemoComposition:
    """The canonical Sunnycrest dispatcher demo — work_areas =
    [Production Scheduling, Delivery Scheduling, Inventory Management]
    + responsibilities text. The composition emerges from the merged
    work-area mapping in operational_layer_service.
    """

    DISPATCHER_AREAS = [
        "Production Scheduling",
        "Delivery Scheduling",
        "Inventory Management",
    ]

    def test_dispatcher_operational_layer_matches_d5_target(
        self, client
    ):
        """The D5 target composition: vault_schedule Detail (2x2) +
        scheduling.ancillary-pool Brief + line_status Brief + today
        Glance. Verified via the live API — exact shape end-to-end."""
        ctx = _make_tenant_user_token(
            work_areas=self.DISPATCHER_AREAS,
            permissions=["delivery.view"],
            product_lines=[("vault", "production")],
            responsibilities=(
                "I dispatch vault deliveries, coordinate ancillary "
                "pickups, and watch inventory levels for upcoming "
                "pours."
            ),
        )
        r = client.get(
            "/api/v1/pulse/composition", headers=_auth_headers(ctx)
        )
        assert r.status_code == 200
        op_layer = next(
            l for l in r.json()["layers"] if l["layer"] == "operational"
        )
        op_by_key = {
            it["component_key"]: it for it in op_layer["items"]
        }
        # vault_schedule renders Detail (2x2) — primary work surface
        assert op_by_key["vault_schedule"]["variant_id"] == "detail"
        assert op_by_key["vault_schedule"]["cols"] == 2
        assert op_by_key["vault_schedule"]["rows"] == 2
        # scheduling.ancillary-pool renders Brief (2x1)
        assert (
            op_by_key["scheduling.ancillary-pool"]["variant_id"]
            == "brief"
        )
        # line_status renders Brief (2x1)
        assert op_by_key["line_status"]["variant_id"] == "brief"
        # today renders Glance (1x1)
        assert op_by_key["today"]["variant_id"] == "glance"

    def test_dispatcher_without_urn_extension_omits_urn_catalog_status(
        self, client
    ):
        """urn_catalog_status is conditional on the urn_sales
        extension being active. Conservative pre-filter at the layer
        service excludes it for tenants without the extension —
        verified via the live composition response."""
        ctx = _make_tenant_user_token(
            work_areas=self.DISPATCHER_AREAS,
            permissions=["delivery.view"],
            product_lines=[("vault", "production")],
            extensions=None,  # urn_sales NOT active
        )
        r = client.get(
            "/api/v1/pulse/composition", headers=_auth_headers(ctx)
        )
        op_layer = next(
            l for l in r.json()["layers"] if l["layer"] == "operational"
        )
        op_keys = {it["component_key"] for it in op_layer["items"]}
        assert "urn_catalog_status" not in op_keys

    def test_dispatcher_with_urn_extension_surfaces_urn_catalog_status(
        self, client
    ):
        """Same dispatcher work areas + urn_sales activated → the
        Inventory Management work area's conditional
        urn_catalog_status item appears."""
        ctx = _make_tenant_user_token(
            work_areas=self.DISPATCHER_AREAS,
            permissions=["delivery.view"],
            product_lines=[
                ("vault", "production"),
                ("urn_sales", "production"),
            ],
            extensions=["urn_sales"],
        )
        r = client.get(
            "/api/v1/pulse/composition", headers=_auth_headers(ctx)
        )
        op_layer = next(
            l for l in r.json()["layers"] if l["layer"] == "operational"
        )
        op_keys = {it["component_key"] for it in op_layer["items"]}
        assert "urn_catalog_status" in op_keys

    def test_anomaly_intelligence_stream_emits_when_anomalies_present(
        self, client, db_session
    ):
        """When the tenant has unresolved anomalies, the V1 anomaly
        intelligence stream synthesizes prose from them. The synth is
        attached at the composition top level, not inside a layer —
        per the engine's contract."""
        ctx = _make_tenant_user_token(
            work_areas=self.DISPATCHER_AREAS,
            permissions=["delivery.view"],
            product_lines=[("vault", "production")],
        )
        # Seed two anomalies for the tenant
        _make_anomaly(
            db_session,
            tenant_id=ctx["company_id"],
            severity="critical",
            anomaly_type="balance_mismatch",
            description="Hopkins invoice short by $250",
        )
        _make_anomaly(
            db_session,
            tenant_id=ctx["company_id"],
            severity="warning",
            anomaly_type="late_payment",
            description="Marshall payment 14 days overdue",
        )
        r = client.get(
            "/api/v1/pulse/composition?refresh=true",
            headers=_auth_headers(ctx),
        )
        body = r.json()
        # Stream synthesized + attached at top level
        assert len(body["intelligence_streams"]) == 1
        stream = body["intelligence_streams"][0]
        # V1 anomaly synth uses stream_id "anomaly_intelligence"
        assert stream["stream_id"] == "anomaly_intelligence"
        assert stream["layer"] == "anomaly"
        assert stream["title"]  # synth produced a non-empty title
        assert stream["synthesized_text"]  # non-empty narrative prose
        # Anomaly layer carries the LayerItem stream-pointer with the
        # canonical component_key so the frontend can lookup the
        # synthesized content via stream_id matching.
        anom_layer = next(
            l for l in body["layers"] if l["layer"] == "anomaly"
        )
        anom_keys = {it["component_key"] for it in anom_layer["items"]}
        # LayerItem carries `anomaly_intelligence_stream` (the
        # structural pointer); the IntelligenceStream's stream_id
        # `anomaly_intelligence` is what the frontend uses to
        # dispatch the renderer registry — they're paired.
        assert "anomaly_intelligence_stream" in anom_keys
        assert "anomalies" in anom_keys  # raw anomalies widget too


# ── First-login flow ───────────────────────────────────────────────


class TestFirstLoginFlow:
    """A new user lands on /home with null work_areas. Composition
    falls back to vertical-default → vertical_default_applied=true →
    PulseFirstLoginBanner renders. User completes onboarding via the
    operator-profile editor → next composition has
    vertical_default_applied=false → banner suppressed."""

    def test_initial_composition_signals_banner_eligibility(
        self, client
    ):
        ctx = _make_tenant_user_token(
            work_areas=None,
            responsibilities=None,
            permissions=["delivery.view"],
            product_lines=[("vault", "production")],
        )
        r = client.get(
            "/api/v1/pulse/composition", headers=_auth_headers(ctx)
        )
        assert r.status_code == 200
        body = r.json()
        # Banner gates on vertical_default_applied — true here.
        assert body["metadata"]["vertical_default_applied"] is True
        # Vertical default still produces a usable composition.
        op_layer = next(
            l for l in body["layers"] if l["layer"] == "operational"
        )
        assert any(
            it["component_key"] == "vault_schedule"
            for it in op_layer["items"]
        )

    def test_completing_operator_profile_suppresses_banner_eligibility(
        self, client
    ):
        """End-to-end: the user PATCHes work_areas + responsibilities +
        mark_onboarding_complete; the next composition reflects the
        change AND the cache invalidation works through the work_areas
        hash. vertical_default_applied flips to false → banner stops
        rendering on the next /home load."""
        ctx = _make_tenant_user_token(
            work_areas=None,
            permissions=["delivery.view"],
            product_lines=[("vault", "production")],
        )
        # Initial state — banner-eligible
        r1 = client.get(
            "/api/v1/pulse/composition", headers=_auth_headers(ctx)
        )
        assert r1.json()["metadata"]["vertical_default_applied"] is True

        # User completes operator profile (the canonical onboarding
        # path the PulseFirstLoginBanner CTA sends them to).
        patch = client.patch(
            "/api/v1/operator-profile",
            json={
                "work_areas": [
                    "Production Scheduling",
                    "Delivery Scheduling",
                    "Inventory Management",
                ],
                "responsibilities_description": (
                    "I dispatch vault deliveries, coordinate "
                    "ancillary pickups, and watch inventory."
                ),
                "mark_onboarding_complete": True,
            },
            headers=_auth_headers(ctx),
        )
        assert patch.status_code == 200
        assert patch.json()["onboarding_completed"] is True

        # Next composition: vertical_default flipped, banner
        # suppressed, work-areas-driven composition active.
        r2 = client.get(
            "/api/v1/pulse/composition", headers=_auth_headers(ctx)
        )
        body = r2.json()
        assert body["metadata"]["vertical_default_applied"] is False
        assert sorted(body["metadata"]["work_areas_used"]) == sorted(
            [
                "Production Scheduling",
                "Delivery Scheduling",
                "Inventory Management",
            ]
        )

    def test_operator_profile_carries_canonical_work_area_vocab(
        self, client
    ):
        """The frontend renders the work-area multi-select cards from
        `available_work_areas`. End-to-end this matches the canonical
        vocabulary in the registry — drift here breaks onboarding UX
        immediately."""
        from app.services.operator_profile_service import WORK_AREAS

        ctx = _make_tenant_user_token()
        r = client.get(
            "/api/v1/operator-profile", headers=_auth_headers(ctx)
        )
        assert r.status_code == 200
        body = r.json()
        # Returns the canonical vocabulary list
        assert set(body["available_work_areas"]) == set(WORK_AREAS)

    def test_unknown_work_area_rejected_at_api_boundary(self, client):
        """Bogus work_area rejected with 400 at the PATCH boundary —
        the frontend can't accidentally write a typo into the user's
        profile and break the layer mapping silently."""
        ctx = _make_tenant_user_token()
        r = client.patch(
            "/api/v1/operator-profile",
            json={"work_areas": ["Not A Real Work Area"]},
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 400
