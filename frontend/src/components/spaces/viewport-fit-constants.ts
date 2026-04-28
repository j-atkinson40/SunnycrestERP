/**
 * Pulse viewport-fit math constants — Phase W-4a Step 6 Commit 1.
 *
 * Source of truth: DESIGN_LANGUAGE.md §13.3.4 (Viewport-Fit Math).
 * This module mirrors the canonical constants table verbatim. If
 * anything here drifts from §13.3.4, the canon is the contract — fix
 * here, not there.
 *
 * Hard-coded values per Step 6 canon ("September: hard-coded
 * constants per `frontend/src/components/spaces/PulseSurface.tsx`
 * module-level"). Dynamic ResizeObserver detection of chrome
 * elements is the post-September canonical target — TODO at the
 * bottom of this file.
 *
 * All values in pixels unless noted. Names mirror the §13.3.4
 * constants table exactly so a future audit can grep this file
 * against the canon.
 */


// ── Chrome heights (always present) ──────────────────────────────────


/** AppLayout top header. `h-14` = 56 px. See
 *  `frontend/src/components/layout/app-layout.tsx`. */
export const APP_HEADER_HEIGHT = 56

/** DotNav rail at bottom of sidebar (always present, even on mobile
 *  where it's part of the bottom-tab-bar overlay). Rough vertical
 *  claim — actual ~h-8 + padding. */
export const DOT_NAV_HEIGHT = 32

/** Mobile-only bottom tab bar. `h-14`. Hidden on tablet+ (≥768 px).
 *  See `frontend/src/components/layout/mobile-tab-bar.tsx`. */
export const MOBILE_TAB_BAR_HEIGHT = 56


// ── PulseSurface internal chrome ─────────────────────────────────────


/** PulseSurface page padding-y total. `py-6` × 2 sides = 24 + 24. */
export const PULSE_PAGE_PADDING_Y = 48

/** Vertical spacing between layers. `space-y-4` ≈ 16 px between
 *  adjacent layers; total = (N_layers − 1) × this constant. With 4
 *  canonical layers → 3 inter-layer gaps × 16 = 48 px. */
export const LAYER_SPACING = 16

/** Brass-thread divider above Operational layer. `mt-2` (8 px) +
 *  `pt-4` (16 px) + 1 px border ≈ 24 px overhead. Only above
 *  Operational layer per §13.3.2. */
export const BRASS_THREAD_OVERHEAD = 24

/** First-login banner (when visible). Sparkles icon + heading +
 *  body + CTA + dismiss X ≈ 96 px. Only when banner shows;
 *  vertical-default-NOT-applied users get 0. */
export const BANNER_HEIGHT = 96

/** Empty-with-advisory layer height. Per §13.3.2 amendment: empty
 *  layers with advisory text ("All clear", "Quiet day so far.")
 *  render at this fixed height regardless of viewport scale. They
 *  sit OUTSIDE the row-count-weighted allocation. */
export const EMPTY_LAYER_ADVISORY_HEIGHT = 32


// ── Grid spacing ─────────────────────────────────────────────────────


/** Cell-to-cell vertical gap in the grid. `gap-3` = 12 px. */
export const CELL_GAP_Y = 12

/** Cell-to-cell horizontal gap. Same as Y; `gap-3`. */
export const CELL_GAP_X = 12


// ── Tier-three threshold + viewport breakpoints ──────────────────────


/** When solved cell_height drops below this, viewport-fit mode is
 *  abandoned for the session — natural-height + scroll mode dispatches
 *  per §13.3.4 Step 5. Also the floor of the §13.4.1 ultra-compact
 *  density tier (80–100 px range). */
export const MIN_READABLE_CELL_HEIGHT = 80

/** Viewport widths below this dispatch directly to natural-height
 *  scroll mode regardless of cell_height (mobile fallback per
 *  §13.3.1). */
export const MOBILE_BREAKPOINT = 600

/** Viewport widths below this use the 4-col tablet tier; ≥ this use
 *  the 6-col desktop tier. Tier-based column-count work itself ships
 *  in Commit 2 — Commit 1 just exports the breakpoint. */
export const TABLET_BREAKPOINT = 1024


// ── --pulse-scale clamp formula constants ────────────────────────────


/** Anchor available_pulse_height for --pulse-scale = 1.0. Roughly
 *  the 1080p desktop minus typical chrome (~896-900 px available).
 *  See §13.3.4 Step 6. */
export const BASELINE_AVAILABLE_HEIGHT = 900

/** Minimum --pulse-scale (compressed viewports). At
 *  available_pulse_height = ~787 px (≈ 0.875 × 900) and below, scale
 *  pins here. */
export const SCALE_FLOOR = 0.875

/** Maximum --pulse-scale (large viewports). At
 *  available_pulse_height = ~1125 px (= 1.25 × 900) and above, scale
 *  pins here; additional viewport space distributes as cell-internal
 *  breathing room (Apple Pro app discipline per §10). */
export const SCALE_CEILING = 1.25


// ── Transition discipline ────────────────────────────────────────────


/** CSS transition duration for cell-height recomputation, per §13.3.2
 *  amendment + §13.3.4 transition-discipline canon. 300-400ms ease-
 *  out target; 350ms chosen as midpoint with cubic-bezier ease-out. */
export const CELL_HEIGHT_TRANSITION_DURATION_MS = 350

/** Easing curve for cell-height + tier-transition CSS transitions.
 *  Matches Tailwind's `ease-out` cubic-bezier (well-established
 *  settle-feel curve). */
export const CELL_HEIGHT_TRANSITION_EASING = "cubic-bezier(0.4, 0, 0.2, 1)"


// ── ResizeObserver debounce ──────────────────────────────────────────


/** Debounce window for window-resize events. Pulse recomputes
 *  cell_height on resize, but spamming during a continuous drag
 *  causes thrash. 16 ms ≈ 1 frame — feels instant but coalesces
 *  bursts. */
export const RESIZE_DEBOUNCE_MS = 16


// ── Future work (post-September dynamic detection) ───────────────────


/**
 * TODO (post-September): replace the hard-coded chrome heights above
 * with dynamic measurement via ResizeObserver on the actual chrome
 * elements (#app-header, #dot-nav, #mobile-tab-bar, .pulse-banner).
 * Per §13.3.4 canon: "Post-September canonical target: dynamic
 * `ResizeObserver` on each chrome element so changes to header
 * height / DotNav height ripple naturally without canon updates."
 *
 * Until then: when AppLayout / DotNav / MobileTabBar / banner sizes
 * change, update the constants here in lockstep with the layout
 * components. Canon §13.3.4 documents the constants table; both
 * must stay in sync (mirror discipline).
 */
