/**
 * The suite-size floor — the pure halves of `scripts/assert-suite-size.mjs`.
 *
 * ⚠️ THE GUARD'S REASON TO EXIST, so a reader does not take it for ceremony. Run
 * cap6_10 of the 2026-10-07 worker-cap experiment printed
 * `Test Files 338 passed (338)` while SIX FILES NEVER RAN — the denominator fell
 * from 344 and the line still read complete. vitest cannot catch that alone: the
 * six files were never counted, so its own collected total was already 338, and
 * ran-against-collected compares 338 to 338. The only reference that can disagree
 * is one written down earlier.
 *
 * ⚠️ THE END-TO-END BEHAVIOUR IS BREAK-TESTED AGAINST A REAL RUN, NOT HERE. These
 * cover the comparison and the shape-reading; the `--exclude` run that produces a
 * genuine exit-0 shortfall is in the commit body, because it needs a whole vitest
 * invocation and this file must stay cheap.
 */
import { describe, expect, it } from "vitest"

// @ts-expect-error — plain .mjs with no type declarations, imported on purpose so
// the test exercises the same module CI runs rather than a typed copy of it.
import { compare, readTotals } from "../../scripts/assert-suite-size.mjs"

const ok = { testResults: new Array(344).fill({}), numTotalTests: 4549 }

describe("readTotals", () => {
  it("takes the file count from testResults.length", () => {
    expect(readTotals(ok)).toEqual({ files: 344, tests: 4549 })
  })

  it("⚠️ does NOT use numTotalTestSuites, which counts describe blocks", () => {
    // Measured on a real 2-file subset: `numTotalTestSuites: 4`, `testResults: 2`.
    // Reading the former would have made this guard measure a unit nobody meant,
    // and the number would have looked plausible.
    const withSuites = { ...ok, numTotalTestSuites: 999 }
    expect(readTotals(withSuites).files).toBe(344)
  })

  it.each([
    ["null", null],
    ["a string", "nope"],
    ["an object with no testResults", { numTotalTests: 10 }],
    ["an object with no numTotalTests", { testResults: [] }],
  ])("throws on %s rather than reporting zero", (_label, input) => {
    // ⚠️ THROWS, NOT RETURNS ZERO. A zero would be a shortfall and would happen to
    // fail — for the wrong reason, and with a message about the suite rather than
    // about the input. An unreadable summary is an instrument fault.
    expect(() => readTotals(input as never)).toThrow()
  })
})

describe("compare", () => {
  const base = { files: 344, tests: 4549 }

  it("passes when both totals match the baseline", () => {
    expect(compare({ files: 344, tests: 4549 }, base).shortfalls).toEqual([])
  })

  it("fails on ONE missing file even when the test total holds", () => {
    // The real failure mode: a file whose tests were all skipped or that never
    // started. The test total can look fine while a file is gone.
    const { shortfalls } = compare({ files: 343, tests: 4549 }, base)
    expect(shortfalls).toEqual([{ key: "files", got: 343, expected: 344 }])
  })

  it("fails on the real numbers from the run that caused this guard", () => {
    // cap6_10, 2026-10-07: 338 files / 4499 tests, against 344 / 4549.
    const { shortfalls } = compare({ files: 338, tests: 4499 }, base)
    expect(shortfalls).toEqual([
      { key: "files", got: 338, expected: 344 },
      { key: "tests", got: 4499, expected: 4549 },
    ])
  })

  it("is a FLOOR — growth passes and is reported, not failed", () => {
    const { shortfalls, growth } = compare({ files: 345, tests: 4600 }, base)
    expect(shortfalls).toEqual([])
    expect(growth).toEqual(["files", "tests"])
  })

  it("throws when the baseline itself is malformed", () => {
    // ⚠️ A baseline with a missing key would otherwise compare `undefined` and
    // `got < undefined` is false — so a typo in the fixture would silently disable
    // the guard while leaving it green. That is the exact shape this file exists
    // to prevent, one layer up.
    expect(() => compare({ files: 1, tests: 1 }, { files: 344 } as never)).toThrow()
  })
})
