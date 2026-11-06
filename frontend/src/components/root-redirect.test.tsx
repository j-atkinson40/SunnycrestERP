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

// ⚠️ DEFAULTS TO null — "no PresetThemeProvider above me" — which is the state
// the eight tests below were written against and must keep. Only the
// area-limited cases override it.
const mockPreset = vi.fn<() => { navigation: unknown } | null>(() => null)
vi.mock("@/contexts/preset-theme-context", () => ({
  usePresetThemeOptional: () => mockPreset(),
}))


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
 * Payroll 2 follow-up (2026-11-06) — an area-limited user lands on her area.
 *
 * James signed in as the real Payroll-role user on production and landed on
 * Home, whose note comes from `/briefings/*` — which the server refuses for
 * her. The page reported an honest error rather than an empty day, so the
 * message was right and the destination was wrong.
 *
 * ⚠️ These tests mount `RootRedirect` WITHOUT a `PresetThemeProvider`, exactly
 * as the eight above do, because the no-provider case is load-bearing rather
 * than incidental: the first version of this feature used the throwing
 * `usePresetTheme` and reddened all eight. The component now reads the
 * optional hook, so "no provider" means "the nav is not knowable here" and the
 * redirect correctly does not fire.
 */
describe("area-limited landing", () => {
  it("does NOT redirect when the nav is not knowable (no provider mounted)", () => {
    // ⚠️ The honest failure. Without the nav there is no way to know which
    // route is hers, and guessing one would be the third list this change
    // exists to avoid. She falls through to the default and sees the same
    // honest error she saw before — no worse, and no invented route.
    mockUseAuth.mockReturnValue({
      user: { role_slug: "payroll" },
      isLoading: false,
      isAuthenticated: true,
      track: "office_management",
      consoleAccess: [],
      limitedToAreas: ["payroll"],
    })
    expect(renderAt("/").queryByTestId("home")).not.toBeNull()
  })

  it("leaves an unlimited user on /home, limited_to_areas being null", () => {
    // The mirror: the field exists for everyone, and null must change nothing.
    mockUseAuth.mockReturnValue({
      user: { role_slug: "office" },
      isLoading: false,
      isAuthenticated: true,
      track: "office_management",
      consoleAccess: [],
      limitedToAreas: null,
    })
    expect(renderAt("/").queryByTestId("home")).not.toBeNull()
  })

  it("leaves a user on /home when /auth/me omits the field entirely", () => {
    // An older payload. `undefined` must read as unlimited, not as limited to
    // nothing — otherwise a version skew would strand every user.
    mockUseAuth.mockReturnValue({
      user: { role_slug: "office" },
      isLoading: false,
      isAuthenticated: true,
      track: "office_management",
      consoleAccess: [],
      limitedToAreas: undefined,
    })
    expect(renderAt("/").queryByTestId("home")).not.toBeNull()
  })
})


describe("area-limited landing, with the nav available", () => {
  /** The shape PresetThemeProvider exposes, trimmed to what the redirect reads. */
  function navWith(items: { label: string; href: string; area?: string }[]) {
    return { navigation: { sections: [{ title: "", items }], presetAccent: "#000", presetLabel: "x" } }
  }

  it("sends a payroll-limited user to /payroll, not /home", () => {
    // ⚠️ THE BEHAVIOUR JAMES ASKED FOR, at the wiring rather than at the
    // helper. `landingRouteForAreas` is unit-tested next door; this asserts
    // RootRedirect actually calls it and honours the answer — the gap that
    // CLAUDE.md §11 shapes 2 and 3 are both about.
    mockUseAuth.mockReturnValue({
      user: { role_slug: "payroll" },
      isLoading: false,
      isAuthenticated: true,
      track: "office_management",
      consoleAccess: [],
      limitedToAreas: ["payroll"],
    })
    mockPreset.mockReturnValue(
      navWith([{ label: "Payroll", href: "/payroll", area: "payroll" }]) as never,
    )
    const r = renderAt("/")
    expect(r.queryByTestId("payroll")).not.toBeNull()
    expect(r.queryByTestId("home")).toBeNull()
    mockPreset.mockReturnValue(null)
  })

  it("leaves an unlimited user on /home even with the nav available", () => {
    // The control. Without it the test above would pass on a redirect that
    // fires for everybody, which would send every office user to /payroll.
    mockUseAuth.mockReturnValue({
      user: { role_slug: "office" },
      isLoading: false,
      isAuthenticated: true,
      track: "office_management",
      consoleAccess: [],
      limitedToAreas: null,
    })
    mockPreset.mockReturnValue(
      navWith([
        { label: "Home", href: "/dashboard" },
        { label: "Payroll", href: "/payroll", area: "payroll" },
      ]) as never,
    )
    const r = renderAt("/")
    expect(r.queryByTestId("home")).not.toBeNull()
    expect(r.queryByTestId("payroll")).toBeNull()
    mockPreset.mockReturnValue(null)
  })

  it("does not redirect a limited user whose nav came back empty", () => {
    // She can reach nothing, so there is nowhere to send her. Falling through
    // beats a redirect loop or an invented route.
    mockUseAuth.mockReturnValue({
      user: { role_slug: "payroll" },
      isLoading: false,
      isAuthenticated: true,
      track: "office_management",
      consoleAccess: [],
      limitedToAreas: [],
    })
    mockPreset.mockReturnValue(navWith([]) as never)
    expect(renderAt("/").queryByTestId("home")).not.toBeNull()
    mockPreset.mockReturnValue(null)
  })

  it("still sends a driver to /driver even if limited", () => {
    // A configuration nobody has made, asserted so the specialized entries
    // keep priority rather than being silently reordered by this change.
    mockUseAuth.mockReturnValue({
      user: { role_slug: "driver" },
      isLoading: false,
      isAuthenticated: true,
      track: "office_management",
      consoleAccess: [],
      limitedToAreas: ["payroll"],
    })
    mockPreset.mockReturnValue(
      navWith([{ label: "Payroll", href: "/payroll", area: "payroll" }]) as never,
    )
    const r = renderAt("/")
    expect(r.queryByTestId("driver")).not.toBeNull()
    expect(r.queryByTestId("payroll")).toBeNull()
    mockPreset.mockReturnValue(null)
  })
})
