/**
 * AccountingCompletenessTab tests — CR-2 A-4.
 *
 * ⚠️ THE BRANCHES ARE THE POINT, NOT THE HAPPY PATH. This page has three states
 * a tolerant implementation would collapse into one green tick, and each of them
 * means something different about the books:
 *
 *   - the fetch failed        → we do not know
 *   - no rows, quiet counted  → complete
 *   - no rows, nothing quiet  → nothing is DECLARED, so nothing can be missing
 *
 * A review that renders "all clear" for any of the other two is worse than no
 * review, because it is consulted INSTEAD of looking. So every one is pinned
 * here, including the negative assertion that the failure state does not say
 * anything reassuring.
 *
 * Per CLAUDE.md's comment-code discipline: the empty / loading / error paths are
 * exactly the ones a happy-path fixture skips, and DotNav's dead early-return
 * survived 14 months for want of this.
 */
import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import AccountingCompletenessTab from "./AccountingCompletenessTab"
import type { CompletenessResult, CompletenessRun } from "@/services/completeness-service"

const getReview = vi.fn()
const getObligations = vi.fn()

vi.mock("@/services/completeness-service", () => ({
  completenessService: {
    getReview: (...args: unknown[]) => getReview(...args),
    // CR-3 D-2. The tab now mounts `DeclaredObligations`, which fetches its own
    // data — so this mock has to answer for it or every test in the file dies on
    // `getObligations is not a function` in a child component, which reads like
    // a failure of whatever the test was actually asserting.
    getObligations: (...args: unknown[]) => getObligations(...args),
  },
}))

/**
 * ⚠️ THE BLOCK BODY ON `beforeEach` BELOW IS LOAD-BEARING. `() => fn.mockReset()`
 * looks identical but is not: `mockReset()` returns the MOCK, a function, and
 * vitest treats a function returned from a hook as a TEARDOWN callback. So it
 * calls `getReview()` after the test with nobody awaiting the result — and with
 * a rejection configured, that is an unhandled rejection that fails the test
 * with the raw error rather than an assertion.
 *
 * Diagnosed by bisection, and the first two hypotheses were both wrong (eager
 * promise construction in `mockRejectedValue`; then `cleanup`). Worth the note
 * because the failure surfaces on the REJECTION test while the actual defect is
 * in a hook shared by every test in the file, and the concise-arrow form is what
 * most of this codebase's test files would reach for.
 */
beforeEach(() => {
  getReview.mockReset()
  getObligations.mockReset()
  getObligations.mockResolvedValue({ obligations: [] })
})
afterEach(cleanup)

function run(over: Partial<CompletenessRun> = {}): CompletenessRun {
  return {
    key: "production_log_daily",
    label: "Production log filed",
    role_slug: "production",
    verdict: "missing",
    actionable: true,
    first: "2026-08-08",
    last: "2026-08-13",
    periods: 6,
    detail: "Nothing since 8 Aug — 6 periods.",
    ...over,
  }
}

function result(over: Partial<CompletenessResult> = {}): CompletenessResult {
  return { rows: [], quiet_summary: "", actionable_count: 0, ...over }
}

describe("the three states a green tick would collapse", () => {
  it("renders the failure as a failure, and says no conclusion can be drawn", async () => {
    getReview.mockRejectedValue(new Error("boom"))
    render(<AccountingCompletenessTab />)

    expect(await screen.findByText("The review did not run.")).toBeInTheDocument()
    expect(screen.getByText(/No conclusion should be drawn/)).toBeInTheDocument()
    // The whole reason this test exists: an unavailable review must never read
    // as a quiet month.
    expect(screen.queryByText("Nothing outstanding.")).not.toBeInTheDocument()
    expect(screen.queryByText(/No obligations are declared/)).not.toBeInTheDocument()
  })

  it("distinguishes COMPLETE from NOTHING DECLARED", async () => {
    getReview.mockResolvedValue(result({ quiet_summary: "4 obligations current." }))
    const { unmount } = render(<AccountingCompletenessTab />)

    expect(await screen.findByText("Nothing outstanding.")).toBeInTheDocument()
    expect(screen.getByText("4 obligations current.")).toBeInTheDocument()
    expect(screen.queryByText(/No obligations are declared/)).not.toBeInTheDocument()
    unmount()
    cleanup()

    // Same empty `rows`, and it must NOT read the same way. A tenant with no
    // expectations is the one case where a clean page is a lie.
    getReview.mockResolvedValue(result())
    render(<AccountingCompletenessTab />)

    expect(
      await screen.findByText("No obligations are declared for this tenant."),
    ).toBeInTheDocument()
    expect(screen.getByText(/not the same as a complete period/i)).toBeInTheDocument()
    expect(screen.queryByText("Nothing outstanding.")).not.toBeInTheDocument()
  })
})

describe("rows", () => {
  it("names the obligation, its verdict, its span and WHOSE duty it is", async () => {
    getReview.mockResolvedValue(
      result({ rows: [run()], actionable_count: 1 }),
    )
    render(<AccountingCompletenessTab />)

    expect(await screen.findByText("Production log filed")).toBeInTheDocument()
    expect(screen.getByText("Missing")).toBeInTheDocument()
    expect(screen.getByText("Nothing since 8 Aug — 6 periods.")).toBeInTheDocument()
    // Without an owner, "missing" is a complaint rather than something anyone
    // can pick up.
    expect(screen.getByText("production")).toBeInTheDocument()
    // The count is emphasised in its own <span>, so the headline is split across
    // elements — matched on the paragraph's whole text rather than by loosening
    // it to a substring, which would pass on "11 obligations" too.
    expect(
      screen.getByText(
        (_, el) =>
          el?.tagName === "P" &&
          el.textContent?.replace(/\s+/g, " ").trim() ===
            "1 obligation needs attention.",
      ),
    ).toBeInTheDocument()
  })

  it("does NOT file `unknown` under handled — the check failing is not a clean period", async () => {
    getReview.mockResolvedValue(
      result({
        rows: [run({ verdict: "unknown", detail: "Probe failed." })],
        actionable_count: 1,
      }),
    )
    render(<AccountingCompletenessTab />)

    // Rendered as its own state, not as the grey that `declined` gets.
    expect(await screen.findByText("Check failed")).toBeInTheDocument()
    expect(screen.queryByText("Declined")).not.toBeInTheDocument()
  })

  it("renders `reported_none` as a row, because a run of nil claims is a finding", async () => {
    getReview.mockResolvedValue(
      result({
        rows: [run({ verdict: "reported_none", actionable: false })],
        quiet_summary: "3 obligations current.",
        actionable_count: 0,
      }),
    )
    render(<AccountingCompletenessTab />)

    expect(await screen.findByText("Reported none")).toBeInTheDocument()
    // Not actionable, so the headline is clean — but the row is still visible,
    // which is the whole safeguard against the nil-claim carve-out being abused.
    expect(screen.getByText("Nothing outstanding.")).toBeInTheDocument()
  })

  it("renders `declined` as a visible answer rather than a gap", async () => {
    // ⚠️ THE ROW THIS TAB HAS ALWAYS STYLED AND NEVER RECEIVED. `summarise`
    // selected on ACTIONABLE, so a declination left the endpoint as a +1 to the
    // quiet count and this branch was dead. Pinned from the tab's side too, so a
    // future narrowing of the backend's selection fails here as well as there.
    getReview.mockResolvedValue(
      result({
        rows: [
          run({
            verdict: "declined",
            actionable: false,
            detail: "Declined 1 May 2026: no on-site pours",
          }),
        ],
        quiet_summary: "3 obligations current.",
        actionable_count: 0,
      }),
    )
    render(<AccountingCompletenessTab />)

    expect(await screen.findByText("Declined")).toBeInTheDocument()
    expect(
      screen.getByText("Declined 1 May 2026: no on-site pours"),
    ).toBeInTheDocument()
    // An answer, not a gap: visible, and it does not raise the headline count.
    expect(screen.getByText("Nothing outstanding.")).toBeInTheDocument()
  })

  it("renders `contradicted` as its own state, not as declined and not as missing", async () => {
    // Folding it into `declined` would hide the finding behind a quiet grey
    // pill; rendering it as `missing` would say something is absent when the
    // finding is that something ARRIVED.
    getReview.mockResolvedValue(
      result({
        rows: [
          run({
            verdict: "contradicted",
            actionable: true,
            detail:
              "Declined, and evidence arrived anyway in 2 periods, 9 Aug–10 Aug.",
          }),
        ],
        actionable_count: 1,
      }),
    )
    render(<AccountingCompletenessTab />)

    expect(await screen.findByText("Contradicted")).toBeInTheDocument()
    expect(screen.queryByText("Declined")).not.toBeInTheDocument()
    expect(screen.queryByText("Missing")).not.toBeInTheDocument()
    expect(
      screen.getByText(
        "Declined, and evidence arrived anyway in 2 periods, 9 Aug–10 Aug.",
      ),
    ).toBeInTheDocument()
  })

  it("renders what it is given and does not re-filter the backend's shape", async () => {
    // `summarise` already decided what shows. If this component filtered too,
    // the review's shape would be decided in two places.
    getReview.mockResolvedValue(
      result({
        rows: [run({ verdict: "arrived", actionable: false, key: "bank_feed_daily" })],
        actionable_count: 0,
      }),
    )
    render(<AccountingCompletenessTab />)

    expect(await screen.findByText("Arrived")).toBeInTheDocument()
  })
})

describe("refresh", () => {
  it("clears a stale result when the refresh fails", async () => {
    getReview.mockResolvedValueOnce(
      result({ rows: [run()], actionable_count: 1 }),
    )
    render(<AccountingCompletenessTab />)
    expect(await screen.findByText("Production log filed")).toBeInTheDocument()

    // The worst outcome this page has is being confidently wrong about the date
    // in its own header, so the previous verdicts must not survive the failure.
    getReview.mockRejectedValueOnce(new Error("gone"))
    await userEvent.click(screen.getByRole("button", { name: /refresh/i }))

    await waitFor(() =>
      expect(screen.getByText("The review did not run.")).toBeInTheDocument(),
    )
    expect(screen.queryByText("Production log filed")).not.toBeInTheDocument()
  })
})
