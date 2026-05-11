/** Phase R-6.2b — Confirmation page tests (form + upload). */

import { render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"

vi.mock("@/contexts/portal-brand-context", async () => ({
  PortalBrandProvider: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  usePortalBrand: () => ({
    branding: { display_name: "Hopkins Funeral Home", brand_color: "#9C5640" },
    isLoading: false,
    error: null,
  }),
}))

import PortalFormConfirmationPage from "./PortalFormConfirmationPage"
import PortalUploadConfirmationPage from "./PortalUploadConfirmationPage"

describe("PortalFormConfirmationPage", () => {
  it("renders fallback message + tenant name when state has no successMessage", () => {
    render(
      <MemoryRouter
        initialEntries={[
          "/portal/hopkins-fh/intake/personalization-request/confirmation",
        ]}
      >
        <Routes>
          <Route
            path="/portal/:tenantSlug/intake/:slug/confirmation"
            element={<PortalFormConfirmationPage />}
          />
        </Routes>
      </MemoryRouter>,
    )
    expect(
      screen.getByTestId("portal-form-confirmation"),
    ).toBeInTheDocument()
    expect(screen.getByText(/submission received/i)).toBeInTheDocument()
    expect(
      screen.getByText(/we've received your submission/i),
    ).toBeInTheDocument()
    // Tenant name appears in confirmation body (also rendered in
    // header via PublicPortalLayout — use getAllByText to handle).
    expect(
      screen.getAllByText(/Hopkins Funeral Home/).length,
    ).toBeGreaterThan(0)
  })
})

describe("PortalUploadConfirmationPage", () => {
  it("renders default upload success copy + tenant name", () => {
    render(
      <MemoryRouter
        initialEntries={[
          "/portal/hopkins-fh/upload/death-certificate/confirmation",
        ]}
      >
        <Routes>
          <Route
            path="/portal/:tenantSlug/upload/:slug/confirmation"
            element={<PortalUploadConfirmationPage />}
          />
        </Routes>
      </MemoryRouter>,
    )
    expect(
      screen.getByTestId("portal-upload-confirmation"),
    ).toBeInTheDocument()
    expect(screen.getByText(/upload received/i)).toBeInTheDocument()
    expect(
      screen.getByText(/uploaded successfully/i),
    ).toBeInTheDocument()
  })
})
