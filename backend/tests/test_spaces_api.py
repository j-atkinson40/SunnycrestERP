"""Integration tests — Spaces API + command bar integration.

Scope: HTTP-level. Covers the 10 endpoints + tenant/user isolation
+ space-scoped command bar ranking + space-switch synthesis.
"""

from __future__ import annotations

import uuid

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _make_ctx(*, role_slug: str = "admin", vertical: str = "manufacturing"):
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
            name=f"SP-{suffix}",
            slug=f"sp-{suffix}",
            is_active=True,
            vertical=vertical,
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name=role_slug.title(),
            slug=role_slug,
            is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@sp.co",
            first_name="SP",
            last_name="User",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,  # bypass permission gates in command-bar tests
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "user_id": user.id,
            "company_id": co.id,
            "token": token,
            "slug": co.slug,
        }
    finally:
        db.close()


@pytest.fixture
def ctx():
    return _make_ctx(role_slug="director", vertical="funeral_home")


@pytest.fixture
def ctx_b():
    return _make_ctx(role_slug="admin", vertical="manufacturing")


@pytest.fixture
def auth(ctx):
    return {
        "Authorization": f"Bearer {ctx['token']}",
        "X-Company-Slug": ctx["slug"],
    }


@pytest.fixture
def auth_b(ctx_b):
    return {
        "Authorization": f"Bearer {ctx_b['token']}",
        "X-Company-Slug": ctx_b["slug"],
    }


# ── API endpoints ────────────────────────────────────────────────────


class TestSpacesAPI:
    def test_list_empty_then_create(self, client, auth):
        r = client.get("/api/v1/spaces", headers=auth)
        assert r.status_code == 200
        body = r.json()
        assert body["spaces"] == []
        assert body["active_space_id"] is None

        r = client.post(
            "/api/v1/spaces",
            json={"name": "My Space", "accent": "warm", "icon": "home"},
            headers=auth,
        )
        assert r.status_code == 201
        sp = r.json()
        assert sp["name"] == "My Space"
        assert sp["is_default"] is True  # first space auto-default
        assert sp["pins"] == []

    def test_get_single_space(self, client, auth):
        r = client.post(
            "/api/v1/spaces", json={"name": "Thing"}, headers=auth
        )
        sid = r.json()["space_id"]
        r2 = client.get(f"/api/v1/spaces/{sid}", headers=auth)
        assert r2.status_code == 200
        assert r2.json()["space_id"] == sid

    def test_get_space_cross_user_404(self, client, auth, auth_b):
        r = client.post("/api/v1/spaces", json={"name": "Mine"}, headers=auth)
        sid = r.json()["space_id"]
        r2 = client.get(f"/api/v1/spaces/{sid}", headers=auth_b)
        assert r2.status_code == 404

    def test_update_space(self, client, auth):
        sp = client.post(
            "/api/v1/spaces", json={"name": "A"}, headers=auth
        ).json()
        r = client.patch(
            f"/api/v1/spaces/{sp['space_id']}",
            json={"name": "B", "accent": "crisp"},
            headers=auth,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "B"
        assert r.json()["accent"] == "crisp"

    def test_delete_and_404_on_second_delete(self, client, auth):
        a = client.post(
            "/api/v1/spaces", json={"name": "A"}, headers=auth
        ).json()
        client.post(
            "/api/v1/spaces", json={"name": "B"}, headers=auth
        )  # keep a default around
        r = client.delete(f"/api/v1/spaces/{a['space_id']}", headers=auth)
        assert r.status_code == 200
        assert r.json()["status"] == "deleted"

        r2 = client.delete(f"/api/v1/spaces/{a['space_id']}", headers=auth)
        assert r2.status_code == 404

    def test_activate_sets_active_space_id(self, client, auth):
        a = client.post(
            "/api/v1/spaces", json={"name": "A"}, headers=auth
        ).json()
        b = client.post(
            "/api/v1/spaces", json={"name": "B"}, headers=auth
        ).json()
        r = client.post(
            f"/api/v1/spaces/{b['space_id']}/activate", headers=auth
        )
        assert r.status_code == 200
        listing = client.get("/api/v1/spaces", headers=auth).json()
        assert listing["active_space_id"] == b["space_id"]

    def test_reorder_spaces(self, client, auth):
        a = client.post("/api/v1/spaces", json={"name": "A"}, headers=auth).json()
        b = client.post("/api/v1/spaces", json={"name": "B"}, headers=auth).json()
        c = client.post("/api/v1/spaces", json={"name": "C"}, headers=auth).json()
        r = client.post(
            "/api/v1/spaces/reorder",
            json={"space_ids": [c["space_id"], a["space_id"], b["space_id"]]},
            headers=auth,
        )
        assert r.status_code == 200
        ids = [s["space_id"] for s in r.json()["spaces"]]
        assert ids == [c["space_id"], a["space_id"], b["space_id"]]

    def test_space_cap_enforced_at_api(self, client, auth):
        # Phase 8e — cap bumped 5 → 7. Test renamed from
        # `test_five_space_cap_enforced_at_api`. The `ctx` fixture
        # user has a `director` role on `funeral_home`, which seeds
        # 3 spaces (Arrangement + Administrative + Ownership) on
        # register. So we can only create 4 more before hitting the
        # 7-space cap.
        from app.services.spaces.types import MAX_SPACES_PER_USER

        # Find out how many already exist (seeded on creation).
        existing = client.get("/api/v1/spaces", headers=auth).json()
        start = len(existing["spaces"])
        # Create up to cap.
        for i in range(MAX_SPACES_PER_USER - start):
            client.post(
                "/api/v1/spaces", json={"name": f"S{i}"}, headers=auth
            )
        r = client.post(
            "/api/v1/spaces", json={"name": "Over"}, headers=auth
        )
        assert r.status_code == 400
        assert f"up to {MAX_SPACES_PER_USER}" in r.json()["detail"]

    def test_add_nav_pin(self, client, auth):
        sp = client.post(
            "/api/v1/spaces", json={"name": "X"}, headers=auth
        ).json()
        r = client.post(
            f"/api/v1/spaces/{sp['space_id']}/pins",
            json={"pin_type": "nav_item", "target_id": "/cases"},
            headers=auth,
        )
        assert r.status_code == 201
        pin = r.json()
        assert pin["label"] == "Active Cases"
        assert pin["href"] == "/cases"
        assert pin["unavailable"] is False

    def test_add_pin_idempotent(self, client, auth):
        sp = client.post(
            "/api/v1/spaces", json={"name": "X"}, headers=auth
        ).json()
        r1 = client.post(
            f"/api/v1/spaces/{sp['space_id']}/pins",
            json={"pin_type": "nav_item", "target_id": "/financials"},
            headers=auth,
        )
        r2 = client.post(
            f"/api/v1/spaces/{sp['space_id']}/pins",
            json={"pin_type": "nav_item", "target_id": "/financials"},
            headers=auth,
        )
        assert r1.json()["pin_id"] == r2.json()["pin_id"]

    def test_remove_pin(self, client, auth):
        sp = client.post(
            "/api/v1/spaces", json={"name": "X"}, headers=auth
        ).json()
        pin = client.post(
            f"/api/v1/spaces/{sp['space_id']}/pins",
            json={"pin_type": "nav_item", "target_id": "/cases"},
            headers=auth,
        ).json()
        r = client.delete(
            f"/api/v1/spaces/{sp['space_id']}/pins/{pin['pin_id']}",
            headers=auth,
        )
        assert r.status_code == 200

    def test_reorder_pins_via_api(self, client, auth):
        sp = client.post(
            "/api/v1/spaces", json={"name": "X"}, headers=auth
        ).json()
        p1 = client.post(
            f"/api/v1/spaces/{sp['space_id']}/pins",
            json={"pin_type": "nav_item", "target_id": "/cases"},
            headers=auth,
        ).json()
        p2 = client.post(
            f"/api/v1/spaces/{sp['space_id']}/pins",
            json={"pin_type": "nav_item", "target_id": "/financials"},
            headers=auth,
        ).json()
        r = client.post(
            f"/api/v1/spaces/{sp['space_id']}/pins/reorder",
            json={"pin_ids": [p2["pin_id"], p1["pin_id"]]},
            headers=auth,
        )
        assert r.status_code == 200
        pins = r.json()["pins"]
        assert [p["pin_id"] for p in pins] == [p2["pin_id"], p1["pin_id"]]

    def test_auth_required(self, client):
        # FastAPI's HTTPBearer returns 403 (Forbidden) rather than
        # 401 (Unauthorized) for a missing auth header — this matches
        # the framework's default behavior. Either counts as "auth
        # is enforced."
        r = client.get("/api/v1/spaces")
        assert r.status_code in (401, 403)


# ── Command bar integration ─────────────────────────────────────────


class TestCommandBarIntegration:
    def _setup_with_space(self, client, auth):
        sp = client.post(
            "/api/v1/spaces",
            json={"name": "Arrangement", "accent": "warm", "icon": "calendar-heart"},
            headers=auth,
        ).json()
        client.post(
            f"/api/v1/spaces/{sp['space_id']}/activate", headers=auth
        )
        return sp

    def test_space_switch_result_on_name_match(self, client, auth):
        # Create TWO spaces so there's a non-active space to switch to.
        self._setup_with_space(client, auth)
        other = client.post(
            "/api/v1/spaces",
            json={"name": "Ownership", "accent": "neutral"},
            headers=auth,
        ).json()

        r = client.post(
            "/api/v1/command-bar/query",
            json={"query": "ownership"},
            headers=auth,
        )
        assert r.status_code == 200
        results = r.json()["results"]
        switch_hits = [x for x in results if x["id"].startswith("space_switch:")]
        assert len(switch_hits) == 1
        assert switch_hits[0]["primary_label"] == "Switch to Ownership"
        assert switch_hits[0]["url"] == f"/?__switch_space={other['space_id']}"

    def test_current_active_space_excluded_from_switch(self, client, auth):
        sp = self._setup_with_space(client, auth)
        # Query the ACTIVE space's name — it should NOT appear as a
        # switch target.
        r = client.post(
            "/api/v1/command-bar/query",
            json={
                "query": "arrangement",
                "context": {"active_space_id": sp["space_id"]},
            },
            headers=auth,
        )
        results = r.json()["results"]
        switch_hits = [x for x in results if x["id"].startswith("space_switch:")]
        assert len(switch_hits) == 0

    def test_pinned_nav_item_gets_score_boost(self, client, auth):
        # Create a space, activate it, pin /financials. Query
        # "financials" — the registry-matched navigate result for
        # /financials should be boosted above the typical score for
        # a plain match. We verify via score (boost yields a
        # non-trivial delta) rather than asserting ordering, since
        # the test env may have multiple matching results.
        sp = self._setup_with_space(client, auth)
        client.post(
            f"/api/v1/spaces/{sp['space_id']}/pins",
            json={"pin_type": "nav_item", "target_id": "/financials"},
            headers=auth,
        )

        # Baseline query — no active_space_id.
        baseline = client.post(
            "/api/v1/command-bar/query",
            json={"query": "financials"},
            headers=auth,
        ).json()
        baseline_scores = {
            r["id"]: r["score"]
            for r in baseline["results"]
            if r["url"] == "/financials"
        }

        # Boosted query — active_space_id set to the one with the pin.
        boosted = client.post(
            "/api/v1/command-bar/query",
            json={
                "query": "financials",
                "context": {"active_space_id": sp["space_id"]},
            },
            headers=auth,
        ).json()
        boosted_scores = {
            r["id"]: r["score"]
            for r in boosted["results"]
            if r["url"] == "/financials"
        }

        # Some result matching /financials should have a strictly
        # higher score when the space boost kicks in.
        assert baseline_scores, "no /financials results in baseline"
        assert boosted_scores, "no /financials results in boosted"
        matching_ids = set(baseline_scores) & set(boosted_scores)
        assert matching_ids, "no overlap between baseline and boosted results"
        any_boosted = any(
            boosted_scores[mid] > baseline_scores[mid] for mid in matching_ids
        )
        assert any_boosted, (
            f"expected at least one boosted hit, got base={baseline_scores} "
            f"boosted={boosted_scores}"
        )

    def test_active_space_id_accepted_in_context_schema(self, client, auth):
        # Simple smoke — the request validator must accept the new
        # field. Empty/unknown space id should still get 200 (the
        # ranking boost is a no-op with no pins).
        r = client.post(
            "/api/v1/command-bar/query",
            json={
                "query": "dashboard",
                "context": {"active_space_id": "sp_unknown"},
            },
            headers=auth,
        )
        assert r.status_code == 200

    def test_prefix_match_synthesizes_switch(self, client, auth):
        self._setup_with_space(client, auth)
        client.post(
            "/api/v1/spaces",
            json={"name": "Ownership", "accent": "neutral"},
            headers=auth,
        )
        r = client.post(
            "/api/v1/command-bar/query",
            json={"query": "owner"},  # prefix of "Ownership"
            headers=auth,
        )
        assert r.status_code == 200
        results = r.json()["results"]
        hits = [x for x in results if x["id"].startswith("space_switch:")]
        assert any("Ownership" in h["primary_label"] for h in hits)

    def test_single_char_no_synthesis(self, client, auth):
        """Prefix rule requires >=2 chars — one-char queries don't
        spam the result list with every space."""
        self._setup_with_space(client, auth)
        r = client.post(
            "/api/v1/command-bar/query",
            json={"query": "a"},
            headers=auth,
        )
        results = r.json()["results"]
        hits = [x for x in results if x["id"].startswith("space_switch:")]
        # Not exact ("arrangement" != "a"), len<2 so no prefix hit.
        assert len(hits) == 0
