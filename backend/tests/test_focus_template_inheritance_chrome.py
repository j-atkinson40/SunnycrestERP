"""Focus Template Inheritance — chrome substrate tests (sub-arc B-3).

Covers:

    TestChromeValidation        — validate_chrome_blob shape rules
    TestCoreServiceChrome       — Tier 1 chrome stored + versioned
    TestTemplateServiceChrome   — Tier 2 chrome_overrides stored + versioned
    TestCompositionServiceChrome — Tier 3 deltas.chrome_overrides round-trip
    TestResolverChromeCascade   — field-level merge across all three tiers
    TestApiChrome               — admin API request/response wiring

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
    BORDER_STYLES,
    InvalidChromeShape,
    InvalidCompositionShape,
    InvalidCoreShape,
    InvalidTemplateShape,
    create_core,
    create_or_update_composition,
    create_template,
    get_core_by_id,
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


_FULL_CHROME = {
    "background_color": "#1a1a1a",
    "drop_shadow": {
        "offset_x": 0,
        "offset_y": 4,
        "blur": 12,
        "spread": 0,
        "color": "rgba(0,0,0,0.18)",
    },
    "border": {
        "width": 1,
        "style": "solid",
        "color": "#333",
        "radius": 8,
    },
    "padding": {"top": 24, "right": 24, "bottom": 24, "left": 24},
}


# ═══ TestChromeValidation ═══════════════════════════════════════════


class TestChromeValidation:
    def test_full_valid_blob(self):
        # Does not raise.
        validate_chrome_blob(_FULL_CHROME)

    def test_empty_dict_valid(self):
        validate_chrome_blob({})

    def test_subset_of_fields_valid(self):
        validate_chrome_blob({"background_color": "#fff"})
        validate_chrome_blob({"padding": {"top": 8, "right": 8, "bottom": 8, "left": 8}})

    def test_explicit_null_each_field_valid(self):
        validate_chrome_blob(
            {
                "background_color": None,
                "drop_shadow": None,
                "border": None,
                "padding": None,
            }
        )

    def test_unknown_top_level_key_rejected(self):
        with pytest.raises(InvalidChromeShape, match="unknown keys"):
            validate_chrome_blob({"margin": {"top": 4}})

    def test_unknown_border_subkey_rejected(self):
        with pytest.raises(InvalidChromeShape, match="border has unknown keys"):
            validate_chrome_blob(
                {
                    "border": {
                        "width": 1,
                        "style": "solid",
                        "color": "#000",
                        "radius": 4,
                        "phase": 12,
                    }
                }
            )

    def test_invalid_border_style_rejected(self):
        with pytest.raises(InvalidChromeShape, match="border.style must be one of"):
            validate_chrome_blob(
                {
                    "border": {
                        "width": 1,
                        "style": "double",
                        "color": "#000",
                        "radius": 4,
                    }
                }
            )

    def test_negative_padding_rejected(self):
        with pytest.raises(InvalidChromeShape, match="padding.top must be >= 0"):
            validate_chrome_blob(
                {"padding": {"top": -1, "right": 0, "bottom": 0, "left": 0}}
            )

    def test_negative_blur_rejected(self):
        with pytest.raises(InvalidChromeShape, match="drop_shadow.blur must be >= 0"):
            validate_chrome_blob(
                {
                    "drop_shadow": {
                        "offset_x": 0,
                        "offset_y": 0,
                        "blur": -2,
                        "spread": 0,
                        "color": "#000",
                    }
                }
            )

    def test_negative_spread_allowed(self):
        validate_chrome_blob(
            {
                "drop_shadow": {
                    "offset_x": 0,
                    "offset_y": 2,
                    "blur": 4,
                    "spread": -2,
                    "color": "#000",
                }
            }
        )

    def test_drop_shadow_missing_field_rejected(self):
        with pytest.raises(
            InvalidChromeShape, match="drop_shadow missing required keys"
        ):
            validate_chrome_blob(
                {
                    "drop_shadow": {
                        "offset_x": 0,
                        "offset_y": 2,
                        "blur": 4,
                        "spread": 0,
                        # missing color
                    }
                }
            )

    def test_non_dict_rejected(self):
        with pytest.raises(InvalidChromeShape):
            validate_chrome_blob("not a dict")
        with pytest.raises(InvalidChromeShape):
            validate_chrome_blob([])

    def test_module_constants_shape(self):
        assert CHROME_FIELDS == (
            "background_color",
            "drop_shadow",
            "border",
            "padding",
        )
        assert BORDER_STYLES == frozenset({"solid", "dashed", "dotted", "none"})


# ═══ TestCoreServiceChrome ══════════════════════════════════════════


class TestCoreServiceChrome:
    def test_create_with_chrome_stored(self, db):
        core = _make_core(db, chrome=_FULL_CHROME)
        assert core.chrome == _FULL_CHROME

    def test_create_without_chrome_defaults_empty(self, db):
        core = _make_core(db)
        assert core.chrome == {}

    def test_create_with_invalid_chrome_rejects(self, db):
        with pytest.raises(InvalidCoreShape):
            _make_core(db, chrome={"margin": 4})

    def test_update_chrome_version_bumps_and_preserves(self, db):
        core_v1 = _make_core(db, chrome={"background_color": "#000"})
        core_v2 = update_core(
            db,
            core_v1.id,
            chrome={"background_color": "#fff"},
        )
        assert core_v2.version == 2
        assert core_v2.chrome == {"background_color": "#fff"}
        # v1 row deactivated but retained for audit.
        prior = db.query(FocusCore).filter(FocusCore.id == core_v1.id).first()
        assert prior is not None
        assert prior.is_active is False

    def test_update_without_chrome_preserves_prior(self, db):
        core_v1 = _make_core(db, chrome={"background_color": "#abc"})
        core_v2 = update_core(db, core_v1.id, display_name="Renamed")
        assert core_v2.chrome == {"background_color": "#abc"}


# ═══ TestTemplateServiceChrome ═════════════════════════════════════


class TestTemplateServiceChrome:
    def test_create_with_chrome_overrides_stored(self, db):
        core = _make_core(db, chrome=_FULL_CHROME)
        t = _make_template(
            db,
            core.id,
            chrome_overrides={"background_color": "#f0f0f0"},
        )
        assert t.chrome_overrides == {"background_color": "#f0f0f0"}

    def test_create_without_chrome_defaults_empty(self, db):
        core = _make_core(db)
        t = _make_template(db, core.id)
        assert t.chrome_overrides == {}

    def test_create_with_invalid_chrome_rejects(self, db):
        core = _make_core(db)
        with pytest.raises(InvalidTemplateShape):
            _make_template(
                db,
                core.id,
                chrome_overrides={
                    "border": {
                        "width": 1,
                        "style": "groove",
                        "color": "#000",
                        "radius": 0,
                    }
                },
            )

    def test_update_chrome_overrides_version_bump_preserves(self, db):
        core = _make_core(db)
        t1 = _make_template(db, core.id, chrome_overrides={"background_color": "#abc"})
        t2 = update_template(
            db,
            t1.id,
            chrome_overrides={"background_color": "#def"},
        )
        assert t2.version == 2
        assert t2.chrome_overrides == {"background_color": "#def"}

    def test_update_without_chrome_preserves(self, db):
        core = _make_core(db)
        t1 = _make_template(db, core.id, chrome_overrides={"background_color": "#abc"})
        t2 = update_template(db, t1.id, display_name="Renamed")
        assert t2.chrome_overrides == {"background_color": "#abc"}


# ═══ TestCompositionServiceChrome ═══════════════════════════════════


class TestCompositionServiceChrome:
    def test_upsert_with_chrome_overrides_stored(self, db, tenant_company):
        core = _make_core(db, chrome=_FULL_CHROME)
        t = _make_template(db, core.id)
        comp = create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"chrome_overrides": {"background_color": "#fff"}},
        )
        assert comp.deltas["chrome_overrides"] == {"background_color": "#fff"}

    def test_upsert_invalid_chrome_in_deltas_rejects(self, db, tenant_company):
        core = _make_core(db)
        t = _make_template(db, core.id)
        with pytest.raises(InvalidCompositionShape):
            create_or_update_composition(
                db,
                tenant_id=tenant_company,
                template_id=t.id,
                deltas={"chrome_overrides": {"padding": "not a dict"}},
            )

    def test_reset_clears_chrome_overrides(self, db, tenant_company):
        core = _make_core(db)
        t = _make_template(db, core.id)
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"chrome_overrides": {"background_color": "#abc"}},
        )
        reset = reset_composition_to_default(db, tenant_company, t.id)
        assert reset.deltas["chrome_overrides"] == {}


# ═══ TestResolverChromeCascade ══════════════════════════════════════


class TestResolverChromeCascade:
    def test_tier1_only_inherits_to_resolved(self, db):
        core = _make_core(db, chrome=_FULL_CHROME)
        _make_template(db, core.id)
        r = resolve_focus(db, template_slug="scheduling-default")
        assert r.resolved_chrome is not None
        assert r.resolved_chrome["background_color"] == "#1a1a1a"
        assert r.resolved_chrome["padding"] == {
            "top": 24,
            "right": 24,
            "bottom": 24,
            "left": 24,
        }
        for field in CHROME_FIELDS:
            assert r.sources["chrome_sources"][field] == "tier1" if (
                _FULL_CHROME[field] is not None or field in _FULL_CHROME
            ) else None

    def test_tier2_single_field_override(self, db):
        core = _make_core(db, chrome=_FULL_CHROME)
        _make_template(
            db,
            core.id,
            chrome_overrides={"background_color": "#ffffff"},
        )
        r = resolve_focus(db, template_slug="scheduling-default")
        assert r.resolved_chrome["background_color"] == "#ffffff"
        assert r.sources["chrome_sources"]["background_color"] == "tier2"
        # Other fields still come from tier1.
        assert r.sources["chrome_sources"]["padding"] == "tier1"
        assert r.resolved_chrome["padding"]["top"] == 24

    def test_tier2_all_fields_override(self, db):
        core = _make_core(db, chrome=_FULL_CHROME)
        tier2_chrome = {
            "background_color": "#abcdef",
            "drop_shadow": None,
            "border": {
                "width": 2,
                "style": "dashed",
                "color": "#000",
                "radius": 4,
            },
            "padding": {"top": 8, "right": 8, "bottom": 8, "left": 8},
        }
        _make_template(db, core.id, chrome_overrides=tier2_chrome)
        r = resolve_focus(db, template_slug="scheduling-default")
        assert r.resolved_chrome == tier2_chrome
        for field in CHROME_FIELDS:
            assert r.sources["chrome_sources"][field] == "tier2"

    def test_three_tier_cascade_different_fields(self, db, tenant_company):
        core = _make_core(db, chrome=_FULL_CHROME)
        t = _make_template(
            db, core.id, chrome_overrides={"background_color": "#tier2"}
        )
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={
                "chrome_overrides": {
                    "padding": {"top": 4, "right": 4, "bottom": 4, "left": 4}
                }
            },
        )
        r = resolve_focus(
            db,
            template_slug="scheduling-default",
            tenant_id=tenant_company,
        )
        assert r.resolved_chrome["background_color"] == "#tier2"
        assert r.sources["chrome_sources"]["background_color"] == "tier2"
        assert r.resolved_chrome["padding"] == {
            "top": 4, "right": 4, "bottom": 4, "left": 4,
        }
        assert r.sources["chrome_sources"]["padding"] == "tier3"
        # drop_shadow still cascades from tier1.
        assert r.sources["chrome_sources"]["drop_shadow"] == "tier1"
        assert r.resolved_chrome["drop_shadow"] is not None

    def test_explicit_null_in_tier2_overrides_tier1(self, db):
        core = _make_core(db, chrome=_FULL_CHROME)
        _make_template(
            db,
            core.id,
            chrome_overrides={"drop_shadow": None},
        )
        r = resolve_focus(db, template_slug="scheduling-default")
        # Key presence with None value wins over tier1's full shadow.
        assert r.resolved_chrome["drop_shadow"] is None
        assert r.sources["chrome_sources"]["drop_shadow"] == "tier2"

    def test_empty_template_chrome_overrides_passes_through(self, db):
        core = _make_core(db, chrome=_FULL_CHROME)
        _make_template(db, core.id, chrome_overrides={})
        r = resolve_focus(db, template_slug="scheduling-default")
        for field in CHROME_FIELDS:
            assert r.sources["chrome_sources"][field] == "tier1"

    def test_composition_without_chrome_resolves_from_tiers_1_2(
        self, db, tenant_company
    ):
        core = _make_core(db, chrome={"background_color": "#tier1"})
        t = _make_template(
            db, core.id, chrome_overrides={"background_color": "#tier2"}
        )
        # Composition with deltas but no chrome_overrides key.
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"hidden_placement_ids": []},
        )
        r = resolve_focus(
            db,
            template_slug="scheduling-default",
            tenant_id=tenant_company,
        )
        assert r.resolved_chrome["background_color"] == "#tier2"
        assert r.sources["chrome_sources"]["background_color"] == "tier2"

    def test_all_fields_none_collapses_to_top_level_none(self, db):
        core = _make_core(db)  # core chrome is {}
        _make_template(db, core.id)
        r = resolve_focus(db, template_slug="scheduling-default")
        # Every chrome field absent in every tier → top-level None.
        assert r.resolved_chrome is None
        for field in CHROME_FIELDS:
            assert r.sources["chrome_sources"][field] is None

    def test_chrome_sources_per_field_shape(self, db):
        core = _make_core(db, chrome={"background_color": "#abc"})
        _make_template(db, core.id)
        r = resolve_focus(db, template_slug="scheduling-default")
        for field in CHROME_FIELDS:
            assert field in r.sources["chrome_sources"]
        assert r.sources["chrome_sources"]["background_color"] == "tier1"
        # The remaining absent fields resolve to None.
        assert r.sources["chrome_sources"]["padding"] is None


# ═══ TestApiChrome ══════════════════════════════════════════════════


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
        self.tenant_token = create_access_token(
            {"sub": self.user.id, "company_id": self.co.id}, realm="tenant"
        )

    @property
    def platform_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.platform_token}"}

    @property
    def tenant_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.tenant_token}",
            "X-Company-Slug": self.co.slug,
        }

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


class TestApiChrome:
    def test_post_cores_with_chrome_succeeds(self, client, api_ctx):
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
            "chrome": _FULL_CHROME,
        }
        r = client.post(
            f"{API_ROOT}/cores", json=body, headers=api_ctx.platform_headers
        )
        assert r.status_code == 201, r.text
        payload = r.json()
        assert payload["chrome"] == _FULL_CHROME

    def test_post_cores_with_invalid_chrome_returns_400(self, client, api_ctx):
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
            "chrome": {"margin": {"top": 0}},
        }
        r = client.post(
            f"{API_ROOT}/cores", json=body, headers=api_ctx.platform_headers
        )
        assert r.status_code in (400, 422), r.text

    def test_post_templates_with_chrome_overrides_succeeds(
        self, client, api_ctx, db
    ):
        core = _make_core(db, chrome=_FULL_CHROME)
        body = {
            "scope": "platform_default",
            "vertical": None,
            "template_slug": "scheduling-default",
            "display_name": "Default",
            "description": None,
            "inherits_from_core_id": core.id,
            "rows": [],
            "canvas_config": {},
            "chrome_overrides": {"background_color": "#abcdef"},
        }
        r = client.post(
            f"{API_ROOT}/templates",
            json=body,
            headers=api_ctx.platform_headers,
        )
        assert r.status_code == 201, r.text
        payload = r.json()
        assert payload["chrome_overrides"] == {"background_color": "#abcdef"}

    def test_get_resolve_includes_resolved_chrome(
        self, client, api_ctx, db
    ):
        core = _make_core(db, chrome=_FULL_CHROME)
        _make_template(db, core.id)
        r = client.get(
            f"{API_ROOT}/resolve",
            params={"template_slug": "scheduling-default"},
            headers=api_ctx.platform_headers,
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["resolved_chrome"] is not None
        assert payload["resolved_chrome"]["background_color"] == "#1a1a1a"
        assert "chrome_sources" in payload["sources"]
        for field in CHROME_FIELDS:
            assert field in payload["sources"]["chrome_sources"]
