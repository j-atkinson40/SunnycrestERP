/**
 * The Payroll page — where a payroll-limited user LANDS.
 *
 * ⚠️ These tests exist because the page was a placeholder for one release
 * after the Focus shipped — "Payroll review is coming" was the whole of what a
 * payroll-limited user found behind the one nav item she had, while the Focus
 * already worked.
 *
 * ⚠️ An earlier version of this comment explained that via
 * `landingRouteForAreas`. That function was DELETED on 2026-11-16: it never
 * ran, and every user lands on `/home` per James's ruling. The page still
 * matters — it is reached from her sidebar, not by landing.
 */

import { render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import PayrollHome from "./payroll-home"

const api = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock("@/lib/api-client", () => ({ default: api }))

const focusApi = vi.hoisted(() => ({ getWeekFocus: vi.fn() }))
vi.mock("@/lib/payroll/focus-api", () => focusApi)

const WEEK = {
  id: "w44",
  week_number: 44,
  week_end_date: "2026-10-31",
  check_date: "2026-11-05",
  status: "calculated",
}

const FOCUS = {
  week_id: "w44",
  dues: { total: "193.93", members_paying: 11, members_total: 13 },
}

function renderPage() {
  return render(
    <MemoryRouter>
      <PayrollHome />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  api.get.mockResolvedValue({ data: { weeks: [WEEK] } })
  focusApi.getWeekFocus.mockResolvedValue(FOCUS)
})


describe("the week she lands on", () => {
  it("shows the week, its dues, and a way into the Focus", async () => {
    renderPage()
    expect(await screen.findByText(/Week 44/)).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByText(/193\.93/)).toBeInTheDocument(),
    )
    expect(screen.getByText(/11 of 13 paying/)).toBeInTheDocument()
    const link = screen.getByTestId("open-weekly-payroll")
    expect(link).toHaveAttribute(
      "href",
      "/home?focus=weekly-payroll&week_id=w44",
    )
  })

  it("⚠️ the link carries the WEEK — an unscoped Focus shows 'No week chosen'", async () => {
    renderPage()
    const link = await screen.findByTestId("open-weekly-payroll")
    expect(link.getAttribute("href")).toContain("week_id=w44")
  })

  it("offers the upload route when the week has no figures yet", async () => {
    focusApi.getWeekFocus.mockRejectedValue(new Error("403"))
    renderPage()
    expect(
      await screen.findByText(/No hours for week 44 yet/),
    ).toBeInTheDocument()
    expect(screen.getByTestId("open-weekly-payroll")).toHaveTextContent(
      /upload/i,
    )
  })
})


describe("empty and failed states are different, and both are written", () => {
  it("⚠️ with no weeks it says so and offers NO link", async () => {
    api.get.mockResolvedValue({ data: { weeks: [] } })
    renderPage()
    expect(await screen.findByText(/No payroll weeks yet/)).toBeInTheDocument()
    // A link needs a week to scope to. One that opened nothing would be
    // worse than its absence.
    expect(screen.queryByTestId("open-weekly-payroll")).not.toBeInTheDocument()
  })

  it("⚠️ a failure does NOT render as 'nothing here'", async () => {
    api.get.mockRejectedValue(new Error("boom"))
    renderPage()
    expect(
      await screen.findByText(/could not be loaded/i),
    ).toBeInTheDocument()
    // The empty state would read as "payroll has not started", which is a
    // different and wrong statement.
    expect(screen.queryByText(/No payroll weeks yet/)).not.toBeInTheDocument()
  })

  it("never says 'Payroll review is coming'", async () => {
    renderPage()
    await screen.findByText(/Week 44/)
    expect(screen.queryByText(/review is coming/i)).not.toBeInTheDocument()
  })
})


describe("the last approved week", () => {
  it("is shown when it is not the current one", async () => {
    api.get.mockResolvedValue({
      data: {
        weeks: [
          WEEK,
          { ...WEEK, id: "w43", week_number: 43, status: "approved",
            check_date: "2026-10-29" },
        ],
      },
    })
    renderPage()
    expect(await screen.findByTestId("payroll-last-approved")).toHaveTextContent(
      /Week 43/,
    )
    expect(screen.getByTestId("open-last-approved")).toHaveAttribute(
      "href",
      "/home?focus=weekly-payroll&week_id=w43",
    )
  })

  it("is not repeated when the current week IS the last approved one", async () => {
    api.get.mockResolvedValue({
      data: { weeks: [{ ...WEEK, status: "approved" }] },
    })
    renderPage()
    await screen.findByText(/Week 44/)
    expect(screen.queryByTestId("payroll-last-approved")).not.toBeInTheDocument()
  })
})


describe("the source of the lines", () => {
  it("⚠️ reads the payroll endpoints, NEVER the note", async () => {
    // The note is DIFFERENTIAL: its composition gate withholds a non-prompt
    // whose digest matches what it last said. Sourced from the note, this
    // page would be full on the first visit of the day and empty on every
    // reload after it.
    renderPage()
    await screen.findByText(/Week 44/)
    const called = api.get.mock.calls.map((c) => String(c[0]))
    expect(called.some((u) => u.includes("/payroll-reports/weeks"))).toBe(true)
    expect(called.some((u) => u.includes("/note"))).toBe(false)
  })
})


describe("loading is not empty", () => {
  it("⚠️ does not say 'to upload' while the dues are still loading", async () => {
    // The first version did, so the page asserted the week had no hours a
    // moment before showing its dues. Caught by reading a screenshot.
    let release: (v: unknown) => void = () => {}
    focusApi.getWeekFocus.mockReturnValue(new Promise((r) => { release = r }))
    renderPage()
    const link = await screen.findByTestId("open-weekly-payroll")
    expect(link).toHaveTextContent("Open weekly payroll")
    expect(link).not.toHaveTextContent(/upload/i)
    release(FOCUS)
    await waitFor(() => expect(screen.getByText(/193\.93/)).toBeInTheDocument())
  })
})
