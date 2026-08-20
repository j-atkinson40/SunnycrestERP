/**
 * TAX-3 — the Exemptions tab distinguishes "couldn't load" from "nothing to show".
 *
 * ⚠️ THIS TAB CALLED AN ENDPOINT THAT RETURNED 500 ON EVERY CALL, FOR AS LONG AS
 * IT EXISTED, AND SAID "No tax-exempt customers". `GET /tax/exemptions` queried
 * `customers.tax_status` — a column present in the database and absent from the
 * ORM model — so it raised AttributeError before any SQL ran. The fetch here was
 * `.catch(() => {})`, so the failure became an empty array, and an empty array
 * renders identically to a working query with nothing to report.
 *
 * That is the same defect as the two swallowed health checks in
 * `financial_report_service` — a compliance surface reporting all-clear because
 * it could not run. The endpoint is now backed by `TaxCertificate`; this file
 * pins the part that stops it lying if it breaks again.
 *
 * ⚠️ THE FAILURE TEST IS THE ONE THAT MATTERS. A rendering test for the happy
 * path would have passed against the old broken code too — it returned `[]` and
 * rendered the empty state without error.
 */
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import TaxSettingsPage from "./tax-settings"
import apiClient from "@/lib/api-client"

/* ⚠️ `api-client` is a DEFAULT export (`api-client.ts:149`) and this page
   imports it as one. A named-export mock type-checks and then fails at render
   with "No 'default' export is defined on the mock" — read from the source
   rather than assumed, per the same mock-shape trap that cost time on the
   customers ZIP tests. */
vi.mock("@/lib/api-client", () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const api = vi.mocked(apiClient)

function mockGet(handler: (url: string) => unknown) {
  api.get.mockImplementation((url: string) => {
    const result = handler(url)
    return result instanceof Error
      ? Promise.reject(result)
      : Promise.resolve({ data: result } as never)
  })
}

async function openExemptionsTab() {
  render(
    <MemoryRouter>
      <TaxSettingsPage />
    </MemoryRouter>,
  )
  const tab = await screen.findByRole("button", { name: /exemptions/i })
  tab.click()
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe("the Exemptions tab", () => {
  it("says it could not load when the request fails", async () => {
    mockGet((url) => (url === "/tax/exemptions" ? new Error("500") : []))
    await openExemptionsTab()

    expect(await screen.findByText(/couldn't load exemptions/i)).toBeInTheDocument()
    // ⚠️ AND IT MUST NOT ALSO CLAIM THERE IS NOTHING TO SHOW. Rendering both
    // would restore the ambiguity this change removed.
    expect(screen.queryByText(/no exemption certificates on file/i)).not.toBeInTheDocument()
  })

  it("warns that a failed load is not a clean result", async () => {
    mockGet((url) => (url === "/tax/exemptions" ? new Error("500") : []))
    await openExemptionsTab()
    expect(await screen.findByText(/not a clean result/i)).toBeInTheDocument()
  })

  it("shows the empty state — and no error — when the request succeeds with no rows", async () => {
    mockGet(() => [])
    await openExemptionsTab()

    expect(await screen.findByText(/no exemption certificates on file/i)).toBeInTheDocument()
    expect(screen.queryByText(/couldn't load exemptions/i)).not.toBeInTheDocument()
  })

  it("renders certificate rows from the repointed endpoint", async () => {
    mockGet((url) =>
      url === "/tax/exemptions"
        ? [{
            certificate_id: "c-1", customer_id: "cu-1", customer_name: "Hopkins Funeral Home",
            cert_type: "resale", cert_number: "R-8842", scope: "blanket",
            valid_through: "2026-09-01", attached: true,
            is_expired: false, is_expiring: true, missing_cert: false,
          }]
        : [],
    )
    await openExemptionsTab()

    expect(await screen.findByText("Hopkins Funeral Home")).toBeInTheDocument()
    expect(screen.getByText(/Cert #R-8842/)).toBeInTheDocument()
  })

  it("says an open-dated certificate is open-dated rather than leaving it blank", async () => {
    /* An absent expiry is a real answer — the certificate never lapses — and
       reads as missing data unless it is named. */
    mockGet((url) =>
      url === "/tax/exemptions"
        ? [{
            certificate_id: "c-2", customer_id: "cu-2", customer_name: "St Mary's",
            cert_type: "exempt_org", cert_number: null, scope: "blanket",
            valid_through: null, attached: false,
            is_expired: false, is_expiring: false, missing_cert: true,
          }]
        : [],
    )
    await openExemptionsTab()

    expect(await screen.findByText(/Open-dated/)).toBeInTheDocument()
    expect(screen.getByText(/No certificate number/)).toBeInTheDocument()
  })
})
