"""Focus Template Inheritance — page-background substrate tests (sub-arc B-4).

Covers the substrate v1 vocabulary added in sub-arc B-4:

    TestSubstrateValidation        — validate_substrate_blob shape rules
    TestSubstratePresetExpansion   — expand_substrate_preset behaviors
    TestTemplateServiceSubstrate   — Tier 2 substrate stored + versioned
    TestCompositionServiceSubstrate — Tier 3 deltas.substrate_overrides round-trip
    TestResolverSubstrateCascade   — preset expansion + Tier 2 → Tier 3 cascade
    TestApiSubstrate               — admin API request/response wiring

Tier 1 (focus_cores) is intentionally substrate-free — substrate is
a Focus-level atmospheric backdrop, not a core composition concern.
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
    SUBSTRATE_FIELDS,
    SUBSTRATE_PRESETS,
    VALID_SUBSTRATE_PRESETS,
    InvalidCompositionShape,
    InvalidSubstrateShape,
    InvalidTemplateShape,
    create_core,
    create_or_update_composition,
    create_template,
    expand_substrate_preset,
    reset_composition_to_default,
    resolve_focus,
    update_template,
    validate_substrate_blob,
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
            name=f"FTI Substrate {suffix}",
            slug=f"ftisub-{suffix}",
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


# ═══ TestSubstrateValidation ═══════════════════════════════════════


class TestSubstrateValidation:
    def test_empty_dict_valid(self):
        validate_substrate_blob({})

    def test_preset_only_valid(self):
        for p in VALID_SUBSTRATE_PRESETS:
            validate_substrate_blob({"preset": p})

    def test_preset_with_intensity_valid(self):
        validate_substrate_blob({"preset": "morning-warm", "intensity": 50})

    def test_custom_with_token_overrides_valid(self):
        validate_substrate_blob(
            {
                "preset": "custom",
                "base_token": "surface-base",
                "accent_token_1": "accent-brass-subtle",
                "accent_token_2": "status-warning-muted",
                "intensity": 65,
            }
        )

    def test_invalid_preset_rejected(self):
        with pytest.raises(InvalidSubstrateShape, match="preset must be one of"):
            validate_substrate_blob({"preset": "midnight"})

    def test_intensity_out_of_bounds_rejected(self):
        with pytest.raises(
            InvalidSubstrateShape, match=r"intensity must be in \[0, 100\]"
        ):
            validate_substrate_blob({"intensity": 101})
        with pytest.raises(
            InvalidSubstrateShape, match=r"intensity must be in \[0, 100\]"
        ):
            validate_substrate_blob({"intensity": -1})

    def test_unknown_key_rejected(self):
        with pytest.raises(InvalidSubstrateShape, match="unknown keys"):
            validate_substrate_blob({"gradient": "rainbow"})

    def test_empty_string_token_rejected(self):
        with pytest.raises(
            InvalidSubstrateShape, match="base_token must be a non-empty string"
        ):
            validate_substrate_blob({"base_token": ""})

    def test_non_dict_rejected(self):
        with pytest.raises(InvalidSubstrateShape, match="substrate must be a dict"):
            validate_substrate_blob("morning-warm")  # type: ignore[arg-type]
        with pytest.raises(InvalidSubstrateShape, match="substrate must be a dict"):
            validate_substrate_blob(None)  # type: ignore[arg-type]

    def test_module_constants_shape(self):
        assert SUBSTRATE_FIELDS == (
            "preset",
            "intensity",
            "base_token",
            "accent_token_1",
            "accent_token_2",
        )
        assert VALID_SUBSTRATE_PRESETS == frozenset(
            {
                "morning-warm",
                "morning-cool",
                "evening-lounge",
                "neutral",
                "custom",
            }
        )


# ═══ TestSubstratePresetExpansion ══════════════════════════════════


class TestSubstratePresetExpansion:
    def test_no_preset_returns_unchanged(self):
        assert expand_substrate_preset({}) == {}
        assert expand_substrate_preset({"intensity": 50}) == {"intensity": 50}

    def test_morning_warm_returns_canonical_defaults(self):
        result = expand_substrate_preset({"preset": "morning-warm"})
        assert result["preset"] == "morning-warm"
        assert result["base_token"] == "surface-base"
        assert result["accent_token_1"] == "accent-brass-subtle"
        assert result["accent_token_2"] == "status-warning-muted"
        assert result["intensity"] == 70

    def test_morning_cool_defaults(self):
        result = expand_substrate_preset({"preset": "morning-cool"})
        assert result["base_token"] == "surface-base"
        assert result["accent_token_1"] == "status-info-muted"
        assert result["accent_token_2"] == "accent-brass-subtle"
        assert result["intensity"] == 55

    def test_evening_lounge_defaults(self):
        result = expand_substrate_preset({"preset": "evening-lounge"})
        assert result["base_token"] == "surface-sunken"
        assert result["accent_token_1"] == "accent-brass-muted"
        assert result["accent_token_2"] == "accent-brass-subtle"
        assert result["intensity"] == 80

    def test_neutral_minimal_defaults(self):
        result = expand_substrate_preset({"preset": "neutral"})
        assert result["base_token"] == "surface-base"
        assert result["accent_token_1"] is None
        assert result["accent_token_2"] is None
        assert result["intensity"] == 15

    def test_custom_returns_unchanged(self):
        blob = {"preset": "custom", "base_token": "my-token"}
        assert expand_substrate_preset(blob) == blob

    def test_overrides_preserved_on_top_of_preset(self):
        result = expand_substrate_preset(
            {"preset": "morning-warm", "intensity": 25}
        )
        # Overlay wins for intensity; preset defaults supply the rest.
        assert result["intensity"] == 25
        assert result["base_token"] == "surface-base"
        assert result["accent_token_1"] == "accent-brass-subtle"


# ═══ TestTemplateServiceSubstrate ══════════════════════════════════


class TestTemplateServiceSubstrate:
    def test_create_with_substrate_stored(self, db):
        substrate = {"preset": "morning-warm", "intensity": 40}
        core = _make_core(db)
        t = _make_template(db, core.id, substrate=substrate)
        assert t.substrate == substrate

    def test_create_default_empty_substrate(self, db):
        core = _make_core(db)
        t = _make_template(db, core.id)
        assert t.substrate == {}

    def test_create_invalid_substrate_rejected(self, db):
        core = _make_core(db)
        with pytest.raises(InvalidTemplateShape, match="preset must be one of"):
            _make_template(db, core.id, substrate={"preset": "splash"})

    def test_update_version_bump_preserves_substrate(self, db):
        core = _make_core(db)
        t1 = _make_template(
            db, core.id, substrate={"preset": "morning-warm"}
        )
        t2 = update_template(
            db, t1.id, display_name="Renamed"
        )
        # Substrate preserved when not passed to update.
        assert t2.substrate == {"preset": "morning-warm"}
        assert t2.version == t1.version + 1

    def test_update_can_replace_substrate(self, db):
        core = _make_core(db)
        t1 = _make_template(
            db, core.id, substrate={"preset": "morning-warm"}
        )
        t2 = update_template(
            db, t1.id, substrate={"preset": "evening-lounge", "intensity": 90}
        )
        assert t2.substrate == {"preset": "evening-lounge", "intensity": 90}


# ═══ TestCompositionServiceSubstrate ═══════════════════════════════


class TestCompositionServiceSubstrate:
    def test_upsert_with_substrate_overrides_stored(self, db, tenant_company):
        core = _make_core(db)
        t = _make_template(db, core.id, substrate={"preset": "morning-warm"})
        comp = create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"substrate_overrides": {"intensity": 95}},
        )
        assert comp.deltas["substrate_overrides"] == {"intensity": 95}

    def test_upsert_invalid_substrate_overrides_rejected(
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
                deltas={"substrate_overrides": {"preset": "midnight"}},
            )

    def test_reset_clears_substrate_overrides(self, db, tenant_company):
        core = _make_core(db)
        t = _make_template(db, core.id, substrate={"preset": "morning-warm"})
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"substrate_overrides": {"preset": "evening-lounge"}},
        )
        reset = reset_composition_to_default(db, tenant_company, t.id)
        assert reset.deltas["substrate_overrides"] == {}


# ═══ TestResolverSubstrateCascade ══════════════════════════════════


class TestResolverSubstrateCascade:
    def test_tier2_morning_warm_only(self, db):
        core = _make_core(db)
        _make_template(db, core.id, substrate={"preset": "morning-warm"})
        r = resolve_focus(db, template_slug="scheduling-default")
        assert r.resolved_substrate is not None
        assert r.resolved_substrate["preset"] == "morning-warm"
        assert r.resolved_substrate["base_token"] == "surface-base"
        assert r.resolved_substrate["intensity"] == 70
        # Every field provenance should be tier2 (or None for fields
        # not declared by the preset — but morning-warm declares all).
        for field in ("preset", "intensity", "base_token", "accent_token_1", "accent_token_2"):
            assert r.sources["substrate_sources"][field] == "tier2"

    def test_tier2_morning_warm_plus_tier3_intensity_override(
        self, db, tenant_company
    ):
        core = _make_core(db)
        t = _make_template(
            db, core.id, substrate={"preset": "morning-warm"}
        )
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"substrate_overrides": {"intensity": 50}},
        )
        r = resolve_focus(
            db, template_slug="scheduling-default", tenant_id=tenant_company
        )
        assert r.resolved_substrate["intensity"] == 50
        assert r.resolved_substrate["base_token"] == "surface-base"
        assert r.sources["substrate_sources"]["intensity"] == "tier3"
        assert r.sources["substrate_sources"]["base_token"] == "tier2"

    def test_tier3_preset_replaces_tier2_preset_via_expansion(
        self, db, tenant_company
    ):
        core = _make_core(db)
        t = _make_template(
            db, core.id, substrate={"preset": "morning-warm"}
        )
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"substrate_overrides": {"preset": "evening-lounge"}},
        )
        r = resolve_focus(
            db, template_slug="scheduling-default", tenant_id=tenant_company
        )
        # Tier 3's preset expands to evening-lounge defaults; those
        # win at every overlapping field per cascade.
        assert r.resolved_substrate["preset"] == "evening-lounge"
        assert r.resolved_substrate["base_token"] == "surface-sunken"
        assert r.resolved_substrate["accent_token_1"] == "accent-brass-muted"
        assert r.resolved_substrate["intensity"] == 80
        for field in (
            "preset", "intensity", "base_token",
            "accent_token_1", "accent_token_2",
        ):
            assert r.sources["substrate_sources"][field] == "tier3"

    def test_tier3_specific_field_overrides_tier2_preset(
        self, db, tenant_company
    ):
        core = _make_core(db)
        t = _make_template(
            db, core.id, substrate={"preset": "morning-warm"}
        )
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"substrate_overrides": {"base_token": "my-custom-token"}},
        )
        r = resolve_focus(
            db, template_slug="scheduling-default", tenant_id=tenant_company
        )
        assert r.resolved_substrate["base_token"] == "my-custom-token"
        # Intensity still inherited from tier2's morning-warm preset.
        assert r.resolved_substrate["intensity"] == 70
        assert r.sources["substrate_sources"]["base_token"] == "tier3"
        assert r.sources["substrate_sources"]["intensity"] == "tier2"

    def test_custom_with_tokens_no_preset_defaults(self, db):
        core = _make_core(db)
        _make_template(
            db,
            core.id,
            substrate={
                "preset": "custom",
                "base_token": "tok-a",
                "accent_token_1": "tok-b",
                "intensity": 33,
            },
        )
        r = resolve_focus(db, template_slug="scheduling-default")
        assert r.resolved_substrate["preset"] == "custom"
        assert r.resolved_substrate["base_token"] == "tok-a"
        assert r.resolved_substrate["accent_token_1"] == "tok-b"
        # accent_token_2 wasn't declared — None at every tier.
        assert r.resolved_substrate["accent_token_2"] is None
        assert r.resolved_substrate["intensity"] == 33

    def test_both_tiers_different_fields(self, db, tenant_company):
        core = _make_core(db)
        t = _make_template(
            db,
            core.id,
            substrate={"preset": "custom", "base_token": "tok-a"},
        )
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={
                "substrate_overrides": {
                    "preset": "custom",
                    "accent_token_1": "tok-b",
                },
            },
        )
        r = resolve_focus(
            db, template_slug="scheduling-default", tenant_id=tenant_company
        )
        # base_token from tier2 (custom doesn't expand defaults).
        assert r.resolved_substrate["base_token"] == "tok-a"
        assert r.sources["substrate_sources"]["base_token"] == "tier2"
        assert r.resolved_substrate["accent_token_1"] == "tok-b"
        assert r.sources["substrate_sources"]["accent_token_1"] == "tier3"
        # tier3 declared preset="custom" too, so preset source = tier3.
        assert r.sources["substrate_sources"]["preset"] == "tier3"

    def test_substrate_sources_per_field_tier(self, db, tenant_company):
        core = _make_core(db)
        t = _make_template(db, core.id, substrate={"preset": "morning-warm"})
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"substrate_overrides": {"intensity": 100}},
        )
        r = resolve_focus(
            db, template_slug="scheduling-default", tenant_id=tenant_company
        )
        for field in SUBSTRATE_FIELDS:
            assert field in r.sources["substrate_sources"]

    def test_empty_at_both_tiers_collapses_to_none(self, db):
        core = _make_core(db)
        _make_template(db, core.id)
        r = resolve_focus(db, template_slug="scheduling-default")
        assert r.resolved_substrate is None
        for field in SUBSTRATE_FIELDS:
            assert r.sources["substrate_sources"][field] is None

    def test_resolver_does_not_validate_token_existence(self, db):
        # Service layer accepts any non-empty string for token fields.
        # Resolver does not validate against any theme — that's a
        # consumer-side concern.
        core = _make_core(db)
        _make_template(
            db,
            core.id,
            substrate={"preset": "custom", "base_token": "made-up-token-name"},
        )
        r = resolve_focus(db, template_slug="scheduling-default")
        assert r.resolved_substrate["base_token"] == "made-up-token-name"

    def test_expand_substrate_preset_runs_before_cascade_not_after(
        self, db, tenant_company
    ):
        # If preset expansion ran AFTER cascade, a tier3 preset=evening
        # against a tier2 intensity=99 would resolve intensity=99
        # (tier2 wins per cascade, then preset expands — but expansion
        # is per-tier-before-cascade, so tier3 contributes its
        # expanded form's intensity=80 to the cascade).
        core = _make_core(db)
        t = _make_template(
            db, core.id, substrate={"preset": "custom", "intensity": 99}
        )
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"substrate_overrides": {"preset": "evening-lounge"}},
        )
        r = resolve_focus(
            db, template_slug="scheduling-default", tenant_id=tenant_company
        )
        # Tier 3's preset expansion gives intensity=80; tier 2's
        # intensity=99 is also present, but tier 3 wins per cascade.
        assert r.resolved_substrate["intensity"] == 80
        assert r.sources["substrate_sources"]["intensity"] == "tier3"


# ═══ TestApiSubstrate ══════════════════════════════════════════════


class _ApiCtx:
    def __init__(self):
        from app.models.role import Role
        from app.models.user import User

        self.s = SessionLocal()
        suffix = uuid.uuid4().hex[:6]
        self.suffix = suffix
        self.co = Company(
            id=str(uuid.uuid4()),
            name=f"FTI Substrate API {suffix}",
            slug=f"ftisuba-{suffix}",
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
            email=f"substrate-{suffix}@fti.test",
            hashed_password="x",
            first_name="S",
            last_name="A",
            role_id=self.role.id,
            is_active=True,
        )
        self.s.add(self.user)
        self.platform_admin = PlatformUser(
            id=str(uuid.uuid4()),
            email=f"platform-substrate-{suffix}@bridgeable.test",
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


class TestApiSubstrate:
    def test_post_templates_with_substrate_succeeds(
        self, client, api_ctx, db
    ):
        core = _make_core(db)
        body = {
            "scope": "platform_default",
            "vertical": None,
            "template_slug": "substrate-api-template",
            "display_name": "Substrate API",
            "inherits_from_core_id": core.id,
            "rows": [],
            "canvas_config": {},
            "chrome_overrides": {},
            "substrate": {"preset": "morning-warm", "intensity": 60},
        }
        r = client.post(
            f"{API_ROOT}/templates",
            json=body,
            headers=api_ctx.platform_headers,
        )
        assert r.status_code == 201, r.text
        payload = r.json()
        assert payload["substrate"] == {
            "preset": "morning-warm",
            "intensity": 60,
        }

    def test_post_templates_invalid_substrate_rejected(
        self, client, api_ctx, db
    ):
        core = _make_core(db)
        body = {
            "scope": "platform_default",
            "vertical": None,
            "template_slug": "substrate-api-bad",
            "display_name": "Bad",
            "inherits_from_core_id": core.id,
            "rows": [],
            "canvas_config": {},
            "chrome_overrides": {},
            "substrate": {"preset": "midnight"},
        }
        r = client.post(
            f"{API_ROOT}/templates",
            json=body,
            headers=api_ctx.platform_headers,
        )
        assert r.status_code in (400, 422), r.text

    def test_put_templates_substrate_update_succeeds(
        self, client, api_ctx, db
    ):
        core = _make_core(db)
        t = _make_template(
            db, core.id, substrate={"preset": "morning-warm"}
        )
        r = client.put(
            f"{API_ROOT}/templates/{t.id}",
            json={"substrate": {"preset": "evening-lounge"}},
            headers=api_ctx.platform_headers,
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["substrate"] == {"preset": "evening-lounge"}

    def test_get_resolve_returns_resolved_substrate(
        self, client, api_ctx, db
    ):
        core = _make_core(db)
        _make_template(
            db, core.id, substrate={"preset": "morning-warm"}
        )
        r = client.get(
            f"{API_ROOT}/resolve",
            params={"template_slug": "scheduling-default"},
            headers=api_ctx.platform_headers,
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["resolved_substrate"] is not None
        assert payload["resolved_substrate"]["preset"] == "morning-warm"
        assert payload["resolved_substrate"]["base_token"] == "surface-base"
        assert "substrate_sources" in payload["sources"]
        for field in SUBSTRATE_FIELDS:
            assert field in payload["sources"]["substrate_sources"]


def test_substrate_presets_module_constant_shape():
    # Smoke-test the canonical preset dictionary as a module constant
    # so downstream consumers can assume key set + types.
    assert set(SUBSTRATE_PRESETS.keys()) == VALID_SUBSTRATE_PRESETS
    # Each non-custom preset declares non-empty defaults; custom is {}.
    for name, defaults in SUBSTRATE_PRESETS.items():
        if name == "custom":
            assert defaults == {}
        else:
            assert isinstance(defaults, dict)
            assert len(defaults) >= 1
