/**
 * TAX-2 B-2 — the create form collects the ZIP, because tax resolves from it.
 *
 * ⚠️ THIS FORM ASKED FOR CITY AND STATE AND NOT THE ZIP, while the CSV import on
 * the SAME PAGE lists `zip_code` among its expected columns. So importing
 * produced taxable customers and typing produced untaxable ones, from one
 * screen, with nothing saying so.
 *
 * The ZIP is not one address field among several. `get_jurisdiction_for_order`
 * (backend `tax_service.py:39-49`) resolves a taxing county from
 * `zip_code or billing_zip` through the platform's zip→county map, and there is
 * NO city→county path — `grep "city" county_geographic_service.py` returns
 * nothing. City and state cannot substitute. Measured on production 2026-08-19:
 * zero customers on any tenant carry a ZIP, so every resolution returns
 * `unresolved` and charges nothing.
 *
 * ⚠️ AND THE TEST THAT MATTERS IS THE PAYLOAD ONE, NOT THE RENDER ONE. An input
 * can exist, accept typing, and never reach the request — which is A-2's void
 * call in a different costume: correct-looking code nothing invokes. So the
 * assertion is on what `createCustomer` was CALLED WITH, and it was verified by
 * removing `zip_code` from the payload and watching it fail.
 */
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"

import CustomersPage from "./customers"
import { customerService } from "@/services/customer-service"

vi.mock("@/contexts/auth-context", () => ({
  useAuth: () => ({ company: { name: "Test Vault Co" }, isAdmin: true, hasPermission: () => true }),
}))
vi.mock("@/contexts/extension-context", () => ({
  useExtensions: () => ({ isExtensionEnabled: () => false }),
}))
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock("@/services/customer-service", () => ({
  customerService: {
    getCustomers: vi.fn(),
    getStats: vi.fn(),
    createCustomer: vi.fn(),
    importCustomersCsv: vi.fn(),
  },
}))

const svc = vi.mocked(customerService)

beforeEach(() => {
  vi.clearAllMocks()
  // ⚠️ SHAPES READ FROM THE PAGE, NOT GUESSED. It consumes `data.items` and
  // `data.total` (`customers.tsx:151-152`) and renders five `stats.*` fields
  // (`:562-584`); a mock missing either crashes the render with an error that
  // looks like a defect in the field under test.
  svc.getCustomers.mockResolvedValue({ items: [], total: 0 } as never)
  svc.getStats.mockResolvedValue({
    total_customers: 0, active_customers: 0, on_hold: 0,
    over_limit_count: 0, total_outstanding: 0,
  } as never)
  svc.createCustomer.mockResolvedValue({ id: "c-1" } as never)
})

async function openCreateAndFill(zip: string | null) {
  render(
    <MemoryRouter>
      <CustomersPage />
    </MemoryRouter>,
  )
  await waitFor(() => expect(svc.getCustomers).toHaveBeenCalled())

  const opener = await screen.findByRole("button", { name: /^add customer$/i })
  await userEvent.click(opener)

  // ⚠️ BY PLACEHOLDER, NOT BY LABEL — the pre-existing fields on this form use
  // a bare <Label> with no `htmlFor` and an <Input> with no `id`, so
  // `getByLabelText` cannot reach them. The NEW ZIP field is wired properly and
  // is found by label; matching the old fields the same way would have meant
  // relabelling markup this sub-arc has no business touching. The gap is real
  // and recorded in the B-2 report.
  const name = await screen.findByPlaceholderText(/Johnson Funeral Home/i)
  await userEvent.type(name, "Hopkins Funeral Home")

  if (zip !== null) {
    await userEvent.type(screen.getByLabelText(/zip code/i), zip)
  }
  await userEvent.click(screen.getByRole("button", { name: /^create customer$/i }))
}

describe("the create form asks for the ZIP", () => {
  it("renders a ZIP field alongside city and state", async () => {
    render(
      <MemoryRouter>
        <CustomersPage />
      </MemoryRouter>,
    )
    await waitFor(() => expect(svc.getCustomers).toHaveBeenCalled())
    await userEvent.click(
      await screen.findByRole("button", { name: /^add customer$/i }),
    )
    expect(await screen.findByLabelText(/zip code/i)).toBeInTheDocument()
    // The two it already asked for, which the resolver cannot use on their own.
    expect(screen.getByText("City")).toBeInTheDocument()
    expect(screen.getByText("State")).toBeInTheDocument()
  })

  it("says what leaving it blank costs, in the operator's terms", async () => {
    render(
      <MemoryRouter>
        <CustomersPage />
      </MemoryRouter>,
    )
    await waitFor(() => expect(svc.getCustomers).toHaveBeenCalled())
    await userEvent.click(
      await screen.findByRole("button", { name: /^add customer$/i }),
    )
    // ⚠️ THE DISTINCTION THAT CARRIES THE LIABILITY. Zero tax because nothing
    // resolved and zero tax because a certificate applies are the same number
    // and different obligations.
    expect(
      await screen.findByText(/not the same as being exempt/i),
    ).toBeInTheDocument()
  })

  it("is NOT marked required", async () => {
    /* Ruled in B-2: the funeral-home path resolves by cemetery county, and
       Places-discovered customers may have no ZIP. Requiredness belongs at the
       resolution boundary — refuse an order you cannot tax — not here. */
    render(
      <MemoryRouter>
        <CustomersPage />
      </MemoryRouter>,
    )
    await waitFor(() => expect(svc.getCustomers).toHaveBeenCalled())
    await userEvent.click(
      await screen.findByRole("button", { name: /^add customer$/i }),
    )
    const zip = await screen.findByLabelText(/zip code/i)
    expect(zip).not.toBeRequired()
  })
})

describe("the ZIP reaches the request", () => {
  it("sends zip_code in the create payload", async () => {
    /* ⚠️ THE WIRING ASSERTION. A field that renders and never reaches the
       request is the failure this arc has shipped twice. */
    await openCreateAndFill("13021")
    await waitFor(() => expect(svc.createCustomer).toHaveBeenCalled())
    expect(svc.createCustomer.mock.calls[0][0]).toMatchObject({
      name: "Hopkins Funeral Home",
      zip_code: "13021",
    })
  })

  it("omits it rather than sending an empty string when left blank", async () => {
    /* `"" || undefined` — an empty string would write a blank ZIP over a real
       one on any path that reuses this payload shape, and `zip_code.trim()[:5]`
       on the backend would then resolve nothing while LOOKING populated. */
    await openCreateAndFill(null)
    await waitFor(() => expect(svc.createCustomer).toHaveBeenCalled())
    expect(svc.createCustomer.mock.calls[0][0].zip_code).toBeUndefined()
  })
})
