/// <reference types="node" />
/**
 * Widget renderer parity — Phase W-4a Step 6 Commit 4.
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
 * Scope: Pulse-eligible widgets only. The backend `WIDGET_DEFINITIONS`
 * list contains widgets for multiple surfaces — Operations Board
 * dashboards, Vault Overview dashboards, Pulse, etc. Dashboard
 * surfaces use a separate `componentMap` registration mechanism
 * (`WidgetGrid.tsx`); Pulse uses `getWidgetRenderer`. This parity
 * test covers ONLY widgets where `supported_surfaces` includes
 * `"pulse_grid"` because those are the widget_ids that flow through
 * `getWidgetRenderer`. Dashboard-only widgets dispatch elsewhere and
 * have their own parity guarantees per the dashboard mounts.
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
 * Known deferred drift documented inline: see `KNOWN_DEFERRED` set.
 */

import { readFileSync } from "node:fs"
import { resolve } from "node:path"

import { describe, expect, it, beforeAll } from "vitest"

import { getWidgetRenderer } from "@/components/focus/canvas/widget-renderers"
import { MissingWidgetEmptyState } from "@/components/focus/canvas/MissingWidgetEmptyState"
import { MockSavedViewWidget } from "@/components/focus/canvas/MockSavedViewWidget"

// Load all production widget-registration modules. Side-effect
// imports populate the `getWidgetRenderer` registry. Order matches
// the production app bootstrap (App.tsx imports these modules).
import "@/components/widgets/foundation/register"
import "@/components/widgets/manufacturing/register"
import "@/components/dispatch/scheduling-focus/register"


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
