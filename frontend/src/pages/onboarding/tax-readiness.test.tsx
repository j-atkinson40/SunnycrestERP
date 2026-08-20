/**
 * TAX-4 — the readiness page distinguishes three states that look alike.
 *
 * ⚠️ "COULDN'T CHECK", "NOTHING TO CHECK" AND "ALL CLEAR" RENDER IDENTICALLY
 * UNLESS EACH IS SAID OUT LOUD. This arc found that failure three times in one
 * codebase — a health check swallowing its exception into "finding silently
 * absent", an Exemptions tab rendering "No tax-exempt customers" on a 500, and
 * a seed logging "would apply" while writing nothing. All three reported
 * all-clear about a condition they had not evaluated.
 *
 * The empty state is the subtle one and it is tested here explicitly: a tenant
 * with no customers has not been found compliant, it has been found untested.
 *
 * ⚠️ AND THE PAGE MUST NOT IMPLY ZERO IS REQUIRED. Completing the step means the
 * tenant looked. A tenant with 400 imported customers and 30 bad addresses must
 * be able to finish onboarding, and copy that reads as a blocker turns a known
 * problem into a stuck one.
 */
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import TaxReadinessPage from "./tax-readiness"
import apiClient from "@/lib/api-client"

/* `api-client` is a DEFAULT export (`api-client.ts:149`) — a named-export mock
   type-checks and then fails at render with "No 'default' export is defined". */
vi.mock("@/lib/api-client", () => ({
  default: { get: vi.fn() },
}))

const api = vi.mocked(apiClient)

const EMPTY = {
  total_customers: 0, resolves: 0, unresolved: 0,
  counts: { no_address: 0, ambiguous: 0, unconfigured: 0, resolves: 0 },
  customers: { no_address: [], ambiguous: [], unconfigured: [], resolves: [] },
  verdict: "reported_none",
}

function renderPage() {
  render(
    <MemoryRouter>
      <TaxReadinessPage />
    </MemoryRouter>,
  )
}

beforeEach(() => vi.clearAllMocks())

describe("the tax readiness page", () => {
  it("says it could not check when the request fails", async () => {
    api.get.mockRejectedValue(new Error("500") as never)
    renderPage()

    expect(await screen.findByText(/couldn.t check tax readiness/i)).toBeInTheDocument()
    expect(await screen.findByText(/not a clean result/i)).toBeInTheDocument()
    // ⚠️ AND MUST NOT ALSO CLAIM THERE IS NOTHING TO CHECK — rendering both
    // restores the ambiguity this page exists to remove.
    //
    // NOTE ON WHAT THIS DOES AND DOES NOT PROVE: the guard is `!report`, not a
    // `failed` flag. Removing the `.catch` entirely still renders this card,
    // because a rejected promise leaves `report` null either way. That is the
    // component being correct by shape rather than by bookkeeping — and it is
    // why the Exemptions tab needed a flag and this does not: there a swallowed
    // failure left an empty ARRAY, indistinguishable from a real empty result.
    expect(screen.queryByText(/no customers yet/i)).not.toBeInTheDocument()
  })

  it("distinguishes no customers from all customers resolving", async () => {
    api.get.mockResolvedValue({ data: EMPTY } as never)
    renderPage()

    expect(await screen.findByText(/no customers yet/i)).toBeInTheDocument()
    expect(screen.queryByText(/every customer resolves/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/couldn.t check/i)).not.toBeInTheDocument()
  })

  it("says every customer resolves only when they do", async () => {
    api.get.mockResolvedValue({
      data: {
        ...EMPTY, total_customers: 3, resolves: 3, verdict: "complete",
        counts: { ...EMPTY.counts, resolves: 3 },
        customers: {
          ...EMPTY.customers,
          resolves: [{ customer_id: "a", customer_name: "A", county: "cayuga", rate_percentage: 8 }],
        },
      },
    } as never)
    renderPage()
    expect(await screen.findByText(/every customer resolves to a tax county/i)).toBeInTheDocument()
  })

  it("renders each unresolved customer's own reason, not a count", async () => {
    /* ⚠️ THE REASON IS THE DELIVERABLE. "3 customers unresolved" sends someone
       hunting; naming the counties an ambiguous ZIP spans is actionable. */
    api.get.mockResolvedValue({
      data: {
        ...EMPTY, total_customers: 2, resolves: 0, unresolved: 2, verdict: "partial",
        counts: { no_address: 1, ambiguous: 1, unconfigured: 0, resolves: 0 },
        customers: {
          ...EMPTY.customers,
          no_address: [{
            customer_id: "c1", customer_name: "Hopkins FH", zip_code: null,
            reason: "Hopkins FH has no ZIP code on file — sales tax resolves from the ZIP",
          }],
          ambiguous: [{
            customer_id: "c2", customer_name: "Seneca Falls Co", zip_code: "14456",
            reason: "ZIP 14456 spans counties charging different rates (Ontario 7.5%, Seneca 8%)",
          }],
        },
      },
    } as never)
    renderPage()

    expect(await screen.findByText(/no ZIP code on file/i)).toBeInTheDocument()
    expect(screen.getByText(/Ontario 7.5%, Seneca 8%/)).toBeInTheDocument()
    // The two failures are grouped separately because they want different fixes.
    expect(screen.getByText(/add a ZIP code to these customers/i)).toBeInTheDocument()
    expect(screen.getByText(/set the tax county on these customers/i)).toBeInTheDocument()
  })

  it("tells the tenant they can finish with unresolved customers", async () => {
    /* Otherwise an unfinishable checklist reads as the tenant's fault. */
    api.get.mockResolvedValue({
      data: {
        ...EMPTY, total_customers: 1, resolves: 0, unresolved: 1, verdict: "partial",
        counts: { no_address: 1, ambiguous: 0, unconfigured: 0, resolves: 0 },
        customers: {
          ...EMPTY.customers,
          no_address: [{ customer_id: "c1", customer_name: "X", zip_code: null, reason: "no ZIP" }],
        },
      },
    } as never)
    renderPage()
    expect(await screen.findByText(/can finish setting up with these unresolved/i)).toBeInTheDocument()
  })
})
