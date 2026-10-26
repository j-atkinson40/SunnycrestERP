/**
 * The rulebook pane: what it shows, what it says it does not do, and the two edits.
 *
 * ⚠️ THE FIXTURES COME FROM THE SERVER'S CONTRACT. `order_list/rulebook.rulebook`
 * decides the shape and `test_rulebook.py` pins it against real rows; a double built by
 * reading `RulebookPane.tsx` would agree with it by construction and assert nothing.
 *
 * ⚠️ AND THE FOOTER IS TESTED HARDEST, because it is the one line that stops a reader
 * believing a rule they can see is a rule that is acting. "nothing uses the rulebook in
 * this slice. It records and shows" (James, 2026-10-26).
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const getRulebook = vi.fn()
const updateRule = vi.fn()

vi.mock("@/services/order-list-service", () => ({
  getRulebook: (...a: unknown[]) => getRulebook(...a),
  updateRule: (...a: unknown[]) => updateRule(...a),
}))

import { RulebookPane } from "./RulebookPane"

const FOOTER = "Opas doesn’t use these yet"

function book(over: Record<string, unknown> = {}) {
  return {
    rules: [
      {
        id: "r1",
        text: "Veterans take the Continental rather than the Monticello.",
        created_at: "2026-10-26T13:00:00Z",
        who: "Dave Miller",
        change: "vault · Monticello Burial Vault → Continental Burial Vault",
        reason: "they always take the continental for a veteran",
        decision_id: "d1",
      },
    ],
    footer: FOOTER,
    ...over,
  }
}

beforeEach(() => {
  getRulebook.mockReset()
  updateRule.mockReset()
  getRulebook.mockResolvedValue(book())
  updateRule.mockResolvedValue({ id: "r1", text: "x", is_active: true })
})

async function mount(props: Record<string, unknown> = {}) {
  const out = render(<RulebookPane {...props} />)
  await waitFor(() => expect(screen.getByTestId("opas-rulebook-title")).toBeTruthy())
  return out
}

describe("what it shows", () => {
  it("the sentence, who wrote it, when, the change and their own words", async () => {
    await mount()
    const rule = screen.getByTestId("opas-rule-r1")
    expect(rule.textContent).toContain("Veterans take the Continental rather than the Monticello.")
    expect(rule.textContent).toContain("Dave Miller")
    expect(rule.textContent).toContain("Oct 26")
    expect(rule.textContent).toContain("vault · Monticello Burial Vault → Continental Burial Vault")
    expect(rule.textContent).toContain("they always take the continental for a veteran")
  })

  it("⚠️ SAYS NOTHING USES THESE YET — with rules and without", async () => {
    await mount()
    expect(screen.getByTestId("opas-rulebook-footer").textContent).toBe(FOOTER)

    getRulebook.mockResolvedValue(book({ rules: [], empty: "No rules yet" }))
    const { unmount } = render(<RulebookPane />)
    await waitFor(() => expect(screen.getAllByTestId("opas-rulebook-empty")).toBeTruthy())
    // ⚠️ AN EMPTY RULEBOOK IS THE LIKELIEST MOMENT for somebody to wonder what it would
    // do if it had any, so the footer must not be conditional on there being rules.
    expect(screen.getAllByTestId("opas-rulebook-footer").at(-1)?.textContent).toBe(FOOTER)
    unmount()
  })

  it("says so when there are no rules", async () => {
    getRulebook.mockResolvedValue(book({ rules: [], empty: "No rules yet" }))
    await mount()
    expect(screen.getByTestId("opas-rulebook-empty").textContent).toBe("No rules yet")
  })

  it("renders a rule with no provenance as plain text", async () => {
    // A rule whose decision row was purged — `SET NULL`, by design, because the rule
    // outlives the log.
    getRulebook.mockResolvedValue(book({
      rules: [{ id: "r2", text: "Survives." }],
    }))
    await mount()
    expect(screen.getByTestId("opas-rule-r2").textContent).toContain("Survives.")
    expect(screen.queryByTestId("opas-rule-source-r2")).toBeNull()
  })

  it("the change is a link only when something can open it", async () => {
    await mount()
    // ⚠️ NO HANDLER, NO BUTTON. Nothing opens a decision row yet — the log has no pane
    // — and a link that cannot resolve is the dead click the cemetery row avoided for
    // two weeks by being inert.
    expect(screen.queryByTestId("opas-rule-source-r1")).toBeNull()

    const onOpenDecision = vi.fn()
    const { unmount } = render(<RulebookPane onOpenDecision={onOpenDecision} />)
    await waitFor(() => expect(screen.getAllByTestId("opas-rule-source-r1")).toBeTruthy())
    fireEvent.click(screen.getAllByTestId("opas-rule-source-r1")[0])
    expect(onOpenDecision).toHaveBeenCalledWith("d1")
    unmount()
  })
})

describe("the two edits", () => {
  it("edits a rule's sentence", async () => {
    await mount()
    fireEvent.click(screen.getByTestId("opas-rule-edit-open-r1"))
    const box = screen.getByTestId("opas-rule-edit-r1") as HTMLTextAreaElement
    // ⚠️ A TEXTAREA IN THE PANE, NOT THE BAR. The bar is the only input for CAPTURE, by
    // ruling; editing a stored rule is a row-level edit and routing it through the bar
    // would make it indistinguishable from a new request.
    expect(box.value).toBe("Veterans take the Continental rather than the Monticello.")
    fireEvent.change(box, { target: { value: "Veterans take the Continental." } })
    fireEvent.click(screen.getByTestId("opas-rule-save-r1"))
    await waitFor(() =>
      expect(updateRule).toHaveBeenCalledWith("r1", { text: "Veterans take the Continental." }),
    )
  })

  it("switches a rule off", async () => {
    await mount()
    fireEvent.click(screen.getByTestId("opas-rule-off-r1"))
    await waitFor(() => expect(updateRule).toHaveBeenCalledWith("r1", { is_active: false }))
  })

  it("re-reads after BOTH edits, so the pane is not stale", async () => {
    // ⚠️ BOTH, AND A BREAK TEST IS WHY. This only clicked "Switch off", so the SAVE
    // path's own `read()` was unwatched — deleting it turned nothing red. Two paths
    // change the book and each has to refresh it.
    await mount()
    expect(getRulebook).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByTestId("opas-rule-off-r1"))
    await waitFor(() => expect(getRulebook).toHaveBeenCalledTimes(2))

    fireEvent.click(screen.getByTestId("opas-rule-edit-open-r1"))
    fireEvent.change(screen.getByTestId("opas-rule-edit-r1"), {
      target: { value: "Reworded." },
    })
    fireEvent.click(screen.getByTestId("opas-rule-save-r1"))
    await waitFor(() => expect(getRulebook).toHaveBeenCalledTimes(3))
  })

  it("re-reads when the host says a rule landed", async () => {
    // ⚠️ THE RULE IS CONFIRMED IN THE BAR, NOT IN THIS PANE. Without `refresh` a pane
    // already open would keep showing the book as it was before the rule the person
    // just wrote.
    const { rerender } = await mount({ refresh: 0 })
    expect(getRulebook).toHaveBeenCalledTimes(1)
    rerender(<RulebookPane refresh={1} />)
    await waitFor(() => expect(getRulebook).toHaveBeenCalledTimes(2))
  })
})

describe("reading", () => {
  it("says so while reading and says so when it cannot", async () => {
    let resolve!: (v: unknown) => void
    getRulebook.mockReturnValue(new Promise((r) => { resolve = r }))
    const { unmount } = render(<RulebookPane />)
    expect(screen.getByTestId("opas-rulebook-loading")).not.toBeNull()
    resolve(book())
    await waitFor(() => expect(screen.getByTestId("opas-rulebook-title")).toBeTruthy())
    unmount()

    getRulebook.mockRejectedValue(new Error("500"))
    render(<RulebookPane />)
    await waitFor(() =>
      expect(screen.getByTestId("opas-rulebook-error").textContent)
        .toBe("Could not read the rulebook"),
    )
  })
})
