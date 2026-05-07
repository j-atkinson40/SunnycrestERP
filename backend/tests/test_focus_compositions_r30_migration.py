"""R-3.0 migration backfill — pure-Python tests for the
`_backfill_rows_from_placements` helper in
`backend/alembic/versions/r88_focus_compositions_rows.py`.

The migration's data path is unit-testable in isolation because the
backfill helper is a pure function: list[placements] + canvas_config →
list[rows]. End-to-end migration is exercised on staging post-deploy
via the existing alembic upgrade head + seed_focus_compositions
re-run; that flow runs in CI's seed-idempotency gate.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_migration_module():
    here = Path(__file__).resolve()
    backend_root = here.parent.parent
    target = (
        backend_root
        / "alembic"
        / "versions"
        / "r88_focus_compositions_rows.py"
    )
    spec = importlib.util.spec_from_file_location(
        "r88_focus_compositions_rows", target
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_empty_placements_yield_empty_rows():
    mod = _load_migration_module()
    assert mod._backfill_rows_from_placements([], {}) == []


def test_single_placement_single_row():
    mod = _load_migration_module()
    placements = [
        {
            "placement_id": "today",
            "component_kind": "widget",
            "component_name": "today",
            "grid": {
                "column_start": 1,
                "column_span": 12,
                "row_start": 1,
                "row_span": 3,
            },
            "prop_overrides": {},
            "display_config": {"show_header": True},
        }
    ]
    rows = mod._backfill_rows_from_placements(
        placements, {"total_columns": 12, "row_height": 64}
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["column_count"] == 12
    assert row["row_height"] == 64
    assert row["column_widths"] is None
    assert row["nested_rows"] is None
    # Row gets a UUID
    assert isinstance(row["row_id"], str)
    assert len(row["row_id"]) >= 8

    p = row["placements"][0]
    assert p["placement_id"] == "today"
    # 1-indexed column_start → 0-indexed starting_column
    assert p["starting_column"] == 0
    assert p["column_span"] == 12
    assert p["display_config"] == {"show_header": True}
    assert p["nested_rows"] is None


def test_multiple_placements_same_row_cluster_into_one_row():
    """Three placements all at row_start=1 cluster into a single row."""
    mod = _load_migration_module()
    placements = [
        {
            "placement_id": "a",
            "component_kind": "widget",
            "component_name": "today",
            "grid": {
                "column_start": 1,
                "column_span": 4,
                "row_start": 1,
                "row_span": 3,
            },
            "prop_overrides": {},
            "display_config": {},
        },
        {
            "placement_id": "b",
            "component_kind": "widget",
            "component_name": "anomalies",
            "grid": {
                "column_start": 5,
                "column_span": 4,
                "row_start": 1,
                "row_span": 3,
            },
            "prop_overrides": {},
            "display_config": {},
        },
        {
            "placement_id": "c",
            "component_kind": "widget",
            "component_name": "recent_activity",
            "grid": {
                "column_start": 9,
                "column_span": 4,
                "row_start": 1,
                "row_span": 3,
            },
            "prop_overrides": {},
            "display_config": {},
        },
    ]
    rows = mod._backfill_rows_from_placements(
        placements, {"total_columns": 12, "row_height": 64}
    )
    assert len(rows) == 1
    assert len(rows[0]["placements"]) == 3
    # Sorted by starting_column ascending
    assert [p["placement_id"] for p in rows[0]["placements"]] == ["a", "b", "c"]
    assert [p["starting_column"] for p in rows[0]["placements"]] == [0, 4, 8]


def test_placements_at_different_row_starts_yield_separate_rows():
    """Three placements at row_start=1, 4, 8 yield three rows in order."""
    mod = _load_migration_module()
    placements = [
        {
            "placement_id": "today",
            "component_kind": "widget",
            "component_name": "today",
            "grid": {
                "column_start": 1,
                "column_span": 1,
                "row_start": 1,
                "row_span": 3,
            },
            "prop_overrides": {},
            "display_config": {},
        },
        {
            "placement_id": "recent",
            "component_kind": "widget",
            "component_name": "recent_activity",
            "grid": {
                "column_start": 1,
                "column_span": 1,
                "row_start": 4,
                "row_span": 4,
            },
            "prop_overrides": {},
            "display_config": {},
        },
        {
            "placement_id": "anomalies",
            "component_kind": "widget",
            "component_name": "anomalies",
            "grid": {
                "column_start": 1,
                "column_span": 1,
                "row_start": 8,
                "row_span": 3,
            },
            "prop_overrides": {},
            "display_config": {},
        },
    ]
    rows = mod._backfill_rows_from_placements(
        placements, {"total_columns": 1, "row_height": 64}
    )
    assert len(rows) == 3
    # Order preserved by row_start ascending
    assert rows[0]["placements"][0]["placement_id"] == "today"
    assert rows[1]["placements"][0]["placement_id"] == "recent"
    assert rows[2]["placements"][0]["placement_id"] == "anomalies"
    # All rows inherit canvas_config.total_columns=1
    assert all(r["column_count"] == 1 for r in rows)


def test_default_column_count_when_canvas_config_missing():
    """Falls back to 12 when canvas_config doesn't specify total_columns."""
    mod = _load_migration_module()
    placements = [
        {
            "placement_id": "a",
            "component_kind": "widget",
            "component_name": "today",
            "grid": {
                "column_start": 1,
                "column_span": 12,
                "row_start": 1,
                "row_span": 3,
            },
            "prop_overrides": {},
            "display_config": {},
        }
    ]
    rows = mod._backfill_rows_from_placements(placements, {})
    assert rows[0]["column_count"] == 12


def test_clamps_starting_column_within_column_count():
    """Defensive: if pre-R-3.0 data had placement at column_start that
    exceeds the column_count, backfill clamps rather than crashes."""
    mod = _load_migration_module()
    placements = [
        {
            "placement_id": "a",
            "component_kind": "widget",
            "component_name": "today",
            "grid": {
                "column_start": 5,  # 1-indexed
                "column_span": 1,
                "row_start": 1,
                "row_span": 1,
            },
            "prop_overrides": {},
            "display_config": {},
        }
    ]
    # Caller's column_count is 1; 1-indexed column_start=5 (= 0-indexed 4)
    # exceeds column_count-1=0. Clamp to 0.
    rows = mod._backfill_rows_from_placements(placements, {"total_columns": 1})
    assert rows[0]["placements"][0]["starting_column"] == 0
    assert rows[0]["placements"][0]["column_span"] == 1


def test_seeded_compositions_backfill_pattern():
    """Mirrors the actual pre-R-3.0 seeded `vertical_default` compositions
    (single-column, 3 placements stacked via row_start=1, 4, 8). Verifies
    backfill produces 3 single-column rows in order — same visual output
    post-migration."""
    mod = _load_migration_module()
    placements = [
        {
            "placement_id": "today",
            "component_kind": "widget",
            "component_name": "today",
            "grid": {
                "column_start": 1,
                "column_span": 1,
                "row_start": 1,
                "row_span": 3,
            },
            "prop_overrides": {},
            "display_config": {"show_header": True, "show_border": True},
        },
        {
            "placement_id": "recent-activity",
            "component_kind": "widget",
            "component_name": "recent_activity",
            "grid": {
                "column_start": 1,
                "column_span": 1,
                "row_start": 4,
                "row_span": 4,
            },
            "prop_overrides": {},
            "display_config": {"show_header": True, "show_border": True},
        },
        {
            "placement_id": "anomalies",
            "component_kind": "widget",
            "component_name": "anomalies",
            "grid": {
                "column_start": 1,
                "column_span": 1,
                "row_start": 8,
                "row_span": 3,
            },
            "prop_overrides": {},
            "display_config": {"show_header": True, "show_border": True},
        },
    ]
    canvas = {"total_columns": 1, "row_height": 64, "gap_size": 12}
    rows = mod._backfill_rows_from_placements(placements, canvas)
    assert len(rows) == 3
    for row in rows:
        assert row["column_count"] == 1
        assert row["row_height"] == 64
        assert row["column_widths"] is None
        assert row["nested_rows"] is None
        assert len(row["placements"]) == 1
        assert row["placements"][0]["starting_column"] == 0
        assert row["placements"][0]["column_span"] == 1
        # Display config preserved verbatim
        assert row["placements"][0]["display_config"] == {
            "show_header": True,
            "show_border": True,
        }


def test_unique_row_ids_per_run():
    """Each row gets a fresh UUID; no collisions across rows in one run."""
    mod = _load_migration_module()
    placements = [
        {
            "placement_id": str(i),
            "component_kind": "widget",
            "component_name": "today",
            "grid": {
                "column_start": 1,
                "column_span": 1,
                "row_start": i,
                "row_span": 1,
            },
            "prop_overrides": {},
            "display_config": {},
        }
        for i in range(1, 6)
    ]
    rows = mod._backfill_rows_from_placements(placements, {"total_columns": 1})
    row_ids = [r["row_id"] for r in rows]
    assert len(set(row_ids)) == len(rows)
