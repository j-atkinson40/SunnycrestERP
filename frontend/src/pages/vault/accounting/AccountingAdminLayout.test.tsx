/**
 * The Accounting area's gate — CR-3.
 *
 * ⚠️ THE COMPLETENESS REVIEW WAS ADMIN-ONLY BY INHERITANCE, NOT BY DECISION.
 * CR-2 A-4 mounted its tab inside V-1e's admin-only accounting subtree
 * (`ba424db6`, April 2026) and picked up that subtree's guard. The comment beside
 * the guard justified it as parity with "the gate the backend uses on every
 * endpoint under /api/v1/vault/accounting/*" — true of the six configuration
 * tabs, and false of the completeness router, which mounts at
 * /api/v1/completeness and gates on `get_current_user`. So the accountant the
 * whole arc was scoped around could not open the surface built for them, and
 * nothing had decided that.
 *
 * The correction is a DELIBERATE gate, not a removed one: accounting
 * RESPONSIBILITY reaches the area, `admin` reaches the configuration.
 *
 * ⚠️ AND THE TAB BAR HAS TO AGREE WITH THE ROUTER. Rendering six tabs that
 * bounce the clicker to /unauthorized is built-and-unreachable wearing a
 * navigation costume — worse than hiding them, because it invites the click.
 * That agreement is what these tests hold; the two are separate code paths and
 * nothing else makes them move together.
 */
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"

import AccountingAdminLayout, {
  ACCOUNTING_ROLES,
  AccountingLanding,
} from "./AccountingAdminLayout"
import { ProtectedRoute } from "@/components/protected-route"

const mockUseAuth = vi.fn()
vi.mock("@/contexts/auth-context", () => ({
  useAuth: () => mockUseAuth(),
}))
vi.mock("@/contexts/extension-context", () => ({
  useExtensions: () => ({ isExtensionEnabled: () => true }),
}))

afterEach(cleanup)

function asRole(roleSlug: string | null) {
  mockUseAuth.mockReturnValue({
    user: roleSlug ? { role_slug: roleSlug } : null,
    isLoading: false,
    isAuthenticated: true,
    isAdmin: roleSlug === "admin",
    hasPermission: () => false,
    hasModule: () => true,
    consoleAccess: new Set<string>(),
    track: null,
  })
}

describe("the tab bar shows only what the clicker can open", () => {
  it("gives an admin every tab", () => {
    asRole("admin")
    render(
      <MemoryRouter>
        <AccountingAdminLayout />
      </MemoryRouter>,
    )
    for (const label of [
      "Periods & Locks",
      "Completeness",
      "Agent Schedules",
      "GL Classification",
      "Tax Config",
      "Statement Templates",
      "COA Templates",
    ]) {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument()
    }
  })

  it("gives an accountant Completeness and nothing that would bounce them", () => {
    asRole("accountant")
    render(
      <MemoryRouter>
        <AccountingAdminLayout />
      </MemoryRouter>,
    )
    expect(
      screen.getByRole("link", { name: "Completeness" }),
    ).toBeInTheDocument()
    // The six configuration tabs administer the tenant's accounting and stay
    // admin-only. Showing them here would invite a click into /unauthorized.
    expect(screen.getAllByRole("link")).toHaveLength(1)
  })
})

describe("the landing route knows who is asking", () => {
  function renderLanding() {
    return render(
      <MemoryRouter initialEntries={["/vault/accounting"]}>
        <Routes>
          <Route path="/vault/accounting">
            <Route index element={<AccountingLanding />} />
            <Route path="periods" element={<div data-testid="periods" />} />
            <Route
              path="completeness"
              element={<div data-testid="completeness" />}
            />
          </Route>
        </Routes>
      </MemoryRouter>,
    )
  }

  it("lands an admin on Periods", () => {
    asRole("admin")
    renderLanding()
    expect(screen.getByTestId("periods")).toBeInTheDocument()
  })

  it("lands an accountant on Completeness, not on the tab they cannot open", () => {
    // ⚠️ THE FIXED REDIRECT WOULD HAVE GRANTED ACCESS AND THEN BOUNCED THEM.
    // `/vault/accounting` redirected to `periods` unconditionally; opening the
    // area to the accountant without this makes their first click a 403.
    asRole("accountant")
    renderLanding()
    expect(screen.getByTestId("completeness")).toBeInTheDocument()
    expect(screen.queryByTestId("periods")).not.toBeInTheDocument()
  })
})

describe("the route gate is a list, not an absence of one", () => {
  function renderGuarded() {
    return render(
      <MemoryRouter initialEntries={["/guarded"]}>
        <Routes>
          <Route
            element={<ProtectedRoute anyRole={[...ACCOUNTING_ROLES]} />}
          >
            <Route path="/guarded" element={<div data-testid="in" />} />
          </Route>
          <Route path="/unauthorized" element={<div data-testid="out" />} />
        </Routes>
      </MemoryRouter>,
    )
  }

  it.each(["admin", "accountant"])("admits %s", (role) => {
    asRole(role)
    renderGuarded()
    expect(screen.getByTestId("in")).toBeInTheDocument()
  })

  it.each(["office", "production", "driver"])("refuses %s", (role) => {
    // The correction was a NARROWER gate, not a removed one. If this ever
    // admits an operational role, `anyRole` has stopped gating.
    asRole(role)
    renderGuarded()
    expect(screen.getByTestId("out")).toBeInTheDocument()
  })

  it("refuses a user whose role could not be resolved", () => {
    // The permissive reading — "we could not tell, so let them through" — is the
    // graceful path, and this is a gate.
    asRole(null)
    renderGuarded()
    expect(screen.getByTestId("out")).toBeInTheDocument()
  })
})
