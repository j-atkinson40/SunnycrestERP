/**
 * The authoring surface, and WHERE it sits — CR-3 D-2.
 *
 * ⚠️ PLACEMENT IS THE RULING, SO PLACEMENT IS WHAT THESE ASSERT. Declining is
 * reachable from the review because a control only reachable from settings is
 * safe and never found — four surfaces were built-and-unreachable in the
 * fortnight before this, one of them in this arc. But:
 *
 *   a control sitting on a red row is answered in the mood of clearing that row;
 *   the same control one section down is answered in the mood of describing the
 *   business.
 *
 * That distinction lives entirely in the rendered layout. If the decline button
 * ends up adjacent to a `missing` row the argument has collapsed no matter what
 * the component tree says, so the tests below check the DOM relationship — the
 * section is a SIBLING that FOLLOWS the review, and no control is inside a
 * review row — rather than checking that a button exists somewhere.
 *
 * "It renders" was A-3's mount, which was an import and nothing else.
 */
import { cleanup, render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import AccountingCompletenessTab from "./AccountingCompletenessTab"
import DeclaredObligations from "./DeclaredObligations"
import type { Obligation } from "@/services/completeness-service"

const getReview = vi.fn()
const getObligations = vi.fn()
const decline = vi.fn()
const revokeDeclination = vi.fn()

vi.mock("@/services/completeness-service", () => ({
  completenessService: {
    getReview: (...a: unknown[]) => getReview(...a),
    getObligations: (...a: unknown[]) => getObligations(...a),
    decline: (...a: unknown[]) => decline(...a),
    revokeDeclination: (...a: unknown[]) => revokeDeclination(...a),
  },
}))

// Block bodies, not concise arrows: `mockReset()` returns the mock, and vitest
// treats a function returned from a hook as a teardown callback — which then
// calls the mock after the test with nobody awaiting it. Diagnosed in A-4.
beforeEach(() => {
  getReview.mockReset()
  getObligations.mockReset()
  decline.mockReset()
  revokeDeclination.mockReset()
})
afterEach(cleanup)

function obligation(over: Partial<Obligation> = {}): Obligation {
  return {
    key: "delivery_confirmations_daily",
    label: "Deliveries confirmed",
    role_slug: "driver",
    cadence: "daily",
    matters_because: "Unconfirmed deliveries stall the invoice they should trigger.",
    declination: null,
    ...over,
  }
}

const DECLINED = obligation({
  key: "production_log_daily",
  label: "Production log filed",
  role_slug: "production",
  declination: {
    id: "dec-1",
    declined_on: "2026-05-01",
    reason: "no on-site pours",
    declined_by_name: "Ada Kowalski",
    declined_by_role_slug: "accountant",
  },
})

describe("where the control sits", () => {
  beforeEach(() => {
    // A review with a real `missing` row — the adjacency this must not have.
    getReview.mockResolvedValue({
      rows: [
        {
          key: "production_log_daily",
          label: "Production log filed",
          role_slug: "production",
          verdict: "missing",
          actionable: true,
          first: "2026-08-08",
          last: "2026-08-13",
          periods: 6,
          detail: "Nothing since 8 Aug — 6 periods.",
        },
      ],
      quiet_summary: "3 obligations current.",
      actionable_count: 1,
    })
    getObligations.mockResolvedValue({
      obligations: [obligation()],
    })
  })

  it("puts no decline control inside a review row", async () => {
    render(<AccountingCompletenessTab />)
    const missingRow = await screen.findByText("Nothing since 8 Aug — 6 periods.")
    const row = missingRow.closest("li")
    expect(row).not.toBeNull()

    // ⚠️ THE ASSERTION THE RULING REDUCES TO. Anything that offers to declare an
    // obligation away must not be reachable from within the red row it would
    // silence.
    expect(
      within(row as HTMLElement).queryByRole("button", { name: /don't do this/i }),
    ).toBeNull()
    expect(
      within(row as HTMLElement).queryByRole("button", { name: /resume/i }),
    ).toBeNull()
  })

  it("renders the section AFTER the review, as a sibling and not a descendant", async () => {
    render(<AccountingCompletenessTab />)
    const section = await screen.findByTestId("declared-obligations")
    const missingRow = await screen.findByText("Nothing since 8 Aug — 6 periods.")
    const reviewList = missingRow.closest("ul")
    expect(reviewList).not.toBeNull()

    expect(section.contains(reviewList)).toBe(false)
    expect((reviewList as HTMLElement).contains(section)).toBe(false)

    // DOCUMENT_POSITION_FOLLOWING (4): the section comes after the review list.
    // A control ABOVE the exceptions would read as a filter on them.
    const rel = (reviewList as HTMLElement).compareDocumentPosition(section)
    expect(rel & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it("has its own heading, so the section is a different question", async () => {
    render(<AccountingCompletenessTab />)
    expect(
      await screen.findByRole("heading", { name: "Declared obligations" }),
    ).toBeInTheDocument()
  })

  it("survives the review failing, because the obligations exist either way", async () => {
    // ⚠️ MOUNTED OUTSIDE THE REVIEW'S SUCCESS BRANCH ON PURPOSE. Hiding the
    // authoring surface behind a failed fetch would make a transient error look
    // like a tenant with nothing to declare.
    getReview.mockRejectedValue(new Error("boom"))
    render(<AccountingCompletenessTab />)
    expect(await screen.findByText("The review did not run.")).toBeInTheDocument()
    expect(await screen.findByTestId("declared-obligations")).toBeInTheDocument()
    expect(await screen.findByText("Deliveries confirmed")).toBeInTheDocument()
  })
})

describe("the list is the full declared set, not the review's exceptions", () => {
  it("shows obligations that are perfectly fine", async () => {
    // The review would have folded these into "3 obligations current." A
    // control derived from review rows could only decline what was already red.
    getObligations.mockResolvedValue({
      obligations: [obligation(), obligation({ key: "b", label: "Toolbox talk held" })],
    })
    render(<DeclaredObligations />)
    expect(await screen.findByText("Deliveries confirmed")).toBeInTheDocument()
    expect(screen.getByText("Toolbox talk held")).toBeInTheDocument()
  })

  it("says whose duty each one is and why it matters", async () => {
    getObligations.mockResolvedValue({ obligations: [obligation()] })
    render(<DeclaredObligations />)
    expect(
      await screen.findByText(/Unconfirmed deliveries stall the invoice/),
    ).toBeInTheDocument()
    expect(screen.getByText(/daily · driver/)).toBeInTheDocument()
  })
})

describe("the permission lives at the endpoint, not in the payload", () => {
  it("renders the control for anyone who got the data at all", async () => {
    // ⚠️ D-2 SHIPPED A `may_decline` FLAG AND THE ENDPOINT GATE MADE IT A DECOY.
    // The flag existed so no button would render that then 403s. Once
    // `/completeness/obligations` refused everyone outside the accounting roles,
    // it became structurally always `true` — a field that reads as a permission
    // check and checks nothing, which is the shape this codebase has been burned
    // by twice (`AUTO_COMMIT_THRESHOLD`, `suggested_count`). The server's refusal
    // is the permission; reaching this data means you may write.
    getObligations.mockResolvedValue({ obligations: [obligation()] })
    render(<DeclaredObligations />)
    expect(
      await screen.findByRole("button", { name: /don't do this/i }),
    ).toBeInTheDocument()
  })

  it("shows the refusal rather than an empty list when the endpoint says no", async () => {
    // What a non-accounting role now gets: a 403, surfaced. An empty list would
    // read as "this tenant declares nothing", which is a different fact.
    getObligations.mockRejectedValue({
      response: { data: { detail: "The obligation list is the tenant's accounting responsibility" } },
    })
    render(<DeclaredObligations />)
    expect(
      await screen.findByText(/accounting responsibility/i),
    ).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /don't do this/i })).toBeNull()
  })
})

describe("declining", () => {
  beforeEach(() => {
    getObligations.mockResolvedValue({ obligations: [obligation()] })
  })

  it("requires a reason before it will submit", async () => {
    render(<DeclaredObligations />)
    await userEvent.click(
      await screen.findByRole("button", { name: /don't do this/i }),
    )
    const submit = screen.getByRole("button", { name: /record declination/i })
    // "We don't do that" with no reason is the weak assertion this arc rejected
    // everywhere else, and it stands until someone revokes it.
    expect(submit).toBeDisabled()

    await userEvent.type(screen.getByRole("textbox"), "   ")
    expect(submit).toBeDisabled()

    await userEvent.type(screen.getByRole("textbox"), "no fleet")
    expect(submit).toBeEnabled()
  })

  it("posts the key and the reason, and re-reads both surfaces", async () => {
    decline.mockResolvedValue({ status: "declined" })
    const onChanged = vi.fn()
    render(<DeclaredObligations onChanged={onChanged} />)

    await userEvent.click(
      await screen.findByRole("button", { name: /don't do this/i }),
    )
    await userEvent.type(screen.getByRole("textbox"), "no fleet")
    await userEvent.click(screen.getByRole("button", { name: /record declination/i }))

    await waitFor(() =>
      expect(decline).toHaveBeenCalledWith({
        expectation_key: "delivery_confirmations_daily",
        reason: "no fleet",
      }),
    )
    // The review above shows the same facts; leaving it stale would let the page
    // contradict itself.
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
    expect(getObligations).toHaveBeenCalledTimes(2)
  })

  it("sends no effective date, so a declination cannot be back-dated", async () => {
    // ⚠️ THE RETROACTIVE REWRITE D-3 REMOVED, HANDED BACK AS A PARAMETER.
    // Declining on 13 Aug erased six days of `missing` before D-3; a caller
    // choosing 1 May would erase four months, through an endpoint.
    decline.mockResolvedValue({ status: "declined" })
    render(<DeclaredObligations />)
    await userEvent.click(
      await screen.findByRole("button", { name: /don't do this/i }),
    )
    await userEvent.type(screen.getByRole("textbox"), "no fleet")
    await userEvent.click(screen.getByRole("button", { name: /record declination/i }))

    await waitFor(() => expect(decline).toHaveBeenCalled())
    expect(Object.keys(decline.mock.calls[0][0]).sort()).toEqual([
      "expectation_key",
      "reason",
    ])
  })

  it("keeps the form open and says so when the write fails", async () => {
    // A bare Error carries no axios `response.data.detail`, so
    // `getApiErrorMessage` returns the fallback — asserted as the fallback
    // rather than as "nope", because pretending the message came from the
    // server would be a test that agrees with an implementation it invented.
    decline.mockRejectedValue(new Error("nope"))
    render(<DeclaredObligations />)
    await userEvent.click(
      await screen.findByRole("button", { name: /don't do this/i }),
    )
    await userEvent.type(screen.getByRole("textbox"), "no fleet")
    await userEvent.click(screen.getByRole("button", { name: /record declination/i }))

    // A failed write that closed the form silently would read as success.
    await waitFor(() =>
      expect(screen.getByText("That did not save.")).toBeInTheDocument(),
    )
    expect(screen.getByRole("textbox")).toBeInTheDocument()
  })
})

describe("a declined obligation", () => {
  beforeEach(() => {
    getObligations.mockResolvedValue({ obligations: [DECLINED] })
  })

  it("names who declined it, when, and why", async () => {
    // Attribution at the point of use is the cheapest thing that stops a
    // declination being used to clear a report. Snapshotted, so it says who
    // answered THEN rather than what they hold now.
    render(<DeclaredObligations />)
    // Matched on the paragraph's whole normalised text. The line is split
    // across a <span> and several interpolations, so a substring query finds
    // nothing and would read as the attribution being absent.
    const line = await screen.findByText(
      (_, el) =>
        el?.tagName === "P" &&
        /^Declined .* by Ada Kowalski \(accountant\): no on-site pours$/.test(
          el.textContent?.replace(/\s+/g, " ").trim() ?? "",
        ),
    )
    expect(line).toBeInTheDocument()
    // The date is rendered through the locale formatter, so assert the parts
    // that are locale-stable rather than pinning "1 May 2026" and coupling the
    // test to whichever locale the runner happens to have.
    expect(line.textContent).toMatch(/2026/)
    expect(line.textContent).toMatch(/May/)
  })

  it("offers to resume rather than to decline again", async () => {
    render(<DeclaredObligations />)
    expect(
      await screen.findByRole("button", { name: /resume/i }),
    ).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /don't do this/i })).toBeNull()
  })

  it("revokes by id with a reason, and does not delete", async () => {
    revokeDeclination.mockResolvedValue({ status: "revoked" })
    render(<DeclaredObligations />)
    await userEvent.click(await screen.findByRole("button", { name: /resume/i }))
    await userEvent.type(screen.getByRole("textbox"), "we took it back in house")
    await userEvent.click(
      screen.getByRole("button", { name: /resume this obligation/i }),
    )
    await waitFor(() =>
      expect(revokeDeclination).toHaveBeenCalledWith(
        "dec-1",
        "we took it back in house",
      ),
    )
  })
})

describe("the section's own failure state", () => {
  it("says the list did not load rather than rendering an empty one", async () => {
    // An empty list and a failed fetch are different facts, and the second one
    // rendered as the first would say this tenant has nothing to declare.
    getObligations.mockRejectedValue(new Error("gone"))
    render(<DeclaredObligations />)
    expect(
      await screen.findByText(/Could not load the declared obligations|gone/i),
    ).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /don't do this/i })).toBeNull()
  })
})
