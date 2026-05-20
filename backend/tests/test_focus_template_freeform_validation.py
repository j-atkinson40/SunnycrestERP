"""FF-1 — free-form Focus canvas placement validator tests.

Exercises the extended `_validate_rows` + `_validate_placement` logic
against the canonical free-form placement shape (x / y / width / height
/ z_index in pixels) introduced in sub-arc FF-1, plus regression
coverage that the existing grid shape continues to validate unchanged.

Sub-arc reference: see locked decisions Q-1 through Q-5, Q-23, Q-24,
Q-25 in `docs/investigations/2026-05-20-free-form-focus-canvas.md`.

Class-of-bug guard: pure-JSONB extension means both shapes coexist in
the same `focus_templates.rows` column. The validator dispatches on
field presence (x/y/width/height → freeform; otherwise → grid).
Template-level consistency rejects mixed-shape templates so a single
template never carries both shapes simultaneously.
"""

from __future__ import annotations

import uuid

import pytest

from app.database import SessionLocal
from app.models.focus_composition import FocusComposition
from app.models.focus_core import FocusCore
from app.models.focus_template import FocusTemplate
from app.services.focus_template_inheritance.focus_cores_service import (
    create_core,
)
from app.services.focus_template_inheritance.focus_templates_service import (
    DEFAULT_CANVAS_HEIGHT,
    DEFAULT_CANVAS_WIDTH,
    InvalidTemplateShape,
    _validate_rows,
    create_template,
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


def _make_core(db) -> FocusCore:
    return create_core(
        db,
        core_slug=f"kb-{uuid.uuid4().hex[:6]}",
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


def _freeform_row(placements: list[dict]) -> list[dict]:
    """Wrap placements in the minimum row envelope. column_count is
    irrelevant for free-form placements but the row-level validator
    still requires it (rows are the row envelope; FF-2's canvas
    substrate replaces row-as-layout-axis semantically but FF-1 keeps
    the JSONB envelope identical for back-compat)."""
    return [
        {
            "row_index": 0,
            "column_count": 12,
            "placements": placements,
        }
    ]


def _grid_placement(**overrides) -> dict:
    base = {
        "placement_id": f"p-{uuid.uuid4().hex[:6]}",
        "component_kind": "widget",
        "component_name": "day-strip-widget",
        "starting_column": 0,
        "column_span": 4,
    }
    base.update(overrides)
    return base


def _freeform_placement(**overrides) -> dict:
    base = {
        "placement_id": f"p-{uuid.uuid4().hex[:6]}",
        "component_kind": "widget",
        "component_name": "day-strip-widget",
        "x": 100,
        "y": 100,
        "width": 320,
        "height": 180,
    }
    base.update(overrides)
    return base


# ═══ Free-form acceptance ════════════════════════════════════════


class TestFreeFormValidation:
    def test_accepts_valid_freeform_placement(self, db):
        core = _make_core(db)
        rows = _freeform_row([_freeform_placement()])
        _validate_rows(rows, core=core, canvas_config={"width": 1200, "height": 800})

    def test_accepts_freeform_with_z_index(self, db):
        core = _make_core(db)
        rows = _freeform_row([_freeform_placement(z_index=5)])
        _validate_rows(rows, core=core, canvas_config={"width": 1200, "height": 800})

    def test_handles_missing_z_index_defaults_zero(self, db):
        core = _make_core(db)
        # z_index absent → defaults 0 inside validator. No exception.
        placement = _freeform_placement()
        assert "z_index" not in placement
        rows = _freeform_row([placement])
        _validate_rows(rows, core=core, canvas_config={"width": 1200, "height": 800})

    def test_accepts_float_dimensions(self, db):
        """x/y/width/height are 'positive numbers' per Q-1; floats from
        snap-to-grid math should be accepted (FF-2's snap config emits
        floats; storage coerces at write time but validator accepts)."""
        core = _make_core(db)
        rows = _freeform_row(
            [_freeform_placement(x=100.5, y=200.25, width=320.0, height=180.0)]
        )
        _validate_rows(rows, core=core, canvas_config={"width": 1200, "height": 800})

    def test_preserves_is_core_on_freeform(self, db):
        """Free-form placement marked is_core=true still enforces
        component_kind + component_name match the inherited core."""
        core = _make_core(db)
        # is_core=true requires matching the core's component_kind+name.
        rows = _freeform_row(
            [
                _freeform_placement(
                    component_kind="focus-core",
                    component_name="SchedulingKanbanCore",
                    is_core=True,
                )
            ]
        )
        _validate_rows(rows, core=core, canvas_config={"width": 1200, "height": 800})

    def test_rejects_mismatched_is_core_freeform(self, db):
        """A free-form placement with is_core=true must match the core's
        registered component identity (same rule as grid)."""
        core = _make_core(db)
        rows = _freeform_row(
            [
                _freeform_placement(
                    component_kind="widget",
                    component_name="bogus-core",
                    is_core=True,
                )
            ]
        )
        with pytest.raises(InvalidTemplateShape, match="does not match"):
            _validate_rows(
                rows, core=core, canvas_config={"width": 1200, "height": 800}
            )


# ═══ Free-form rejection ═════════════════════════════════════════


class TestFreeFormRejection:
    def test_rejects_x_plus_width_exceeds_canvas(self, db):
        core = _make_core(db)
        rows = _freeform_row(
            [_freeform_placement(x=1000, y=100, width=300, height=180)]
        )
        # 1000 + 300 = 1300 > canvas_width=1200
        with pytest.raises(InvalidTemplateShape, match="exceeds canvas_config.width"):
            _validate_rows(
                rows, core=core, canvas_config={"width": 1200, "height": 800}
            )

    def test_rejects_y_plus_height_exceeds_canvas(self, db):
        core = _make_core(db)
        rows = _freeform_row(
            [_freeform_placement(x=100, y=700, width=320, height=200)]
        )
        # 700 + 200 = 900 > canvas_height=800
        with pytest.raises(
            InvalidTemplateShape, match="exceeds canvas_config.height"
        ):
            _validate_rows(
                rows, core=core, canvas_config={"width": 1200, "height": 800}
            )

    def test_rejects_width_less_than_one(self, db):
        core = _make_core(db)
        rows = _freeform_row([_freeform_placement(width=0)])
        with pytest.raises(InvalidTemplateShape, match="width must be >= 1"):
            _validate_rows(
                rows, core=core, canvas_config={"width": 1200, "height": 800}
            )

    def test_rejects_negative_x(self, db):
        core = _make_core(db)
        rows = _freeform_row([_freeform_placement(x=-10)])
        with pytest.raises(InvalidTemplateShape, match="x must be >= 0"):
            _validate_rows(
                rows, core=core, canvas_config={"width": 1200, "height": 800}
            )

    def test_rejects_non_numeric_dimension(self, db):
        core = _make_core(db)
        rows = _freeform_row([_freeform_placement(width="320")])
        with pytest.raises(InvalidTemplateShape, match="width must be a number"):
            _validate_rows(
                rows, core=core, canvas_config={"width": 1200, "height": 800}
            )

    def test_rejects_boolean_dimension(self, db):
        """bool is technically a subclass of int in Python; reject it
        explicitly so True/False can't slip through as 1/0."""
        core = _make_core(db)
        rows = _freeform_row([_freeform_placement(width=True)])
        with pytest.raises(InvalidTemplateShape, match="width must be a number"):
            _validate_rows(
                rows, core=core, canvas_config={"width": 1200, "height": 800}
            )

    def test_rejects_non_integer_z_index(self, db):
        core = _make_core(db)
        rows = _freeform_row([_freeform_placement(z_index=1.5)])
        with pytest.raises(InvalidTemplateShape, match="z_index must be an integer"):
            _validate_rows(
                rows, core=core, canvas_config={"width": 1200, "height": 800}
            )


# ═══ Canvas defaults + canvas_config handling ════════════════════


class TestCanvasConfigDefaults:
    def test_uses_default_canvas_dimensions_when_config_missing(self, db):
        """When canvas_config is None/absent, validator falls back to
        DEFAULT_CANVAS_WIDTH × DEFAULT_CANVAS_HEIGHT (1200×800)."""
        core = _make_core(db)
        # x+width=1199 < 1200 default → accept
        rows = _freeform_row([_freeform_placement(x=900, y=100, width=299, height=180)])
        _validate_rows(rows, core=core)

    def test_rejects_when_exceeds_default_dimensions(self, db):
        core = _make_core(db)
        # x+width=1300 > 1200 default
        rows = _freeform_row([_freeform_placement(x=1000, y=100, width=300, height=180)])
        with pytest.raises(InvalidTemplateShape, match="exceeds canvas_config.width"):
            _validate_rows(rows, core=core)

    def test_respects_custom_canvas_dimensions(self, db):
        """Operators can override canvas dims; validator honors them."""
        core = _make_core(db)
        # x+width=1500 < 1600 → accept
        rows = _freeform_row(
            [_freeform_placement(x=1000, y=100, width=500, height=180)]
        )
        _validate_rows(
            rows, core=core, canvas_config={"width": 1600, "height": 1200}
        )

    def test_default_canvas_constants_match_spec(self):
        """Sanity: Q-2 locks default to 1200×800."""
        assert DEFAULT_CANVAS_WIDTH == 1200
        assert DEFAULT_CANVAS_HEIGHT == 800


# ═══ create_template default stamping ════════════════════════════


class TestCreateTemplateCanvasStamping:
    def test_stamps_default_canvas_config_when_empty(self, db):
        """create_template stamps width=1200/height=800 on empty config."""
        core = _make_core(db)
        tpl = create_template(
            db,
            scope="platform_default",
            template_slug="ff1-empty-cfg",
            display_name="FF-1 empty",
            inherits_from_core_id=core.id,
            rows=[],
            canvas_config={},  # explicit empty
        )
        assert tpl.canvas_config == {"width": 1200, "height": 800}

    def test_stamps_default_canvas_config_when_none(self, db):
        core = _make_core(db)
        tpl = create_template(
            db,
            scope="platform_default",
            template_slug="ff1-none-cfg",
            display_name="FF-1 none",
            inherits_from_core_id=core.id,
            rows=[],
            canvas_config=None,
        )
        assert tpl.canvas_config == {"width": 1200, "height": 800}

    def test_preserves_explicit_canvas_config(self, db):
        """Operators (or F-series test fixtures) passing explicit keys
        must be respected verbatim — no stamping fires."""
        core = _make_core(db)
        tpl = create_template(
            db,
            scope="platform_default",
            template_slug="ff1-custom-cfg",
            display_name="FF-1 custom",
            inherits_from_core_id=core.id,
            rows=[],
            canvas_config={"gap_size": 4, "padding": 8},
        )
        # Explicit values preserved; no width/height added.
        assert tpl.canvas_config == {"gap_size": 4, "padding": 8}

    def test_preserves_partial_canvas_config(self, db):
        """An operator who passes only width=1600 is respected; no
        stamping infill. (FF-2 reads with fallback to defaults at
        consumer side if a key is missing.)"""
        core = _make_core(db)
        tpl = create_template(
            db,
            scope="platform_default",
            template_slug="ff1-partial-cfg",
            display_name="FF-1 partial",
            inherits_from_core_id=core.id,
            rows=[],
            canvas_config={"width": 1600},
        )
        assert tpl.canvas_config == {"width": 1600}


# ═══ Grid-shape regression (F-series invariant) ═══════════════════


class TestGridShapeRegression:
    def test_grid_placement_still_validates(self, db):
        """Existing F-series shape is untouched."""
        core = _make_core(db)
        rows = [
            {
                "row_index": 0,
                "column_count": 12,
                "placements": [
                    _grid_placement(starting_column=0, column_span=4),
                    _grid_placement(starting_column=4, column_span=8),
                ],
            }
        ]
        _validate_rows(rows, core=core)

    def test_grid_placement_still_rejects_out_of_bounds(self, db):
        core = _make_core(db)
        rows = [
            {
                "row_index": 0,
                "column_count": 12,
                "placements": [_grid_placement(starting_column=8, column_span=8)],
            }
        ]
        # 8 + 8 > 12
        with pytest.raises(InvalidTemplateShape, match="exceeds row column_count"):
            _validate_rows(rows, core=core)

    def test_two_separate_templates_can_use_different_shapes(self, db):
        """Two templates: one all-grid, one all-freeform. Each validates
        independently. Cross-template shape coexistence in the DB is
        explicitly supported per Q-23 pure-JSONB-extension."""
        core = _make_core(db)
        # Grid template.
        tpl_grid = create_template(
            db,
            scope="platform_default",
            template_slug="ff1-mix-grid",
            display_name="Grid",
            inherits_from_core_id=core.id,
            rows=[
                {
                    "row_index": 0,
                    "column_count": 12,
                    "placements": [_grid_placement()],
                }
            ],
        )
        # Free-form template.
        tpl_ff = create_template(
            db,
            scope="platform_default",
            template_slug="ff1-mix-ff",
            display_name="Free-form",
            inherits_from_core_id=core.id,
            rows=_freeform_row([_freeform_placement()]),
        )
        assert tpl_grid.id != tpl_ff.id


# ═══ Mixed-shape rejection (template-level consistency) ══════════


class TestMixedShapeRejection:
    def test_rejects_template_with_grid_and_freeform_placements(self, db):
        """All placements in a single template must be the same shape.
        Mixed templates rejected at template level after individual
        placement validation."""
        core = _make_core(db)
        rows = [
            {
                "row_index": 0,
                "column_count": 12,
                "placements": [
                    _grid_placement(),
                    _freeform_placement(),
                ],
            }
        ]
        with pytest.raises(
            InvalidTemplateShape,
            match="all be grid-shaped or all be free-form-shaped",
        ):
            _validate_rows(
                rows, core=core, canvas_config={"width": 1200, "height": 800}
            )

    def test_rejects_mixed_across_rows(self, db):
        """Mixed-shape rejection fires across rows, not just within a
        single row."""
        core = _make_core(db)
        rows = [
            {
                "row_index": 0,
                "column_count": 12,
                "placements": [_grid_placement()],
            },
            {
                "row_index": 1,
                "column_count": 12,
                "placements": [_freeform_placement()],
            },
        ]
        with pytest.raises(
            InvalidTemplateShape,
            match="all be grid-shaped or all be free-form-shaped",
        ):
            _validate_rows(
                rows, core=core, canvas_config={"width": 1200, "height": 800}
            )

    def test_create_template_rejects_mixed_shape(self, db):
        """End-to-end via create_template: mixed-shape rejection
        surfaces at the service boundary."""
        core = _make_core(db)
        with pytest.raises(InvalidTemplateShape, match="all be grid-shaped"):
            create_template(
                db,
                scope="platform_default",
                template_slug="ff1-mixed",
                display_name="FF-1 mixed",
                inherits_from_core_id=core.id,
                rows=[
                    {
                        "row_index": 0,
                        "column_count": 12,
                        "placements": [
                            _grid_placement(),
                            _freeform_placement(),
                        ],
                    }
                ],
            )
