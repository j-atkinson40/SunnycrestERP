/**
 * PtrConsentErrorBanner tests — Phase 1F FH-director-side PTR consent
 * error chrome at canonical `_handle_approve` flow.
 *
 * Coverage:
 *   - Renders nothing on null share_dispatch (canonical happy path —
 *     no error chrome surfaces)
 *   - Renders nothing on `granted` outcome (canonical happy-path
 *     dispatch surfaces no error chrome)
 *   - Renders canonical error chrome with canonical error_detail copy
 *     for each canonical 4 failure mode (ptr_missing,
 *     consent_default, consent_pending_outbound, consent_pending_inbound)
 *   - Canonical "Request consent" affordance routes to canonical
 *     settings page per r75 canon
 *   - Canonical action label varies per canonical outcome (request /
 *     review / open / connect)
 */

import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it } from "vitest"

import { PtrConsentErrorBanner } from "./PtrConsentErrorBanner"
import type { ShareDispatchResponse } from "@/types/personalization-studio"


function _renderWith(shareDispatch: ShareDispatchResponse | null) {
  return render(
    <MemoryRouter>
      <PtrConsentErrorBanner shareDispatch={shareDispatch} />
    </MemoryRouter>,
  )
}


describe("PtrConsentErrorBanner", () => {
  it("renders nothing on null share_dispatch (canonical happy path)", () => {
    const { container } = _renderWith(null)
    expect(container).toBeEmptyDOMElement()
  })

  it("renders nothing on canonical 'granted' outcome", () => {
    const { container } = _renderWith({
      outcome: "granted",
      share_id: "share-1",
      target_company_id: "mfg-co",
      target_company_name: "Sunnycrest",
      relationship_id: "ptr-1",
      error_detail: null,
    })
    expect(container).toBeEmptyDOMElement()
  })

  it("renders canonical error chrome on consent_default", () => {
    _renderWith({
      outcome: "consent_default",
      share_id: null,
      target_company_id: "mfg-co",
      target_company_name: "Sunnycrest",
      relationship_id: "ptr-1",
      error_detail:
        "Cross-tenant Personalization Studio sharing consent has not been requested between this funeral home and Sunnycrest.",
    })

    const banner = screen.getByTestId("ptr-consent-error-banner")
    expect(banner).toHaveAttribute("data-outcome", "consent_default")
    expect(
      screen.getByTestId("ptr-consent-error-detail"),
    ).toHaveTextContent(/has not been requested/i)
    // Canonical "Request consent" affordance routes to canonical
    // settings page per r75 canon.
    const link = screen.getByTestId("ptr-consent-action-link")
    expect(link).toHaveTextContent("Request consent")
    expect(link).toHaveAttribute(
      "href",
      "/settings/personalization-studio/cross-tenant-sharing-consent",
    )
  })

  it("renders canonical error chrome on consent_pending_outbound", () => {
    _renderWith({
      outcome: "consent_pending_outbound",
      share_id: null,
      target_company_id: "mfg-co",
      target_company_name: "Sunnycrest",
      relationship_id: "ptr-1",
      error_detail: "Awaiting Sunnycrest acceptance of the consent request.",
    })

    const banner = screen.getByTestId("ptr-consent-error-banner")
    expect(banner).toHaveAttribute(
      "data-outcome",
      "consent_pending_outbound",
    )
    expect(
      screen.getByTestId("ptr-consent-action-link"),
    ).toHaveTextContent("Open consent settings")
  })

  it("renders canonical error chrome on consent_pending_inbound", () => {
    _renderWith({
      outcome: "consent_pending_inbound",
      share_id: null,
      target_company_id: "mfg-co",
      target_company_name: "Sunnycrest",
      relationship_id: "ptr-1",
      error_detail:
        "Sunnycrest has requested cross-tenant sharing consent.",
    })

    expect(
      screen.getByTestId("ptr-consent-error-banner"),
    ).toHaveAttribute("data-outcome", "consent_pending_inbound")
    expect(
      screen.getByTestId("ptr-consent-action-link"),
    ).toHaveTextContent("Review pending consent request")
  })

  it("renders canonical error chrome on ptr_missing with manufacturer-connection deep-link", () => {
    _renderWith({
      outcome: "ptr_missing",
      share_id: null,
      target_company_id: null,
      target_company_name: null,
      relationship_id: null,
      error_detail:
        "No active manufacturer connection found.",
    })

    const banner = screen.getByTestId("ptr-consent-error-banner")
    expect(banner).toHaveAttribute("data-outcome", "ptr_missing")
    const link = screen.getByTestId("ptr-consent-action-link")
    expect(link).toHaveTextContent("Connect manufacturer")
    // Canonical ptr_missing routes to canonical platform tenant
    // relationship management surface (NOT consent settings).
    expect(link).toHaveAttribute(
      "href",
      "/settings/platform-tenant-relationships",
    )
  })

  it("renders canonical fallback copy when error_detail is null", () => {
    _renderWith({
      outcome: "consent_default",
      share_id: null,
      target_company_id: null,
      target_company_name: null,
      relationship_id: null,
      error_detail: null,
    })
    expect(
      screen.getByTestId("ptr-consent-error-detail"),
    ).toHaveTextContent(
      /Approved memorial design could not be shared with the manufacturer/i,
    )
  })
})
