#!/usr/bin/env node
/**
 * Refuse a vitest run whose SUITE SHRANK.
 *
 * ⚠️ WHY THIS EXISTS. Measured 2026-10-07, run cap6_10 of a worker-cap experiment:
 *
 *     Test Files  338 passed (338)
 *          Tests  4493 passed | 5 skipped | 1 todo (4499)
 *         Errors  6 errors
 *     Error: [vitest-pool]: Failed to start forks worker for test files …
 *     Caused by: Error: [vitest-pool-runner]: Timeout waiting for worker to respond
 *
 * SIX TEST FILES NEVER RAN, and the summary printed `338 passed (338)` — the
 * denominator fell from 344 and the line still reads complete. That is the shape
 * CLAUDE.md calls "a gate reports its denominator", arriving inside the test
 * runner's own summary. Only a separately-recorded expected total caught it.
 *
 * ⚠️ AND VITEST CANNOT CATCH THIS BY ITSELF, WHICH IS THE WHOLE ARGUMENT FOR A
 * COMMITTED BASELINE. The six files that failed to start workers were not counted
 * in the total at all, so vitest's own "collected" number was already 338.
 * Comparing ran-against-collected inside one run compares 338 to 338. The only
 * reference that can disagree is one written down earlier and read back.
 *
 * ⚠️ IN THE RUNS OBSERVED SO FAR, A SHORTFALL ALWAYS CAME WITH `Errors N` AND A
 * NON-ZERO EXIT, SO CI WOULD ALREADY HAVE GONE RED. This guard is for the case
 * where it does not: an `include` pattern that stops matching, a file renamed to
 * `.test.ts.bak`, a `describe.skip` at the top of a file, an `exclude` typo. Each
 * removes tests with exit 0 and a summary that reads complete. The break test
 * below reproduces exactly that — `--exclude` on real files, exit 0, shortfall —
 * because it is the case nothing else covers.
 *
 * ⚠️ A FLOOR, NOT AN EQUALITY. Adding tests must not fail CI. Removing them on
 * purpose means lowering the baseline IN THE SAME DIFF, which is the ratchet the
 * backend's `_EXCLUDED_CEILING` already uses in the other direction — the number
 * may only move in a reviewed commit, never by drift.
 *
 * Reads the vitest JSON reporter's output. ⚠️ FILES COME FROM `testResults.length`,
 * NOT `numTotalTestSuites` — measured: a 2-file subset reported
 * `numTotalTestSuites: 4`, because that field counts `describe` blocks. Using it
 * would have made this guard measure a unit nobody meant.
 *
 * Usage: node scripts/assert-suite-size.mjs <summary.json> [baseline.json]
 */
import { readFileSync } from "node:fs";

export function readTotals(summary) {
  if (summary == null || typeof summary !== "object") {
    throw new Error("summary is not an object");
  }
  if (!Array.isArray(summary.testResults)) {
    throw new Error("summary has no testResults array");
  }
  if (typeof summary.numTotalTests !== "number") {
    throw new Error("summary has no numeric numTotalTests");
  }
  return { files: summary.testResults.length, tests: summary.numTotalTests };
}

export function compare(got, baseline) {
  const shortfalls = [];
  for (const key of ["files", "tests"]) {
    if (typeof baseline[key] !== "number") {
      throw new Error(`baseline has no numeric ${key}`);
    }
    if (got[key] < baseline[key]) {
      shortfalls.push({ key, got: got[key], expected: baseline[key] });
    }
  }
  const growth = ["files", "tests"].filter((k) => got[k] > baseline[k]);
  return { shortfalls, growth };
}

function main() {
  const [summaryPath, baselinePath = "fixtures/suite-size.json"] =
    process.argv.slice(2);
  if (!summaryPath) {
    console.error("usage: assert-suite-size.mjs <summary.json> [baseline.json]");
    process.exit(2);
  }

  // ⚠️ AN ABSENT OR UNPARSEABLE SUMMARY IS A FAILURE, NEVER A PASS. A guard that
  // skips when its input is missing is the shape that lets a run with no reporter
  // output look clean.
  let summary;
  try {
    summary = JSON.parse(readFileSync(summaryPath, "utf8"));
  } catch (e) {
    console.error(`suite-size: cannot read ${summaryPath}: ${e.message}`);
    process.exit(1);
  }
  const baseline = JSON.parse(readFileSync(baselinePath, "utf8"));

  let got;
  try {
    got = readTotals(summary);
  } catch (e) {
    console.error(`suite-size: ${summaryPath} is not a vitest summary: ${e.message}`);
    process.exit(1);
  }

  let result;
  try {
    result = compare(got, baseline);
  } catch (e) {
    // ⚠️ A MALFORMED BASELINE IS AN INSTRUMENT FAULT, REPORTED AS ONE. `compare`
    // throws rather than treating a missing key as satisfied, because `got < undefined`
    // is false — a typo in the fixture would otherwise disable the guard and leave it
    // green, which is the exact shape this guard exists to catch, one layer up.
    console.error(`suite-size: ${baselinePath} is unusable: ${e.message}`);
    process.exit(1);
  }
  const { shortfalls, growth } = result;
  console.log(
    `suite-size: ran ${got.files} files / ${got.tests} tests; ` +
      `baseline ${baseline.files} files / ${baseline.tests} tests`
  );
  if (shortfalls.length > 0) {
    for (const s of shortfalls) {
      console.error(
        `suite-size: FAIL — ${s.key} shrank: ran ${s.got}, baseline ${s.expected} ` +
          `(${s.expected - s.got} missing)`
      );
    }
    console.error(
      "suite-size: a run that executes fewer files or tests than the baseline has " +
        "not tested what the baseline says it tests. If the removal is deliberate, " +
        "lower fixtures/suite-size.json in the same commit."
    );
    process.exit(1);
  }
  if (growth.length > 0) {
    console.log(
      `suite-size: ${growth.join(" and ")} grew — raise fixtures/suite-size.json ` +
        "when convenient so the floor keeps up."
    );
  }
}

// Only run when invoked directly, so the tests can import the pure functions.
if (process.argv[1] && process.argv[1].endsWith("assert-suite-size.mjs")) {
  main();
}
