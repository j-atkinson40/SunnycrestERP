/**
 * RuntimeEditorShell recovery affordance tests — R-7-α.
 *
 * Each error branch in RuntimeEditorShell renders a recovery
 * affordance (button) that lets the operator escape the dead-end
 * state without manual URL surgery. Pre-R-7-α these branches were
 * prose-only; R-6.1/R-6.2 hand-validation sessions routinely hit
 * them when admin tokens expired mid-session.
 *
 * Covered branches:
 *   - runtime-editor-unauth → "Sign in" → navigate("/login")
 *   - runtime-editor-forbidden → "Return to admin home" → "/bridgeable-admin"
 *   - runtime-editor-loading (after 10s timeout) → "Cancel and return
 *     to picker" → navigate(pathname, {replace:true}) strips query
 *     params so the outer shell falls through to TenantUserPicker
 *     per R-1.6.1's picker-as-child arrangement.
 *
 * The runtime-editor-impersonation-missing branch lives inside
 * <ShellWithTenantContext> which requires the full TenantProviders
 * stack (AuthProvider + many siblings); its recovery affordance is
 * exercised by spec 37 instead.
 */
import { render, screen, act } from "@testing-library/react"
import { MemoryRouter, Routes, Route } from "react-router-dom"
import { describe, expect, it, vi, beforeEach } from "vitest"

import RuntimeEditorShell from "@/bridgeable-admin/pages/runtime-editor/RuntimeEditorShell"


// Mock the admin auth context per-scenario.
const mockUseAdminAuth = vi.fn()
vi.mock("@/bridgeable-admin/lib/admin-auth-context", () => ({
  useAdminAuth: () => mockUseAdminAuth(),
}))

// Mock useNavigate so we can assert routing calls without mounting
// destination routes.
const mockNavigate = vi.fn()
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  )
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})


function renderAt(initial: string) {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <Routes>
        <Route path="/runtime-editor/*" element={<RuntimeEditorShell />} />
      </Routes>
    </MemoryRouter>,
  )
}


describe("RuntimeEditorShell — R-7-α recovery affordances", () => {
  beforeEach(() => {
    mockNavigate.mockClear()
    vi.useRealTimers()
  })

  it("renders Sign in button when unauthenticated and navigates to /login on click", () => {
    mockUseAdminAuth.mockReturnValue({ user: null, loading: false })
    renderAt("/runtime-editor/")
    const btn = screen.getByTestId("runtime-editor-unauth-signin")
    expect(btn).toBeTruthy()
    expect(btn.textContent).toContain("Sign in")
    btn.click()
    expect(mockNavigate).toHaveBeenCalledWith("/login")
  })

  it("renders admin-home button when forbidden and navigates on click", () => {
    mockUseAdminAuth.mockReturnValue({
      user: { role: "office", email: "office@x.test" },
      loading: false,
    })
    renderAt("/runtime-editor/")
    const btn = screen.getByTestId("runtime-editor-forbidden-admin-home")
    expect(btn).toBeTruthy()
    expect(btn.textContent).toContain("Return to admin home")
    btn.click()
    expect(mockNavigate).toHaveBeenCalledWith("/bridgeable-admin")
  })

  it("does NOT render loading cancel button before 10s timeout", () => {
    vi.useFakeTimers()
    mockUseAdminAuth.mockReturnValue({ user: null, loading: true })
    renderAt("/runtime-editor/")
    // Loading spinner is visible.
    expect(screen.getByTestId("runtime-editor-loading")).toBeTruthy()
    // Cancel button NOT yet visible (timer hasn't fired).
    expect(
      screen.queryByTestId("runtime-editor-loading-cancel"),
    ).toBeFalsy()
  })

  it("renders cancel button after 10s loading timeout + clears params on click", () => {
    vi.useFakeTimers()
    mockUseAdminAuth.mockReturnValue({ user: null, loading: true })
    renderAt("/runtime-editor/?tenant=hopkins-fh&user=abc")
    expect(
      screen.queryByTestId("runtime-editor-loading-cancel"),
    ).toBeFalsy()
    // Advance past the 10s threshold.
    act(() => {
      vi.advanceTimersByTime(10_000)
    })
    const btn = screen.getByTestId("runtime-editor-loading-cancel")
    expect(btn).toBeTruthy()
    expect(btn.textContent).toContain("Cancel and return to picker")
    btn.click()
    // Strips query params by navigating to bare pathname with
    // replace:true; outer shell falls through to TenantUserPicker.
    expect(mockNavigate).toHaveBeenCalledWith("/runtime-editor/", {
      replace: true,
    })
  })
})
