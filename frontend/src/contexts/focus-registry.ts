/**
 * Focus registry — Phase A Session 2.
 *
 * Pattern B: focus ids register once with their intrinsic core mode +
 * display metadata. Consumers of `useFocus().open(id)` never pass mode
 * as a prop — the registry is the source of truth for "what mode does
 * this Focus use."
 *
 * Design discipline (open-closed):
 *   Adding a new mode requires exactly three touches:
 *     1. Append to the `CoreMode` type union below.
 *     2. Add one entry to MODE_RENDERERS in components/focus/mode-
 *        dispatcher.tsx. TypeScript's exhaustive-record check catches
 *        a forgotten entry at compile time.
 *     3. Register a focus that uses the mode (via registerFocus here).
 *   No existing mode's code changes.
 *
 * Naming convention: camelCase for core mode identifiers. Distinct
 * from the backend `triage_queue` pin_type literal (snake_case) — the
 * pin_type namespace identifies *pinnable target kinds*; the core
 * mode namespace identifies *rendering patterns*. Different concepts,
 * different namespaces.
 *
 * Roadmap modes (not in Session 2, but the type union is designed to
 * admit them without refactor): calendar, map, timeline, tree, form,
 * comparison.
 */


/** Core rendering mode for a Focus. Open for extension: append new
 *  entries here + add a MODE_RENDERERS row in mode-dispatcher.tsx. */
export type CoreMode =
  | "kanban"
  | "singleRecord"
  | "editCanvas"
  | "triageQueue"
  | "matrix"


/** Layout-state scaffold for per-session / per-user / tenant-default
 *  persistence. Session 2 stored only the session-ephemeral tier in
 *  memory on FocusContext. Session 3 ships free-form canvas coordinates
 *  (x / y / width / height in pixels, 8px-snapped) replacing Session
 *  2's earlier placeholder grid shape. Session 4 adds the
 *  `focus_sessions` + `focus_layout_defaults` tables for the other
 *  two tiers.
 *
 *  Generic parameter `TCoreLayout` allows mode-specific layout shapes
 *  (e.g. `LayoutState<KanbanColumnOrder>` or `LayoutState<TriageCursor>`)
 *  while preserving the base contract. Defaults to `unknown` — modes
 *  opt in to specialized types when they need them. */

/** Zone anchors for a canvas widget (Phase A Session 3.5).
 *
 *  Replaces Session 3's absolute-pixel positioning. Anchors keep
 *  widget positioning stable across viewport changes (window snap,
 *  browser resize, multi-device): a widget anchored to `right-rail`
 *  with offsetX=32 always renders in the right rail regardless of
 *  viewport width.
 *
 *  Eight anchors — no `center-center` by design. Widgets must never
 *  occlude the anchored core; the top-center and bottom-center
 *  anchors provide above/below-core placement without invading the
 *  core zone.
 */
export type WidgetAnchor =
  | "top-left"
  | "top-center"
  | "top-right"
  | "left-rail"
  | "right-rail"
  | "bottom-left"
  | "bottom-center"
  | "bottom-right"


/** Zone-relative widget position. offsetX/offsetY are distances in
 *  pixels from the anchor edge(s) — all values 8px multiples.
 *
 *  Resolution semantics per anchor (viewport dims = vw, vh):
 *    top-left      → screen.x = offsetX                 y = offsetY
 *    top-center    → screen.x = (vw-width)/2 + offsetX  y = offsetY
 *    top-right     → screen.x = vw-width-offsetX        y = offsetY
 *    left-rail     → screen.x = offsetX                 y = offsetY
 *    right-rail    → screen.x = vw-width-offsetX        y = offsetY
 *    bottom-left   → screen.x = offsetX                 y = vh-height-offsetY
 *    bottom-center → screen.x = (vw-width)/2+offsetX    y = vh-height-offsetY
 *    bottom-right  → screen.x = vw-width-offsetX        y = vh-height-offsetY
 *
 *  left-rail and right-rail use offsetY from the TOP of the viewport
 *  (same as top-* anchors) — rails span vertically by definition;
 *  offsetY picks the vertical position within the rail. */
export interface WidgetPosition {
  anchor: WidgetAnchor
  offsetX: number
  offsetY: number
  width: number
  height: number
}

/** Full per-widget state. Session 3 ships with just `position`;
 *  future sessions may add `isMinimized`, `zIndex`, custom props per
 *  widget type, etc. Nested shape future-proofs without reshaping
 *  consumers. */
export interface WidgetState {
  position: WidgetPosition
}

export type WidgetId = string

export interface LayoutState<TCoreLayout = unknown> {
  widgets: Record<WidgetId, WidgetState>
  coreLayout?: TCoreLayout
}

export interface LayoutConfig<TCoreLayout = unknown> {
  /** Admin-set baseline for this Focus type across the tenant.
   *  Persisted in `focus_layout_defaults` (Session 4). */
  tenantDefault?: LayoutState<TCoreLayout>
  /** Per-user persisted override. Saved automatically when the user
   *  rearranges. Persisted in `focus_sessions` (Session 4). */
  userOverride?: LayoutState<TCoreLayout>
  /** Current in-memory state for this session. Resets on Focus exit.
   *  Session 2 is the only tier with a live implementation. */
  sessionEphemeral?: LayoutState<TCoreLayout>
}


/** One registered Focus. Ids are opaque strings — convention is
 *  kebab-case for readability (e.g. "funeral-scheduling",
 *  "proof-review"). Session 2 seeds five `test-<mode>` ids for the
 *  dev test page; Phase B registers the first real-workflow focus
 *  ("funeral-scheduling"). */
export interface FocusConfig {
  id: string
  mode: CoreMode
  displayName: string
  /** Optional default layout — Session 2 doesn't consume it yet; the
   *  dispatcher will read `config.defaultLayout?.tenantDefault` to
   *  seed `sessionEphemeral` on open (Session 4). */
  defaultLayout?: LayoutConfig
}


// ── Singleton registry ────────────────────────────────────────────

const _registry = new Map<string, FocusConfig>()


/** Register a Focus. If the id is already registered, the new config
 *  replaces the old — sessions seeding at module load should be
 *  idempotent. Not a runtime error because HMR re-executes module
 *  bodies during dev. */
export function registerFocus(config: FocusConfig): void {
  _registry.set(config.id, config)
}


/** Look up a registered Focus by id. Returns null for unknown ids —
 *  the ModeDispatcher renders an error state; consumers handle this
 *  as a data-layer miss, not an exception. */
export function getFocusConfig(id: string): FocusConfig | null {
  return _registry.get(id) ?? null
}


/** Enumerate all registered Focuses. Used by the dev test page +
 *  future Cmd+K "open Focus" search. Order is insertion order. */
export function listFocusConfigs(): FocusConfig[] {
  return Array.from(_registry.values())
}


/** Test-only: wipe the registry. Vitest beforeEach hooks call this
 *  to isolate tests from seed side effects. NOT exported for general
 *  consumption — prefix underscore signals internal. */
export function _resetRegistryForTests(): void {
  _registry.clear()
}


// ── Seed: five stub Focuses — one per core mode (dev test page) ──

registerFocus({
  id: "test-kanban",
  mode: "kanban",
  displayName: "Kanban stub",
  // Session 3 — seed one mock saved-view widget on Kanban so the
  // canvas contract is exercised as soon as the Focus opens. The
  // other stubs open without widgets; smart-positioning shows its
  // value when a user pins something mid-session.
  defaultLayout: {
    tenantDefault: {
      widgets: {
        "mock-saved-view-1": {
          position: {
            anchor: "top-left",
            offsetX: 32,
            offsetY: 96,
            width: 320,
            height: 240,
          },
        },
      },
    },
  },
})

registerFocus({
  id: "test-single-record",
  mode: "singleRecord",
  displayName: "Single-record stub",
})

registerFocus({
  id: "test-edit-canvas",
  mode: "editCanvas",
  displayName: "Edit-canvas stub",
})

registerFocus({
  id: "test-triage-queue",
  mode: "triageQueue",
  displayName: "Triage-queue stub",
})

registerFocus({
  id: "test-matrix",
  mode: "matrix",
  displayName: "Matrix stub",
})
