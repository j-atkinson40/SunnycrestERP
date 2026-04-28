"""Phase 8e — Spaces + default views + reapply-defaults tests.

Scope:
  - Template expansion (6 new combinations + 2 enrichments)
  - Saved-view seed dependency verification (each saved_view pin in
    a new 8e template has a matching SeedTemplate in saved_views/seed.py)
  - default_home_route field round-trip (create, patch, clear)
  - MAX_SPACES_PER_USER bump 5 → 7
  - Reapply-defaults endpoint (counts + idempotency)
  - NAV_LABEL_TABLE coverage for every new nav_item pin target

Intentionally NOT covered (driver template absence):
  - (funeral_home, "driver") and (manufacturing, "driver") are
    excluded per the Phase 8e architectural decision: drivers are
    operational roles requiring portal-shaped UX, not platform-
    shaped UX. Those roles land in Phase 8e.2 with portal infra.
    See SPACES_ARCHITECTURE.md.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.services.saved_views import seed as sv_seed
from app.services.spaces import (
    MAX_SPACES_PER_USER,
    SpaceError,
    SpaceLimitExceeded,
    create_space,
    get_space,
    get_spaces_for_user,
    seed_for_user,
    update_space,
)
from app.services.spaces import registry as reg
from app.services.spaces.types import SpaceConfig


# ── Fixtures (reused pattern from test_spaces_unit.py) ──────────────


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def _make_tenant_user(
    *,
    role_slug: str,
    vertical: str,
) -> dict:
    """Create a tenant + role + user. Returns dict with
    user_id, company_id, company_slug so API tests can build the
    subdomain-style tenant header the middleware requires."""
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"P8E-{suffix}",
            slug=f"p8e-{suffix}",
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
            email=f"u-{suffix}@p8e.co",
            first_name="P8E",
            last_name="User",
            hashed_password="x",
            is_active=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        return {
            "user_id": user.id,
            "company_id": co.id,
            "company_slug": co.slug,
        }
    finally:
        db.close()


def _fresh_user(db_session, *, role_slug: str, vertical: str):
    """Convenience for service-layer tests that need the User ORM."""
    from app.models.user import User

    ctx = _make_tenant_user(role_slug=role_slug, vertical=vertical)
    return db_session.query(User).filter(User.id == ctx["user_id"]).one()


def _api_ctx(db_session, *, role_slug: str, vertical: str):
    """For API tests: returns (user, headers) where headers carry
    the JWT + X-Company-Slug so the tenant middleware resolves."""
    from app.core.security import create_access_token
    from app.models.user import User

    ctx = _make_tenant_user(role_slug=role_slug, vertical=vertical)
    user = db_session.query(User).filter(User.id == ctx["user_id"]).one()
    token = create_access_token(
        {"sub": user.id, "company_id": ctx["company_id"]}
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Company-Slug": ctx["company_slug"],
    }
    return user, headers


# ── Template expansion — 6 new combinations seed correctly ──────────


class TestPhase8eTemplates:
    """Every new (vertical, role_slug) pair seeds the expected
    number of spaces with the expected names + the default space's
    default_home_route."""

    @pytest.mark.parametrize(
        "vertical,role,expected_names,default_name,default_route",
        [
            (
                "cemetery",
                "admin",
                ["Operations", "Administrative", "Ownership"],
                "Operations",
                "/interments",
            ),
            (
                "cemetery",
                "office",
                ["Administrative", "Operational"],
                "Administrative",
                "/financials",
            ),
            (
                "crematory",
                "admin",
                ["Operations", "Administrative"],
                "Operations",
                "/crematory/schedule",
            ),
            (
                "crematory",
                "office",
                ["Operations", "Administrative"],
                "Operations",
                "/crematory/schedule",
            ),
            (
                "funeral_home",
                "accountant",
                ["Books", "Reports"],
                "Books",
                "/financials",
            ),
            (
                "manufacturing",
                "accountant",
                ["Books", "Reports", "Compliance"],
                "Books",
                "/financials",
            ),
        ],
    )
    def test_new_template_seeds(
        self,
        db_session,
        vertical,
        role,
        expected_names,
        default_name,
        default_route,
    ):
        user = _fresh_user(db_session, role_slug=role, vertical=vertical)
        seed_for_user(db_session, user=user)
        spaces = get_spaces_for_user(db_session, user=user)
        # Admin users also get the Phase 8a Settings system space; count
        # only user-facing (non-system) spaces against expected_names.
        user_spaces = [s for s in spaces if not s.is_system]
        assert len(user_spaces) == len(expected_names)
        names = [s.name for s in user_spaces]
        for expected in expected_names:
            assert expected in names, (
                f"{vertical}/{role} missing {expected} in {names}"
            )
        # Exactly one default (system spaces never set is_default)
        defaults = [s for s in spaces if s.is_default]
        assert len(defaults) == 1
        assert defaults[0].name == default_name
        assert defaults[0].default_home_route == default_route


# ── Enrichment — mfg/production gets safety_program_triage pin ──────


class TestPhase8eEnrichments:
    def test_mfg_production_space_has_safety_program_triage_pin(
        self, db_session
    ):
        user = _fresh_user(
            db_session, role_slug="production", vertical="manufacturing"
        )
        seed_for_user(db_session, user=user)
        spaces = get_spaces_for_user(db_session, user=user)
        production = next((s for s in spaces if s.name == "Production"), None)
        assert production is not None
        triage_pins = [
            p for p in production.pins if p.pin_type == "triage_queue"
        ]
        target_ids = [p.target_id for p in triage_pins]
        assert "task_triage" in target_ids
        assert "safety_program_triage" in target_ids

    def test_mfg_safety_trainer_gets_compliance_plus_training(
        self, db_session
    ):
        user = _fresh_user(
            db_session,
            role_slug="safety_trainer",
            vertical="manufacturing",
        )
        created = seed_for_user(db_session, user=user)
        # Phase W-4a — Home system space added for all users; count
        # increments by 1 vs pre-W-4a (was 2: Compliance + Training).
        assert created == 3  # Home + Compliance + Training
        spaces = get_spaces_for_user(db_session, user=user)
        names = [s.name for s in spaces]
        assert "Home" in names  # Phase W-4a system space
        assert "Compliance" in names
        assert "Training" in names
        assert "General" not in names  # promoted away from fallback


# ── Driver template invariant — evolves across phases ──────────────
#
# Phase 8e: driver roles have NO templates (operational roles get
#   portal UX in Phase 8e.2; pre-8e.2 drivers fall to General).
# Phase 8e.2: MFG driver gets a template WITH access_mode="portal_partner".
#
# The invariant renamed from `TestNoDriverTemplates` to
# `TestDriverTemplatesUsePortalAccessMode`. The broader rule stays
# test-enforced: any role whose slug is an operational role (driver,
# yard_operator, removal_staff) MUST have access_mode starting with
# "portal_" if a template exists. Office role templates MUST use
# "platform".


class TestDriverTemplatesUsePortalAccessMode:
    """Phase 8e.2 — driver role templates must be portal-shaped.

    Operational-role templates (driver today; yard_operator and
    removal_staff when added) must declare access_mode="portal_*".
    Office role templates must declare access_mode="platform".
    This invariant prevents accidental regression where a driver
    template gets added with office-shaped UX semantics.
    """

    # Operational roles — these slugs MUST use portal access mode
    # if they have a template.
    _OPERATIONAL_ROLES: frozenset[str] = frozenset(
        ("driver", "yard_operator", "removal_staff")
    )

    def test_mfg_driver_template_exists_with_portal_access_mode(self):
        """MFG driver got a template in Phase 8e.2 with
        access_mode="portal_partner" + tenant_branding=True +
        write_mode="limited"."""
        templates = reg.SEED_TEMPLATES.get(
            ("manufacturing", "driver"), []
        )
        assert len(templates) == 1
        t = templates[0]
        assert t.access_mode == "portal_partner"
        assert t.tenant_branding is True
        assert t.write_mode == "limited"
        # 12-hour session per audit spec.
        assert t.session_timeout_minutes == 12 * 60

    def test_fh_driver_has_no_template(self, db_session):
        """Phase 8e.2 ships MFG driver only. FH driver still falls
        to FALLBACK — FH removal staff work dispatches through case
        workflows, no driver-specific portal yet. Phase W-4a — Home
        system space is added for ALL users including FH driver, so
        the count is 2 (Home + General) not 1."""
        assert ("funeral_home", "driver") not in reg.SEED_TEMPLATES
        user = _fresh_user(
            db_session, role_slug="driver", vertical="funeral_home"
        )
        seed_for_user(db_session, user=user)
        spaces = get_spaces_for_user(db_session, user=user)
        # Phase W-4a — Home + General
        assert len(spaces) == 2
        names = {s.name for s in spaces}
        assert names == {"Home", "General"}

    def test_all_operational_role_templates_use_portal_access_mode(self):
        """Invariant: if SEED_TEMPLATES has ANY entry for an
        operational role slug, that template MUST have
        access_mode starting with "portal_". No silent drift back
        to platform semantics for operational roles."""
        violations: list[tuple[str, str, str, str]] = []
        for (vertical, role_slug), templates in reg.SEED_TEMPLATES.items():
            if role_slug not in self._OPERATIONAL_ROLES:
                continue
            for t in templates:
                if not t.access_mode.startswith("portal_"):
                    violations.append(
                        (vertical, role_slug, t.name, t.access_mode)
                    )
        assert not violations, (
            "Operational-role templates must use access_mode starting "
            f"with 'portal_': {violations}"
        )

    def test_all_office_role_templates_use_platform_access_mode(self):
        """Symmetric invariant: office-role templates MUST use
        access_mode="platform". No accidental portal-shaped office
        space."""
        violations: list[tuple[str, str, str, str]] = []
        for (vertical, role_slug), templates in reg.SEED_TEMPLATES.items():
            if role_slug in self._OPERATIONAL_ROLES:
                continue
            for t in templates:
                if t.access_mode != "platform":
                    violations.append(
                        (vertical, role_slug, t.name, t.access_mode)
                    )
        assert not violations, (
            "Office-role templates must use access_mode='platform': "
            f"{violations}"
        )




# ── Saved-view seed dependency verification ─────────────────────────


class TestSavedViewSeedDependencies:
    """Every Phase 8e template that references
    saved_view_seed:<role>:<key> must have a matching SeedTemplate
    in saved_views/seed.py so the pin resolves at read time."""

    def test_every_saved_view_pin_has_matching_seed(self):
        """Cross-reference SEED_TEMPLATES (spaces) against
        SEED_TEMPLATES (saved_views). For every pin with
        target_seed_key starting `saved_view_seed:`, confirm the
        matching (role_slug, template_id) exists in the saved_views
        registry FOR AT LEAST ONE VERTICAL."""
        missing: list[tuple[str, str, str, str]] = []
        for (vertical, role_slug), templates in reg.SEED_TEMPLATES.items():
            for tpl in templates:
                for pin in tpl.pins:
                    if pin.pin_type != "saved_view":
                        continue
                    if not pin.target.startswith("saved_view_seed:"):
                        continue
                    # seed key format: saved_view_seed:{role}:{tid}
                    parts = pin.target.split(":")
                    if len(parts) != 3:
                        continue
                    _, seed_role, seed_tid = parts
                    # Must exist in saved_views SEED_TEMPLATES for
                    # (vertical, seed_role) — same vertical the space
                    # template is seeded into.
                    sv_templates = sv_seed.SEED_TEMPLATES.get(
                        (vertical, seed_role), []
                    )
                    matching = [
                        t for t in sv_templates if t.template_id == seed_tid
                    ]
                    if not matching:
                        missing.append(
                            (vertical, role_slug, tpl.name, pin.target)
                        )
        assert not missing, (
            "Space templates reference saved_view_seed keys with no "
            "matching saved_views SeedTemplate:\n"
            + "\n".join(
                f"  {v}/{r} {tn!r} → {target}"
                for v, r, tn, target in missing
            )
        )

    def test_cemetery_admin_saved_views_seed(self):
        """Explicit test for a Phase 8e combination.

        Phase W-4a Step 3 (Pattern A enforcement) removed the
        `recent_cases` template (entity_type=fh_case) from this
        seed combination — fh_case is funeral_home-only per the
        entity registry's allowed_verticals. Cemeteries' own
        entity_type (interments) will land here when the cemetery
        data model solidifies.
        """
        sv_templates = sv_seed.SEED_TEMPLATES.get(("cemetery", "admin"), [])
        ids = {t.template_id for t in sv_templates}
        assert "outstanding_invoices" in ids
        # Regression guard: no FH-typed templates here.
        assert "recent_cases" not in ids
        for tpl in sv_templates:
            assert tpl.entity_type != "fh_case", (
                f"Cemetery/admin seed template {tpl.template_id!r} "
                f"declares entity_type='fh_case' — cross-vertical "
                f"contamination per Pattern A."
            )

    def test_fh_accountant_saved_views_seed(self):
        sv_templates = sv_seed.SEED_TEMPLATES.get(
            ("funeral_home", "accountant"), []
        )
        ids = {t.template_id for t in sv_templates}
        assert "outstanding_invoices" in ids

    def test_manufacturing_admin_does_not_seed_fh_recent_cases(self):
        """Cross-vertical contamination regression guard (Phase W-4a
        Step 1, April 2026): manufacturing tenants don't have FH
        cases. The `recent_cases` template (entity_type=fh_case) was
        previously seeded for `("manufacturing", "admin")` and
        accumulated FH-typed saved views in manufacturing tenants'
        vault_items. Removed per the saved-view-vertical-scope-
        inheritance canon (BRIDGEABLE_MASTER §3.25 forthcoming
        amendment + DESIGN_LANGUAGE §13.4.1 forthcoming amendment).
        Step 3 architectural fix will enforce at registry / creation
        / read layers; this guard prevents the seed from regressing.
        """
        sv_templates = sv_seed.SEED_TEMPLATES.get(
            ("manufacturing", "admin"), []
        )
        ids = {t.template_id for t in sv_templates}
        # Sanity: outstanding_invoices stays — it's mfg-compatible.
        assert "outstanding_invoices" in ids
        # Regression guard: no FH-typed saved views.
        assert "recent_cases" not in ids
        # Defense-in-depth: no template should declare entity_type
        # "fh_case" for the manufacturing/admin pair.
        for tpl in sv_templates:
            assert tpl.entity_type != "fh_case", (
                f"Manufacturing/admin seed template {tpl.template_id!r} "
                f"declares entity_type='fh_case' — cross-vertical "
                f"contamination. Remove this template or move it to "
                f"the funeral_home/admin combination."
            )


# ── default_home_route round-trip ───────────────────────────────────


class TestDefaultHomeRoute:
    def test_create_with_route(self, db_session):
        user = _fresh_user(
            db_session, role_slug="admin", vertical="manufacturing"
        )
        sp = create_space(
            db_session,
            user=user,
            name="My custom space",
            default_home_route="/quoting",
        )
        assert sp.default_home_route == "/quoting"

    def test_create_without_route_is_null(self, db_session):
        user = _fresh_user(
            db_session, role_slug="admin", vertical="manufacturing"
        )
        sp = create_space(
            db_session, user=user, name="No route"
        )
        assert sp.default_home_route is None

    def test_update_sets_route(self, db_session):
        user = _fresh_user(
            db_session, role_slug="admin", vertical="manufacturing"
        )
        sp = create_space(db_session, user=user, name="Test")
        updated = update_space(
            db_session,
            user=user,
            space_id=sp.space_id,
            default_home_route="/financials",
        )
        assert updated.default_home_route == "/financials"

    def test_update_clears_route_on_null(self, db_session):
        user = _fresh_user(
            db_session, role_slug="admin", vertical="manufacturing"
        )
        sp = create_space(
            db_session,
            user=user,
            name="Test",
            default_home_route="/financials",
        )
        updated = update_space(
            db_session,
            user=user,
            space_id=sp.space_id,
            default_home_route=None,
        )
        assert updated.default_home_route is None

    def test_update_unset_preserves_route(self, db_session):
        """Passing no default_home_route kwarg at all should
        preserve the existing value."""
        user = _fresh_user(
            db_session, role_slug="admin", vertical="manufacturing"
        )
        sp = create_space(
            db_session,
            user=user,
            name="Test",
            default_home_route="/financials",
        )
        # Omit default_home_route; only change the name.
        updated = update_space(
            db_session,
            user=user,
            space_id=sp.space_id,
            name="Renamed",
        )
        assert updated.default_home_route == "/financials"
        assert updated.name == "Renamed"

    def test_seeded_template_carries_route(self, db_session):
        """FH director's Arrangement space should have
        default_home_route set from the template."""
        user = _fresh_user(
            db_session, role_slug="director", vertical="funeral_home"
        )
        seed_for_user(db_session, user=user)
        spaces = get_spaces_for_user(db_session, user=user)
        arr = next((s for s in spaces if s.name == "Arrangement"), None)
        assert arr is not None
        assert arr.default_home_route == "/cases"

    def test_round_trip_through_json(self):
        """SpaceConfig.to_dict/from_dict preserves default_home_route."""
        cfg = SpaceConfig(
            space_id=SpaceConfig.new_id(),
            name="Test",
            icon="home",
            accent="neutral",
            display_order=0,
            is_default=True,
            pins=[],
            default_home_route="/dashboard",
        )
        restored = SpaceConfig.from_dict(cfg.to_dict())
        assert restored.default_home_route == "/dashboard"

    def test_legacy_json_without_field_round_trips_as_null(self):
        """Users seeded before Phase 8e have spaces JSON without
        default_home_route. from_dict should not crash + return None."""
        legacy_json = {
            "space_id": "sp_abc123def456",
            "name": "Legacy",
            "icon": "home",
            "accent": "neutral",
            "display_order": 0,
            "is_default": True,
            "pins": [],
        }
        restored = SpaceConfig.from_dict(legacy_json)
        assert restored.default_home_route is None


# ── MAX_SPACES_PER_USER bump ────────────────────────────────────────


class TestMaxSpacesBump:
    def test_cap_is_seven(self):
        assert MAX_SPACES_PER_USER == 7

    def test_can_create_up_to_seven(self, db_session):
        user = _fresh_user(
            db_session, role_slug="admin", vertical="manufacturing"
        )
        # Delete any seeded spaces first
        from app.services.spaces.crud import _load_spaces
        existing = _load_spaces(user)
        for sp in existing:
            from app.services.spaces import delete_space
            try:
                delete_space(db_session, user=user, space_id=sp.space_id)
            except SpaceError:
                pass
        # Now create 7
        for i in range(MAX_SPACES_PER_USER):
            create_space(db_session, user=user, name=f"Space {i + 1}")
        # 8th should fail
        with pytest.raises(SpaceLimitExceeded):
            create_space(db_session, user=user, name="Space 8")


# ── Reapply-defaults endpoint ───────────────────────────────────────


class TestReapplyDefaultsEndpoint:
    """HTTP-layer test. Uses TestClient + DB-created user + JWT
    token. X-Company-Slug header carries the tenant context the
    middleware needs."""

    def test_reapply_returns_counts_shape(self, db_session):
        from app.main import app

        _user, headers = _api_ctx(
            db_session, role_slug="director", vertical="funeral_home"
        )
        client = TestClient(app)
        resp = client.post(
            "/api/v1/spaces/reapply-defaults", headers=headers
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body.keys()) == {
            "saved_views",
            "spaces",
            "briefings",
        }
        # On first call, spaces seed may or may not run depending on
        # whether register_user fired already. We accept any non-
        # negative int.
        assert body["saved_views"] >= 0
        assert body["spaces"] >= 0
        assert body["briefings"] >= 0

    def test_reapply_is_idempotent(self, db_session):
        """Calling twice in a row produces zero new saved views and
        zero new spaces the second time — both track via
        preferences arrays. Briefings counter reports 1-on-success
        by contract in reapply_role_defaults_for_user (not a
        created-row count), so it's not asserted against zero."""
        from app.main import app

        _user, headers = _api_ctx(
            db_session, role_slug="admin", vertical="manufacturing"
        )
        client = TestClient(app)
        client.post("/api/v1/spaces/reapply-defaults", headers=headers)
        second = client.post(
            "/api/v1/spaces/reapply-defaults", headers=headers
        )
        body = second.json()
        assert body["saved_views"] == 0
        assert body["spaces"] == 0
        # briefings: pre-Phase-8e contract reports 1 on any
        # successful seed_preferences_for_user call (which is itself
        # internally idempotent on preferences.briefings_seeded_for_roles).
        # Acceptable: 0 or 1.
        assert body["briefings"] in (0, 1)

    def test_reapply_requires_auth(self):
        from app.main import app

        client = TestClient(app)
        # No token — unauthenticated requests are rejected before
        # the tenant middleware matters.
        resp = client.post("/api/v1/spaces/reapply-defaults")
        assert resp.status_code in (401, 403, 404)


# ── NAV_LABEL_TABLE coverage — every nav_item pin has a fallback ────


class TestNavLabelCoverage:
    def test_every_new_nav_item_has_label(self):
        """Every nav_item pin target in Phase 8e templates should
        have an entry in NAV_LABEL_TABLE — otherwise PinnedSection
        falls back to (href, 'Link') which is readable but not
        pretty. This test gates future template additions against
        forgetting the label."""
        missing: list[str] = []
        for templates in reg.SEED_TEMPLATES.values():
            for tpl in templates:
                for pin in tpl.pins:
                    if pin.pin_type != "nav_item":
                        continue
                    if reg.get_nav_label(pin.target) is None:
                        missing.append(pin.target)
        assert not missing, (
            f"nav_item pins missing NAV_LABEL_TABLE entries: "
            f"{sorted(set(missing))}"
        )


# ── API schema surfaces default_home_route ──────────────────────────


class TestDefaultHomeRouteViaAPI:
    def test_create_with_route_via_api(self, db_session):
        from app.main import app

        _user, headers = _api_ctx(
            db_session, role_slug="admin", vertical="manufacturing"
        )
        client = TestClient(app)
        resp = client.post(
            "/api/v1/spaces",
            headers=headers,
            json={
                "name": "API Test",
                "default_home_route": "/dashboard",
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["default_home_route"] == "/dashboard"

    def test_patch_clears_route_via_api(self, db_session):
        from app.main import app

        _user, headers = _api_ctx(
            db_session, role_slug="admin", vertical="manufacturing"
        )
        client = TestClient(app)
        create = client.post(
            "/api/v1/spaces",
            headers=headers,
            json={"name": "API Test 2", "default_home_route": "/financials"},
        )
        space_id = create.json()["space_id"]
        patch = client.patch(
            f"/api/v1/spaces/{space_id}",
            headers=headers,
            json={"default_home_route": None},
        )
        assert patch.status_code == 200, patch.text
        assert patch.json()["default_home_route"] is None

    def test_patch_without_route_key_preserves(self, db_session):
        """Omitting default_home_route from the PATCH body must not
        clear it — relies on model_fields_set detection."""
        from app.main import app

        _user, headers = _api_ctx(
            db_session, role_slug="admin", vertical="manufacturing"
        )
        client = TestClient(app)
        create = client.post(
            "/api/v1/spaces",
            headers=headers,
            json={"name": "API Test 3", "default_home_route": "/quoting"},
        )
        space_id = create.json()["space_id"]
        # Rename only — don't touch the route key
        patch = client.patch(
            f"/api/v1/spaces/{space_id}",
            headers=headers,
            json={"name": "Renamed"},
        )
        assert patch.status_code == 200, patch.text
        assert patch.json()["default_home_route"] == "/quoting"
        assert patch.json()["name"] == "Renamed"
