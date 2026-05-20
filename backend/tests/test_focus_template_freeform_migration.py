"""Tests for r104 Focus template free-form migration.

Exercises the pure-function migration helpers + their idempotency
guarantees in both directions (upgrade + downgrade). The pure
helpers (`_migrate_rows_to_freeform`, `_migrate_rows_to_grid`,
`_stamp_canvas_dimensions`, `_is_already_freeform`, `_is_already_grid`)
are tested against constructed fixture rows. End-to-end DB exercise
defers to the `alembic upgrade head` step in build verification
(local dev DB is empty + staging deploy hits the seeded templates).

Class-of-bug guards:
  - Idempotency in both directions (re-running upgrade/downgrade is
    a no-op on already-migrated data).
  - Round-trip safety (upgrade → downgrade restores grid-equivalent
    shape; structural fields preserved).
  - Partial canvas_config preserved (existing keys survive the
    width/height stamp).
  - Inherited core placement uses Q-20 formula (not generic widget
    translation).
  - Non-dict rows / non-dict placements pass through (defensive).
"""

from __future__ import annotations

import importlib.util
import os

import pytest


# Load the migration module directly by file path. Alembic migration
# files aren't importable via dotted-path because their parents lack
# __init__.py + filenames begin with digits in some cases.
_MIGRATION_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "alembic",
    "versions",
    "r104_migrate_focus_templates_to_freeform.py",
)
_spec = importlib.util.spec_from_file_location(
    "r104_migrate_focus_templates_to_freeform",
    os.path.abspath(_MIGRATION_PATH),
)
assert _spec is not None and _spec.loader is not None
r104 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r104)


# ─── Fixtures ────────────────────────────────────────────────────


def _grid_row(placements: list[dict], column_count: int = 12) -> dict:
    return {
        "row_id": "r1",
        "column_count": column_count,
        "placements": placements,
    }


def _grid_widget(
    *,
    pid: str = "w1",
    starting_column: int = 0,
    column_span: int = 4,
    component_name: str = "day-strip-widget",
) -> dict:
    return {
        "placement_id": pid,
        "component_kind": "widget",
        "component_name": component_name,
        "starting_column": starting_column,
        "column_span": column_span,
    }


def _grid_core(
    *,
    pid: str = "core",
    starting_column: int = 0,
    column_span: int = 12,
) -> dict:
    return {
        "placement_id": pid,
        "is_core": True,
        "component_kind": "focus-core",
        "component_name": "SchedulingKanbanCore",
        "starting_column": starting_column,
        "column_span": column_span,
    }


def _freeform_widget(
    *,
    pid: str = "w1",
    x: float = 100,
    y: float = 100,
    width: float = 320,
    height: float = 180,
) -> dict:
    return {
        "placement_id": pid,
        "component_kind": "widget",
        "component_name": "day-strip-widget",
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "z_index": 0,
    }


# ─── Shape detection ─────────────────────────────────────────────


class TestShapeDetection:
    def test_detects_freeform_via_x(self):
        rows = [_grid_row([_freeform_widget()])]
        assert r104._is_already_freeform(rows) is True
        assert r104._is_already_grid(rows) is False

    def test_detects_grid_via_starting_column(self):
        rows = [_grid_row([_grid_widget()])]
        assert r104._is_already_freeform(rows) is False
        assert r104._is_already_grid(rows) is True

    def test_empty_rows_neither(self):
        assert r104._is_already_freeform([]) is False
        assert r104._is_already_grid([]) is False

    def test_empty_placements_neither(self):
        rows = [{"row_id": "r1", "column_count": 12, "placements": []}]
        assert r104._is_already_freeform(rows) is False
        assert r104._is_already_grid(rows) is False

    def test_detects_freeform_when_only_width_present(self):
        # Field-presence semantics — any of x/y/width/height is enough
        placement = {
            "placement_id": "p",
            "component_kind": "widget",
            "component_name": "w",
            "width": 100,
        }
        rows = [_grid_row([placement])]
        assert r104._is_already_freeform(rows) is True

    def test_handles_non_dict_row(self):
        # Defensive — string row passes through without crashing.
        rows = ["not-a-dict"]
        assert r104._is_already_freeform(rows) is False
        assert r104._is_already_grid(rows) is False


# ─── Pure-function migration ─────────────────────────────────────


class TestMigrateToFreeform:
    def test_widget_translation_basic(self):
        rows = [_grid_row([_grid_widget(starting_column=0, column_span=6)])]
        migrated = r104._migrate_rows_to_freeform(
            rows, canvas_width=1200, canvas_height=800
        )
        p = migrated[0]["placements"][0]
        # 0 * 100 = 0; 6 * 100 = 600
        assert p["x"] == 0
        assert p["width"] == 600
        assert p["y"] == 0  # row_index 0
        assert p["height"] == 200
        assert p["z_index"] == 0

    def test_widget_translation_offset(self):
        rows = [_grid_row([_grid_widget(starting_column=6, column_span=6)])]
        migrated = r104._migrate_rows_to_freeform(
            rows, canvas_width=1200, canvas_height=800
        )
        p = migrated[0]["placements"][0]
        # 6 * 100 = 600
        assert p["x"] == 600
        assert p["width"] == 600

    def test_widget_y_uses_row_index(self):
        rows = [
            _grid_row([_grid_widget(pid="w0")]),
            _grid_row([_grid_widget(pid="w1")]),
            _grid_row([_grid_widget(pid="w2")]),
        ]
        migrated = r104._migrate_rows_to_freeform(
            rows, canvas_width=1200, canvas_height=800
        )
        assert migrated[0]["placements"][0]["y"] == 0
        assert migrated[1]["placements"][0]["y"] == 200
        assert migrated[2]["placements"][0]["y"] == 400

    def test_widget_clears_grid_fields(self):
        rows = [_grid_row([_grid_widget()])]
        migrated = r104._migrate_rows_to_freeform(
            rows, canvas_width=1200, canvas_height=800
        )
        p = migrated[0]["placements"][0]
        assert "starting_column" not in p
        assert "column_span" not in p

    def test_row_loses_column_count(self):
        rows = [_grid_row([_grid_widget()], column_count=12)]
        migrated = r104._migrate_rows_to_freeform(
            rows, canvas_width=1200, canvas_height=800
        )
        assert "column_count" not in migrated[0]
        assert migrated[0]["row_id"] == "r1"  # other fields preserved

    def test_core_uses_q20_formula(self):
        rows = [_grid_row([_grid_core(starting_column=0, column_span=12)])]
        migrated = r104._migrate_rows_to_freeform(
            rows, canvas_width=1200, canvas_height=800
        )
        p = migrated[0]["placements"][0]
        # Q-20: span 12 → core_width 1200, core_x 0, core_y 40,
        # core_height 760
        assert p["x"] == 0
        assert p["width"] == 1200
        assert p["y"] == 40
        assert p["height"] == 760
        assert p["z_index"] == 0
        # is_core preserved
        assert p["is_core"] is True

    def test_core_narrower_span_centered(self):
        rows = [_grid_row([_grid_core(starting_column=2, column_span=8)])]
        migrated = r104._migrate_rows_to_freeform(
            rows, canvas_width=1200, canvas_height=800
        )
        p = migrated[0]["placements"][0]
        # span 8 → core_width 800, core_x 200 (centered)
        assert p["width"] == 800
        assert p["x"] == 200
        assert p["y"] == 40

    def test_preserves_placement_metadata(self):
        widget = _grid_widget()
        widget["prop_overrides"] = {"foo": "bar"}
        widget["display_config"] = {"show_header": False, "z_index": 2}
        rows = [_grid_row([widget])]
        migrated = r104._migrate_rows_to_freeform(
            rows, canvas_width=1200, canvas_height=800
        )
        p = migrated[0]["placements"][0]
        assert p["prop_overrides"] == {"foo": "bar"}
        assert p["display_config"] == {"show_header": False, "z_index": 2}
        assert p["placement_id"] == widget["placement_id"]
        assert p["component_kind"] == "widget"
        assert p["component_name"] == "day-strip-widget"

    def test_mixed_widget_and_core(self):
        rows = [
            _grid_row(
                [
                    _grid_core(pid="core", starting_column=0, column_span=12),
                ]
            ),
            _grid_row(
                [
                    _grid_widget(pid="w1", starting_column=0, column_span=6),
                    _grid_widget(pid="w2", starting_column=6, column_span=6),
                ]
            ),
        ]
        migrated = r104._migrate_rows_to_freeform(
            rows, canvas_width=1200, canvas_height=800
        )
        # Core uses Q-20: y=40, height=760
        core_p = migrated[0]["placements"][0]
        assert core_p["y"] == 40
        assert core_p["height"] == 760
        # Widgets in row index 1: y=200
        w1, w2 = migrated[1]["placements"]
        assert w1["y"] == 200 and w1["height"] == 200
        assert w2["y"] == 200 and w2["x"] == 600


# ─── Canvas stamping ─────────────────────────────────────────────


class TestStampCanvasDimensions:
    def test_empty_canvas_gets_defaults(self):
        out = r104._stamp_canvas_dimensions({})
        assert out["width"] == 1200
        assert out["height"] == 800

    def test_none_canvas_gets_defaults(self):
        out = r104._stamp_canvas_dimensions(None)
        assert out["width"] == 1200
        assert out["height"] == 800

    def test_partial_canvas_preserved(self):
        # FF-1 pattern: existing keys survive stamping.
        out = r104._stamp_canvas_dimensions({"gap_size": 4, "padding": 16})
        assert out["gap_size"] == 4
        assert out["padding"] == 16
        assert out["width"] == 1200
        assert out["height"] == 800

    def test_explicit_dimensions_preserved(self):
        out = r104._stamp_canvas_dimensions(
            {"width": 1600, "height": 1000, "gap_size": 8}
        )
        assert out["width"] == 1600
        assert out["height"] == 1000
        assert out["gap_size"] == 8

    def test_only_width_provided_height_stamped(self):
        out = r104._stamp_canvas_dimensions({"width": 1600})
        assert out["width"] == 1600
        assert out["height"] == 800


# ─── Downgrade (free-form → grid) ────────────────────────────────


class TestMigrateToGrid:
    def test_widget_reverse(self):
        # x=600, width=600 → starting_column=6, column_span=6
        rows = [_grid_row([_freeform_widget(x=600, width=600, y=0)])]
        # Clear column_count to simulate already-migrated state
        del rows[0]["column_count"]
        reverted = r104._migrate_rows_to_grid(rows, canvas_width=1200)
        p = reverted[0]["placements"][0]
        assert p["starting_column"] == 6
        assert p["column_span"] == 6
        assert "x" not in p
        assert "y" not in p
        assert "width" not in p
        assert "height" not in p
        assert "z_index" not in p

    def test_row_regains_column_count(self):
        rows = [{"row_id": "r1", "placements": [_freeform_widget()]}]
        reverted = r104._migrate_rows_to_grid(rows, canvas_width=1200)
        assert reverted[0]["column_count"] == 12

    def test_round_trip_widget(self):
        # Round-trip: grid → free-form → grid restores equivalent shape
        original = [
            _grid_row(
                [
                    _grid_widget(pid="w1", starting_column=0, column_span=4),
                    _grid_widget(pid="w2", starting_column=4, column_span=4),
                    _grid_widget(pid="w3", starting_column=8, column_span=4),
                ]
            )
        ]
        free_form = r104._migrate_rows_to_freeform(
            original, canvas_width=1200, canvas_height=800
        )
        restored = r104._migrate_rows_to_grid(free_form, canvas_width=1200)
        for orig_p, rest_p in zip(
            original[0]["placements"], restored[0]["placements"]
        ):
            assert rest_p["starting_column"] == orig_p["starting_column"]
            assert rest_p["column_span"] == orig_p["column_span"]
            assert rest_p["placement_id"] == orig_p["placement_id"]
        assert restored[0]["column_count"] == 12

    def test_clamps_overflow(self):
        # Free-form placement near right edge that would round to
        # column_span exceeding 12 — clamped.
        rows = [
            _grid_row(
                [_freeform_widget(x=1100, width=400)]
            )  # 1100/100=11, 400/100=4 → 11+4=15 > 12 → span clamped to 1
        ]
        del rows[0]["column_count"]
        reverted = r104._migrate_rows_to_grid(rows, canvas_width=1200)
        p = reverted[0]["placements"][0]
        assert p["starting_column"] == 11
        assert p["column_span"] == 1


# ─── Idempotency ─────────────────────────────────────────────────


class TestIdempotency:
    def test_upgrade_skips_already_freeform(self):
        rows = [_grid_row([_freeform_widget()])]
        # _is_already_freeform short-circuits in upgrade path
        assert r104._is_already_freeform(rows) is True

    def test_upgrade_twice_no_op(self):
        rows = [_grid_row([_grid_widget(starting_column=0, column_span=6)])]
        once = r104._migrate_rows_to_freeform(
            rows, canvas_width=1200, canvas_height=800
        )
        # Second call would only fire in raw form; but per upgrade
        # contract the SQL layer skips via _is_already_freeform. Verify
        # the check returns True on the migrated output.
        assert r104._is_already_freeform(once) is True

    def test_downgrade_skips_already_grid(self):
        rows = [_grid_row([_grid_widget()])]
        # Already grid — downgrade should classify as grid
        assert r104._is_already_grid(rows) is True
        # And as not-freeform
        assert r104._is_already_freeform(rows) is False

    def test_downgrade_skips_empty(self):
        rows = []
        assert r104._is_already_freeform(rows) is False
        assert r104._is_already_grid(rows) is False


# ─── Defensive shapes ────────────────────────────────────────────


class TestDefensive:
    def test_non_dict_row_passes_through(self):
        rows = ["surprise-string", _grid_row([_grid_widget()])]
        migrated = r104._migrate_rows_to_freeform(
            rows, canvas_width=1200, canvas_height=800
        )
        assert migrated[0] == "surprise-string"
        # Real row still migrated
        assert "x" in migrated[1]["placements"][0]

    def test_non_dict_placement_passes_through(self):
        rows = [
            {
                "row_id": "r1",
                "column_count": 12,
                "placements": ["not-a-dict", _grid_widget()],
            }
        ]
        migrated = r104._migrate_rows_to_freeform(
            rows, canvas_width=1200, canvas_height=800
        )
        assert migrated[0]["placements"][0] == "not-a-dict"
        assert "x" in migrated[0]["placements"][1]

    def test_missing_starting_column_defaults_to_zero(self):
        # Defensive — a malformed placement missing starting_column
        # gets sensible defaults so the migration doesn't crash mid-run.
        placement = {
            "placement_id": "p",
            "component_kind": "widget",
            "component_name": "w",
            "column_span": 4,
        }
        rows = [_grid_row([placement])]
        migrated = r104._migrate_rows_to_freeform(
            rows, canvas_width=1200, canvas_height=800
        )
        p = migrated[0]["placements"][0]
        assert p["x"] == 0


# ─── JSONB coercion ──────────────────────────────────────────────


class TestCoerceJsonb:
    def test_dict_passthrough(self):
        assert r104._coerce_jsonb({"a": 1}) == {"a": 1}

    def test_list_passthrough(self):
        assert r104._coerce_jsonb([1, 2]) == [1, 2]

    def test_string_parsed(self):
        assert r104._coerce_jsonb('{"a": 1}') == {"a": 1}

    def test_none_passthrough(self):
        assert r104._coerce_jsonb(None) is None


# ─── End-to-end via SQLAlchemy (if DB available) ─────────────────


@pytest.fixture
def db_session():
    """Optional DB fixture. Tests in this section run only when the
    bridgeable_dev database is reachable; otherwise skip gracefully.
    The pure-function tests above cover the core migration logic;
    this section exercises the SQL UPDATE round-trip."""
    try:
        from app.database import SessionLocal

        s = SessionLocal()
        try:
            # Probe connection
            s.execute(__import__("sqlalchemy").text("SELECT 1")).scalar()
        except Exception:
            s.close()
            pytest.skip("DB not reachable for end-to-end migration test")
        yield s
        s.close()
    except Exception:
        pytest.skip("DB stack not available")


class TestEndToEndUpdate:
    """End-to-end: seed a FocusCore + grid-shape FocusTemplate, run
    the migration helpers via the connection bind, verify the row
    came back free-form-shape + canvas_config stamped."""

    def test_full_upgrade_cycle_on_seeded_template(self, db_session):
        import json as _json
        import uuid

        from app.models.focus_composition import FocusComposition
        from app.models.focus_core import FocusCore
        from app.models.focus_template import FocusTemplate
        from app.services.focus_template_inheritance.focus_cores_service import (
            create_core,
        )
        from app.services.focus_template_inheritance.focus_templates_service import (
            create_template,
        )

        # Clean slate
        db_session.query(FocusComposition).delete()
        db_session.query(FocusTemplate).delete()
        db_session.query(FocusCore).delete()
        db_session.commit()

        core = create_core(
            db_session,
            core_slug=f"r104-test-core-{uuid.uuid4().hex[:6]}",
            display_name="Test Core",
            description="r104 migration test core",
            registered_component_kind="focus-core",
            registered_component_name="TestCore",
            default_starting_column=0,
            default_column_span=12,
            default_row_index=0,
            min_column_span=4,
            max_column_span=12,
            canvas_config={},
        )

        grid_rows = [
            _grid_row(
                [
                    {
                        "placement_id": "core1",
                        "is_core": True,
                        "component_kind": "focus-core",
                        "component_name": "TestCore",
                        "starting_column": 0,
                        "column_span": 12,
                    }
                ]
            ),
            _grid_row(
                [
                    _grid_widget(
                        pid="w1", starting_column=0, column_span=6
                    ),
                    _grid_widget(
                        pid="w2", starting_column=6, column_span=6
                    ),
                ]
            ),
        ]
        template = create_template(
            db_session,
            scope="platform_default",
            vertical=None,
            template_slug=f"r104-test-{uuid.uuid4().hex[:6]}",
            display_name="r104 test",
            inherits_from_core_id=core.id,
            rows=grid_rows,
            canvas_config={"gap_size": 4},  # partial canvas_config
        )
        template_id = template.id

        # Sanity: pre-migration shape is grid + canvas_config stamped
        # by create_template's FF-1 pattern (since gap_size triggers
        # "non-empty" branch — canvas_config preserved without stamping).
        # Verify pre-state shape.
        pre = (
            db_session.query(FocusTemplate)
            .filter(FocusTemplate.id == template_id)
            .one()
        )
        assert r104._is_already_grid(pre.rows) is True
        # canvas_config has gap_size but might NOT have width/height
        # depending on create_template behavior — that's fine; r104
        # will stamp during migration.

        # Run the upgrade pure-function path against the live row
        conn = db_session.connection()
        rows_jsonb = r104._coerce_jsonb(pre.rows) or []
        canvas_cfg = r104._coerce_jsonb(pre.canvas_config) or {}
        new_canvas = r104._stamp_canvas_dimensions(canvas_cfg)
        new_rows = r104._migrate_rows_to_freeform(
            rows_jsonb,
            canvas_width=int(new_canvas["width"]),
            canvas_height=int(new_canvas["height"]),
        )
        import sqlalchemy as _sa

        conn.execute(
            _sa.text(
                "UPDATE focus_templates "
                "SET rows = CAST(:rows AS jsonb), "
                "    canvas_config = CAST(:canvas AS jsonb) "
                "WHERE id = :id"
            ),
            {
                "rows": _json.dumps(new_rows),
                "canvas": _json.dumps(new_canvas),
                "id": template_id,
            },
        )
        db_session.commit()

        post = (
            db_session.query(FocusTemplate)
            .filter(FocusTemplate.id == template_id)
            .one()
        )
        # Post-migration assertions
        assert r104._is_already_freeform(post.rows) is True
        assert post.canvas_config["width"] == 1200
        assert post.canvas_config["height"] == 800
        assert post.canvas_config["gap_size"] == 4  # preserved
        # Core placement honors Q-20
        core_p = post.rows[0]["placements"][0]
        assert core_p["is_core"] is True
        assert core_p["y"] == 40
        assert core_p["width"] == 1200
        # Widget translation
        widgets = post.rows[1]["placements"]
        assert widgets[0]["x"] == 0
        assert widgets[0]["width"] == 600
        assert widgets[0]["y"] == 200  # row_index 1
        assert widgets[1]["x"] == 600
        # column_count stripped
        assert "column_count" not in post.rows[0]

        # Clean up
        db_session.query(FocusTemplate).delete()
        db_session.query(FocusCore).delete()
        db_session.commit()
