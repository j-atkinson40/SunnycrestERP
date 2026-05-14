"""Focus Template Inheritance — chrome substrate tests (sub-arc B-3.5).

Covers the wholesale-replaced chrome v2 vocabulary:

    TestChromeValidationV2        — validate_chrome_blob shape rules (v2)
    TestPresetExpansion           — expand_preset behaviors
    TestCoreServiceChrome         — Tier 1 chrome stored + versioned
    TestTemplateServiceChrome     — Tier 2 chrome_overrides stored + versioned
    TestCompositionServiceChrome  — Tier 3 deltas.chrome_overrides round-trip
    TestResolverChromeCascadeV2   — preset expansion + field-level cascade
    TestApiChromeV2               — admin API request/response wiring

All tests share the B-1 clean-slate autouse fixture pattern.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.database import SessionLocal
from app.models.company import Company
from app.models.focus_composition import FocusComposition
from app.models.focus_core import FocusCore
from app.models.focus_template import FocusTemplate
from app.models.platform_user import PlatformUser
from app.services.focus_template_inheritance import (
    CHROME_FIELDS,
    PRESETS,
    VALID_PRESETS,
    InvalidChromeShape,
    InvalidCompositionShape,
    InvalidCoreShape,
    InvalidTemplateShape,
    create_core,
    create_or_update_composition,
    create_template,
    expand_preset,
    reset_composition_to_default,
    resolve_focus,
    update_core,
    update_template,
    validate_chrome_blob,
)


API_ROOT = "/api/platform/admin/focus-template-inheritance"


# ─── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def _cleanup():
    def _wipe():
        s = SessionLocal()
        try:
            s.query(FocusComposition).delete()
            s.query(FocusTemplate).delete()
            s.query(FocusCore).delete()
            s.commit()
        finally:
            s.close()

    _wipe()
    yield
    _wipe()


@pytest.fixture
def tenant_company():
    s = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"FTI Chrome {suffix}",
            slug=f"fticc-{suffix}",
            is_active=True,
            vertical="funeral_home",
        )
        s.add(co)
        s.commit()
        yield co.id
        s.delete(co)
        s.commit()
    finally:
        s.close()


def _make_core(db, *, slug: str = "scheduling-kanban", **kwargs) -> FocusCore:
    defaults = dict(
        core_slug=slug,
        display_name="Scheduling Kanban",
        description="Kanban core",
        registered_component_kind="focus-core",
        registered_component_name="SchedulingKanbanCore",
        default_starting_column=0,
        default_column_span=12,
        default_row_index=0,
        min_column_span=8,
        max_column_span=12,
        canvas_config={},
    )
    defaults.update(kwargs)
    return create_core(db, **defaults)


def _make_template(db, core_id: str, **kwargs) -> FocusTemplate:
    defaults = dict(
        scope="platform_default",
        vertical=None,
        template_slug="scheduling-default",
        display_name="Default Scheduling",
        description=None,
        inherits_from_core_id=core_id,
        rows=[],
        canvas_config={},
    )
    defaults.update(kwargs)
    return create_template(db, **defaults)


# ═══ TestChromeValidationV2 ═════════════════════════════════════════


class TestChromeValidationV2:
    def test_empty_dict_valid(self):
        validate_chrome_blob({})

    def test_preset_only_valid(self):
        for p in VALID_PRESETS:
            validate_chrome_blob({"preset": p})

    def test_preset_with_slider_overrides_valid(self):
        validate_chrome_blob(
            {"preset": "card", "elevation": 50, "corner_radius": 75}
        )

    def test_custom_preset_with_token_overrides_valid(self):
        validate_chrome_blob(
            {
                "preset": "custom",
                "background_token": "surface-elevated",
                "border_token": "border-subtle",
                "padding_token": "space-4",
                "elevation": 25,
                "corner_radius": 50,
            }
        )

    def test_invalid_preset_rejected(self):
        with pytest.raises(InvalidChromeShape, match="preset must be one of"):
            validate_chrome_blob({"preset": "splash"})

    def test_elevation_out_of_bounds_rejected(self):
        with pytest.raises(InvalidChromeShape, match=r"elevation must be in \[0, 100\]"):
            validate_chrome_blob({"elevation": 101})
        with pytest.raises(InvalidChromeShape, match=r"elevation must be in \[0, 100\]"):
            validate_chrome_blob({"elevation": -1})

    def test_corner_radius_out_of_bounds_rejected(self):
        with pytest.raises(InvalidChromeShape, match=r"corner_radius must be in \[0, 100\]"):
            validate_chrome_blob({"corner_radius": 101})

    def test_unknown_key_rejected(self):
        with pytest.raises(InvalidChromeShape, match="unknown keys"):
            validate_chrome_blob({"margin": 4})

    def test_b3_keys_rejected(self):
        # B-3's vocabulary is fully retired — every prior key must
        # trip the unknown-keys gate.
        for key in ("background_color", "drop_shadow", "border", "padding"):
            with pytest.raises(InvalidChromeShape, match="unknown keys"):
                validate_chrome_blob({key: {}})

    def test_token_field_permissive(self):
        # Any non-empty string accepted.
        validate_chrome_blob({"background_token": "surface-elevated"})
        validate_chrome_blob({"border_token": "any-string-the-author-likes"})
        validate_chrome_blob({"padding_token": "space-6"})
        with pytest.raises(InvalidChromeShape, match="non-empty string"):
            validate_chrome_blob({"background_token": ""})

    def test_explicit_null_each_field_valid(self):
        validate_chrome_blob(
            {
                "preset": None,
                "elevation": None,
                "corner_radius": None,
                "background_token": None,
                "border_token": None,
                "padding_token": None,
            }
        )

    def test_module_constants_shape(self):
        assert CHROME_FIELDS == (
            "preset",
            "elevation",
            "corner_radius",
            "backdrop_blur",
            "background_token",
            "border_token",
            "padding_token",
        )
        assert VALID_PRESETS == frozenset(
            {
                "card",
                "modal",
                "dropdown",
                "toast",
                "floating",
                "frosted",
                "custom",
            }
        )

    # ─── Sub-arc C-1 additions: frosted preset + backdrop_blur ────

    def test_frosted_preset_valid(self):
        validate_chrome_blob({"preset": "frosted"})

    def test_backdrop_blur_in_range_valid(self):
        validate_chrome_blob({"backdrop_blur": 0})
        validate_chrome_blob({"backdrop_blur": 60})
        validate_chrome_blob({"backdrop_blur": 100})

    def test_backdrop_blur_out_of_bounds_rejected(self):
        with pytest.raises(
            InvalidChromeShape, match=r"backdrop_blur must be in \[0, 100\]"
        ):
            validate_chrome_blob({"backdrop_blur": 101})
        with pytest.raises(
            InvalidChromeShape, match=r"backdrop_blur must be in \[0, 100\]"
        ):
            validate_chrome_blob({"backdrop_blur": -1})

    def test_backdrop_blur_null_valid(self):
        validate_chrome_blob({"backdrop_blur": None})


# ═══ TestPresetExpansion ════════════════════════════════════════════


class TestPresetExpansion:
    def test_no_preset_returns_unchanged(self):
        assert expand_preset({}) == {}
        assert expand_preset({"elevation": 50}) == {"elevation": 50}

    def test_preset_none_returns_unchanged(self):
        assert expand_preset({"preset": None}) == {"preset": None}

    def test_card_preset_returns_canonical_defaults(self):
        result = expand_preset({"preset": "card"})
        assert result["background_token"] == "surface-elevated"
        assert result["elevation"] == 37
        assert result["corner_radius"] == 37
        assert result["padding_token"] == "space-6"
        assert result["preset"] == "card"

    def test_modal_preset(self):
        result = expand_preset({"preset": "modal"})
        assert result["background_token"] == "surface-raised"
        assert result["elevation"] == 62
        assert result["corner_radius"] == 62

    def test_dropdown_preset_includes_border_token(self):
        result = expand_preset({"preset": "dropdown"})
        assert result["border_token"] == "border-subtle"
        assert result["padding_token"] == "space-2"

    def test_floating_preset_includes_border_brass(self):
        result = expand_preset({"preset": "floating"})
        assert result["border_token"] == "border-brass"
        assert result["elevation"] == 87

    def test_toast_preset(self):
        result = expand_preset({"preset": "toast"})
        assert result["elevation"] == 87
        assert result["corner_radius"] == 37

    def test_custom_preset_returns_unchanged(self):
        blob = {"preset": "custom", "background_token": "my-token"}
        assert expand_preset(blob) == blob

    def test_overrides_preserved_on_top_of_preset(self):
        result = expand_preset({"preset": "card", "elevation": 80})
        # Overlay wins for elevation; preset defaults supply the rest.
        assert result["elevation"] == 80
        assert result["corner_radius"] == 37
        assert result["background_token"] == "surface-elevated"

    # ─── Sub-arc C-1: frosted preset expansion ────────────────────

    def test_frosted_preset_returns_canonical_defaults(self):
        result = expand_preset({"preset": "frosted"})
        assert result["preset"] == "frosted"
        assert result["background_token"] == "surface-elevated"
        assert result["elevation"] == 50
        assert result["corner_radius"] == 62
        assert result["padding_token"] == "space-6"
        assert result["backdrop_blur"] == 60
        assert result["border_token"] == "border-subtle"

    def test_frosted_preset_with_backdrop_blur_override(self):
        result = expand_preset({"preset": "frosted", "backdrop_blur": 100})
        # Overlay wins for backdrop_blur; rest from preset.
        assert result["backdrop_blur"] == 100
        assert result["background_token"] == "surface-elevated"
        assert result["elevation"] == 50


# ═══ TestCoreServiceChrome ══════════════════════════════════════════


class TestCoreServiceChrome:
    def test_create_with_chrome_stored(self, db):
        chrome = {"preset": "card", "elevation": 80}
        core = _make_core(db, chrome=chrome)
        assert core.chrome == chrome

    def test_create_without_chrome_defaults_empty(self, db):
        core = _make_core(db)
        assert core.chrome == {}

    def test_create_with_invalid_chrome_rejects(self, db):
        with pytest.raises(InvalidCoreShape):
            _make_core(db, chrome={"background_color": "#000"})  # B-3 key

    def test_update_chrome_version_bumps_and_preserves(self, db):
        core_v1 = _make_core(db, chrome={"preset": "card"})
        core_v2 = update_core(db, core_v1.id, chrome={"preset": "modal"})
        assert core_v2.version == 2
        assert core_v2.chrome == {"preset": "modal"}


# ═══ TestTemplateServiceChrome ═════════════════════════════════════


class TestTemplateServiceChrome:
    def test_create_with_chrome_overrides_stored(self, db):
        core = _make_core(db, chrome={"preset": "card"})
        t = _make_template(db, core.id, chrome_overrides={"elevation": 90})
        assert t.chrome_overrides == {"elevation": 90}

    def test_create_without_chrome_defaults_empty(self, db):
        core = _make_core(db)
        t = _make_template(db, core.id)
        assert t.chrome_overrides == {}

    def test_create_with_invalid_chrome_rejects(self, db):
        core = _make_core(db)
        with pytest.raises(InvalidTemplateShape):
            _make_template(
                db, core.id, chrome_overrides={"preset": "splash"}
            )


# ═══ TestCompositionServiceChrome ═══════════════════════════════════


class TestCompositionServiceChrome:
    def test_upsert_with_chrome_overrides_stored(self, db, tenant_company):
        core = _make_core(db, chrome={"preset": "card"})
        t = _make_template(db, core.id)
        comp = create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"chrome_overrides": {"corner_radius": 100}},
        )
        assert comp.deltas["chrome_overrides"] == {"corner_radius": 100}

    def test_upsert_b3_shape_in_deltas_rejects(self, db, tenant_company):
        core = _make_core(db)
        t = _make_template(db, core.id)
        with pytest.raises(InvalidCompositionShape):
            create_or_update_composition(
                db,
                tenant_id=tenant_company,
                template_id=t.id,
                deltas={"chrome_overrides": {"padding": {"top": 4}}},
            )

    def test_reset_clears_chrome_overrides(self, db, tenant_company):
        core = _make_core(db)
        t = _make_template(db, core.id)
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"chrome_overrides": {"preset": "modal"}},
        )
        reset = reset_composition_to_default(db, tenant_company, t.id)
        assert reset.deltas["chrome_overrides"] == {}


# ═══ TestResolverChromeCascadeV2 ════════════════════════════════════


class TestResolverChromeCascadeV2:
    def test_tier1_preset_only_expands_to_canonical_defaults(self, db):
        core = _make_core(db, chrome={"preset": "card"})
        _make_template(db, core.id)
        r = resolve_focus(db, template_slug="scheduling-default")
        assert r.resolved_chrome is not None
        assert r.resolved_chrome["preset"] == "card"
        assert r.resolved_chrome["background_token"] == "surface-elevated"
        assert r.resolved_chrome["elevation"] == 37
        assert r.resolved_chrome["corner_radius"] == 37
        assert r.resolved_chrome["padding_token"] == "space-6"
        # Every populated field traces to tier1.
        for field in ("preset", "background_token", "elevation",
                      "corner_radius", "padding_token"):
            assert r.sources["chrome_sources"][field] == "tier1"
        assert r.sources["chrome_sources"]["border_token"] is None

    def test_tier2_slider_override_on_tier1_preset(self, db):
        core = _make_core(db, chrome={"preset": "card"})
        _make_template(db, core.id, chrome_overrides={"elevation": 80})
        r = resolve_focus(db, template_slug="scheduling-default")
        # Tier 2's elevation wins; rest of card preset cascades from
        # Tier 1's expanded form.
        assert r.resolved_chrome["elevation"] == 80
        assert r.sources["chrome_sources"]["elevation"] == "tier2"
        assert r.resolved_chrome["background_token"] == "surface-elevated"
        assert r.sources["chrome_sources"]["background_token"] == "tier1"

    def test_tier2_preset_replaces_tier1_preset(self, db):
        core = _make_core(db, chrome={"preset": "card"})
        _make_template(db, core.id, chrome_overrides={"preset": "modal"})
        r = resolve_focus(db, template_slug="scheduling-default")
        # Each field present in Tier 2's expanded form wins. Modal's
        # background_token, elevation, corner_radius, padding_token
        # come from tier2 expansion. border_token is None in modal,
        # but it's also missing from tier1 — net None.
        assert r.resolved_chrome["preset"] == "modal"
        assert r.sources["chrome_sources"]["preset"] == "tier2"
        assert r.resolved_chrome["background_token"] == "surface-raised"
        assert r.sources["chrome_sources"]["background_token"] == "tier2"
        assert r.resolved_chrome["elevation"] == 62
        assert r.sources["chrome_sources"]["elevation"] == "tier2"

    def test_tier3_overrides_specific_field_over_tier2_preset(
        self, db, tenant_company
    ):
        core = _make_core(db, chrome={"preset": "card"})
        t = _make_template(db, core.id, chrome_overrides={"preset": "modal"})
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"chrome_overrides": {"corner_radius": 100}},
        )
        r = resolve_focus(
            db, template_slug="scheduling-default", tenant_id=tenant_company
        )
        assert r.resolved_chrome["corner_radius"] == 100
        assert r.sources["chrome_sources"]["corner_radius"] == "tier3"
        # Rest of modal preset still wins from tier2.
        assert r.resolved_chrome["background_token"] == "surface-raised"
        assert r.sources["chrome_sources"]["background_token"] == "tier2"

    def test_tier3_explicit_null_overrides_parent(
        self, db, tenant_company
    ):
        # Key-presence semantics: explicit None at Tier 3 wins over
        # parent tier's value. `preset=None` carries the "no preset"
        # state through cascade — it does NOT mean "inherit."
        core = _make_core(db, chrome={"preset": "card"})
        t = _make_template(db, core.id)
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"chrome_overrides": {"background_token": None}},
        )
        r = resolve_focus(
            db, template_slug="scheduling-default", tenant_id=tenant_company
        )
        assert r.resolved_chrome["background_token"] is None
        assert r.sources["chrome_sources"]["background_token"] == "tier3"

    def test_custom_preset_full_token_overrides(self, db):
        core = _make_core(
            db,
            chrome={
                "preset": "custom",
                "background_token": "surface-sunken",
                "border_token": "border-strong",
                "padding_token": "space-4",
                "elevation": 50,
                "corner_radius": 25,
            },
        )
        _make_template(db, core.id)
        r = resolve_focus(db, template_slug="scheduling-default")
        # Custom preset means "no defaults" — every explicit field
        # passes through verbatim.
        assert r.resolved_chrome["preset"] == "custom"
        assert r.resolved_chrome["background_token"] == "surface-sunken"
        assert r.resolved_chrome["border_token"] == "border-strong"
        assert r.resolved_chrome["padding_token"] == "space-4"
        assert r.resolved_chrome["elevation"] == 50
        assert r.resolved_chrome["corner_radius"] == 25

    def test_three_tiers_contribute_different_fields(
        self, db, tenant_company
    ):
        core = _make_core(db, chrome={"preset": "card"})
        t = _make_template(
            db, core.id, chrome_overrides={"corner_radius": 90}
        )
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"chrome_overrides": {"border_token": "border-brass"}},
        )
        r = resolve_focus(
            db, template_slug="scheduling-default", tenant_id=tenant_company
        )
        # preset, background, elevation, padding from tier1 (card)
        # corner_radius from tier2
        # border_token from tier3
        assert r.sources["chrome_sources"]["preset"] == "tier1"
        assert r.sources["chrome_sources"]["background_token"] == "tier1"
        assert r.sources["chrome_sources"]["elevation"] == "tier1"
        assert r.sources["chrome_sources"]["padding_token"] == "tier1"
        assert r.sources["chrome_sources"]["corner_radius"] == "tier2"
        assert r.sources["chrome_sources"]["border_token"] == "tier3"
        assert r.resolved_chrome["corner_radius"] == 90
        assert r.resolved_chrome["border_token"] == "border-brass"

    def test_chrome_sources_per_field_field_names_are_v2(self, db):
        core = _make_core(db, chrome={"preset": "card"})
        _make_template(db, core.id)
        r = resolve_focus(db, template_slug="scheduling-default")
        # Every CHROME_FIELDS key present in chrome_sources.
        for field in CHROME_FIELDS:
            assert field in r.sources["chrome_sources"]

    def test_empty_at_all_tiers_collapses_to_none(self, db):
        core = _make_core(db)
        _make_template(db, core.id)
        r = resolve_focus(db, template_slug="scheduling-default")
        assert r.resolved_chrome is None
        for field in CHROME_FIELDS:
            assert r.sources["chrome_sources"][field] is None

    def test_slider_value_preserved_through_cascade(self, db):
        core = _make_core(db, chrome={"elevation": 42, "corner_radius": 7})
        _make_template(db, core.id)
        r = resolve_focus(db, template_slug="scheduling-default")
        # Storage is integer 0-100; resolver does not map to tokens.
        assert r.resolved_chrome["elevation"] == 42
        assert r.resolved_chrome["corner_radius"] == 7

    def test_resolver_does_not_validate_token_existence(self, db):
        # Service layer accepts any non-empty string for token fields.
        # Resolver does not validate against any theme — that's a
        # consumer-side concern.
        core = _make_core(
            db, chrome={"background_token": "made-up-token-name"}
        )
        _make_template(db, core.id)
        r = resolve_focus(db, template_slug="scheduling-default")
        assert r.resolved_chrome["background_token"] == "made-up-token-name"

    # ─── Sub-arc C-1: backdrop_blur + frosted cascade ─────────────

    def test_frosted_preset_resolves_through_cascade(self, db):
        core = _make_core(db, chrome={"preset": "frosted"})
        _make_template(db, core.id)
        r = resolve_focus(db, template_slug="scheduling-default")
        assert r.resolved_chrome is not None
        assert r.resolved_chrome["backdrop_blur"] == 60
        assert r.resolved_chrome["background_token"] == "surface-elevated"
        assert r.sources["chrome_sources"]["backdrop_blur"] == "tier1"

    def test_backdrop_blur_tier3_overrides_tier1(self, db, tenant_company):
        core = _make_core(db, chrome={"preset": "frosted"})
        t = _make_template(db, core.id)
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"chrome_overrides": {"backdrop_blur": 100}},
        )
        r = resolve_focus(
            db, template_slug="scheduling-default", tenant_id=tenant_company
        )
        assert r.resolved_chrome["backdrop_blur"] == 100
        assert r.sources["chrome_sources"]["backdrop_blur"] == "tier3"
        # Other frosted fields still flow from tier1.
        assert r.sources["chrome_sources"]["background_token"] == "tier1"

    def test_expand_preset_runs_before_cascade_not_after(self, db):
        # If preset expansion ran AFTER cascade, a tier2 preset=modal
        # against a tier1 elevation=99 would resolve elevation=99
        # (tier1 wins per cascade, then preset expands — but expansion
        # is per-tier-before-cascade, so tier2 contributes its
        # expanded form's elevation=62 to the cascade).
        core = _make_core(db, chrome={"elevation": 99})
        _make_template(db, core.id, chrome_overrides={"preset": "modal"})
        r = resolve_focus(db, template_slug="scheduling-default")
        # Tier 2's preset expansion gives elevation=62; tier1's
        # elevation=99 is present too but tier 2 wins per cascade.
        assert r.resolved_chrome["elevation"] == 62
        assert r.sources["chrome_sources"]["elevation"] == "tier2"


# ═══ TestApiChromeV2 ════════════════════════════════════════════════


class _ApiCtx:
    def __init__(self):
        from app.models.role import Role
        from app.models.user import User

        self.s = SessionLocal()
        suffix = uuid.uuid4().hex[:6]
        self.suffix = suffix
        self.co = Company(
            id=str(uuid.uuid4()),
            name=f"FTI Chrome API {suffix}",
            slug=f"ftica-{suffix}",
            is_active=True,
            vertical="funeral_home",
        )
        self.s.add(self.co)
        self.s.flush()
        self.role = Role(
            id=str(uuid.uuid4()),
            company_id=self.co.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        self.s.add(self.role)
        self.s.flush()
        self.user = User(
            id=str(uuid.uuid4()),
            company_id=self.co.id,
            email=f"chrome-{suffix}@fti.test",
            hashed_password="x",
            first_name="C",
            last_name="A",
            role_id=self.role.id,
            is_active=True,
        )
        self.s.add(self.user)
        self.platform_admin = PlatformUser(
            id=str(uuid.uuid4()),
            email=f"platform-chrome-{suffix}@bridgeable.test",
            hashed_password="x",
            first_name="P",
            last_name="A",
            role="super_admin",
            is_active=True,
        )
        self.s.add(self.platform_admin)
        self.s.commit()
        self.platform_token = create_access_token(
            {"sub": self.platform_admin.id}, realm="platform"
        )

    @property
    def platform_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.platform_token}"}

    def close(self):
        from app.models.role import Role as _R
        from app.models.user import User as _U

        s2 = SessionLocal()
        try:
            s2.query(FocusComposition).filter(
                FocusComposition.tenant_id == self.co.id
            ).delete()
            s2.query(_U).filter(_U.company_id == self.co.id).delete()
            s2.query(_R).filter(_R.company_id == self.co.id).delete()
            obj = s2.query(Company).filter(Company.id == self.co.id).first()
            if obj is not None:
                s2.delete(obj)
            s2.query(PlatformUser).filter(
                PlatformUser.id == self.platform_admin.id
            ).delete()
            s2.commit()
        finally:
            s2.close()
        self.s.close()


@pytest.fixture
def api_ctx():
    ctx = _ApiCtx()
    yield ctx
    ctx.close()


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


class TestApiChromeV2:
    def test_post_cores_with_v2_chrome_succeeds(self, client, api_ctx):
        body = {
            "core_slug": "scheduling-kanban",
            "display_name": "SK",
            "registered_component_kind": "focus-core",
            "registered_component_name": "SchedulingKanbanCore",
            "default_starting_column": 0,
            "default_column_span": 12,
            "default_row_index": 0,
            "min_column_span": 8,
            "max_column_span": 12,
            "canvas_config": {},
            "chrome": {"preset": "card", "elevation": 80},
        }
        r = client.post(
            f"{API_ROOT}/cores", json=body, headers=api_ctx.platform_headers
        )
        assert r.status_code == 201, r.text
        payload = r.json()
        assert payload["chrome"] == {"preset": "card", "elevation": 80}

    def test_post_cores_with_b3_shape_returns_400(self, client, api_ctx):
        body = {
            "core_slug": "scheduling-kanban",
            "display_name": "SK",
            "registered_component_kind": "focus-core",
            "registered_component_name": "SchedulingKanbanCore",
            "default_starting_column": 0,
            "default_column_span": 12,
            "default_row_index": 0,
            "min_column_span": 8,
            "max_column_span": 12,
            "canvas_config": {},
            "chrome": {"background_color": "#000"},
        }
        r = client.post(
            f"{API_ROOT}/cores", json=body, headers=api_ctx.platform_headers
        )
        assert r.status_code in (400, 422), r.text

    def test_get_resolve_returns_v2_resolved_chrome(self, client, api_ctx, db):
        core = _make_core(db, chrome={"preset": "card"})
        _make_template(db, core.id)
        r = client.get(
            f"{API_ROOT}/resolve",
            params={"template_slug": "scheduling-default"},
            headers=api_ctx.platform_headers,
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["resolved_chrome"] is not None
        assert payload["resolved_chrome"]["preset"] == "card"
        assert payload["resolved_chrome"]["background_token"] == "surface-elevated"

    def test_resolve_chrome_sources_uses_v2_field_names(
        self, client, api_ctx, db
    ):
        core = _make_core(db, chrome={"preset": "card"})
        _make_template(db, core.id)
        r = client.get(
            f"{API_ROOT}/resolve",
            params={"template_slug": "scheduling-default"},
            headers=api_ctx.platform_headers,
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        sources = payload["sources"]["chrome_sources"]
        # Field names are v2 only.
        for field in CHROME_FIELDS:
            assert field in sources
        # B-3 field names are NOT in the sources dict.
        for legacy_field in (
            "background_color", "drop_shadow", "border", "padding"
        ):
            assert legacy_field not in sources


def test_presets_module_constant_shape():
    # Smoke-test the canonical preset dictionary as a module constant
    # so downstream consumers can assume key set + types.
    assert set(PRESETS.keys()) == VALID_PRESETS
    # Each non-custom preset declares non-empty defaults; custom is {}.
    for name, defaults in PRESETS.items():
        if name == "custom":
            assert defaults == {}
        else:
            assert isinstance(defaults, dict)
            assert len(defaults) >= 3
