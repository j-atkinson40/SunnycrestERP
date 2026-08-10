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
 *  offsetY picks the vertical position within the rail.
 *
 *  Aesthetic Arc Session 1.5 — `height` extended to accept `"auto"`
 *  for content-driven sizing per the new "Widget Content Sizing"
 *  principle (PLATFORM_PRODUCT_PRINCIPLES.md). When height is
 *  "auto":
 *    • WidgetChrome omits inline height (lets content determine it)
 *    • Optional `maxHeight` caps growth with overflow scroll
 *    • Vertical resize zones no-op (height isn't user-tunable when
 *      content drives it)
 *    • `resolvePosition` substitutes 0 for height in math; this is
 *      safe for top-*, left-rail, right-rail anchors (which don't
 *      use height in y-positioning); bottom-* anchors should not
 *      use auto-height (the y-anchor needs a number to subtract
 *      from viewportHeight). Test: the canonical AncillaryPoolPin
 *      uses right-rail anchor — height-in-y math irrelevant.
 *  Width remains required (layout-constrained); only height is
 *  optional-content-driven per the principle. */
export interface WidgetPosition {
  anchor: WidgetAnchor
  offsetX: number
  offsetY: number
  width: number
  height: number | "auto"
  /** Optional cap on widget height when `height === "auto"`. Above
   *  this, the widget body scrolls. Ignored when height is a fixed
   *  number. */
  maxHeight?: number
}

/** Full per-widget state. Session 3 ships with just `position`;
 *  Session 4.3b.3 adds optional `widgetType` for the typed-widget
 *  registry (see `components/focus/canvas/widget-renderers.ts`).
 *  Widget Library Phase W-1 (DESIGN_LANGUAGE.md §12.3) adds
 *  `variant_id` for the per-instance variant selection (Glance /
 *  Brief / Detail / Deep). Future sessions may add `isMinimized`,
 *  `zIndex`, custom props per widget type, etc. Nested shape
 *  future-proofs without reshaping consumers.
 *
 *  `widgetType` is OPTIONAL for back-compat: pre-4.3b.3 layouts that
 *  predate the typed-widget system (test-kanban's mock layout, any
 *  legacy persisted layouts) leave it undefined, which the registry
 *  resolves to `MockSavedViewWidget`.
 *
 *  `variant_id` is OPTIONAL for back-compat per Decision 10
 *  (both contracts coexist 1-2 release windows). When undefined,
 *  the widget renders its canvas-tier default variant. Phase W-3+
 *  layouts set explicitly per Section 12 reference implementation
 *  (e.g. funeral-scheduling Focus tenantDefault sets
 *  `variant_id: "detail"` on the AncillaryPoolPin instance for
 *  full scrollable list rendering). */
export interface WidgetState {
  position: WidgetPosition
  widgetType?: string
  /** Phase W-1 — Section 12.2 variant selection. */
  variant_id?: "glance" | "brief" | "detail" | "deep"
  /** Phase W-3b — per-instance widget configuration.
   *
   *  Loose `Record<string, unknown>` at the framework boundary.
   *  Widgets narrow internally per their `WidgetDefinition.config_schema`.
   *  Examples:
   *    - `saved_view` widget on canvas: `{view_id: string}`
   *    - `today` widget: undefined (no per-instance config)
   *
   *  Persisted in `focus_sessions.layout_state` JSONB alongside
   *  position + widgetType + variant_id. Dispatch sites (Canvas,
   *  StackRail, BottomSheet, StackExpandedOverlay) pass it through
   *  to the widget component via `WidgetRendererProps.config`. */
  config?: Record<string, unknown>
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
  /** Optional specialized renderer for this Focus. When provided, the
   *  ModeDispatcher uses this component instead of the generic stub
   *  registered for `mode` in `MODE_RENDERERS`. Phase B Session 4
   *  introduced this extension point so a real-workflow Focus (e.g.
   *  funeral scheduling) can ship its own core that reads live data +
   *  does real drag-drop, without displacing the `test-kanban` stub
   *  used by the Phase A dev test page. Open-closed: a future
   *  specialized kanban (Redi-Rock dispatch, disinterment scheduling)
   *  registers its own `coreComponent` without touching
   *  `MODE_RENDERERS`. */
  coreComponent?: React.ComponentType<{
    focusId: string
    config: FocusConfig
  }>
  /** Optional decoupling between the registered Focus id and the
   *  composition lookup key. May 2026 (composition runtime
   *  integration phase): the canvas-based Focus composition layer
   *  (focus_compositions table) keys compositions by `focus_type`
   *  string. The registered Focus id (e.g. `"funeral-scheduling"`)
   *  is descriptive; the composition's `focus_type` (e.g.
   *  `"scheduling"`) is the categorization the visual editor
   *  authors against. When this field is set, runtime composition
   *  resolution uses it as the lookup key; when unset, callers
   *  fall back to the registered id.
   *
   *  Example: `funeral-scheduling` registers with
   *  `compositionFocusType: "scheduling"` so the seeded scheduling
   *  composition's `focus_type="scheduling"` row resolves
   *  regardless of the descriptive id. */
  compositionFocusType?: string
  /** Which triage queue a `mode: "triageQueue"` Focus renders. The
   *  Decide-primitive binding as DATA, not hardcode: TriageQueueCore
   *  reads this to mount the real Phase 5 triage workspace scoped to
   *  the queue (3a.1-B). The next triage Focus (cash receipts,
   *  month-end) sets its own `queueId` — same core renders it. Maps to
   *  a backend `triage_queues.queue_id` (e.g. "workflow_review_triage").
   *  Ignored by non-triageQueue modes. */
  queueId?: string
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
  // Session 3.7 — seed THREE widgets so stack mode has something to
  // cycle through and icon-mode sheet has a meaningful widget list.
  // Anchors differ so canvas-mode placement is visually distinct
  // (top-left, right-rail, bottom-right).
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
        "mock-saved-view-2": {
          position: {
            anchor: "right-rail",
            offsetX: 16,
            offsetY: 96,
            width: 280,
            height: 320,
          },
        },
        "mock-saved-view-3": {
          position: {
            anchor: "bottom-right",
            offsetX: 32,
            offsetY: 32,
            width: 280,
            height: 200,
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

// Decision Triage — the Decide-primitive-as-Focus (3a.1-B). Bound to the
// workflow_review_triage queue, where the Legacy Order workflow stages its
// proof for approval. Open via ?focus=decision-triage. The next triage Focus
// (cash receipts, month-end) registers the same way with its own queueId.
registerFocus({
  id: "decision-triage",
  mode: "triageQueue",
  displayName: "Decision Triage",
  queueId: "workflow_review_triage",
})

// ── Accounting Focuses (FB-1) ──────────────────────────────────────────────
//
// THE ACCOUNTING SUITE HAD ZERO FOCUSES BEFORE THIS, not one. Books Review was
// described as a Focus for weeks; it is a purpose-built DISPLAY COMPONENT
// (ReconciliationExceptionDisplay) rendering inside the /triage/ page, bound to
// the Focus primitive nowhere. Verified: `reconciliation_review_triage` had zero
// non-test references in frontend/src.
//
// Each binding is data only — `TriageQueueCore` renders whatever queue its
// `queueId` names, so a Focus over an existing queue costs one entry and no
// component. What it does NOT cost is a way in: see the command-bar entries in
// services/actions/triage.ts, without which a registered Focus is reachable only
// by typing ?focus= into the URL, which is the state `decision-triage` has been
// in since it shipped.
//
// ONE QUEUE WAS DELIBERATELY NOT BOUND. `ar_collections_triage` is a worklist,
// not a bounded decision: the condition that stages an item (this customer owes
// and is overdue) does not resolve when the operator sends the drafted email —
// it resolves when they pay, elsewhere and later, and tomorrow's run re-stages
// the same customers. THE QUEUE'S EMPTINESS IS NOT EVIDENCE THE DECISION WAS
// MADE, which is the test. It keeps its /triage/ page, which is honest about
// being a list.
//
// `cash_receipts_matching_triage` WAS held here, on the reasoning that it and
// Books Review answer "what is this unmatched money" from opposite ends and that
// post-A-2 Books Review has claim machinery cash receipts lacks. FB-2 re-derived
// that at HEAD and BOUND IT (below). The two queues answer DIFFERENT QUESTIONS
// OVER DIFFERENT OBJECTS, and resolving either leaves the other open:
//
//   Books Review   item = a BANK STATEMENT LINE — "what is this line, and does
//                  it correspond to something the books already recorded?"
//   Cash receipts  item = a CUSTOMER PAYMENT — "which invoice does this settle?"
//
// Applying a payment to an invoice leaves the bank line unreconciled; clearing
// the bank line against the payment record leaves the payment unapplied in the
// AR subledger. `_try_claim` stops one payment being claimed by two statement
// lines — that protects bank reconciliation, and is not the guard that
// payment-to-invoice application needs.

registerFocus({
  id: "books-review",
  mode: "triageQueue",
  displayName: "Books Review",
  queueId: "reconciliation_review_triage",
})

// The strongest of the four by the bounded-decision test: per-JOB cardinality
// (one item, one irreversible decision, a period lock on the far side), and it
// terminates by construction because `awaiting_approval` is a state a job leaves.
registerFocus({
  id: "month-end-close",
  mode: "triageQueue",
  displayName: "Month-End Close",
  queueId: "month_end_close_triage",
})

// Bounded in principle — every uncategorized line is coded and the set is
// finite. ⚠️ UNEXERCISED IN PRACTICE: on dev this queue has never held an item,
// because `find_uncategorized_expenses` reports `total_bill_lines_in_period: 0`
// on every one of 5,167 runs. That is a source-population fact (no vendor bills
// dated inside the run's window), NOT an agent defect — the four steps complete
// and the classifier is reached. Production is UNVERIFIED. Bound anyway because
// the emptiness is data, not structure; revisit if production is empty too.
registerFocus({
  id: "expense-categorization",
  mode: "triageQueue",
  displayName: "Expense Categorization",
  queueId: "expense_categorization_triage",
})

// FB-2. Passes the bounded-decision test cleanly and is the one queue on the
// tenant with real volume behind it: `approve_match` writes the
// CustomerPaymentApplication, moves `Invoice.amount_paid`, flips status when
// fully applied and resolves the anomaly in ONE transaction — so the condition
// that staged the item is closed BY the action, which is the whole test.
// Contrast `ar_collections_triage` above, where sending the email leaves the
// invoice just as overdue as it was.
//
// Production substrate at binding time: 208 anomalies ever, 3 unresolved —
// against ar_collections' 2 and month_end_close's 0. The most-exercised queue
// the tenant has, and until now reachable only as a /triage/ list.
//
// ⚠️ THIS IS THE FIFTH FOCUS ON THE WRONG SIDE OF A SPLIT NOBODY HAS DECIDED.
// The frontend registry now holds 5 production triageQueue Focuses; the backend
// `focus_templates` table holds 2 (`decision-triage`, `legacy-generation`), and
// the overlap is `decision-triage` alone. "Cash receipts is bound" and "the Map
// can point at cash receipts" remain SEPARATE CLAIMS, and only the first is
// true. Recorded so the eventual reconciliation has an accurate count rather
// than a rediscovery.
registerFocus({
  id: "cash-receipts",
  mode: "triageQueue",
  displayName: "Cash Receipts",
  queueId: "cash_receipts_matching_triage",
})

registerFocus({
  id: "test-matrix",
  mode: "matrix",
  displayName: "Matrix stub",
})
