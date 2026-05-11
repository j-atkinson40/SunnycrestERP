/** Phase R-6.2b — PortalFormPage tests. */

import { render, screen, waitFor, fireEvent } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"

import PortalFormPage from "./PortalFormPage"

// Mock the brand provider so it doesn't try to fetch.
vi.mock("@/contexts/portal-brand-context", async () => {
  return {
    PortalBrandProvider: ({ children }: { children: React.ReactNode }) => (
      <div>{children}</div>
    ),
    usePortalBrand: () => ({
      branding: { display_name: "Hopkins Funeral Home", brand_color: "#9C5640" },
      isLoading: false,
      error: null,
    }),
  }
})

// Mock Turnstile so we don't try to mount the iframe.
vi.mock("@marsidev/react-turnstile", () => ({
  Turnstile: () => <div data-testid="turnstile-stub" />,
}))

// Mock the intake service.
vi.mock("@/services/intake", () => ({
  getFormConfig: vi.fn(),
  submitForm: vi.fn(),
}))

import { getFormConfig, submitForm } from "@/services/intake"

const mockFormConfig = {
  id: "cfg-1",
  name: "Personalization Request",
  slug: "personalization-request",
  description: "Tell us about your loved one.",
  form_schema: {
    version: "1.0",
    fields: [
      {
        id: "deceased_name",
        type: "text" as const,
        label: "Name",
        required: true,
        max_length: 200,
      },
      {
        id: "family_contact_email",
        type: "email" as const,
        label: "Email",
        required: true,
      },
    ],
    captcha_required: false,
  },
  success_message: "Thanks!",
}

function renderPage() {
  return render(
    <MemoryRouter
      initialEntries={["/portal/hopkins-fh/intake/personalization-request"]}
    >
      <Routes>
        <Route
          path="/portal/:tenantSlug/intake/:slug"
          element={<PortalFormPage />}
        />
        <Route
          path="/portal/:tenantSlug/intake/:slug/confirmation"
          element={<div data-testid="confirmation-route" />}
        />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(() => {
  vi.clearAllMocks()
})

describe("PortalFormPage", () => {
  it("fetches + renders the form config + all fields", async () => {
    vi.mocked(getFormConfig).mockResolvedValue(mockFormConfig)
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId("portal-form-page")).toBeInTheDocument()
    })
    expect(screen.getByText("Personalization Request")).toBeInTheDocument()
    expect(screen.getByTestId("intake-field-deceased_name")).toBeInTheDocument()
    expect(
      screen.getByTestId("intake-field-family_contact_email"),
    ).toBeInTheDocument()
  })

  it("renders 404-style error state when config fetch fails", async () => {
    vi.mocked(getFormConfig).mockRejectedValue({
      response: { status: 404 },
    })
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId("portal-form-error")).toBeInTheDocument()
    })
    expect(screen.getByText(/form not found/i)).toBeInTheDocument()
  })

  it("calls submitForm and navigates to confirmation on success", async () => {
    vi.mocked(getFormConfig).mockResolvedValue(mockFormConfig)
    vi.mocked(submitForm).mockResolvedValue({
      submission_id: "sub-1",
      success_message: "Thanks!",
    })
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId("portal-form-page")).toBeInTheDocument()
    })
    fireEvent.change(screen.getByTestId("intake-input-deceased_name"), {
      target: { value: "John Smith" },
    })
    fireEvent.change(
      screen.getByTestId("intake-input-family_contact_email"),
      { target: { value: "mary@hopkins.example.com" } },
    )
    fireEvent.click(screen.getByTestId("portal-form-submit"))
    await waitFor(() => {
      expect(screen.getByTestId("confirmation-route")).toBeInTheDocument()
    })
    expect(submitForm).toHaveBeenCalledWith(
      "hopkins-fh",
      "personalization-request",
      expect.objectContaining({ deceased_name: "John Smith" }),
      null,
    )
  })
})
