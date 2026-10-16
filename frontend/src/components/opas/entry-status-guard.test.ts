/**
 * The pane->bar status guard must not swallow a change to ANY field.
 *
 * ⚠️ THIS TEST EXISTS BECAUSE THE GUARD COMPARED FOUR FIELDS OF A SEVEN-FIELD
 * PAYLOAD. Three were added for the tinting; a status differing only in those was
 * judged equal and discarded one function after being reported. Hovering a pane row
 * set the state, reported it, and the report was dropped — every piece working and
 * the feature not.
 *
 * ⚠️ AND THE DEFECT IS LATENT RATHER THAN CONSTANT, WHICH IS WHY A TEST IS THE ONLY
 * RELIABLE CATCH. A hover usually lands in the same window as some other status
 * change — a debounced extraction response moving `placeholder` or `spans` — and the
 * combined update gets through, so the feature APPEARS to work when measured by hand.
 * Measured 2026-10-16: with the four-field guard restored, a hover still lit its span.
 * It is the hover that arrives alone that is lost, and that is not reproducible on
 * demand.
 *
 * ⚠️ THE REAL FIX IS THAT THIS TEST ITERATES THE FIELDS. A hand-maintained comparison
 * that must track a type is the defect; the next field added to `EntryPaneStatus`
 * should fail here rather than silently stop propagating.
 */
import { describe, expect, it } from "vitest"

import { sameEntryStatus } from "./entry-status-guard"
import type { EntryPaneStatus } from "./CapturePane"

const BASE: EntryPaneStatus = {
  placeholder: "Which vault?",
  picks: [],
  capturing: true,
  ready: true,
  spans: [{ start: 0, end: 5, state: "captured", field_ids: ["vault"] }],
  spansForText: "order",
  hoveredFieldIds: [],
}

/**
 * One altered value per field. ⚠️ EVERY KEY OF THE TYPE MUST APPEAR HERE — the test
 * below fails if a field exists on the payload and has no variant, which is what
 * makes this a ratchet rather than a snapshot of today's shape.
 */
const VARIANTS: { [K in keyof EntryPaneStatus]-?: EntryPaneStatus[K] } = {
  placeholder: "Which cemetery?",
  picks: [{ field_id: "vault", phrase: "c", options: [["a", "A"]], discriminator: null }] as never,
  capturing: false,
  ready: false,
  spans: [],
  spansForText: "order for",
  hoveredFieldIds: ["vault"],
}

describe("sameEntryStatus", () => {
  it("says a status equals itself", () => {
    expect(sameEntryStatus(BASE, { ...BASE })).toBe(true)
  })

  it("covers every field of the payload", () => {
    // ⚠️ THE CONTROL. If the variant table drifted from the type, the loop below
    // would silently test fewer fields and still pass.
    const fields = Object.keys(BASE) as (keyof EntryPaneStatus)[]
    expect(fields.length).toBeGreaterThanOrEqual(7)
    for (const f of fields) {
      expect(VARIANTS, `no variant for ${f}`).toHaveProperty(f)
    }
  })

  it("reports a DIFFERENCE in each field, one at a time", () => {
    const fields = Object.keys(BASE) as (keyof EntryPaneStatus)[]
    const swallowed = fields.filter((f) =>
      sameEntryStatus(BASE, { ...BASE, [f]: VARIANTS[f] } as EntryPaneStatus),
    )
    expect(
      swallowed,
      `the guard swallows a change to: ${swallowed.join(", ")} — a status differing ` +
        `only in those fields never reaches the bar`,
    ).toEqual([])
  })

  it("compares hoveredFieldIds by CONTENT, not identity", () => {
    // Two arrays with the same ids are the same status; a re-render that rebuilt the
    // array must not force a cascade.
    expect(
      sameEntryStatus(
        { ...BASE, hoveredFieldIds: ["vault"] },
        { ...BASE, hoveredFieldIds: ["vault"] },
      ),
    ).toBe(true)
  })
})
