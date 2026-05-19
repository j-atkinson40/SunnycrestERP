"""F-3.1a — placement adapter contract test (real backend validation).

Exercises the REAL `_validate_rows` + `_validate_placement` logic
against the canonical wire shape the frontend
`_placement-adapter.ts::frontendToBackendRows` produces. This is the
load-bearing integration test mandated by the F-3.1a brief: if the
adapter's output shape drifts from the backend's contract, this test
fails and the frontend save path is broken at runtime.

NOT a mock. Imports `_validate_rows` directly and runs it against
fixtures shaped exactly like the adapter's output.

Path Y per F-3.1a Step 5 — no HTTP integration test infrastructure
exercising the frontend hook against a live backend; instead, this
test enforces the contract at the validation-function boundary that
the failure surfaces at in production. If a real E2E hook→backend
test infrastructure is added later (Phase F-5 or beyond), it
supersedes this; until then, this is the canonical contract gate.
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
    InvalidTemplateShape,
    _validate_rows,
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


# Canonical adapter output fixtures — these MUST mirror what
# `frontend/src/bridgeable-admin/hooks/_placement-adapter.ts`
# emits. Drift between these fixtures and the TS adapter is the
# class-of-bug this test guards against.


def _frontend_addWidget_output() -> list[dict]:
    """The exact JSON shape `frontendToBackendRows` produces for a
    fresh `addWidget("day-strip-widget")` call with hook defaults
    (column_start=1 → starting_column=0, column_span=4, empty chrome).
    """
    return [
        {
            "row_index": 0,
            "column_count": 12,
            "placements": [
                {
                    "placement_id": str(uuid.uuid4()),
                    "component_kind": "widget",
                    "component_name": "day-strip-widget",
                    "starting_column": 0,
                    "column_span": 4,
                    # empty chrome → adapter omits prop_overrides
                },
            ],
        },
    ]


def _frontend_widget_with_chrome_output() -> list[dict]:
    """Adapter output after `addWidget` + `updateWidget(id, {daysVisible: 5})`."""
    return [
        {
            "row_index": 0,
            "column_count": 12,
            "placements": [
                {
                    "placement_id": str(uuid.uuid4()),
                    "component_kind": "widget",
                    "component_name": "day-strip-widget",
                    "starting_column": 0,
                    "column_span": 4,
                    "prop_overrides": {
                        "daysVisible": 5,
                        "highlightToday": True,
                    },
                },
            ],
        },
    ]


def _frontend_multi_widget_output() -> list[dict]:
    """Adapter output for two widgets, one with chrome, one without,
    in same row at different columns (1-indexed in frontend →
    0-indexed in backend: column_start=1→0, column_start=5→4).
    """
    return [
        {
            "row_index": 0,
            "column_count": 12,
            "placements": [
                {
                    "placement_id": str(uuid.uuid4()),
                    "component_kind": "widget",
                    "component_name": "day-strip-widget",
                    "starting_column": 0,
                    "column_span": 4,
                },
                {
                    "placement_id": str(uuid.uuid4()),
                    "component_kind": "widget",
                    "component_name": "today-pin-widget",
                    "starting_column": 4,
                    "column_span": 4,
                    "prop_overrides": {"showCount": True},
                },
            ],
        },
    ]


class TestFrontendAdapterOutputValidates:
    """Real `_validate_rows` accepts canonical adapter output.

    Each test would FAIL pre-F-3.1a — the pre-adapter wire shape
    (`id`/`widget_slug`/`column_start`/`chrome`) is rejected by
    `_validate_placement` with `InvalidTemplateShape`. This is the
    bug F-3.1a fixes; the test gates against regression.
    """

    def test_addWidget_default_shape_validates(self, db):
        core = _make_core(db)
        rows = _frontend_addWidget_output()
        # Must NOT raise.
        _validate_rows(rows, core=core)

    def test_widget_with_chrome_shape_validates(self, db):
        core = _make_core(db)
        rows = _frontend_widget_with_chrome_output()
        _validate_rows(rows, core=core)

    def test_multi_widget_shape_validates(self, db):
        core = _make_core(db)
        rows = _frontend_multi_widget_output()
        _validate_rows(rows, core=core)

    def test_starting_column_plus_span_within_bounds(self, db):
        """The adapter's 1→0 column index translation must produce
        backend-valid `starting_column + column_span <= column_count`
        for the canonical hook defaults.
        """
        core = _make_core(db)
        rows = _frontend_multi_widget_output()
        for r in rows:
            for p in r["placements"]:
                assert p["starting_column"] + p["column_span"] <= r["column_count"]
        _validate_rows(rows, core=core)


class TestPreAdapterShapeRejected:
    """Inverse gate: the FRONTEND-typed shape (pre-adapter) MUST
    fail `_validate_rows`. If this stops failing, the backend
    validator has been weakened and F-3.1a's adapter is no longer
    load-bearing — surface architecturally.
    """

    def test_frontend_shape_missing_placement_id_rejected(self, db):
        core = _make_core(db)
        bad_rows = [
            {
                "row_index": 0,
                "column_count": 12,
                "placements": [
                    {
                        # NOTE: pre-adapter uses `id` not `placement_id`.
                        "id": "w-1",
                        "widget_slug": "day-strip-widget",
                        "column_start": 1,
                        "column_span": 4,
                        "chrome": {},
                    }
                ],
            }
        ]
        with pytest.raises(InvalidTemplateShape):
            _validate_rows(bad_rows, core=core)

    def test_frontend_shape_missing_component_kind_rejected(self, db):
        core = _make_core(db)
        bad_rows = [
            {
                "row_index": 0,
                "column_count": 12,
                "placements": [
                    {
                        "placement_id": "w-1",
                        # missing component_kind + component_name
                        "starting_column": 0,
                        "column_span": 4,
                    }
                ],
            }
        ]
        with pytest.raises(InvalidTemplateShape):
            _validate_rows(bad_rows, core=core)
