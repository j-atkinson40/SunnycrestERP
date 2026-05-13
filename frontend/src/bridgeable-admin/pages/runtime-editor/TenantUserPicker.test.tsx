/**
 * TenantUserPicker tests — Studio 1a-i.B follow-up #3 pickup-and-replay.
 *
 * Verifies that when the operator's source URL carries a deep tenant
 * route tail (the redirect-from-runtime-editor case where the source
 * URL had no resolved vertical), the picker preserves that tail in the
 * post-impersonation navigation target:
 *
 *   pre-impersonation:    /studio/live/dispatch/funeral-schedule
 *   pick manufacturing:   /studio/live/manufacturing/dispatch/funeral-schedule?tenant=...&user=...
 *
 * Plus baseline coverage:
 *   - no-tail source navigates to /studio/live/<vertical>?tenant=...&user=...
 *   - studioContext=false (legacy) navigates to /runtime-editor/?...
 *   - query params preserved through to navigation target
 */
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom"


// Capture navigate calls for assertion.
const navigateMock = vi.fn()
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  )
  return {
    ...actual,
    useNavigate: () => navigateMock,
  }
})


// Mock adminApi for the impersonate POST.
const adminApiPost = vi.fn()
vi.mock("@/bridgeable-admin/lib/admin-api", () => ({
  adminApi: {
    post: (...args: unknown[]) => adminApiPost(...args),
  },
}))


// Mock verticalsService for the useVerticals() hook called by the
// picker (Studio 1a-i.B follow-up #4 disambiguation requires the
// canonical 4 vertical slugs to be known).
vi.mock("@/bridgeable-admin/services/verticals-service", () => ({
  verticalsService: {
    list: vi.fn(async () => [
      { slug: "manufacturing", display_name: "Manufacturing", description: null, status: "published", icon: null, sort_order: 1, created_at: "", updated_at: "" },
      { slug: "funeral_home", display_name: "Funeral Home", description: null, status: "published", icon: null, sort_order: 2, created_at: "", updated_at: "" },
      { slug: "cemetery", display_name: "Cemetery", description: null, status: "published", icon: null, sort_order: 3, created_at: "", updated_at: "" },
      { slug: "crematory", display_name: "Crematory", description: null, status: "published", icon: null, sort_order: 4, created_at: "", updated_at: "" },
    ]),
  },
}))


// Mock TenantPicker to expose a deterministic onSelect callback we
// trigger from the test by clicking a button.
vi.mock("@/bridgeable-admin/components/TenantPicker", () => {
  return {
    TenantPicker: ({
      onSelect,
    }: {
      selected: unknown
      onSelect: (t: { id: string; slug: string; name: string; vertical: string }) => void
      verticalFilter?: string | null
    }) => {
      return (
        <button
          type="button"
          data-testid="mock-tenant-picker"
          onClick={() =>
            onSelect({
              id: "tenant-mfg-001",
              slug: "testco",
              name: "Test Vault Co",
              vertical: "manufacturing",
            })
          }
        >
          Pick MFG Tenant
        </button>
      )
    },
  }
})


import TenantUserPicker from "./TenantUserPicker"


// Probe component shows current location for debugging (not asserted).
function LocationProbe() {
  const loc = useLocation()
  return <div data-testid="probe-location" data-pathname={loc.pathname} />
}


function renderPicker(props: {
  studioContext?: boolean
  startPath?: string
}) {
  const startPath = props.startPath ?? "/bridgeable-admin/runtime-editor"
  return render(
    <MemoryRouter initialEntries={[startPath]}>
      <Routes>
        <Route
          path="*"
          element={
            <>
              <LocationProbe />
              <TenantUserPicker studioContext={props.studioContext} />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  )
}


function mockImpersonateSuccess() {
  adminApiPost.mockResolvedValueOnce({
    data: {
      access_token: "fake-token",
      token_type: "bearer",
      tenant_slug: "testco",
      tenant_name: "Test Vault Co",
      impersonated_user_id: "u1",
      impersonated_user_name: "Admin User",
      expires_in_minutes: 30,
      session_id: "session-abc",
    },
  })
}


beforeEach(async () => {
  navigateMock.mockReset()
  adminApiPost.mockReset()
  window.localStorage.clear()
  // Follow-up #4: reset module-level verticals cache so each test
  // re-fetches the mocked verticals deterministically.
  const { __resetVerticalsCacheForTests } = await import(
    "@/bridgeable-admin/hooks/useVerticals"
  )
  __resetVerticalsCacheForTests()
})

afterEach(() => {
  window.localStorage.clear()
})


describe("TenantUserPicker — pickup-and-replay (Studio 1a-i.B follow-up #3)", () => {
  it("preserves deep tail when picker mounted under /studio/live/<tail>", async () => {
    mockImpersonateSuccess()
    renderPicker({
      studioContext: true,
      startPath: "/bridgeable-admin/studio/live/dispatch/funeral-schedule",
    })
    fireEvent.click(screen.getByTestId("mock-tenant-picker"))
    // Wait for useVerticals() to resolve before triggering handleStart
    // so the disambiguation closure (follow-up #4) has the registry.
    await waitFor(() => {
      // verticalsService.list() is async; the hook's setLoaded flips
      // after resolution. Querying for the start button ensures React
      // has rendered the form section (which requires tenant != null
      // from the prior click).
      expect(screen.getByTestId("runtime-editor-picker-start")).toBeTruthy()
    })
    fireEvent.click(screen.getByTestId("runtime-editor-picker-start"))

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledTimes(1)
    })
    const [target, opts] = navigateMock.mock.calls[0]
    expect(target).toBe(
      "/bridgeable-admin/studio/live/manufacturing/dispatch/funeral-schedule?tenant=testco&user=u1",
    )
    expect(opts).toEqual({ replace: true })
  })

  it("navigates to bare vertical landing when source has no tail", async () => {
    mockImpersonateSuccess()
    renderPicker({
      studioContext: true,
      startPath: "/bridgeable-admin/studio/live",
    })
    fireEvent.click(screen.getByTestId("mock-tenant-picker"))
    // Wait for useVerticals() to resolve before triggering handleStart
    // so the disambiguation closure (follow-up #4) has the registry.
    await waitFor(() => {
      // verticalsService.list() is async; the hook's setLoaded flips
      // after resolution. Querying for the start button ensures React
      // has rendered the form section (which requires tenant != null
      // from the prior click).
      expect(screen.getByTestId("runtime-editor-picker-start")).toBeTruthy()
    })
    fireEvent.click(screen.getByTestId("runtime-editor-picker-start"))

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledTimes(1)
    })
    const [target] = navigateMock.mock.calls[0]
    expect(target).toBe(
      "/bridgeable-admin/studio/live/manufacturing?tenant=testco&user=u1",
    )
  })

  it("preserves multi-segment deep tail with query params", async () => {
    mockImpersonateSuccess()
    renderPicker({
      studioContext: true,
      startPath: "/bridgeable-admin/studio/live/cases/abc-123",
    })
    fireEvent.click(screen.getByTestId("mock-tenant-picker"))
    // Wait for useVerticals() to resolve before triggering handleStart
    // so the disambiguation closure (follow-up #4) has the registry.
    await waitFor(() => {
      // verticalsService.list() is async; the hook's setLoaded flips
      // after resolution. Querying for the start button ensures React
      // has rendered the form section (which requires tenant != null
      // from the prior click).
      expect(screen.getByTestId("runtime-editor-picker-start")).toBeTruthy()
    })
    fireEvent.click(screen.getByTestId("runtime-editor-picker-start"))

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledTimes(1)
    })
    const [target] = navigateMock.mock.calls[0]
    expect(target).toBe(
      "/bridgeable-admin/studio/live/manufacturing/cases/abc-123?tenant=testco&user=u1",
    )
  })

  it("toggleMode edge case — source has known vertical, picker resolves DIFFERENT vertical (follow-up #4 fix)", async () => {
    // Pre-#4: source URL `/studio/live/manufacturing` (from toggleMode)
    // + picker selects a tenant in a different vertical would treat
    // `manufacturing` as the tail and produce
    // `/studio/live/<new-vertical>/manufacturing?...` which fails to
    // match a tenant route.
    //
    // Post-#4: `manufacturing` IS a known vertical → tail="" →
    // post-impersonation URL is the canonical vertical landing.
    //
    // (Mock selects manufacturing here too, so vertical doesn't actually
    // change, but the disambiguation logic runs identically — the key
    // assertion is that `manufacturing` is NOT carried as tail.)
    mockImpersonateSuccess()
    renderPicker({
      studioContext: true,
      startPath: "/bridgeable-admin/studio/live/manufacturing",
    })
    fireEvent.click(screen.getByTestId("mock-tenant-picker"))
    await waitFor(() => {
      expect(screen.getByTestId("runtime-editor-picker-start")).toBeTruthy()
    })
    fireEvent.click(screen.getByTestId("runtime-editor-picker-start"))

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledTimes(1)
    })
    const [target] = navigateMock.mock.calls[0]
    // Target should be the canonical vertical landing — NO
    // `/manufacturing/manufacturing` doubling.
    expect(target).toBe(
      "/bridgeable-admin/studio/live/manufacturing?tenant=testco&user=u1",
    )
  })

  it("legacy (studioContext=false) navigates to /runtime-editor/?... unchanged", async () => {
    mockImpersonateSuccess()
    renderPicker({
      studioContext: false,
      startPath: "/bridgeable-admin/runtime-editor",
    })
    fireEvent.click(screen.getByTestId("mock-tenant-picker"))
    // Wait for useVerticals() to resolve before triggering handleStart
    // so the disambiguation closure (follow-up #4) has the registry.
    await waitFor(() => {
      // verticalsService.list() is async; the hook's setLoaded flips
      // after resolution. Querying for the start button ensures React
      // has rendered the form section (which requires tenant != null
      // from the prior click).
      expect(screen.getByTestId("runtime-editor-picker-start")).toBeTruthy()
    })
    fireEvent.click(screen.getByTestId("runtime-editor-picker-start"))

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledTimes(1)
    })
    const [target] = navigateMock.mock.calls[0]
    expect(target).toBe(
      "/bridgeable-admin/runtime-editor/?tenant=testco&user=u1",
    )
  })
})
