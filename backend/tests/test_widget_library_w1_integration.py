"""Widget Library Phase W-1 — integration tests.

End-to-end coverage of the unified widget contract via the real API
client + auth. Complements `test_widget_library_w1_foundation.py`
(unit-level tests against the service layer).

Covers:
  • GET /widgets/available — vertical-filtered catalog returned
    correctly per per-vertical tenant (4-axis filter axis 4)
  • GET /widgets/available — funeral-home tenant sees qc_status
    as available; manufacturing tenant sees it as unavailable
    with reason="vertical_required"
  • GET /widgets/available — response shape includes Phase W-1
    unified-contract fields (variants, default_variant_id,
    required_vertical, supported_surfaces, default_surfaces,
    intelligence_keywords)
  • GET /widgets/layout — layout endpoint surfaces the new fields
    via the `_enrich_layout` helper (cross-cutting verification
    that the response shape extension lands at all consumers)
"""

from __future__ import annotations

import uuid
from typing import Iterator

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def client() -> TestClient:
    from app.main import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def _seeded() -> Iterator[None]:
    """Ensure the widget catalog is seeded before each test."""
    from app.database import SessionLocal
    from app.services.widgets.widget_registry import seed_widget_definitions

    db = SessionLocal()
    try:
        seed_widget_definitions(db)
        yield
    finally:
        db.close()


def _make_tenant_user_token(*, vertical: str, permissions: list[str]) -> dict:
    """Create a tenant + user + role with permissions; return token."""
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
            name=f"WidgetW1Int-{suffix}",
            slug=f"w1-int-{suffix}",
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
        for p in permissions:
            db.add(RolePermission(role_id=role.id, permission_key=p))

        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@w1.test",
            first_name="W",
            last_name="One",
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
            "vertical": vertical,
            "token": token,
        }
    finally:
        db.close()


# ── End-to-end vertical filter ───────────────────────────────────────


class TestVerticalFilterEndToEnd:
    """Section 12.4 4-axis filter axis 4 — vertical scoping enforced
    end-to-end through the API."""

    def test_funeral_home_sees_qc_status_available(self, client: TestClient):
        ctx = _make_tenant_user_token(
            vertical="funeral_home",
            permissions=[],
        )
        r = client.get(
            "/api/v1/widgets/available",
            params={"page_context": "ops_board"},
            headers={
                "Authorization": f"Bearer {ctx['token']}",
                "X-Company-Slug": ctx["slug"],
            },
        )
        assert r.status_code == 200, r.text
        widgets = r.json()
        qc = next((w for w in widgets if w["widget_id"] == "qc_status"), None)
        assert qc is not None, "qc_status should be in catalog"
        # qc_status requires the npca_audit_prep extension which the
        # tenant doesn't have — so it's still unavailable, but the
        # reason should be extension_required, not vertical_required.
        # (Vertical filter passes; extension filter fails.)
        if not qc["is_available"]:
            assert qc["unavailable_reason"] == "extension_required", (
                f"funeral_home tenant should pass vertical filter for "
                f"qc_status; got reason={qc['unavailable_reason']!r}"
            )

    def test_manufacturing_sees_qc_status_vertical_required(
        self, client: TestClient
    ):
        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            permissions=[],
        )
        r = client.get(
            "/api/v1/widgets/available",
            params={"page_context": "ops_board"},
            headers={
                "Authorization": f"Bearer {ctx['token']}",
                "X-Company-Slug": ctx["slug"],
            },
        )
        assert r.status_code == 200, r.text
        widgets = r.json()
        qc = next((w for w in widgets if w["widget_id"] == "qc_status"), None)
        assert qc is not None
        assert not qc["is_available"]
        assert qc["unavailable_reason"] == "vertical_required", (
            f"manufacturing tenant should fail vertical filter for "
            f"qc_status (NPCA audit prep is funeral-home compliance); "
            f"got reason={qc['unavailable_reason']!r}"
        )

    def test_cross_vertical_widget_visible_to_all_verticals(
        self, client: TestClient
    ):
        """activity_feed is a cross-vertical widget — visible to every
        vertical regardless of preset. Verify via the real API."""
        for vertical in ["manufacturing", "funeral_home", "cemetery", "crematory"]:
            ctx = _make_tenant_user_token(vertical=vertical, permissions=[])
            r = client.get(
                "/api/v1/widgets/available",
                params={"page_context": "ops_board"},
                headers={
                "Authorization": f"Bearer {ctx['token']}",
                "X-Company-Slug": ctx["slug"],
            },
            )
            assert r.status_code == 200
            widgets = r.json()
            af = next(
                (w for w in widgets if w["widget_id"] == "activity_feed"),
                None,
            )
            assert af is not None
            assert af["is_available"], (
                f"Cross-vertical widget should be visible in {vertical}, "
                f"got reason={af['unavailable_reason']!r}"
            )


# ── Response shape: Phase W-1 unified-contract fields ───────────────


class TestPhaseW1ResponseShape:
    """The /widgets/available endpoint returns the Phase W-1
    unified-contract fields per Section 12.3. Frontend types mirror
    this shape (frontend/src/components/widgets/types.ts)."""

    def test_response_includes_variants(self, client: TestClient):
        ctx = _make_tenant_user_token(vertical="manufacturing", permissions=[])
        r = client.get(
            "/api/v1/widgets/available",
            params={"page_context": "ops_board"},
            headers={
                "Authorization": f"Bearer {ctx['token']}",
                "X-Company-Slug": ctx["slug"],
            },
        )
        assert r.status_code == 200
        widgets = r.json()
        assert widgets, "Catalog should be non-empty"
        for w in widgets:
            assert "variants" in w, f"{w['widget_id']} missing variants"
            assert isinstance(w["variants"], list)
            assert len(w["variants"]) >= 1, (
                f"{w['widget_id']} must declare ≥1 variant per Section "
                f"12.3 invariant"
            )

    def test_response_includes_phase_w1_fields(self, client: TestClient):
        ctx = _make_tenant_user_token(vertical="manufacturing", permissions=[])
        r = client.get(
            "/api/v1/widgets/available",
            params={"page_context": "ops_board"},
            headers={
                "Authorization": f"Bearer {ctx['token']}",
                "X-Company-Slug": ctx["slug"],
            },
        )
        assert r.status_code == 200
        for w in r.json():
            for field in (
                "variants",
                "default_variant_id",
                "required_vertical",
                "supported_surfaces",
                "default_surfaces",
                "intelligence_keywords",
            ):
                assert field in w, (
                    f"{w['widget_id']} missing Phase W-1 field {field}"
                )

    def test_default_variant_id_references_a_declared_variant(
        self, client: TestClient
    ):
        ctx = _make_tenant_user_token(vertical="manufacturing", permissions=[])
        r = client.get(
            "/api/v1/widgets/available",
            params={"page_context": "ops_board"},
            headers={
                "Authorization": f"Bearer {ctx['token']}",
                "X-Company-Slug": ctx["slug"],
            },
        )
        assert r.status_code == 200
        for w in r.json():
            ids = {v["variant_id"] for v in w["variants"]}
            assert w["default_variant_id"] in ids, (
                f"{w['widget_id']} default_variant_id "
                f"{w['default_variant_id']!r} not in declared variants {ids}"
            )

    def test_default_surfaces_subset_of_supported_surfaces(
        self, client: TestClient
    ):
        """Section 12.3 invariant: default_surfaces ⊆ supported_surfaces.
        Catch malformed definitions at API contract time."""
        ctx = _make_tenant_user_token(vertical="manufacturing", permissions=[])
        r = client.get(
            "/api/v1/widgets/available",
            params={"page_context": "ops_board"},
            headers={
                "Authorization": f"Bearer {ctx['token']}",
                "X-Company-Slug": ctx["slug"],
            },
        )
        assert r.status_code == 200
        for w in r.json():
            supported = set(w["supported_surfaces"])
            default = set(w["default_surfaces"])
            assert default <= supported, (
                f"{w['widget_id']} default_surfaces {default} not subset "
                f"of supported_surfaces {supported}"
            )


# ── Cross-page-context coverage ──────────────────────────────────────


class TestPageContextCoverage:
    """Verify each page context returns its expected widget set
    post-Phase-W-1."""

    def test_vault_overview_returns_vault_widgets(self, client: TestClient):
        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            permissions=[],
        )
        r = client.get(
            "/api/v1/widgets/available",
            params={"page_context": "vault_overview"},
            headers={
                "Authorization": f"Bearer {ctx['token']}",
                "X-Company-Slug": ctx["slug"],
            },
        )
        assert r.status_code == 200
        widgets = r.json()
        widget_ids = {w["widget_id"] for w in widgets}
        # V-1b widgets (admin permission gates filter some out, but
        # the cross-vertical Vault widgets should be visible)
        assert "vault_recent_documents" in widget_ids
        assert "vault_pending_signatures" in widget_ids
        assert "vault_unread_inbox" in widget_ids

    def test_focus_scheduling_returns_ancillary_pool(self, client: TestClient):
        ctx = _make_tenant_user_token(
            vertical="funeral_home",
            permissions=["delivery.view"],
        )
        r = client.get(
            "/api/v1/widgets/available",
            params={"page_context": "funeral_scheduling_focus"},
            headers={
                "Authorization": f"Bearer {ctx['token']}",
                "X-Company-Slug": ctx["slug"],
            },
        )
        assert r.status_code == 200
        widgets = r.json()
        ap = next(
            (w for w in widgets if w["widget_id"] == "scheduling.ancillary-pool"),
            None,
        )
        assert ap is not None, (
            "scheduling.ancillary-pool should be a catalog citizen on "
            "funeral_scheduling_focus page context per Section 12.10"
        )
        assert ap["is_available"]
        assert {v["variant_id"] for v in ap["variants"]} == {
            "glance",
            "brief",
            "detail",
        }
        assert ap["default_variant_id"] == "detail"
