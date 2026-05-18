"""Focus Template Inheritance — sub-arc E-1 canonical create-time defaults.

Sub-arc E-1 closes the post-C-2 verification gap: newly-created Tier 2
templates with empty `chrome_overrides` / `substrate` / `typography`
get canonical mockup defaults out of the box. Explicit values are
respected verbatim — defaults only apply on empty-or-null.

Covers:
    TestCreateTemplateE1Defaults — create_template wiring for empty blobs
    TestE1DefaultsModule         — defaults.py constants shape
"""

from __future__ import annotations

import uuid

import pytest

from app.database import SessionLocal
from app.models.focus_composition import FocusComposition
from app.models.focus_core import FocusCore
from app.models.focus_template import FocusTemplate
from app.services.focus_template_inheritance import (
    create_core,
    create_template,
)
from app.services.focus_template_inheritance.defaults import (
    DEFAULT_CHROME_OVERRIDES,
    DEFAULT_SUBSTRATE,
    DEFAULT_TYPOGRAPHY,
    is_empty_blob,
)


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


def _seed_core(db) -> str:
    suffix = uuid.uuid4().hex[:6]
    row = create_core(
        db,
        core_slug=f"e1-core-{suffix}",
        display_name="E1 Test Core",
        registered_component_kind="focus-core",
        registered_component_name="SchedulingKanbanCore",
        default_starting_column=0,
        default_column_span=12,
        default_row_index=0,
        min_column_span=8,
        max_column_span=12,
        canvas_config={},
        chrome={
            "preset": "card",
            "corner_radius": 70,
            "padding_token": "space-3",
            "backdrop_blur": 44,
        },
    )
    return row.id


# ═══ TestE1DefaultsModule ══════════════════════════════════════════


class TestE1DefaultsModule:
    """Shape + values of the defaults module — load-bearing for create_template."""

    def test_default_chrome_overrides_is_empty(self):
        """Empty dict cascades chrome from the inherited Tier 1 core unchanged."""
        assert DEFAULT_CHROME_OVERRIDES == {}

    def test_default_substrate_is_canonical_mockup(self):
        """Matches the apple-pre-liquid-glass mockup canvas substrate."""
        assert DEFAULT_SUBSTRATE == {
            "preset": "morning-warm",
            "intensity": 100,
            "base_token": "surface-base",
            "accent_token_1": "surface-elevated",
            "accent_token_2": None,
        }

    def test_default_typography_is_canonical_mockup(self):
        """Matches the mockup card-title (15px / 600) + body (12px / 500) treatment."""
        assert DEFAULT_TYPOGRAPHY == {
            "preset": "frosted-text",
            "heading_weight": 600,
            "body_weight": 500,
            "heading_color_token": "content-strong",
            "body_color_token": "content-base",
        }

    def test_is_empty_blob_none(self):
        assert is_empty_blob(None) is True

    def test_is_empty_blob_empty_dict(self):
        assert is_empty_blob({}) is True

    def test_is_empty_blob_any_key_means_explicit(self):
        # Even an all-null payload counts as explicit operator intent.
        assert is_empty_blob({"preset": None}) is False
        assert is_empty_blob({"preset": "morning-warm"}) is False


# ═══ TestCreateTemplateE1Defaults ══════════════════════════════════


class TestCreateTemplateE1Defaults:
    """create_template wires defaults.py into the create path."""

    def test_empty_substrate_gets_canonical_default(self, db):
        core_id = _seed_core(db)
        tmpl = create_template(
            db,
            scope="platform_default",
            vertical=None,
            template_slug="e1-empty-substrate",
            display_name="E1 Empty Substrate",
            inherits_from_core_id=core_id,
            rows=[],
            canvas_config={},
            substrate=None,
            typography=None,
            chrome_overrides=None,
        )
        assert dict(tmpl.substrate or {}) == DEFAULT_SUBSTRATE

    def test_empty_typography_gets_canonical_default(self, db):
        core_id = _seed_core(db)
        tmpl = create_template(
            db,
            scope="platform_default",
            vertical=None,
            template_slug="e1-empty-typo",
            display_name="E1 Empty Typo",
            inherits_from_core_id=core_id,
            rows=[],
            canvas_config={},
            substrate=None,
            typography=None,
            chrome_overrides=None,
        )
        assert dict(tmpl.typography or {}) == DEFAULT_TYPOGRAPHY

    def test_empty_chrome_overrides_stays_empty(self, db):
        """chrome_overrides default is {} — the template cascades chrome
        from the inherited core unchanged (NOT a frosted-card override)."""
        core_id = _seed_core(db)
        tmpl = create_template(
            db,
            scope="platform_default",
            vertical=None,
            template_slug="e1-empty-chrome",
            display_name="E1 Empty Chrome",
            inherits_from_core_id=core_id,
            rows=[],
            canvas_config={},
            substrate=None,
            typography=None,
            chrome_overrides=None,
        )
        assert dict(tmpl.chrome_overrides or {}) == {}

    def test_all_three_blobs_empty_dict_get_defaults(self, db):
        """`{}` is treated the same as None — canonical defaults apply."""
        core_id = _seed_core(db)
        tmpl = create_template(
            db,
            scope="platform_default",
            vertical=None,
            template_slug="e1-empty-dicts",
            display_name="E1 Empty Dicts",
            inherits_from_core_id=core_id,
            rows=[],
            canvas_config={},
            substrate={},
            typography={},
            chrome_overrides={},
        )
        assert dict(tmpl.substrate or {}) == DEFAULT_SUBSTRATE
        assert dict(tmpl.typography or {}) == DEFAULT_TYPOGRAPHY
        assert dict(tmpl.chrome_overrides or {}) == {}

    def test_explicit_substrate_respected(self, db):
        """Caller-provided values win — defaults NOT applied."""
        core_id = _seed_core(db)
        explicit = {
            "preset": "morning-cool",
            "intensity": 42,
        }
        tmpl = create_template(
            db,
            scope="platform_default",
            vertical=None,
            template_slug="e1-explicit-substrate",
            display_name="E1 Explicit Substrate",
            inherits_from_core_id=core_id,
            rows=[],
            canvas_config={},
            substrate=explicit,
            typography=None,
            chrome_overrides=None,
        )
        assert dict(tmpl.substrate or {}) == explicit
        # Typography still empty → still gets default
        assert dict(tmpl.typography or {}) == DEFAULT_TYPOGRAPHY

    def test_explicit_typography_respected(self, db):
        core_id = _seed_core(db)
        explicit = {
            "preset": "headline",
            "heading_weight": 700,
        }
        tmpl = create_template(
            db,
            scope="platform_default",
            vertical=None,
            template_slug="e1-explicit-typo",
            display_name="E1 Explicit Typo",
            inherits_from_core_id=core_id,
            rows=[],
            canvas_config={},
            substrate=None,
            typography=explicit,
            chrome_overrides=None,
        )
        assert dict(tmpl.typography or {}).get("preset") == "headline"
        assert dict(tmpl.typography or {}).get("heading_weight") == 700

    def test_explicit_chrome_overrides_respected(self, db):
        """Any chrome_overrides key from operator wins — defaults NOT applied."""
        core_id = _seed_core(db)
        explicit = {"corner_radius": 25}
        tmpl = create_template(
            db,
            scope="platform_default",
            vertical=None,
            template_slug="e1-explicit-chrome",
            display_name="E1 Explicit Chrome",
            inherits_from_core_id=core_id,
            rows=[],
            canvas_config={},
            substrate=None,
            typography=None,
            chrome_overrides=explicit,
        )
        assert dict(tmpl.chrome_overrides or {}) == explicit
