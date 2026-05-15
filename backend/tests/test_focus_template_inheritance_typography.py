"""Focus Template Inheritance — typography substrate tests (sub-arc B-5).

Covers the typography v1 vocabulary added in sub-arc B-5:

    TestTypographyValidation        — validate_typography_blob shape rules
    TestTypographyPresetExpansion   — expand_typography_preset behaviors
    TestTemplateServiceTypography   — Tier 2 typography stored + versioned
    TestCompositionServiceTypography — Tier 3 deltas.typography_overrides round-trip
    TestResolverTypographyCascade   — preset expansion + Tier 2 → Tier 3 cascade
    TestApiTypography               — admin API request/response wiring

Tier 1 (focus_cores) is intentionally typography-free — typography is
a Focus-level concern, not a core composition concern. All tests
share the B-1 clean-slate autouse fixture pattern.
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
    TYPOGRAPHY_FIELDS,
    TYPOGRAPHY_PRESETS,
    VALID_TYPOGRAPHY_PRESETS,
    InvalidCompositionShape,
    InvalidTemplateShape,
    InvalidTypographyShape,
    create_core,
    create_or_update_composition,
    create_template,
    expand_typography_preset,
    reset_composition_to_default,
    resolve_focus,
    update_template,
    validate_typography_blob,
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
            name=f"FTI Typography {suffix}",
            slug=f"ftityp-{suffix}",
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


# ═══ TestTypographyValidation ══════════════════════════════════════


class TestTypographyValidation:
    def test_empty_dict_valid(self):
        validate_typography_blob({})

    def test_preset_only_valid(self):
        for p in VALID_TYPOGRAPHY_PRESETS:
            validate_typography_blob({"preset": p})

    def test_preset_with_weight_valid(self):
        validate_typography_blob({"preset": "card-text", "heading_weight": 600})

    def test_custom_with_all_fields_valid(self):
        validate_typography_blob(
            {
                "preset": "custom",
                "heading_weight": 700,
                "heading_color_token": "content-strong",
                "body_weight": 400,
                "body_color_token": "content-base",
            }
        )

    def test_invalid_preset_rejected(self):
        with pytest.raises(InvalidTypographyShape, match="preset must be one of"):
            validate_typography_blob({"preset": "bold-stuff"})

    def test_weight_out_of_bounds_rejected(self):
        with pytest.raises(
            InvalidTypographyShape,
            match=r"heading_weight must be in \[400, 900\]",
        ):
            validate_typography_blob({"heading_weight": 399})
        with pytest.raises(
            InvalidTypographyShape,
            match=r"body_weight must be in \[400, 900\]",
        ):
            validate_typography_blob({"body_weight": 901})
        with pytest.raises(
            InvalidTypographyShape,
            match=r"heading_weight must be in \[400, 900\]",
        ):
            validate_typography_blob({"heading_weight": -1})

    def test_weight_bool_rejected(self):
        # bool is a subclass of int — must be explicitly rejected.
        with pytest.raises(
            InvalidTypographyShape,
            match="heading_weight must be an integer",
        ):
            validate_typography_blob({"heading_weight": True})

    def test_weight_float_rejected(self):
        with pytest.raises(
            InvalidTypographyShape,
            match="body_weight must be an integer",
        ):
            validate_typography_blob({"body_weight": 500.5})

    def test_unknown_key_rejected(self):
        with pytest.raises(InvalidTypographyShape, match="unknown keys"):
            validate_typography_blob({"font_family": "Plex Sans"})

    def test_empty_string_token_rejected(self):
        with pytest.raises(
            InvalidTypographyShape,
            match="heading_color_token must be a non-empty string",
        ):
            validate_typography_blob({"heading_color_token": ""})

    def test_non_dict_rejected(self):
        with pytest.raises(
            InvalidTypographyShape, match="typography must be a dict"
        ):
            validate_typography_blob("card-text")  # type: ignore[arg-type]
        with pytest.raises(
            InvalidTypographyShape, match="typography must be a dict"
        ):
            validate_typography_blob(None)  # type: ignore[arg-type]

    def test_module_constants_shape(self):
        assert TYPOGRAPHY_FIELDS == (
            "preset",
            "heading_weight",
            "heading_color_token",
            "body_weight",
            "body_color_token",
        )
        assert VALID_TYPOGRAPHY_PRESETS == frozenset(
            {"card-text", "frosted-text", "headline", "custom"}
        )


# ═══ TestTypographyPresetExpansion ═════════════════════════════════


class TestTypographyPresetExpansion:
    def test_no_preset_returns_unchanged(self):
        assert expand_typography_preset({}) == {}
        assert expand_typography_preset({"heading_weight": 500}) == {
            "heading_weight": 500
        }

    def test_none_preset_returns_unchanged(self):
        # Explicit preset=None means "no preset; inherit from parent."
        assert expand_typography_preset({"preset": None}) == {"preset": None}

    def test_card_text_canonical_defaults(self):
        result = expand_typography_preset({"preset": "card-text"})
        assert result["preset"] == "card-text"
        assert result["heading_weight"] == 500
        assert result["heading_color_token"] == "content-strong"
        assert result["body_weight"] == 400
        assert result["body_color_token"] == "content-base"

    def test_frosted_text_canonical_defaults(self):
        result = expand_typography_preset({"preset": "frosted-text"})
        assert result["heading_weight"] == 600
        assert result["heading_color_token"] == "content-strong"
        assert result["body_weight"] == 500
        assert result["body_color_token"] == "content-base"

    def test_headline_canonical_defaults(self):
        result = expand_typography_preset({"preset": "headline"})
        assert result["heading_weight"] == 700
        assert result["heading_color_token"] == "content-strong"
        assert result["body_weight"] == 500
        assert result["body_color_token"] == "content-base"

    def test_custom_returns_unchanged(self):
        blob = {"preset": "custom", "heading_weight": 900}
        assert expand_typography_preset(blob) == blob

    def test_overrides_preserved_on_top_of_preset(self):
        result = expand_typography_preset(
            {"preset": "card-text", "heading_weight": 800}
        )
        # Overlay wins for heading_weight; preset defaults supply the rest.
        assert result["heading_weight"] == 800
        assert result["body_weight"] == 400
        assert result["heading_color_token"] == "content-strong"


# ═══ TestTemplateServiceTypography ═════════════════════════════════


class TestTemplateServiceTypography:
    def test_create_with_typography_stored(self, db):
        typography = {"preset": "card-text", "heading_weight": 600}
        core = _make_core(db)
        t = _make_template(db, core.id, typography=typography)
        assert t.typography == typography

    def test_create_default_empty_typography(self, db):
        core = _make_core(db)
        t = _make_template(db, core.id)
        assert t.typography == {}

    def test_create_invalid_typography_rejected(self, db):
        core = _make_core(db)
        with pytest.raises(InvalidTemplateShape, match="preset must be one of"):
            _make_template(db, core.id, typography={"preset": "bold-stuff"})

    def test_update_version_bump_preserves_typography(self, db):
        core = _make_core(db)
        t1 = _make_template(
            db, core.id, typography={"preset": "card-text"}
        )
        t2 = update_template(db, t1.id, display_name="Renamed")
        # Typography preserved when not passed to update.
        assert t2.typography == {"preset": "card-text"}
        assert t2.version == t1.version + 1

    def test_update_can_replace_typography(self, db):
        core = _make_core(db)
        t1 = _make_template(
            db, core.id, typography={"preset": "card-text"}
        )
        t2 = update_template(
            db, t1.id, typography={"preset": "headline", "heading_weight": 800}
        )
        assert t2.typography == {"preset": "headline", "heading_weight": 800}


# ═══ TestCompositionServiceTypography ══════════════════════════════


class TestCompositionServiceTypography:
    def test_upsert_with_typography_overrides_stored(self, db, tenant_company):
        core = _make_core(db)
        t = _make_template(db, core.id, typography={"preset": "card-text"})
        comp = create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"typography_overrides": {"heading_weight": 800}},
        )
        assert comp.deltas["typography_overrides"] == {"heading_weight": 800}

    def test_upsert_invalid_typography_overrides_rejected(
        self, db, tenant_company
    ):
        core = _make_core(db)
        t = _make_template(db, core.id)
        with pytest.raises(
            InvalidCompositionShape, match="preset must be one of"
        ):
            create_or_update_composition(
                db,
                tenant_id=tenant_company,
                template_id=t.id,
                deltas={"typography_overrides": {"preset": "bold-stuff"}},
            )

    def test_reset_clears_typography_overrides(self, db, tenant_company):
        core = _make_core(db)
        t = _make_template(db, core.id, typography={"preset": "card-text"})
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"typography_overrides": {"preset": "headline"}},
        )
        reset = reset_composition_to_default(db, tenant_company, t.id)
        assert reset.deltas["typography_overrides"] == {}


# ═══ TestResolverTypographyCascade ═════════════════════════════════


class TestResolverTypographyCascade:
    def test_tier2_card_text_only(self, db):
        core = _make_core(db)
        _make_template(db, core.id, typography={"preset": "card-text"})
        r = resolve_focus(db, template_slug="scheduling-default")
        assert r.resolved_typography is not None
        assert r.resolved_typography["preset"] == "card-text"
        assert r.resolved_typography["heading_weight"] == 500
        assert r.resolved_typography["body_weight"] == 400
        # Every field provenance should be tier2 (card-text declares all).
        for field in (
            "preset",
            "heading_weight",
            "heading_color_token",
            "body_weight",
            "body_color_token",
        ):
            assert r.sources["typography_sources"][field] == "tier2"

    def test_tier2_frosted_plus_tier3_heading_weight_override(
        self, db, tenant_company
    ):
        core = _make_core(db)
        t = _make_template(
            db, core.id, typography={"preset": "frosted-text"}
        )
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"typography_overrides": {"heading_weight": 700}},
        )
        r = resolve_focus(
            db, template_slug="scheduling-default", tenant_id=tenant_company
        )
        assert r.resolved_typography["heading_weight"] == 700
        # body_weight still inherited from tier2's frosted-text preset.
        assert r.resolved_typography["body_weight"] == 500
        assert r.sources["typography_sources"]["heading_weight"] == "tier3"
        assert r.sources["typography_sources"]["body_weight"] == "tier2"

    def test_tier3_preset_replaces_tier2_preset_via_expansion(
        self, db, tenant_company
    ):
        core = _make_core(db)
        t = _make_template(
            db, core.id, typography={"preset": "card-text"}
        )
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"typography_overrides": {"preset": "headline"}},
        )
        r = resolve_focus(
            db, template_slug="scheduling-default", tenant_id=tenant_company
        )
        # Tier 3's preset expands to headline defaults; those win at
        # every overlapping field per cascade.
        assert r.resolved_typography["preset"] == "headline"
        assert r.resolved_typography["heading_weight"] == 700
        assert r.resolved_typography["body_weight"] == 500
        for field in (
            "preset",
            "heading_weight",
            "heading_color_token",
            "body_weight",
            "body_color_token",
        ):
            assert r.sources["typography_sources"][field] == "tier3"

    def test_tier3_specific_field_overrides_tier2_preset(
        self, db, tenant_company
    ):
        core = _make_core(db)
        t = _make_template(
            db, core.id, typography={"preset": "card-text"}
        )
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={
                "typography_overrides": {"body_color_token": "content-muted"}
            },
        )
        r = resolve_focus(
            db, template_slug="scheduling-default", tenant_id=tenant_company
        )
        assert r.resolved_typography["body_color_token"] == "content-muted"
        # heading_weight still inherited from tier2's card-text preset.
        assert r.resolved_typography["heading_weight"] == 500
        assert r.sources["typography_sources"]["body_color_token"] == "tier3"
        assert r.sources["typography_sources"]["heading_weight"] == "tier2"

    def test_custom_with_tokens_no_preset_defaults(self, db):
        core = _make_core(db)
        _make_template(
            db,
            core.id,
            typography={
                "preset": "custom",
                "heading_weight": 800,
                "heading_color_token": "content-strong",
            },
        )
        r = resolve_focus(db, template_slug="scheduling-default")
        assert r.resolved_typography["preset"] == "custom"
        assert r.resolved_typography["heading_weight"] == 800
        assert r.resolved_typography["heading_color_token"] == "content-strong"
        # body_weight + body_color_token weren't declared — None at every tier.
        assert r.resolved_typography["body_weight"] is None
        assert r.resolved_typography["body_color_token"] is None

    def test_both_tiers_different_fields(self, db, tenant_company):
        core = _make_core(db)
        t = _make_template(
            db,
            core.id,
            typography={"preset": "custom", "heading_weight": 800},
        )
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={
                "typography_overrides": {
                    "preset": "custom",
                    "body_weight": 400,
                },
            },
        )
        r = resolve_focus(
            db, template_slug="scheduling-default", tenant_id=tenant_company
        )
        # heading_weight from tier2 (custom doesn't expand defaults).
        assert r.resolved_typography["heading_weight"] == 800
        assert r.sources["typography_sources"]["heading_weight"] == "tier2"
        assert r.resolved_typography["body_weight"] == 400
        assert r.sources["typography_sources"]["body_weight"] == "tier3"
        # tier3 declared preset="custom" too, so preset source = tier3.
        assert r.sources["typography_sources"]["preset"] == "tier3"

    def test_typography_sources_per_field_tier(self, db, tenant_company):
        core = _make_core(db)
        t = _make_template(db, core.id, typography={"preset": "card-text"})
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"typography_overrides": {"heading_weight": 900}},
        )
        r = resolve_focus(
            db, template_slug="scheduling-default", tenant_id=tenant_company
        )
        for field in TYPOGRAPHY_FIELDS:
            assert field in r.sources["typography_sources"]

    def test_empty_at_both_tiers_collapses_to_none(self, db):
        core = _make_core(db)
        _make_template(db, core.id)
        r = resolve_focus(db, template_slug="scheduling-default")
        assert r.resolved_typography is None
        for field in TYPOGRAPHY_FIELDS:
            assert r.sources["typography_sources"][field] is None

    def test_resolver_does_not_validate_token_existence(self, db):
        # Service layer accepts any non-empty string for token fields.
        # Resolver does not validate against any theme — that's a
        # consumer-side concern.
        core = _make_core(db)
        _make_template(
            db,
            core.id,
            typography={
                "preset": "custom",
                "heading_color_token": "made-up-token-name",
            },
        )
        r = resolve_focus(db, template_slug="scheduling-default")
        assert (
            r.resolved_typography["heading_color_token"] == "made-up-token-name"
        )

    def test_expand_typography_preset_runs_before_cascade_not_after(
        self, db, tenant_company
    ):
        # If preset expansion ran AFTER cascade, a tier3 preset=headline
        # against a tier2 heading_weight=999 (not possible — out of
        # range) would resolve heading_weight=999 (tier2 wins, then
        # preset expands). But expansion is per-tier-before-cascade,
        # so tier3 contributes its expanded form's heading_weight=700
        # to the cascade.
        core = _make_core(db)
        t = _make_template(
            db, core.id, typography={"preset": "custom", "heading_weight": 900}
        )
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"typography_overrides": {"preset": "headline"}},
        )
        r = resolve_focus(
            db, template_slug="scheduling-default", tenant_id=tenant_company
        )
        # Tier 3's preset expansion gives heading_weight=700; tier 2's
        # heading_weight=900 is also present, but tier 3 wins per cascade.
        assert r.resolved_typography["heading_weight"] == 700
        assert r.sources["typography_sources"]["heading_weight"] == "tier3"


# ═══ TestApiTypography ═════════════════════════════════════════════


class _ApiCtx:
    def __init__(self):
        from app.models.role import Role
        from app.models.user import User

        self.s = SessionLocal()
        suffix = uuid.uuid4().hex[:6]
        self.suffix = suffix
        self.co = Company(
            id=str(uuid.uuid4()),
            name=f"FTI Typography API {suffix}",
            slug=f"ftitypa-{suffix}",
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
            email=f"typography-{suffix}@fti.test",
            hashed_password="x",
            first_name="T",
            last_name="A",
            role_id=self.role.id,
            is_active=True,
        )
        self.s.add(self.user)
        self.platform_admin = PlatformUser(
            id=str(uuid.uuid4()),
            email=f"platform-typography-{suffix}@bridgeable.test",
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


class TestApiTypography:
    def test_post_templates_with_typography_succeeds(
        self, client, api_ctx, db
    ):
        core = _make_core(db)
        body = {
            "scope": "platform_default",
            "vertical": None,
            "template_slug": "typography-api-template",
            "display_name": "Typography API",
            "inherits_from_core_id": core.id,
            "rows": [],
            "canvas_config": {},
            "chrome_overrides": {},
            "substrate": {},
            "typography": {"preset": "card-text", "heading_weight": 600},
        }
        r = client.post(
            f"{API_ROOT}/templates",
            json=body,
            headers=api_ctx.platform_headers,
        )
        assert r.status_code == 201, r.text
        payload = r.json()
        assert payload["typography"] == {
            "preset": "card-text",
            "heading_weight": 600,
        }

    def test_post_templates_invalid_typography_rejected(
        self, client, api_ctx, db
    ):
        core = _make_core(db)
        body = {
            "scope": "platform_default",
            "vertical": None,
            "template_slug": "typography-api-bad",
            "display_name": "Bad",
            "inherits_from_core_id": core.id,
            "rows": [],
            "canvas_config": {},
            "chrome_overrides": {},
            "substrate": {},
            "typography": {"preset": "bold-stuff"},
        }
        r = client.post(
            f"{API_ROOT}/templates",
            json=body,
            headers=api_ctx.platform_headers,
        )
        assert r.status_code in (400, 422), r.text

    def test_put_templates_typography_update_succeeds(
        self, client, api_ctx, db
    ):
        core = _make_core(db)
        t = _make_template(
            db, core.id, typography={"preset": "card-text"}
        )
        r = client.put(
            f"{API_ROOT}/templates/{t.id}",
            json={"typography": {"preset": "headline"}},
            headers=api_ctx.platform_headers,
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["typography"] == {"preset": "headline"}

    def test_get_resolve_returns_resolved_typography(
        self, client, api_ctx, db
    ):
        core = _make_core(db)
        _make_template(
            db, core.id, typography={"preset": "card-text"}
        )
        r = client.get(
            f"{API_ROOT}/resolve",
            params={"template_slug": "scheduling-default"},
            headers=api_ctx.platform_headers,
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["resolved_typography"] is not None
        assert payload["resolved_typography"]["preset"] == "card-text"
        assert payload["resolved_typography"]["heading_weight"] == 500
        assert "typography_sources" in payload["sources"]
        for field in TYPOGRAPHY_FIELDS:
            assert field in payload["sources"]["typography_sources"]


def test_typography_presets_module_constant_shape():
    # Smoke-test the canonical preset dictionary as a module constant
    # so downstream consumers can assume key set + types.
    assert set(TYPOGRAPHY_PRESETS.keys()) == VALID_TYPOGRAPHY_PRESETS
    # Each non-custom preset declares non-empty defaults; custom is {}.
    for name, defaults in TYPOGRAPHY_PRESETS.items():
        if name == "custom":
            assert defaults == {}
        else:
            assert isinstance(defaults, dict)
            assert len(defaults) >= 1
