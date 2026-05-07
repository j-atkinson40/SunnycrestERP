"""Phase R-3.0 — composition data model gains rows with per-row column count.

Replaces the uniform 12-column grid with a sequence of rows, each declaring
its own column_count (1-12). Placements within a row use starting_column
(0-indexed) and column_span. Unblocks operational layouts where different
sections want different column counts (e.g., kanban-3-of-4 + widget-1 in
one row, 4 equal widgets in another).

Schema changes:
  - Add `rows JSONB DEFAULT '[]'::jsonb NOT NULL` column. Source of truth
    post-R-3.0.
  - `placements` and `canvas_config` columns retained for one-release grace
    (R-3.2 drops them after the migration window stabilizes — separate
    arc, NOT in R-3.0 scope). App code post-R-3.0 reads/writes only
    `rows`. Downgrade strategy: revert R-3.0 code → reads from
    `placements`. Post-R-3.0 edits in `rows` are not visible after a
    downgrade — operator must re-author. Acceptable risk for a feature
    with only 2 seeded vertical_default rows in production today.

Backfill:
  - Idempotent: detects rows already populated (from prior backfill run
    or post-R-3.0 writes) and skips them.
  - For each composition: cluster placements by `row_start` value;
    each cluster becomes one row at `column_count = canvas_config.total_columns`
    (defaulting to 12). Within each cluster, placements translate
    `column_start` (1-indexed) → `starting_column` (0-indexed).
  - Each generated row gets a fresh UUID `row_id` for stable editor reference.
  - Variant B + nesting extension points (`column_widths`, `nested_rows`)
    are written as null. Application logic ignores them in R-3.0; future
    arcs activate them without schema migration.

Migration head: r87_dashboard_layouts → r88_focus_compositions_rows.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import sqlalchemy as sa
from alembic import op


revision = "r88_focus_compositions_rows"
down_revision = "r87_dashboard_layouts"
branch_labels = None
depends_on = None


logger = logging.getLogger(__name__)


def _coerce_jsonb(value: Any) -> Any:
    """Postgres returns dict/list directly; SQLite returns JSON-string."""
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return None
    return None


def _backfill_rows_from_placements(
    placements: list[dict],
    canvas_config: dict,
) -> list[dict]:
    """Cluster placements by row_start; each cluster becomes one row.

    Translate placement.grid.column_start (1-indexed) → starting_column
    (0-indexed). Strip row_start + row_span (vertical position becomes
    implicit through row order).

    Each row records column_count from canvas_config.total_columns
    (defaulting to 12). Variant B `column_widths` and bounded nesting
    `nested_rows` are written as null.
    """
    if not placements:
        return []

    canvas_config = canvas_config or {}
    column_count = canvas_config.get("total_columns") or 12
    row_height = canvas_config.get("row_height", "auto")

    # Group by row_start; tolerate missing/malformed grid by lumping
    # malformed entries into a synthetic 999 bucket so they survive
    # the migration as non-canonical (admins re-author post-migration).
    by_row_start: dict[int, list[dict]] = {}
    for p in placements:
        if not isinstance(p, dict):
            continue
        grid = p.get("grid") or {}
        rs = grid.get("row_start")
        if not isinstance(rs, int) or rs < 1:
            rs = 999
        by_row_start.setdefault(rs, []).append(p)

    # Sort row_start values ascending; within each cluster sort
    # placements left-to-right by column_start.
    rows: list[dict] = []
    for row_start in sorted(by_row_start.keys()):
        cluster = sorted(
            by_row_start[row_start],
            key=lambda p: (p.get("grid") or {}).get("column_start") or 0,
        )
        translated_placements: list[dict] = []
        for p in cluster:
            grid = p.get("grid") or {}
            cs = grid.get("column_start") or 1
            cspan = grid.get("column_span") or 1
            # 1-indexed → 0-indexed
            starting_column = max(0, cs - 1)
            # Clamp to [0, column_count - 1] for backfill safety
            starting_column = min(starting_column, max(0, column_count - 1))
            # Clamp span so starting_column + column_span <= column_count
            cspan = max(1, min(cspan, column_count - starting_column))
            translated_placements.append(
                {
                    "placement_id": p.get("placement_id") or str(uuid.uuid4()),
                    "component_kind": p.get("component_kind") or "widget",
                    "component_name": p.get("component_name") or "",
                    "starting_column": starting_column,
                    "column_span": cspan,
                    "prop_overrides": p.get("prop_overrides") or {},
                    "display_config": p.get("display_config") or {},
                    "nested_rows": None,
                }
            )
        rows.append(
            {
                "row_id": str(uuid.uuid4()),
                "column_count": column_count,
                "row_height": row_height,
                "column_widths": None,
                "nested_rows": None,
                "placements": translated_placements,
            }
        )
    return rows


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "focus_compositions" not in set(inspector.get_table_names()):
        # Earlier migration (r84) creates the table. If absent, nothing
        # to do — fresh databases will see r88 run after r84 created
        # the table and the column-add path takes over.
        logger.info(
            "[r88] focus_compositions table not present; skipping (will run after r84)"
        )
        return

    existing_columns = {c["name"] for c in inspector.get_columns("focus_compositions")}
    if "rows" not in existing_columns:
        op.add_column(
            "focus_compositions",
            sa.Column(
                "rows",
                sa.JSON().with_variant(
                    sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
                    "postgresql",
                ),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )

    # Backfill — idempotent. Read every composition; if `rows` is
    # empty (just the server default after column-add), populate from
    # `placements` + `canvas_config`. Skip rows that already have
    # populated `rows` (post-R-3.0 writes or repeat backfill runs).
    rows_table = sa.table(
        "focus_compositions",
        sa.column("id", sa.String(36)),
        sa.column("placements", sa.JSON()),
        sa.column("canvas_config", sa.JSON()),
        sa.column("rows", sa.JSON()),
    )

    select_stmt = sa.select(
        rows_table.c.id,
        rows_table.c.placements,
        rows_table.c.canvas_config,
        rows_table.c.rows,
    )

    converted = 0
    skipped_already_populated = 0
    skipped_empty = 0

    for row in bind.execute(select_stmt).fetchall():
        existing_rows = _coerce_jsonb(row.rows)
        if isinstance(existing_rows, list) and len(existing_rows) > 0:
            skipped_already_populated += 1
            continue

        placements = _coerce_jsonb(row.placements) or []
        canvas_config = _coerce_jsonb(row.canvas_config) or {}

        new_rows = _backfill_rows_from_placements(placements, canvas_config)
        if not new_rows:
            # Composition has no placements; backfill leaves rows=[].
            skipped_empty += 1
            continue

        bind.execute(
            sa.update(rows_table)
            .where(rows_table.c.id == row.id)
            .values(rows=new_rows)
        )
        converted += 1

    logger.info(
        "[r88] backfill summary: converted=%d skipped_already_populated=%d skipped_empty=%d",
        converted,
        skipped_already_populated,
        skipped_empty,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "focus_compositions" not in set(inspector.get_table_names()):
        return

    existing_columns = {c["name"] for c in inspector.get_columns("focus_compositions")}
    if "rows" in existing_columns:
        op.drop_column("focus_compositions", "rows")
