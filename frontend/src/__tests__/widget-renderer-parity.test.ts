/// <reference types="node" />
/**
 * Widget renderer parity — Phase W-4a Step 6 Commit 4
 * (+ Arc 4a.2a dashboard-grid branch extension).
 *
 * Per DESIGN_LANGUAGE.md §13.4.3:
 *   "CI parity test mandatory. Every backend `widget_id` declared in
 *    `app/services/widgets/widget_registry.py::WIDGET_DEFINITIONS`
 *    must have a corresponding frontend renderer registered via
 *    `registerWidgetRenderer(widget_id, Component)`. A vitest test
 *    imports all widget-registration modules + asserts every backend
 *    widget_id resolves to a registered renderer (not the fallback).
 *    The CI parity test fails loudly when a backend declaration has
 *    no frontend implementation — surfaces backend/frontend drift
 *    before it reaches production."
 *
 * Scope: TWO BRANCHES per widget-renderer-parity.test.ts:18-24 canon.
 *
 * BRANCH 1 — Pulse-eligible widgets (`supported_surfaces` includes
 * `"pulse_grid"`). These dispatch via `getWidgetRenderer` (canvas
 * registry side-effect-on-import). Pre-Arc-4a.2a this was the only
 * branch.
 *
 * BRANCH 2 — Dashboard-grid widgets (Arc 4a.2a). Widgets with
 * `supported_surfaces` including `"dashboard_grid"` dispatch via
 * WidgetGrid componentMap (`OPS_BOARD_WIDGETS` for ops-board surfaces;
 * `vaultHubRegistry.getComponentMap()` for vault). Active assertion:
 * every dashboard-grid widget in scope has a Path 1 registration via
 * `getByName("widget", widget_id)` in the visual-editor registry.
 * `it.todo` for componentMap completeness (lands in Arc 4a.2b when
 * vault cluster wraps + vaultHubRegistry registers all 9 vault
 * widgets via Path 1).
 *
 * Implementation: parses `backend/app/services/widgets/widget_registry.py`
 * via fs.readFileSync + regex extraction. Avoids creating a sync
 * surface (no JSON fixture to keep current; no API call against a
 * running backend). Mirrors the scroll-mode test pattern (Commit 3)
 * which reads `pulse-density.css` directly.
 *
 * Risk: regex parser breaks if backend file structure changes
 * (e.g., widget_ids generated dynamically). Today widget_ids are
 * static string literals in a top-level Python list — risk is low.
 *
 * Known deferred drift documented inline: see `KNOWN_DEFERRED` set
 * (Pulse branch) + `KNOWN_DEFERRED_VAULT` set (dashboard-grid
 * branch).
 */

import { readFileSync } from "node:fs"
import { resolve } from "node:path"

import { describe, expect, it, beforeAll } from "vitest"

import { getWidgetRenderer } from "@/components/focus/canvas/widget-renderers"
import { MissingWidgetEmptyState } from "@/components/focus/canvas/MissingWidgetEmptyState"
import { MockSavedViewWidget } from "@/components/focus/canvas/MockSavedViewWidget"
import { getByName } from "@/lib/visual-editor/registry"

// Load all production widget-registration modules. Side-effect
// imports populate the `getWidgetRenderer` registry. Order matches
// the production app bootstrap (App.tsx imports these modules).
import "@/components/widgets/foundation/register"
import "@/components/widgets/manufacturing/register"
import "@/components/dispatch/scheduling-focus/register"
// Arc 4a.2a — dashboard-grid branch requires the visual-editor
// registry populated. The auto-register barrel imports
// `dashboard-widgets.ts` which Path 1 wraps all 17 ops-board
// widgets. Imported separately from the canvas registry imports
// above (which feed the Pulse branch); both populate at module
// load.
import "@/lib/visual-editor/registry/auto-register"


// ── Backend widget_registry.py parser ────────────────────────────────


const BACKEND_REGISTRY_PATH = resolve(
  __dirname,
  "../../../backend/app/services/widgets/widget_registry.py",
)


/**
 * Extract Pulse-eligible widget_ids from the backend widget_registry.
 *
 * Each top-level WIDGET_DEFINITIONS entry has a `widget_id` literal
 * + a `supported_surfaces` list. We split the file content on
 * `widget_id` boundaries and inspect each block's
 * `supported_surfaces` list for `"pulse_grid"` membership.
 */
function extractPulseEligibleWidgetIds(): string[] {
  const content = readFileSync(BACKEND_REGISTRY_PATH, "utf8")
  const widgetIdRegex = /"widget_id":\s*"([^"]+)"/g
  const matches: { start: number; widget_id: string }[] = []
  let m: RegExpExecArray | null
  while ((m = widgetIdRegex.exec(content)) !== null) {
    matches.push({ start: m.index, widget_id: m[1] })
  }

  const pulseEligible: string[] = []
  for (let i = 0; i < matches.length; i++) {
    const start = matches[i].start
    const end = i + 1 < matches.length ? matches[i + 1].start : content.length
    const block = content.slice(start, end)
    // Variant blocks (declared inside `variants` arrays) duplicate
    // widget_id under nested objects; we only care about the
    // top-level entry's `supported_surfaces`. The first
    // `supported_surfaces` after the widget_id in the block is the
    // top-level one.
    if (
      block.includes('"supported_surfaces"') &&
      block.includes('"pulse_grid"')
    ) {
      pulseEligible.push(matches[i].widget_id)
    }
  }
  // Deduplicate (variant blocks may emit the same widget_id multiple
  // times in the file).
  return Array.from(new Set(pulseEligible))
}


/**
 * Arc 4a.2a — Extract widget_ids whose backend `supported_surfaces`
 * includes `"dashboard_grid"`. Parallel to extractPulseEligibleWidgetIds.
 *
 * These widgets dispatch via WidgetGrid componentMap (NOT
 * getWidgetRenderer). The dashboard-grid branch asserts every such
 * widget has a Path 1 visual-editor registration via
 * `getByName("widget", id)` so the runtime editor can resolve clicks
 * on the widget DOM.
 */
function extractDashboardEligibleWidgetIds(): string[] {
  const content = readFileSync(BACKEND_REGISTRY_PATH, "utf8")
  const widgetIdRegex = /"widget_id":\s*"([^"]+)"/g
  const matches: { start: number; widget_id: string }[] = []
  let m: RegExpExecArray | null
  while ((m = widgetIdRegex.exec(content)) !== null) {
    matches.push({ start: m.index, widget_id: m[1] })
  }

  const dashboardEligible: string[] = []
  for (let i = 0; i < matches.length; i++) {
    const start = matches[i].start
    const end = i + 1 < matches.length ? matches[i + 1].start : content.length
    const block = content.slice(start, end)
    if (
      block.includes('"supported_surfaces"') &&
      block.includes('"dashboard_grid"')
    ) {
      dashboardEligible.push(matches[i].widget_id)
    }
  }
  return Array.from(new Set(dashboardEligible))
}


// ── Known deferred drift ─────────────────────────────────────────────


/**
 * Widget IDs that the backend declares with `pulse_grid` support but
 * the frontend cannot yet render via `registerWidgetRenderer`. Each
 * entry has a documented reason + tracker reference. The parity test
 * permits these widgets to fail; any widget_id NOT in this set must
 * resolve to a registered renderer.
 *
 * When a deferred entry's blocker is closed, REMOVE it from this
 * set + verify the test passes. Entries left here as documentation;
 * the set should shrink over time, never grow.
 *
 * Phase W-4a Cleanup Session B.2 closed `scheduling.ancillary-pool`
 * — the registration key migrated to the canonical backend key +
 * AncillaryPoolPin gained Brief variant for pulse_grid surface +
 * `useAncillaryPool` hook + `/widget-data/ancillary-pool` endpoint.
 * Map is empty; the structure stays so future deferrals have a
 * documented home (and the stale-entry-detection guard stays armed).
 */
const KNOWN_DEFERRED: ReadonlyMap<string, string> = new Map([])


/**
 * Arc 4a.2a — Widget IDs the backend declares with `dashboard_grid`
 * support but Arc 4a.2a explicitly does NOT wrap. Each entry has a
 * documented reason. The dashboard-grid parity branch permits these
 * widgets to fail Path 1 registration; any dashboard_grid widget NOT
 * in this set must resolve to a registered visual-editor component.
 *
 * Arc 4a.2b ships the vault cluster wrap + closes these entries.
 * `revenue_summary` + `ar_summary` are documented separately —
 * they have NO frontend component and are documented in the Arc
 * 4a.2a build report as a substrate gap (cannot wrap what doesn't
 * exist).
 */
const KNOWN_DEFERRED_VAULT: ReadonlyMap<string, string> = new Map([
  [
    "vault_recent_documents",
    "Arc 4a.2b — vault cluster wrap deferred to next arc per scope split (B-4a2-2).",
  ],
  [
    "vault_pending_signatures",
    "Arc 4a.2b — vault cluster wrap deferred to next arc per scope split (B-4a2-2).",
  ],
  [
    "vault_unread_inbox",
    "Arc 4a.2b — vault cluster wrap deferred to next arc per scope split (B-4a2-2).",
  ],
  [
    "vault_notifications",
    "Arc 4a.2b — vault cluster wrap deferred to next arc per scope split (B-4a2-2).",
  ],
  [
    "vault_recent_deliveries",
    "Arc 4a.2b — vault cluster wrap deferred to next arc per scope split (B-4a2-2).",
  ],
  [
    "vault_crm_recent_activity",
    "Arc 4a.2b — vault cluster wrap deferred to next arc per scope split (B-4a2-2).",
  ],
  [
    "vault_pending_period_close",
    "Arc 4a.2b — vault cluster wrap deferred to next arc per scope split (B-4a2-2).",
  ],
  [
    "vault_gl_classification_review",
    "Arc 4a.2b — vault cluster wrap deferred to next arc per scope split (B-4a2-2).",
  ],
  [
    "vault_agent_recent_activity",
    "Arc 4a.2b — vault cluster wrap deferred to next arc per scope split (B-4a2-2).",
  ],
  [
    "revenue_summary",
    "Arc 4a.2a substrate gap — backend WIDGET_DEFINITIONS declares this widget but NO frontend React component exists today. Cannot wrap what doesn't exist. Documented in Arc 4a.2a build report.",
  ],
  [
    "ar_summary",
    "Arc 4a.2a substrate gap — backend WIDGET_DEFINITIONS declares this widget but NO frontend React component exists today. Cannot wrap what doesn't exist. Documented in Arc 4a.2a build report.",
  ],
])


// ── Tests ────────────────────────────────────────────────────────────


describe("Widget renderer parity (CI gate per DESIGN_LANGUAGE §13.4.3)", () => {
  let pulseEligibleWidgetIds: string[]

  beforeAll(() => {
    pulseEligibleWidgetIds = extractPulseEligibleWidgetIds()
  })

  it("backend registry parser extracts at least 9 Pulse-eligible widget_ids", () => {
    // Sanity check that the regex parser actually found widgets. As
    // of W-4a Step 6 there are 10 Pulse-eligible widgets. If the
    // count drops below 9 something has gone wrong (parse failure
    // OR backend regression).
    expect(pulseEligibleWidgetIds.length).toBeGreaterThanOrEqual(9)
  })

  it("every Pulse-eligible backend widget_id resolves to a registered frontend renderer", () => {
    const failures: { widget_id: string; resolved: string }[] = []
    for (const widget_id of pulseEligibleWidgetIds) {
      if (KNOWN_DEFERRED.has(widget_id)) continue
      const renderer = getWidgetRenderer(widget_id)
      if (
        renderer === MissingWidgetEmptyState ||
        renderer === MockSavedViewWidget
      ) {
        failures.push({
          widget_id,
          resolved:
            renderer === MissingWidgetEmptyState
              ? "MissingWidgetEmptyState"
              : "MockSavedViewWidget",
        })
      }
    }

    if (failures.length > 0) {
      const detail = failures
        .map(
          (f) =>
            `  • backend widget_id "${f.widget_id}" resolves to ${f.resolved} ` +
            `(no frontend renderer registered)`,
        )
        .join("\n")
      throw new Error(
        `Widget renderer parity CI gate failed (DESIGN_LANGUAGE §13.4.3):\n` +
          detail +
          `\n\nFix paths:\n` +
          `  1. Register the missing renderer via registerWidgetRenderer(widget_id, Component) ` +
          `in the matching frontend register.ts (foundation / manufacturing / scheduling-focus).\n` +
          `  2. If the widget cannot ship a frontend renderer yet, add an entry to ` +
          `KNOWN_DEFERRED in this file with a documented reason + tracker reference.\n` +
          `  3. If the widget is dashboard-only and shouldn't reach Pulse, remove ` +
          `"pulse_grid" from its supported_surfaces in widget_registry.py.`,
      )
    }
  })

  it("every KNOWN_DEFERRED entry corresponds to a real backend widget_id", () => {
    // Catches stale KNOWN_DEFERRED entries — if Path 3 ships and
    // someone forgets to remove the entry, this test reminds them
    // by verifying the deferred entry still represents real drift.
    for (const [widget_id, reason] of KNOWN_DEFERRED) {
      expect(reason).toBeTruthy() // every entry has a documented reason
      expect(pulseEligibleWidgetIds).toContain(widget_id)
    }
  })

  it("KNOWN_DEFERRED entries actually resolve to fallback (i.e., the deferred drift is real)", () => {
    // If a KNOWN_DEFERRED entry stops resolving to fallback (someone
    // registered the renderer), this test catches the stale entry +
    // signals "remove this from KNOWN_DEFERRED."
    for (const [widget_id, reason] of KNOWN_DEFERRED) {
      const renderer = getWidgetRenderer(widget_id)
      if (
        renderer !== MissingWidgetEmptyState &&
        renderer !== MockSavedViewWidget
      ) {
        throw new Error(
          `KNOWN_DEFERRED entry "${widget_id}" now resolves to a real renderer. ` +
            `The deferred drift has been closed — remove this entry from KNOWN_DEFERRED.\n` +
            `Original reason: ${reason}`,
        )
      }
    }
  })

  it("the canonical 10 Pulse-eligible widget_ids resolve cleanly (regression guard)", () => {
    // Explicit list of Pulse-eligible widget_ids that should resolve
    // post-W-4a. If any of these regress (someone deletes a
    // register.ts call or renames a key), test fails immediately
    // with the offending widget_id. Regression guard separate from
    // the dynamic backend-walk above.
    //
    // Phase W-4a Cleanup Session B.2 — `scheduling.ancillary-pool`
    // moves from KNOWN_DEFERRED to CANONICAL after the surface-
    // aware refactor closed the Path 3 deferral. List grows from
    // 9 → 10.
    const CANONICAL_PULSE_WIDGETS = [
      "today",
      "operator_profile",
      "recent_activity",
      "anomalies",
      "saved_view",
      "briefing",
      "vault_schedule",
      "line_status",
      "urn_catalog_status",
      "scheduling.ancillary-pool",
    ] as const

    for (const widget_id of CANONICAL_PULSE_WIDGETS) {
      const renderer = getWidgetRenderer(widget_id)
      expect(renderer).toBeDefined()
      expect(renderer).not.toBe(MissingWidgetEmptyState)
      expect(renderer).not.toBe(MockSavedViewWidget)
    }
  })
})


// ─────────────────────────────────────────────────────────────────────
// Arc 4a.2a — Dashboard-grid branch (parallel to Pulse branch above).
//
// Backend widget_ids with `supported_surfaces` including
// `"dashboard_grid"` MUST resolve to a Path 1 visual-editor
// registration via `getByName("widget", widget_id)`. The Path 1
// registration wraps the component with the `data-component-name`
// boundary div so the runtime editor's SelectionOverlay can resolve
// clicks on dashboard surfaces.
//
// Widget_id mapping: backend declares `widget_id` strings; the
// visual-editor registry uses these SAME strings as the `name` field
// (per `dashboard-widgets.ts` registrations — `name: "todays_services"`
// matches backend `widget_id: "todays_services"`). 1:1 lookup via
// getByName.
//
// Vault cluster + revenue_summary/ar_summary deferred per
// KNOWN_DEFERRED_VAULT — vault wraps land in Arc 4a.2b; revenue/ar
// have no frontend component (substrate gap).
// ─────────────────────────────────────────────────────────────────────


describe("Widget renderer parity — dashboard-grid branch (Arc 4a.2a)", () => {
  let dashboardEligibleWidgetIds: string[]

  beforeAll(() => {
    dashboardEligibleWidgetIds = extractDashboardEligibleWidgetIds()
  })

  it("backend registry parser extracts at least 17 dashboard-grid widget_ids", () => {
    // Arc 4a.2a backfilled supported_surfaces on 28 widgets (17 ops-
    // board + 9 vault + revenue_summary + ar_summary). Plus the
    // pre-existing widgets in `./widgets.ts` that declare both
    // `pulse_grid` AND `dashboard_grid` per the W-3a foundation set
    // (saved_view, vault_schedule, etc). Expected count ≥ 17 (the
    // ops-board cluster floor).
    expect(dashboardEligibleWidgetIds.length).toBeGreaterThanOrEqual(17)
  })

  it("every dashboard-grid backend widget_id has a Path 1 visual-editor registration", () => {
    // Active assertion: every widget the backend declares with
    // dashboard_grid support must have a Path 1 wrap registered in
    // the visual-editor registry. Wraps live in:
    //   • `./registrations/dashboard-widgets.ts` (Arc 4a.2a — ops-board cluster; uses snake_case names matching backend widget_id verbatim)
    //   • `./registrations/widgets.ts` (Pulse cluster — many also dashboard_grid; uses kebab-case names per pre-Arc-4a.2a canon)
    //   • `./registrations/scheduling-widgets.ts` (`ancillary-pool` clean slug; canvas key `scheduling.ancillary-pool` carried via `extensions.canvasKey`)
    //
    // Name-convention asymmetry: pre-existing widgets.ts +
    // scheduling-widgets.ts entries adopted kebab-case names; Arc 4a.2a
    // dashboard-widgets.ts uses snake_case to match backend widget_id
    // directly. Acknowledged drift — neither convention is wrong, but
    // the parity test must try MULTIPLE name shapes before declaring
    // failure. Future cleanup arc may unify; not 4a.2a scope.
    //
    // Three lookup shapes attempted per widget_id:
    //   1. Direct (Arc 4a.2a snake_case — backend widget_id verbatim)
    //   2. Kebab-case (`saved_view` → `saved-view` for widgets.ts)
    //   3. Tail-segment after dot (`scheduling.ancillary-pool` → `ancillary-pool` for scheduling-widgets.ts canvas key bridge)
    //
    // KNOWN_DEFERRED_VAULT bypasses 9 vault widgets (wraps in 4a.2b)
    // + 2 substrate-gap widgets (revenue_summary + ar_summary —
    // backend declares them but no frontend component exists).
    const failures: string[] = []
    for (const widget_id of dashboardEligibleWidgetIds) {
      if (KNOWN_DEFERRED_VAULT.has(widget_id)) continue
      const entryDirect = getByName("widget", widget_id)
      const entryKebab = entryDirect
        ? null
        : getByName("widget", widget_id.replace(/_/g, "-"))
      // Tail-segment fallback for dot-namespaced widget_ids like
      // `scheduling.ancillary-pool` (registered as `ancillary-pool`
      // with extensions.canvasKey bridging back to the dotted form).
      const entryTail =
        entryDirect || entryKebab
          ? null
          : widget_id.includes(".")
            ? getByName("widget", widget_id.split(".").pop()!)
            : null
      if (!entryDirect && !entryKebab && !entryTail) {
        failures.push(widget_id)
      }
    }

    if (failures.length > 0) {
      throw new Error(
        `Dashboard-grid parity gate failed (Arc 4a.2a):\n` +
          failures.map((id) => `  • backend widget_id "${id}" has no Path 1 registration (tried snake_case, kebab-case, and tail-segment lookups)`).join("\n") +
          `\n\nFix paths:\n` +
          `  1. Add a registerComponent({...name: "<widget_id>"...})(RawWidget) entry to ` +
          `lib/visual-editor/registry/registrations/dashboard-widgets.ts OR ` +
          `widgets.ts (whichever shim file the widget cluster belongs to).\n` +
          `  2. If the widget cannot ship a Path 1 wrap yet, add an entry to ` +
          `KNOWN_DEFERRED_VAULT in this file with a documented reason + arc reference.\n` +
          `  3. If the widget is misclassified as dashboard_grid, remove ` +
          `"dashboard_grid" from its supported_surfaces in widget_registry.py.`,
      )
    }
  })

  it("every KNOWN_DEFERRED_VAULT entry corresponds to a real backend dashboard-grid widget_id", () => {
    // Stale-entry-detection guard. When Arc 4a.2b ships and someone
    // forgets to remove vault entries from this set, the test fires.
    // Surfaces happen via the absence of the widget from the
    // dynamically-extracted dashboardEligibleWidgetIds list — meaning
    // it isn't being declared with dashboard_grid support in the
    // backend at all. revenue_summary/ar_summary are surfaced via
    // membership in dashboardEligibleWidgetIds (Part 1 backfill
    // added the supported_surfaces declaration on them).
    for (const [widget_id, reason] of KNOWN_DEFERRED_VAULT) {
      expect(reason).toBeTruthy()
      expect(dashboardEligibleWidgetIds).toContain(widget_id)
    }
  })

  it.todo(
    "every dashboard_grid widget not in KNOWN_DEFERRED_VAULT has a componentMap entry " +
      "(closes in Arc 4a.2b when vault cluster wraps + vaultHubRegistry registers all 9 vault widgets via Path 1)",
  )

  it("the canonical 17 ops-board widget_ids resolve to Path 1 registrations (regression guard)", () => {
    // Explicit list of dashboard-grid widget_ids that MUST have Path
    // 1 registrations post-Arc-4a.2a. Mirrors the Pulse branch's
    // canonical regression guard. If any of these regress (someone
    // removes a registration in dashboard-widgets.ts), the test
    // fails immediately with the offending widget_id.
    const CANONICAL_DASHBOARD_WIDGETS = [
      "todays_services",
      "legacy_queue",
      "driver_status",
      "production_status",
      "open_orders",
      "inventory_levels",
      "briefing_summary",
      "activity_feed",
      "at_risk_accounts",
      "qc_status",
      "time_clock",
      "safety_status",
      "compliance_upcoming",
      "team_certifications",
      "my_certifications",
      "my_training",
      "kb_recent",
    ] as const

    for (const widget_id of CANONICAL_DASHBOARD_WIDGETS) {
      const entry = getByName("widget", widget_id)
      expect(entry, `Missing Path 1 registration for widget_id "${widget_id}"`).toBeDefined()
    }
  })
})
