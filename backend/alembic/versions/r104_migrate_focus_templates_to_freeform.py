"""Migrate Focus templates to free-form-shape placements.

Standalone data-migration arc. Reverses investigation Q-24 ("no
migration of seeded templates") as a product decision now that the
FF-series substrate has landed: Decide canvas substrate is free-form;
existing grid-shape templates should match.

Per-placement translation rules:

  Widget placement:
      x       = starting_column * (canvas_width / 12)
      y       = row_index * DEFAULT_ROW_HEIGHT (200)
      width   = column_span * (canvas_width / 12)
      height  = DEFAULT_ROW_HEIGHT (200)  [universal fallback; widget
                                          registry consult lives
                                          frontend-side per F-3]
      z_index = 0

  Inherited core placement (`is_core: true`) per Q-20:
      core_width  = canvas_width * (default_column_span / 12)
      core_x      = (canvas_width - core_width) / 2
      core_y      = 40
      core_height = canvas_height - 40

      default_column_span is read from the placement's existing
      `column_span` (preserves the template-author intent encoded
      in the grid shape — matches FF-2 frontend behavior where the
      Q-20 formula reads from the inherited core's
      default_column_span field).

Idempotent: skips templates whose placements already carry any of
x / y / width / height (already-free-form classification, matching
backend `_placement_shape`).

Canvas dimensions stamped per FF-1 pattern: templates missing
`canvas_config.width` / `.height` get the FF-1 defaults (1200×800).
Pre-existing canvas_config keys (gap_size, background_treatment,
padding, etc.) are preserved.

Grid fields cleared after migration: each placement loses
`starting_column` / `column_span`; rows lose `column_count`.

Reversible. Down migration restores grid shape (column_count=12,
starting_column + column_span derived by rounding x/width against
canvas_width / 12). Provided for emergency rollback only.

Migration head: r103_focus_templates_edit_session →
r104_migrate_focus_templates_to_freeform.
"""

from __future__ import annotations

import json
from typing import Any

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "r104_migrate_focus_templates_to_freeform"
down_revision = "r103_focus_templates_edit_session"
branch_labels = None
depends_on = None


DEFAULT_CANVAS_WIDTH = 1200
DEFAULT_CANVAS_HEIGHT = 800
DEFAULT_ROW_HEIGHT = 200
CORE_TOP_MARGIN = 40

# Free-form discriminator fields. Mirrors backend
# focus_templates_service._FREEFORM_KEYS.
_FREEFORM_KEYS = ("x", "y", "width", "height")


def _coerce_jsonb(value: Any) -> Any:
    """Postgres JSONB columns may come back as dicts/lists (psycopg2 +
    JSONB) or as strings (older driver paths). Normalize to native
    Python."""
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        return json.loads(value)
    if value is None:
        return None
    return value


def _has_freeform_fields(placement: dict) -> bool:
    return any(k in placement for k in _FREEFORM_KEYS)


def _is_already_freeform(rows: list) -> bool:
    """A template is classified as already-free-form if ANY placement
    carries any free-form positioning field. Matches backend
    `_placement_shape` field-presence semantics."""
    if not isinstance(rows, list):
        return False
    for row in rows:
        if not isinstance(row, dict):
            continue
        for placement in row.get("placements", []) or []:
            if isinstance(placement, dict) and _has_freeform_fields(
                placement
            ):
                return True
    return False


def _is_already_grid(rows: list) -> bool:
    """A template is classified as grid-shape if ANY placement carries
    grid positioning fields AND none carry free-form fields. Used by
    downgrade for idempotency."""
    if not isinstance(rows, list):
        return False
    saw_grid = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        for placement in row.get("placements", []) or []:
            if not isinstance(placement, dict):
                continue
            if _has_freeform_fields(placement):
                return False
            if "starting_column" in placement or "column_span" in placement:
                saw_grid = True
    return saw_grid


def _migrate_placement_to_freeform(
    placement: dict,
    *,
    row_index: int,
    canvas_width: int,
    canvas_height: int,
) -> dict:
    """Convert a single grid-shape placement to free-form shape.

    Removes starting_column / column_span; adds x / y / width / height
    / z_index. Preserves every other placement field verbatim
    (placement_id, component_kind, component_name, is_core,
    prop_overrides, display_config, etc.).
    """
    starting_column = placement.get("starting_column", 0)
    column_span = placement.get("column_span", 4)
    if not isinstance(starting_column, int):
        starting_column = 0
    if not isinstance(column_span, int) or column_span < 1:
        column_span = 4

    column_unit = canvas_width / 12.0

    is_core = placement.get("is_core") is True
    if is_core:
        # Q-20 canonical core anchor. core_width derives from the
        # placement's encoded column_span (which the F-series author
        # set to match the core's default_column_span). FF-2's frontend
        # WidgetFreeFormLayer derives it from the live core record;
        # here we use the placement's stored value because the
        # migration must be self-contained — joining focus_cores per
        # row would add complexity for no behavioral difference (the
        # F-series validator already enforces is_core placements match
        # the inherited core's component identity, and authors
        # typically set column_span == default_column_span).
        clamped_span = max(1, min(12, column_span))
        core_width = canvas_width * (clamped_span / 12.0)
        core_x = (canvas_width - core_width) / 2.0
        core_y = CORE_TOP_MARGIN
        core_height = max(1.0, float(canvas_height - CORE_TOP_MARGIN))
        new_placement = {
            k: v
            for k, v in placement.items()
            if k not in ("starting_column", "column_span")
        }
        new_placement["x"] = core_x
        new_placement["y"] = core_y
        new_placement["width"] = core_width
        new_placement["height"] = core_height
        new_placement["z_index"] = 0
        return new_placement

    # Widget placement. Universal 200px height fallback per investigation
    # findings (widget registry's defaultDimensions lives frontend-side;
    # backend has no access at Alembic time + no need — operators
    # adjust heights post-migration via FF-4's resize gesture).
    new_placement = {
        k: v
        for k, v in placement.items()
        if k not in ("starting_column", "column_span")
    }
    new_placement["x"] = starting_column * column_unit
    new_placement["y"] = float(row_index * DEFAULT_ROW_HEIGHT)
    new_placement["width"] = column_span * column_unit
    new_placement["height"] = float(DEFAULT_ROW_HEIGHT)
    new_placement["z_index"] = 0
    return new_placement


def _migrate_rows_to_freeform(
    rows: list,
    *,
    canvas_width: int,
    canvas_height: int,
) -> list:
    """Convert all placements in all rows to free-form. Strips
    `column_count` from each row (rows-as-layout-axis is retired by FF
    canvas substrate; envelope kept for back-compat per FF-1)."""
    migrated_rows: list = []
    for row_index, row in enumerate(rows or []):
        if not isinstance(row, dict):
            migrated_rows.append(row)
            continue
        new_row = {k: v for k, v in row.items() if k != "column_count"}
        new_placements = []
        for placement in row.get("placements", []) or []:
            if not isinstance(placement, dict):
                new_placements.append(placement)
                continue
            new_placements.append(
                _migrate_placement_to_freeform(
                    placement,
                    row_index=row_index,
                    canvas_width=canvas_width,
                    canvas_height=canvas_height,
                )
            )
        new_row["placements"] = new_placements
        migrated_rows.append(new_row)
    return migrated_rows


def _migrate_placement_to_grid(
    placement: dict,
    *,
    canvas_width: int,
) -> dict:
    """Reverse a free-form placement back to grid shape (downgrade)."""
    x = placement.get("x", 0) or 0
    width = placement.get("width", 0) or 0
    column_unit = canvas_width / 12.0
    if column_unit <= 0:
        starting_column = 0
        column_span = 12
    else:
        starting_column = max(0, int(round(x / column_unit)))
        column_span = max(1, int(round(width / column_unit)))
    if starting_column + column_span > 12:
        column_span = max(1, 12 - starting_column)

    new_placement = {
        k: v
        for k, v in placement.items()
        if k not in ("x", "y", "width", "height", "z_index")
    }
    new_placement["starting_column"] = starting_column
    new_placement["column_span"] = column_span
    return new_placement


def _migrate_rows_to_grid(
    rows: list,
    *,
    canvas_width: int,
) -> list:
    """Convert all placements in all rows back to grid shape. Re-adds
    `column_count: 12` to each row."""
    migrated_rows: list = []
    for row in rows or []:
        if not isinstance(row, dict):
            migrated_rows.append(row)
            continue
        new_row = {k: v for k, v in row.items()}
        new_row["column_count"] = 12
        new_placements = []
        for placement in row.get("placements", []) or []:
            if not isinstance(placement, dict):
                new_placements.append(placement)
                continue
            new_placements.append(
                _migrate_placement_to_grid(placement, canvas_width=canvas_width)
            )
        new_row["placements"] = new_placements
        migrated_rows.append(new_row)
    return migrated_rows


def _stamp_canvas_dimensions(canvas_config: dict | None) -> dict:
    """FF-1 pattern: stamp default 1200×800 when width/height missing.
    Preserves every other canvas_config key (gap_size,
    background_treatment, padding, etc.)."""
    cfg = dict(canvas_config or {})
    if "width" not in cfg or not isinstance(
        cfg.get("width"), (int, float)
    ) or not cfg.get("width"):
        cfg["width"] = DEFAULT_CANVAS_WIDTH
    if "height" not in cfg or not isinstance(
        cfg.get("height"), (int, float)
    ) or not cfg.get("height"):
        cfg["height"] = DEFAULT_CANVAS_HEIGHT
    return cfg


def upgrade() -> None:
    conn = op.get_bind()
    rows_result = conn.execute(
        sa.text(
            "SELECT id, template_slug, rows, canvas_config "
            "FROM focus_templates"
        )
    ).fetchall()

    migrated = 0
    skipped = 0
    for row in rows_result:
        template_id = row[0]
        template_slug = row[1]
        rows_jsonb = _coerce_jsonb(row[2]) or []
        canvas_cfg = _coerce_jsonb(row[3]) or {}

        if _is_already_freeform(rows_jsonb):
            print(
                f"[r104] Skipping template {template_slug!r} "
                f"(id={template_id}) — already free-form-shape"
            )
            skipped += 1
            continue

        new_canvas = _stamp_canvas_dimensions(canvas_cfg)
        canvas_width = int(new_canvas["width"])
        canvas_height = int(new_canvas["height"])

        placement_count_before = sum(
            len(r.get("placements", []) or [])
            for r in rows_jsonb
            if isinstance(r, dict)
        )

        print(
            f"[r104] Migrating template {template_slug!r} "
            f"(id={template_id}, placements={placement_count_before}, "
            f"canvas={canvas_width}x{canvas_height})"
        )

        new_rows = _migrate_rows_to_freeform(
            rows_jsonb,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
        )

        conn.execute(
            sa.text(
                "UPDATE focus_templates "
                "SET rows = CAST(:rows AS jsonb), "
                "    canvas_config = CAST(:canvas AS jsonb) "
                "WHERE id = :id"
            ),
            {
                "rows": json.dumps(new_rows),
                "canvas": json.dumps(new_canvas),
                "id": template_id,
            },
        )
        migrated += 1

    print(
        f"[r104] Complete — migrated={migrated} skipped={skipped} "
        f"total={len(rows_result)}"
    )


def downgrade() -> None:
    conn = op.get_bind()
    rows_result = conn.execute(
        sa.text(
            "SELECT id, template_slug, rows, canvas_config "
            "FROM focus_templates"
        )
    ).fetchall()

    reverted = 0
    skipped = 0
    for row in rows_result:
        template_id = row[0]
        template_slug = row[1]
        rows_jsonb = _coerce_jsonb(row[2]) or []
        canvas_cfg = _coerce_jsonb(row[3]) or {}

        if _is_already_grid(rows_jsonb) or not _is_already_freeform(
            rows_jsonb
        ):
            print(
                f"[r104] Skipping template {template_slug!r} "
                f"(id={template_id}) — already grid-shape or empty"
            )
            skipped += 1
            continue

        canvas_width_raw = canvas_cfg.get("width")
        canvas_width = (
            int(canvas_width_raw)
            if isinstance(canvas_width_raw, (int, float))
            and canvas_width_raw
            else DEFAULT_CANVAS_WIDTH
        )

        print(
            f"[r104] Reverting template {template_slug!r} "
            f"(id={template_id}) to grid shape"
        )

        new_rows = _migrate_rows_to_grid(
            rows_jsonb, canvas_width=canvas_width
        )

        conn.execute(
            sa.text(
                "UPDATE focus_templates "
                "SET rows = CAST(:rows AS jsonb) "
                "WHERE id = :id"
            ),
            {
                "rows": json.dumps(new_rows),
                "id": template_id,
            },
        )
        reverted += 1

    print(
        f"[r104] Downgrade complete — reverted={reverted} "
        f"skipped={skipped} total={len(rows_result)}"
    )
