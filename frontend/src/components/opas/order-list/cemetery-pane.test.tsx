/**
 * The Cemetery Pane renders what the record establishes, and nothing else.
 *
 * ⚠️ THE FIXTURES COME FROM THE SERVER'S CONTRACT, not from reading the component.
 * `cemetery.cemetery_detail` decides the shape and the backend suites
 * (`test_cemetery_pane.py`, `test_cemetery_pane_reads.py`) pin it against real rows. A
 * double built by reading `CemeteryPane.tsx` would agree with it by construction and
 * assert nothing — CLAUDE.md §11, fixtures modelled on the implementation.
 *
 * ⚠️ AND THE SPARSE FIXTURE IS THE PRODUCTION ONE. Measured 2026-10-26: there are FOUR
 * cemetery rows platform-wide and `address`, `phone`, `contact_name`, `access_notes`,
 * `equipment_note`, `county`, `zip_code` and lat/long are NULL on every one. So
 * `maryBare()` — a name, a town, the orders, the counts, and "Nothing recorded about
 * getting in yet" — is what James will actually see. The rich fixture is the one that
 * does NOT exist yet, and it is here because the schema permits it, not because a row
 * does.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const getCemeteryDetail = vi.fn()

vi.mock("@/services/order-list-service", () => ({
  getCemeteryDetail: (...args: unknown[]) => getCemeteryDetail(...args),
}))

import { CemeteryPane } from "./CemeteryPane"

/** Production's shape: a name, a town, and nothing else recorded. */
function maryBare(over: Record<string, unknown> = {}) {
  return {
    id: "m1",
    name: "St. Mary's Cemetery",
    meta: "Skaneateles, NY",
    essentials_empty: "Nothing recorded about getting in yet",
    coming: [
      {
        id: "o1", number: "SO-2026-0004", short: "0004", deceased_name: "hart",
        funeral_home: "Riverside Memorial Chapel", customer_id: "c-riverside",
        status: "Confirmed", date_in_week: true, date_primary: "Wed",
        time_label: "10:00",
      },
    ],
    overdue: [],
    overdue_label: "Service day passed, not delivered",
    knows: { deliveries_this_year: 1, year: 2026 },
    ...over,
  }
}

beforeEach(() => {
  getCemeteryDetail.mockReset()
  getCemeteryDetail.mockResolvedValue(maryBare())
})

async function mount(props: Record<string, unknown> = {}) {
  const out = render(<CemeteryPane cemeteryId="m1" {...props} />)
  await waitFor(() => expect(screen.getByTestId("opas-cemetery-title")).toBeTruthy())
  return out
}

describe("the header", () => {
  it("shows the name and the town", async () => {
    await mount()
    expect(screen.getByTestId("opas-cemetery-title").textContent).toBe("St. Mary's Cemetery")
    expect(screen.getByTestId("opas-cemetery-meta").textContent).toContain("Skaneateles, NY")
  })

  it("has no Directions button when no address is recorded", async () => {
    // ⚠️ THE PRODUCTION CASE FOR ALL FOUR CEMETERIES, and the dispatch's rule: "only if
    // an address is recorded". The tempting wrong answer is a name-and-town maps search,
    // which is a guess dressed as a record.
    await mount()
    expect(screen.queryByTestId("opas-cemetery-directions")).toBeNull()
  })

  it("Directions is an anchor to a new tab when there IS an address", async () => {
    getCemeteryDetail.mockResolvedValue(maryBare({
      action: {
        kind: "directions",
        label: "Directions",
        url: "https://www.google.com/maps/search/?api=1&query=22+Fennell+St",
      },
    }))
    await mount()
    const a = screen.getByTestId("opas-cemetery-directions")
    // ⚠️ AN ANCHOR, NOT A BUTTON. It leaves the app, and `rel="noreferrer"` because the
    // destination has no business knowing where the click came from.
    expect(a.tagName).toBe("A")
    expect(a.getAttribute("target")).toBe("_blank")
    expect(a.getAttribute("rel")).toBe("noreferrer")
    expect(a.getAttribute("href")).toContain("22+Fennell+St")
  })
})

describe("the essentials", () => {
  it("says nothing is recorded rather than showing blank labels", async () => {
    await mount()
    expect(screen.queryByTestId("opas-cemetery-essentials")).toBeNull()
    expect(screen.getByTestId("opas-cemetery-essentials-empty").textContent)
      .toBe("Nothing recorded about getting in yet")
  })

  it("renders whatever rows the record does hold", async () => {
    getCemeteryDetail.mockResolvedValue(maryBare({
      essentials: [
        { label: "Address", value: "22 Fennell St, Skaneateles, NY" },
        { label: "Getting in", value: "Back in. Do not use the main lane." },
        { label: "Cemetery provides", value: "Lowering device, Grass, Tent" },
      ],
      essentials_empty: undefined,
    }))
    await mount()
    const kv = screen.getByTestId("opas-cemetery-essentials")
    expect(kv.textContent).toContain("22 Fennell St, Skaneateles, NY")
    expect(kv.textContent).toContain("Back in. Do not use the main lane.")
    expect(kv.textContent).toContain("Lowering device, Grass, Tent")
    // ⚠️ AND NEVER BOTH. The heading must not stand over a list AND a sentence saying
    // there is no list.
    expect(screen.queryByTestId("opas-cemetery-essentials-empty")).toBeNull()
  })

  it("⚠️ NEVER SAYS A FLAG IS FALSE", async () => {
    // The four `cemetery_provides_*` columns are `nullable=False, default=False`, so a
    // False is indistinguishable from "nobody said" — CLAUDE.md §5. The server sends
    // only the TRUE ones; this pins that the client never renders the other direction
    // either, since a client-side "not provided" would reintroduce the same claim.
    await mount()
    const body = document.body.textContent ?? ""
    for (const phrase of ["not provided", "No tent", "Tents: no", "false"]) {
      expect(body).not.toContain(phrase)
    }
  })
})

describe("coming up here", () => {
  it("opens an order, and names the funeral home as its own target", async () => {
    const onOpenOrder = vi.fn()
    const onOpenCustomer = vi.fn()
    await mount({ onOpenOrder, onOpenCustomer })

    const row = screen.getByTestId("opas-cemetery-order-SO-2026-0004")
    expect(row.textContent).toContain("hart")
    expect(row.textContent).toContain("Wed")
    expect(row.textContent).toContain("10:00")
    // ⚠️ THE CEMETERY'S OWN NAME IS NOT ON THE ROW — we are inside its pane.
    expect(row.textContent).not.toContain("St. Mary")
    fireEvent.click(row)
    expect(onOpenOrder).toHaveBeenCalledWith("o1")

    // ⚠️ A SECOND, SEPARATE TARGET. Step 3 of James's walk is the funeral home on the
    // row opening that customer — so it cannot be part of the order's own button.
    const home = screen.getByTestId("opas-cemetery-home-SO-2026-0004")
    expect(home.tagName).toBe("BUTTON")
    fireEvent.click(home)
    expect(onOpenCustomer).toHaveBeenCalledWith("c-riverside", "Riverside Memorial Chapel")
  })

  it("a row with no customer record shows the name as plain text", async () => {
    getCemeteryDetail.mockResolvedValue(maryBare({
      coming: [{
        id: "o1", number: "SO-1", short: "0001", deceased_name: "hart",
        funeral_home: "Riverside Memorial Chapel", status: "Confirmed",
      }],
    }))
    await mount({ onOpenCustomer: vi.fn() })
    expect(screen.queryByTestId("opas-cemetery-home-SO-1")).toBeNull()
    expect(screen.getByText("Riverside Memorial Chapel")).toBeTruthy()
  })

  it("says so when nothing is coming up", async () => {
    getCemeteryDetail.mockResolvedValue(maryBare({ coming: [] }))
    await mount()
    expect(screen.getByTestId("opas-cemetery-coming-empty").textContent)
      .toBe("Nothing coming up here")
  })

  it("the overdue group appears only when there is something in it", async () => {
    await mount()
    expect(screen.queryByTestId("opas-cemetery-group-overdue")).toBeNull()
    // The control: given a row, the group renders with the SERVER's heading.
    getCemeteryDetail.mockResolvedValue(maryBare({
      overdue: [{
        id: "o9", number: "SO-2026-0001", short: "0001", deceased_name: "smith",
        funeral_home: "Hopkins Funeral Home", customer_id: "c-hopkins",
        status: "Draft", date_primary: "Fri Oct 16", time_label: "11:00",
      }],
    }))
    const { unmount } = render(<CemeteryPane cemeteryId="m1" />)
    await waitFor(() => expect(screen.getByTestId("opas-cemetery-group-overdue")).toBeTruthy())
    expect(screen.getByTestId("opas-cemetery-group-overdue").textContent)
      .toContain("Service day passed, not delivered")
    unmount()
  })
})

describe("what Opas knows", () => {
  it("counts the deliveries and names the next one", async () => {
    getCemeteryDetail.mockResolvedValue(maryBare({
      knows: {
        deliveries_this_year: 4, year: 2026,
        next_delivery: { order_id: "o1", line: "Wed · hart" },
      },
    }))
    await mount()
    const knows = screen.getByTestId("opas-cemetery-knows")
    expect(knows.textContent).toContain("Deliveries in 2026")
    expect(knows.textContent).toContain("4")
    expect(knows.textContent).toContain("Wed · hart")
  })

  it("says None scheduled rather than dropping the row", async () => {
    // ⚠️ A MEASURED ABSENCE, NOT A MISSING FIELD. We counted the upcoming orders and
    // there were none — which is a finding, unlike an unrecorded address. That is why
    // this row stays and the essentials rows drop out.
    await mount()
    expect(screen.getByTestId("opas-cemetery-knows").textContent).toContain("None scheduled")
  })

  it("links the other cemetery of the same name, in both places", async () => {
    // ⚠️ CONSTRUCTED — no production tenant has two cemeteries of one name (measured,
    // zero collisions). The server composes both sentences.
    const same = {
      cemetery_id: "m2", name: "St Marys Cemetery", town: "Auburn",
      line: "not the St Marys Cemetery in Auburn",
    }
    getCemeteryDetail.mockResolvedValue(maryBare({
      same_name: same,
      knows: { deliveries_this_year: 1, year: 2026, same_name: same },
    }))
    const onOpenCemetery = vi.fn()
    await mount({ onOpenCemetery })

    // on the meta line, as the prototype has it
    const not = screen.getByTestId("opas-cemetery-not-the-other")
    expect(not.textContent).toBe("not the St Marys Cemetery in Auburn")
    fireEvent.click(not)
    expect(onOpenCemetery).toHaveBeenCalledWith("m2", "St Marys Cemetery")

    // and in "What Opas knows", with the town, which is the discriminator
    const row = screen.getByTestId("opas-cemetery-same-name")
    expect(row.textContent).toBe("St Marys Cemetery, Auburn")
    fireEvent.click(row)
    expect(onOpenCemetery).toHaveBeenCalledTimes(2)
  })

  it("has no same-name line when the name is not shared", async () => {
    await mount()
    expect(screen.queryByTestId("opas-cemetery-not-the-other")).toBeNull()
    expect(screen.queryByTestId("opas-cemetery-same-name")).toBeNull()
  })
})

describe("reading", () => {
  it("says so while reading and says so when it cannot", async () => {
    let resolve!: (v: unknown) => void
    getCemeteryDetail.mockReturnValue(new Promise((r) => { resolve = r }))
    const { unmount } = render(<CemeteryPane cemeteryId="m1" />)
    expect(screen.getByTestId("opas-cemetery-loading")).not.toBeNull()
    resolve(maryBare())
    await waitFor(() => expect(screen.getByTestId("opas-cemetery-title")).toBeTruthy())
    unmount()

    getCemeteryDetail.mockRejectedValue(new Error("404"))
    render(<CemeteryPane cemeteryId="m9" />)
    await waitFor(() =>
      expect(screen.getByTestId("opas-cemetery-error").textContent)
        .toBe("Could not read that cemetery"),
    )
  })

  it("re-reads when the id changes", async () => {
    const { rerender } = await mount()
    expect(getCemeteryDetail).toHaveBeenCalledWith("m1")
    getCemeteryDetail.mockResolvedValue(maryBare({ id: "m2", name: "Oakwood Cemetery" }))
    rerender(<CemeteryPane cemeteryId="m2" />)
    await waitFor(() =>
      expect(screen.getByTestId("opas-cemetery-title").textContent).toBe("Oakwood Cemetery"),
    )
    expect(getCemeteryDetail).toHaveBeenCalledWith("m2")
  })

  it("hands the cemetery up so the bar can answer from it", async () => {
    const onLoaded = vi.fn()
    await mount({ onLoaded })
    expect(onLoaded).toHaveBeenCalledWith(expect.objectContaining({ id: "m1" }))
  })
})
