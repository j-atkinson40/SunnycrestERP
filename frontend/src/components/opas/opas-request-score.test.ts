/**
 * The opener rows of the request set, scored by the SHIPPED predicate.
 *
 * ⚠️ THEY ARE SCORED HERE AND NOT IN THE PYTHON SCORER BECAUSE THE PREDICATE IS
 * TYPESCRIPT. `CAPTURE_START` and `startsCaptureWithParty` are the functions the bar
 * runs; re-expressing them in Python to score them would be a second implementation of
 * the rule — the "two lists" defect this codebase keeps recording, and the exact thing
 * the abbreviation slice was written to avoid. One set, two scorers, each running the
 * real code for its own side.
 *
 * ⚠️ IT READS THE SAME JSONL THE BACKEND SCORER READS, so a row cannot be scored by one
 * side and forgotten by the other.
 */
import { describe, expect, it } from "vitest"

import rawSet from "../../../../backend/tests/data/opas_requests.jsonl?raw"
import { CAPTURE_START, startsCaptureWithParty } from "./opas-routing"

interface Row {
  id: string
  text: string
  context: string
  scored_by: string
  want: { opens_capture?: boolean }
  source: string
}

const ROWS: Row[] = rawSet
  .split("\n")
  .filter((l) => l.trim() !== "")
  .map((l) => JSON.parse(l) as Row)

const OPENER = ROWS.filter((r) => r.scored_by === "opener")

// The tenant's vocabulary as the bar receives it. ⚠️ THE NAMES MATTER: `startsCapture`
// gates on a prefix of a KNOWN home, so a scorer with an empty list would score every
// row as "does not open" and read as a 100% failure of the opener rather than of itself.
const FH = [
  "Hopkins Funeral Home",
  "Riverside Funeral Home",
  "Riverside Memorial Chapel",
  "Smith & Sons Funeral Home",
]

const opens = (p: string) =>
  CAPTURE_START.test(p.toLowerCase()) || startsCaptureWithParty(p, FH)

describe("the request set, opener rows", () => {
  it("⚠️ IS NON-EMPTY, so a green result means something was scored", () => {
    // CLAUDE.md §11: a control that cannot distinguish itself from a failure is not a
    // control. `[].forEach` runs no assertions and reports green.
    expect(ROWS.length).toBeGreaterThan(20)
    expect(OPENER.length).toBeGreaterThan(10)
    // and both answers are represented, so a predicate stuck on one is caught
    const wants = new Set(OPENER.map((r) => r.want.opens_capture))
    expect([...wants].sort()).toEqual([false, true])
  })

  it("every row carries its provenance", () => {
    // "a case with no provenance is a case nobody can check"
    for (const r of ROWS) expect(r.source, r.id).toBeTruthy()
  })

  it.each(OPENER.map((r) => [`${r.id} ${JSON.stringify(r.text)}`, r] as const))(
    "%s",
    (_label, r) => {
      expect(opens(r.text)).toBe(r.want.opens_capture)
    },
  )
})
