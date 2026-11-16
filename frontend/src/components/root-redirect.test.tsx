/**
 * RootRedirect tests — Phase W-4a Step 4 (routing-bug fix).
 *
 * Verifies the canonical entry point per BRIDGEABLE_MASTER §3.26.1.1:
 * authenticated tenant users land on /home (Pulse) on app open.
 *
 * Specialized roles preserved:
 *   - drivers → /driver
 *   - production_delivery track → /console/* (single-console fast path
 *     for delivery_console and production_console)
 *   - unauthenticated → /login
 *   - loading → "Loading..." placeholder
 *
 * Pre-Phase-W-4a-Step-4 the default authenticated tenant fallback was
 * /dashboard. Investigation surfaced this as a discoverability bug —
 * users hitting the canonical "open the app" flow never reached Pulse.
 * The §3.26.1.1 canon makes Home the canonical entry; this redirect
 * honors that. /dashboard remains accessible via direct URL and via
 * Ownership space's default_home_route until Phase W-5 retirement.
 */
import { render } from "@testing-library/react"
import { MemoryRouter, Routes, Route } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"

import { RootRedirect } from "@/components/root-redirect"


// Mock the auth context for each scenario.
const mockUseAuth = vi.fn()
vi.mock("@/contexts/auth-context", () => ({
  useAuth: () => mockUseAuth(),
}))

// ⚠️ **THE PRESET HOOK IS NO LONGER MOCKED, AND THAT IS THE POINT.**
// `RootRedirect` used to branch on `usePresetThemeOptional()`, and these tests
// mocked it to supply a preset — so they exercised a helper while the real
// component, mounted outside the only `PresetThemeProvider`, could never take
// that branch. The branch is deleted (2026-11-16); nothing here supplies a
// preset, which is the production condition.


function renderAt(initial: string) {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <Routes>
        <Route path="/" element={<RootRedirect />} />
        <Route path="/home" element={<div data-testid="home" />} />
        <Route path="/dashboard" element={<div data-testid="dashboard" />} />
        <Route path="/login" element={<div data-testid="login" />} />
        <Route path="/driver" element={<div data-testid="driver" />} />
        <Route path="/payroll" element={<div data-testid="payroll" />} />
        <Route
          path="/console"
          element={<div data-testid="console-multi" />}
        />
        <Route
          path="/console/delivery"
          element={<div data-testid="console-delivery" />}
        />
        <Route
          path="/console/production"
          element={<div data-testid="console-production" />}
        />
      </Routes>
    </MemoryRouter>,
  )
}


describe("RootRedirect", () => {
  it("authenticated tenant user lands on /home (Pulse) — Phase W-4a §3.26.1.1 canon", () => {
    mockUseAuth.mockReturnValue({
      user: { role_slug: "admin" },
      isLoading: false,
      isAuthenticated: true,
      track: "office_management",
      consoleAccess: new Set<string>(),
    })
    renderAt("/")
    // Lands on /home — the canonical Home Space surface.
    expect(document.querySelector('[data-testid="home"]')).toBeTruthy()
    // Does NOT land on /dashboard (regression guard for the pre-Step-4
    // bug where users never reached Pulse via canonical entry flow).
    expect(document.querySelector('[data-testid="dashboard"]')).toBeFalsy()
  })

  it("driver role still lands on /driver (specialized portal entry)", () => {
    mockUseAuth.mockReturnValue({
      user: { role_slug: "driver" },
      isLoading: false,
      isAuthenticated: true,
      track: "office_management",
      consoleAccess: new Set<string>(),
    })
    renderAt("/")
    expect(document.querySelector('[data-testid="driver"]')).toBeTruthy()
    expect(document.querySelector('[data-testid="home"]')).toBeFalsy()
  })

  it("production_delivery + single delivery_console access lands on /console/delivery", () => {
    mockUseAuth.mockReturnValue({
      user: { role_slug: "delivery" },
      isLoading: false,
      isAuthenticated: true,
      track: "production_delivery",
      consoleAccess: new Set(["delivery_console"]),
    })
    renderAt("/")
    expect(
      document.querySelector('[data-testid="console-delivery"]'),
    ).toBeTruthy()
    expect(document.querySelector('[data-testid="home"]')).toBeFalsy()
  })

  it("production_delivery + single production_console access lands on /console/production", () => {
    mockUseAuth.mockReturnValue({
      user: { role_slug: "production" },
      isLoading: false,
      isAuthenticated: true,
      track: "production_delivery",
      consoleAccess: new Set(["production_console"]),
    })
    renderAt("/")
    expect(
      document.querySelector('[data-testid="console-production"]'),
    ).toBeTruthy()
  })

  it("production_delivery + multi-console access lands on /console (chooser)", () => {
    mockUseAuth.mockReturnValue({
      user: { role_slug: "delivery" },
      isLoading: false,
      isAuthenticated: true,
      track: "production_delivery",
      consoleAccess: new Set(["delivery_console", "production_console"]),
    })
    renderAt("/")
    expect(
      document.querySelector('[data-testid="console-multi"]'),
    ).toBeTruthy()
  })

  it("unauthenticated user redirects to /login", () => {
    mockUseAuth.mockReturnValue({
      user: null,
      isLoading: false,
      isAuthenticated: false,
      track: "office_management",
      consoleAccess: new Set<string>(),
    })
    renderAt("/")
    expect(document.querySelector('[data-testid="login"]')).toBeTruthy()
    expect(document.querySelector('[data-testid="home"]')).toBeFalsy()
  })

  it("isLoading state shows Loading... placeholder, no redirect", () => {
    mockUseAuth.mockReturnValue({
      user: null,
      isLoading: true,
      isAuthenticated: false,
      track: "office_management",
      consoleAccess: new Set<string>(),
    })
    renderAt("/")
    // No redirects fired during loading.
    expect(document.body.textContent).toContain("Loading...")
    expect(document.querySelector('[data-testid="home"]')).toBeFalsy()
    expect(document.querySelector('[data-testid="login"]')).toBeFalsy()
  })

  it("non-driver office user lands on /home regardless of role_slug variants", () => {
    // Office, accountant, director, etc. — all default tenant roles
    // that aren't driver and aren't production_delivery track.
    for (const role_slug of ["office", "accountant", "director", "production"]) {
      mockUseAuth.mockReturnValue({
        user: { role_slug },
        isLoading: false,
        isAuthenticated: true,
        track: "office_management",  // not production_delivery
        consoleAccess: new Set<string>(),
      })
      const { unmount } = renderAt("/")
      expect(
        document.querySelector('[data-testid="home"]'),
        `role_slug=${role_slug} should land on /home`,
      ).toBeTruthy()
      unmount()
    }
  })
})


/**
 * ⚠️ WHERE AN AREA-LIMITED USER LANDS — **`/home`, like everyone else.**
 *
 * This replaces a block of tests for a branch that never ran. The old
 * behaviour sent an area-limited user to her own area instead of Home, via
 * `landingRouteForAreas`; `RootRedirect` read `usePresetThemeOptional()` and is
 * mounted outside the only `PresetThemeProvider`, so the hook returned null on
 * every render and the branch was unreachable. The tests supplied a preset
 * through a mock, so they were green against code that could not execute.
 *
 * James's ruling of 2026-11-16: in the redesign every user lands on the note,
 * area-limited users included — so the dead code was also the wrong behaviour,
 * and deleting it was cheaper and safer than moving a provider that every
 * user's sign-in passes through.
 *
 * ⚠️ NOTHING HERE MOCKS THE PRESET HOOK. That is the whole value of the test:
 * it exercises the real component under the real production condition rather
 * than a helper under a condition the app never produces.
 */



describe("an area-limited user lands on the note", () => {
  it("sends a payroll-limited user to /home", () => {
    mockUseAuth.mockReturnValue({
      user: { role_slug: "payroll" },
      isLoading: false,
      isAuthenticated: true,
      track: "office_management",
      consoleAccess: new Set<string>(),
      limitedToAreas: ["payroll"],
    })
    renderAt("/")
    expect(document.querySelector('[data-testid="home"]')).toBeTruthy()
    // ⚠️ The deleted branch sent her HERE instead. The route still exists and
    // she can reach it from her nav; she must not be redirected onto it.
    expect(document.querySelector('[data-testid="payroll"]')).toBeFalsy()
  })

  it("sends a user limited to NOTHING to /home too", () => {
    // `[]` is "limited to nothing" and is distinct from `null`. She reaches no
    // area, and the note composes to an empty note rather than an error.
    mockUseAuth.mockReturnValue({
      user: { role_slug: "payroll" },
      isLoading: false,
      isAuthenticated: true,
      track: "office_management",
      consoleAccess: new Set<string>(),
      limitedToAreas: [],
    })
    renderAt("/")
    expect(document.querySelector('[data-testid="home"]')).toBeTruthy()
  })

  it("⚠️ a driver is still routed to the console, not to the note", () => {
    // The deleted branch carried an explicit driver/console carve-out, so
    // removing it could have changed where those users go. This pins it.
    mockUseAuth.mockReturnValue({
      user: { role_slug: "driver" },
      isLoading: false,
      isAuthenticated: true,
      track: "office_management",
      consoleAccess: new Set<string>(),
      limitedToAreas: ["payroll"],
    })
    renderAt("/")
    expect(document.querySelector('[data-testid="driver"]')).toBeTruthy()
    expect(document.querySelector('[data-testid="home"]')).toBeFalsy()
  })
})
