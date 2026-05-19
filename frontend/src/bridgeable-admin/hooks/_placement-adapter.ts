/**
 * F-3.1a — placement shape adapter (frontend ↔ backend).
 *
 * Background: `useFocusTemplateDraft`'s typed view of placements
 * (`WidgetPlacement` with `id` / `widget_slug` / `column_start` /
 * `column_span` / `chrome`) describes the SAME data as the backend's
 * canonical placement shape (`placement_id` / `component_kind` +
 * `component_name` / `starting_column` / `column_span` /
 * `prop_overrides`), but the field names + key conventions differ.
 *
 * Pre-F-3.1a the hook sent its frontend-shaped placements straight
 * over the wire. `_validate_placement` in
 * `backend/app/services/focus_template_inheritance/focus_templates_service.py`
 * rejected the payload (no `placement_id` string, no `component_kind`,
 * no `starting_column`); backend returned 422; rows were not
 * persisted; subsequent GET returned prior server state and the
 * widget disappeared after refresh.
 *
 * Locked decision (F-3.1a): Path A — frontend adapter. Backend
 * schema stays canonical-correct for both cores (which use
 * `component_kind` + `component_name`) and widgets (same shape).
 * Frontend's widget-narrowed `widget_slug` is an authoring
 * convenience that the adapter widens to backend canonical shape on
 * save and re-narrows on load.
 *
 * Field mapping (both directions):
 *
 *   frontend `id`           ↔  backend `placement_id`
 *   frontend `widget_slug`  ↔  backend `component_kind: "widget"` +
 *                              `component_name: <slug>`
 *   frontend `column_start` ↔  backend `starting_column`
 *                              (1-INDEXED ↔ 0-INDEXED — adapter
 *                               subtracts 1 on send, adds 1 on load)
 *   frontend `column_span`  ↔  backend `column_span` (no change)
 *   frontend `chrome`       ↔  backend `prop_overrides`
 *
 * Row metadata (`row_index` / `column_count` / `placements` list
 * structure) is identical on both sides; the adapter recurses into
 * placements only.
 *
 * Chrome storage path audit (Step 1e): the backend per-placement
 * config field is `prop_overrides` (validated as `dict` at
 * `_validate_placement` lines 214-219). It mirrors the visual
 * editor's component-configuration semantics — per-placement
 * overrides on top of registration defaults. Frontend's `chrome`
 * blob carries the same conceptual payload (per-placement prop
 * overrides via `WidgetInspectorSection`'s `onUpdateWidget` writes).
 * The two are the same data under different names; adapter maps
 * 1:1.
 *
 * Configurable props (F-3.1 investigation Q5): widget configurable
 * props (e.g., Day Strip's `daysVisible`) are written directly into
 * `placement.chrome` by the inspector (`onUpdateWidget(id, { [key]:
 * v })` at WidgetInspectorSection.tsx:103) and read back the same
 * way (`placement.chrome?.[key]` at line 101). They live inside the
 * `chrome` blob — therefore they flow through this adapter via the
 * `chrome ↔ prop_overrides` translation. F-3.1a's adapter fixes
 * configurable-props persistence as a side effect of fixing widget
 * placement persistence — same code path, same bug.
 */

import type { FocusRow, RowsBlob, WidgetPlacement } from "./useFocusTemplateDraft"

/** Backend canonical placement shape — mirrors `_validate_placement`. */
export interface BackendPlacement {
  placement_id: string
  component_kind: string
  component_name: string
  starting_column: number
  column_span: number
  prop_overrides?: Record<string, unknown>
  // Pass-through fields the adapter doesn't translate but preserves
  // on round-trip (display_config, is_core, etc.).
  [extra: string]: unknown
}

/** Backend canonical row shape (placements field replaced by adapter). */
export interface BackendRow {
  row_index?: number
  column_count: number
  placements: BackendPlacement[]
  // Pass-through fields (column_widths, etc.).
  [extra: string]: unknown
}

export type BackendRowsBlob = BackendRow[]

const WIDGET_COMPONENT_KIND = "widget"

/**
 * Frontend → backend. Used on save (PUT body construction).
 *
 * `column_start` is 1-indexed on the frontend; backend
 * `starting_column` is 0-indexed. Subtract 1 on send. Clamp at 0 so
 * a frontend value of 0 (theoretically invalid but defensive) maps
 * to backend 0 rather than -1 (which would trip the
 * `starting_column < 0` validation).
 */
export function frontendToBackendPlacement(
  p: WidgetPlacement,
): BackendPlacement {
  const startingColumn = Math.max(0, (p.column_start ?? 1) - 1)
  const out: BackendPlacement = {
    placement_id: p.id,
    component_kind: WIDGET_COMPONENT_KIND,
    component_name: p.widget_slug,
    starting_column: startingColumn,
    column_span: p.column_span,
  }
  // Only emit prop_overrides when chrome is a non-empty object; the
  // backend treats absence and empty-dict equivalently and absent
  // keeps payloads small.
  if (p.chrome && Object.keys(p.chrome).length > 0) {
    out.prop_overrides = { ...p.chrome }
  }
  return out
}

/**
 * Backend → frontend. Used on load (GET response coercion) + on
 * save-response echo (the backend round-trips the same JSONB shape
 * it received).
 *
 * `starting_column` is 0-indexed on the backend; frontend
 * `column_start` is 1-indexed. Add 1 on load.
 *
 * Tolerant of (a) legacy/raw payloads still in frontend shape (key
 * `id` instead of `placement_id`, etc. — when present, prefer them
 * so a stale-snapshot round-trip doesn't drop fields), (b) absent
 * `prop_overrides` (treated as empty chrome), (c) absent
 * `component_name` (falls back to a literal "unknown" sentinel
 * rather than crashing — the canvas will render the "Unknown widget"
 * fallback panel and the operator can remove the bad placement).
 */
export function backendToFrontendPlacement(
  p: BackendPlacement | Record<string, unknown>,
): WidgetPlacement {
  // Tolerate either-shape input so callers that already hold
  // frontend-shaped placements (legacy snapshots, test fixtures) are
  // never double-translated.
  const rec = p as Record<string, unknown>
  const id =
    typeof rec.placement_id === "string"
      ? rec.placement_id
      : typeof rec.id === "string"
        ? rec.id
        : ""
  const widgetSlug =
    typeof rec.component_name === "string"
      ? rec.component_name
      : typeof rec.widget_slug === "string"
        ? rec.widget_slug
        : "unknown"
  const startingColumn =
    typeof rec.starting_column === "number"
      ? rec.starting_column
      : typeof rec.column_start === "number"
        ? rec.column_start - 1 // already 1-indexed input — back to 0
        : 0
  const columnSpan =
    typeof rec.column_span === "number" ? rec.column_span : 4
  const propOverrides =
    rec.prop_overrides && typeof rec.prop_overrides === "object"
      ? (rec.prop_overrides as Record<string, unknown>)
      : rec.chrome && typeof rec.chrome === "object"
        ? (rec.chrome as Record<string, unknown>)
        : {}
  return {
    id,
    widget_slug: widgetSlug,
    column_start: startingColumn + 1,
    column_span: columnSpan,
    chrome: { ...propOverrides },
  }
}

/** Row-level frontend → backend. Preserves row_index + column_count. */
export function frontendToBackendRow(r: FocusRow): BackendRow {
  return {
    row_index: r.row_index,
    column_count: r.column_count ?? 12,
    placements: (r.placements ?? []).map(frontendToBackendPlacement),
  }
}

/** Row-level backend → frontend. Tolerant of missing column_count. */
export function backendToFrontendRow(
  r: BackendRow | Record<string, unknown>,
): FocusRow {
  const rec = r as Record<string, unknown>
  const rowIndex = typeof rec.row_index === "number" ? rec.row_index : 0
  const columnCount =
    typeof rec.column_count === "number" ? rec.column_count : 12
  const placements = Array.isArray(rec.placements)
    ? (rec.placements as Array<Record<string, unknown>>).map(
        backendToFrontendPlacement,
      )
    : []
  return {
    row_index: rowIndex,
    column_count: columnCount,
    placements,
  }
}

/** Convenience helpers for the rows blob. */
export function frontendToBackendRows(rows: RowsBlob): BackendRowsBlob {
  return rows.map(frontendToBackendRow)
}

export function backendToFrontendRows(
  rows: Array<Record<string, unknown>> | undefined | null,
): RowsBlob {
  if (!Array.isArray(rows)) return []
  return rows.map(backendToFrontendRow)
}
