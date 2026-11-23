/**
 * The status row — the entrance `r234` shipped without.
 *
 * ⚠️ **MOCKED AT `apiClient`, NOT AT `focus-api`.** The row's write goes out
 * form-encoded under an explicit header on a PUT, and every one of those three
 * has broken a payroll write already: a `URLSearchParams` body under
 * `apiClient`'s default JSON content type makes FastAPI report every field
 * missing while the bytes plainly contain them, and it answered 422 from the
 * page while the same request succeeded under curl. Mocking the typed wrapper
 * would test the component against my own account of the request. These tests
 * assert the method, the URL, the header and the encoded body.
 */
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("@/lib/api-client", () => ({
  default: { get: vi.fn(), put: vi.fn(), post: vi.fn() },
}))

import apiClient from "@/lib/api-client"

import { EmployeeStatusRow, statusDate } from "./EmployeeStatusRow"

const get = apiClient.get as unknown as ReturnType<typeof vi.fn>
const put = apiClient.put as unknown as ReturnType<typeof vi.fn>

const NOT_RECORDED = {
  employee_id: "emp-1",
  display_name: "Staring, John",
  status: null,
  since: null,
  history: [],
}

const LEFT_IN_JUNE = {
  employee_id: "emp-1",
  display_name: "Staring, John",
  status: "left",
  since: "2026-06-25",
  history: [
    {
      id: "chg-2",
      status: "left",
      since: "2026-06-25",
      previous_status: "workers_comp",
      previous_since: "2026-02-10",
      reason: "termination date from Payentry",
      changed_at: "2026-11-21T14:05:00+00:00",
      changed_by_user_id: "u-susan",
      changed_by_name: "Susan Mott",
    },
    {
      id: "chg-1",
      status: "workers_comp",
      since: "2026-02-10",
      previous_status: null,
      previous_since: null,
      reason: "out on comp",
      changed_at: "2026-11-21T14:00:00+00:00",
      changed_by_user_id: "u-susan",
      changed_by_name: "Susan Mott",
    },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  get.mockResolvedValue({ data: NOT_RECORDED })
  put.mockResolvedValue({ data: LEFT_IN_JUNE.history[0] })
})


describe("what the row says before anybody has said anything", () => {
  it('shows NOT RECORDED rather than "Working", and says what that costs', async () => {
    // ⚠️ THE STATE EVERY EMPLOYEE ON PRODUCTION IS IN. Measured 2026-11-21:
    // 0 of 30 carry a value. A row that rendered null as "Working" would
    // assert something nobody measured, for thirty people at once.
    render(<EmployeeStatusRow employeeId="emp-1" readOnly={false} />)
    expect(await screen.findByTestId("employee-status-value")).toHaveTextContent(
      "Not recorded",
    )
    expect(screen.getByTestId("employee-status-row")).toHaveTextContent(
      /counts line 1 from who had a check that month/i,
    )
    // ⚠️ THE ACTION IS ON THE VALUE LINE, so its label is a word rather than
    // a sentence. It moved there because the first version pushed the member
    // pane past its clip and hid both this button and the Timecard button —
    // found in the walk-through screenshot, invisible to every test, because
    // Playwright and testing-library both scroll before they click.
    expect(screen.getByTestId("employee-status-change")).toHaveTextContent(
      "Record",
    )
  })

  it("offers no history toggle when there is no history", async () => {
    render(<EmployeeStatusRow employeeId="emp-1" readOnly={false} />)
    await screen.findByTestId("employee-status-value")
    expect(screen.queryByTestId("employee-status-history-toggle")).toBeNull()
  })

  it("says the row did not load, rather than showing it as not recorded", async () => {
    // ⚠️ "NOTHING HERE" AND "THIS DID NOT LOAD" ARE DIFFERENT FACTS. Collapsed,
    // a failed fetch reads as a measured absence — and a measured absence is
    // what flips the R-115 onto its check-counting fallback.
    get.mockRejectedValue(new Error("down"))
    render(<EmployeeStatusRow employeeId="emp-1" readOnly={false} />)
    await waitFor(() =>
      expect(screen.getByTestId("employee-status-row")).toHaveTextContent(
        /could not be loaded/i,
      ),
    )
    expect(screen.queryByTestId("employee-status-value")).toBeNull()
  })
})


describe("who may change it", () => {
  it("offers no editor read-only, and names the permission", async () => {
    render(<EmployeeStatusRow employeeId="emp-1" readOnly />)
    await screen.findByTestId("employee-status-value")
    expect(screen.queryByTestId("employee-status-change")).toBeNull()
    expect(screen.queryByTestId("employee-status-editor")).toBeNull()
    expect(screen.getByTestId("employee-status-row")).toHaveTextContent(
      "payroll.approve",
    )
  })

  it("offers the editor when not read-only — the control for the above", async () => {
    // ⚠️ WITHOUT THIS, THE REFUSAL TEST PASSES ON A ROW THAT NEVER RENDERS A
    // BUTTON AT ALL. A read-only assertion with no positive control cannot
    // distinguish "correctly withheld" from "never built".
    render(<EmployeeStatusRow employeeId="emp-1" readOnly={false} />)
    expect(await screen.findByTestId("employee-status-change")).toBeTruthy()
  })
})


describe("recording a change", () => {
  it("PUTs form-encoded to the employee's status, then re-reads", async () => {
    const user = userEvent.setup()
    render(<EmployeeStatusRow employeeId="emp-1" readOnly={false} />)
    await user.click(await screen.findByTestId("employee-status-change"))

    await user.selectOptions(screen.getByTestId("employee-status-select"), "left")
    await user.type(screen.getByTestId("employee-status-since"), "2026-06-25")
    await user.type(
      screen.getByTestId("employee-status-reason"),
      "termination date from Payentry",
    )
    get.mockResolvedValue({ data: LEFT_IN_JUNE })
    await user.click(screen.getByTestId("employee-status-save"))

    await waitFor(() => expect(put).toHaveBeenCalledTimes(1))
    const [url, body, config] = put.mock.calls[0]
    expect(url).toBe("/payroll-reports/employees/emp-1/status")
    expect(String(body)).toBe(
      "status=left&since=2026-06-25&reason=termination+date+from+Payentry",
    )
    expect(config.headers["Content-Type"]).toBe(
      "application/x-www-form-urlencoded",
    )

    // And the row shows the server's new answer, not the typed one.
    await waitFor(() =>
      expect(screen.getByTestId("employee-status-value")).toHaveTextContent(
        "Left · since Jun 25, 2026",
      ),
    )
  })

  it("will not submit without a date or a reason", async () => {
    const user = userEvent.setup()
    render(<EmployeeStatusRow employeeId="emp-1" readOnly={false} />)
    await user.click(await screen.findByTestId("employee-status-change"))
    const save = screen.getByTestId("employee-status-save")
    expect(save).toBeDisabled()

    await user.type(screen.getByTestId("employee-status-since"), "2026-06-25")
    expect(save).toBeDisabled()
    await user.type(screen.getByTestId("employee-status-reason"), "   ")
    expect(save).toBeDisabled()

    await user.type(screen.getByTestId("employee-status-reason"), "left")
    expect(save).toBeEnabled()
  })

  it("cannot offer a future date in the picker", async () => {
    // ⚠️ A UI AFFORDANCE, NOT A SECOND COPY OF THE RULE. The server refuses a
    // future `since` because the line-1 rule only asks whether a status began
    // before the month, so "left as of next March" would drop the member from
    // months already filed. The `max` here stops the common typo; the refusal
    // stays the server's, with one producer.
    const user = userEvent.setup()
    render(<EmployeeStatusRow employeeId="emp-1" readOnly={false} />)
    await user.click(await screen.findByTestId("employee-status-change"))
    const max = screen.getByTestId("employee-status-since").getAttribute("max")!
    expect(/^\d{4}-\d{2}-\d{2}$/.test(max)).toBe(true)
    const now = new Date()
    const p = (n: number) => String(n).padStart(2, "0")
    expect(max).toBe(
      `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}`,
    )
  })

  it("prints the SERVER's refusal verbatim, not a generic sentence", async () => {
    // ⚠️ The server's four refusals — unknown status, blank reason, future
    // date, no-op — each say what is wrong and what to do. A generic "could
    // not save" discards the only useful part of the reply.
    const user = userEvent.setup()
    put.mockRejectedValue({
      response: {
        status: 400,
        data: { detail: "this employee is already 'left' since 2026-06-25." },
      },
    })
    render(<EmployeeStatusRow employeeId="emp-1" readOnly={false} />)
    await user.click(await screen.findByTestId("employee-status-change"))
    await user.type(screen.getByTestId("employee-status-since"), "2026-06-25")
    await user.type(screen.getByTestId("employee-status-reason"), "again")
    await user.click(screen.getByTestId("employee-status-save"))

    expect(await screen.findByTestId("employee-status-message")).toHaveTextContent(
      "this employee is already 'left' since 2026-06-25.",
    )
    // The editor stays open with what was typed, so it can be corrected.
    expect(screen.getByTestId("employee-status-editor")).toBeTruthy()
  })
})


describe("a write whose reply never arrived", () => {
  /** No `response` — a CORS rejection, a timeout or a reset on the RETURN leg
   *  all look like this, and the server may have committed. */
  const noReply = { message: "Network Error" }

  it("asks the server and says it DID save when the record is there", async () => {
    const user = userEvent.setup()
    put.mockRejectedValue(noReply)
    render(<EmployeeStatusRow employeeId="emp-1" readOnly={false} />)
    await user.click(await screen.findByTestId("employee-status-change"))
    await user.type(screen.getByTestId("employee-status-since"), "2026-06-25")
    await user.type(screen.getByTestId("employee-status-reason"), "Payentry")
    get.mockResolvedValue({ data: LEFT_IN_JUNE })
    await user.click(screen.getByTestId("employee-status-save"))

    expect(await screen.findByTestId("employee-status-message")).toHaveTextContent(
      "It did save — the reply was the only thing lost.",
    )
  })

  it("says it did NOT save when the record is absent", async () => {
    const user = userEvent.setup()
    put.mockRejectedValue(noReply)
    render(<EmployeeStatusRow employeeId="emp-1" readOnly={false} />)
    await user.click(await screen.findByTestId("employee-status-change"))
    await user.type(screen.getByTestId("employee-status-since"), "2026-06-25")
    await user.type(screen.getByTestId("employee-status-reason"), "Payentry")
    await user.click(screen.getByTestId("employee-status-save"))

    expect(await screen.findByTestId("employee-status-message")).toHaveTextContent(
      "It did not save. Nothing was recorded",
    )
  })

  it("says STILL UNKNOWN when the check cannot reach the server either", async () => {
    // ⚠️ THREE OUTCOMES, NOT TWO. Collapsing a failed check into "did not
    // save" is how a false "nothing has been changed" gets back in by a side
    // door — and here a second attempt would record the change twice.
    const user = userEvent.setup()
    put.mockRejectedValue(noReply)
    render(<EmployeeStatusRow employeeId="emp-1" readOnly={false} />)
    await user.click(await screen.findByTestId("employee-status-change"))
    await user.type(screen.getByTestId("employee-status-since"), "2026-06-25")
    await user.type(screen.getByTestId("employee-status-reason"), "Payentry")
    get.mockRejectedValue(new Error("still down"))
    await user.click(screen.getByTestId("employee-status-save"))

    expect(await screen.findByTestId("employee-status-message")).toHaveTextContent(
      /Still unknown/i,
    )
    expect(screen.getByTestId("employee-status-message")).toHaveTextContent(
      /not recorded twice/i,
    )
  })
})


describe("the history is the point of the table", () => {
  beforeEach(() => get.mockResolvedValue({ data: LEFT_IN_JUNE }))

  it("shows how many changes without opening them", async () => {
    render(<EmployeeStatusRow employeeId="emp-1" readOnly />)
    expect(
      await screen.findByTestId("employee-status-history-toggle"),
    ).toHaveTextContent("2 changes recorded")
    expect(screen.queryByTestId("employee-status-history")).toBeNull()
  })

  it("shows old → new, who said so, and the reason", async () => {
    const user = userEvent.setup()
    render(<EmployeeStatusRow employeeId="emp-1" readOnly />)
    await user.click(await screen.findByTestId("employee-status-history-toggle"))
    const h = screen.getByTestId("employee-status-history")
    expect(h).toHaveTextContent("Left since Jun 25, 2026")
    expect(h).toHaveTextContent("was On workers' comp since Feb 10, 2026")
    expect(h).toHaveTextContent("Susan Mott")
    expect(h).toHaveTextContent("termination date from Payentry")
    // The first change replaced nothing, and says so rather than showing blanks.
    expect(h).toHaveTextContent("first recorded")
  })

  it("shows the day it BEGAN and the day it was RECORDED as two dates", async () => {
    // ⚠️ ROUTINELY MONTHS APART — a June leaver recorded in November, which is
    // exactly the entry being made. One field rendered for both would make the
    // R-115 count a leaver into months they had already left.
    const user = userEvent.setup()
    render(<EmployeeStatusRow employeeId="emp-1" readOnly />)
    await user.click(await screen.findByTestId("employee-status-history-toggle"))
    const h = screen.getByTestId("employee-status-history")
    expect(h).toHaveTextContent("since Jun 25, 2026")
    expect(h).toHaveTextContent("recorded Nov 21, 2026")
  })
})


describe("statusDate", () => {
  it("keeps the YEAR, which is why it is not UnionFormCore's shortDate", () => {
    // The five leavers being entered left between February and June; "Jun 25"
    // with no year is the wrong answer for a leaving date.
    expect(statusDate("2026-06-25")).toBe("Jun 25, 2026")
    expect(statusDate("2025-02-10")).toBe("Feb 10, 2025")
  })

  it("reads a BARE date in the local calendar, not as UTC midnight", () => {
    // ⚠️ `new Date("2026-06-25")` is UTC midnight, which west of Greenwich
    // reads back as the 24th. That shipped once: "Due Nov 15" rendered as
    // "Nov 14".
    expect(statusDate("2026-01-01")).toBe("Jan 1, 2026")
    expect(statusDate("2026-12-31")).toBe("Dec 31, 2026")
  })

  it("reads a timestamp as an instant", () => {
    expect(statusDate("2026-11-21T17:00:00+00:00")).toBe("Nov 21, 2026")
  })

  it("renders nothing rather than a fake date when there is none", () => {
    expect(statusDate(null)).toBe("—")
    expect(statusDate("not a date")).toBe("not a date")
  })
})
