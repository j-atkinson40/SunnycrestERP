/**
 * Which shell a tenant user gets — the split James ruled on 2026-11-17.
 *
 * ⚠️ ASSERTS ON WHAT IS ON SCREEN, not on which component was chosen. A test
 * that spied the chooser would pass while the shell rendered a sidebar anyway;
 * the claim is about the chrome, so the chrome is what is read.
 */
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

let limitedToAreas: string[] | null | undefined = null

vi.mock("@/contexts/auth-context", () => ({
  useAuth: () => ({
    user: { first_name: "Probe", last_name: "User", role_name: "payroll" },
    company: { name: "Sunnycrest Precast" },
    limitedToAreas,
    logout: vi.fn(),
    isAdmin: false,
    permissions: [],
    enabledModules: [],
    functionalAreas: [],
  }),
}))

/* The old shell pulls in a large subtree — sidebar, spaces, notifications,
   banners. Each is doubled by something that NAMES ITSELF, so a test that
   expects "the sidebar" fails loudly if the double stops being rendered rather
   than silently matching nothing. */
vi.mock("@/components/layout/sidebar", () => ({
  Sidebar: () => <div data-testid="the-sidebar" />,
}))
vi.mock("@/components/layout/mobile-tab-bar", () => ({
  MobileTabBar: () => <div data-testid="the-tab-bar" />,
}))
vi.mock("@/components/layout/ModeToggle", () => ({ ModeToggle: () => <div /> }))
vi.mock("@/components/layout/notification-dropdown", () => ({
  NotificationDropdown: () => <div data-testid="the-notifications" />,
}))
vi.mock("@/components/accounting-reminder-banner", () => ({
  AccountingReminderBanner: () => <div />,
}))
vi.mock("@/contexts/layout-context", () => ({ useLayout: () => ({ hideTabBar: false }) }))
vi.mock("@/contexts/focus-context", () => ({ useFocus: () => ({ isOpen: false }) }))

import { TenantShell } from "./tenant-shell"

function renderShell() {
  return render(
    <MemoryRouter>
      <TenantShell />
    </MemoryRouter>,
  )
}

describe("the shell split", () => {
  beforeEach(() => { limitedToAreas = null })

  it("an UNLIMITED user keeps the old shell, sidebar and all", () => {
    limitedToAreas = null
    renderShell()
    expect(screen.getByTestId("the-sidebar")).toBeTruthy()
    expect(screen.queryByTestId("limited-shell")).toBeNull()
  })

  it("an AREA-LIMITED user gets the new shell, with NO sidebar", () => {
    limitedToAreas = ["payroll"]
    renderShell()
    expect(screen.getByTestId("limited-shell")).toBeTruthy()
    expect(screen.queryByTestId("the-sidebar")).toBeNull()
    expect(screen.queryByTestId("the-tab-bar")).toBeNull()
    expect(screen.queryByTestId("the-notifications")).toBeNull()
  })

  it("⚠️ `[]` — limited to NOTHING — gets the NEW shell, not the old one", () => {
    // The row a truthiness check gets backwards. Ruling 3 reads "not NULL",
    // and an empty list is not null.
    limitedToAreas = []
    renderShell()
    expect(screen.getByTestId("limited-shell")).toBeTruthy()
    expect(screen.queryByTestId("the-sidebar")).toBeNull()
  })

  it("`undefined` keeps the old shell, so a half-loaded profile does not flip chrome", () => {
    limitedToAreas = undefined
    renderShell()
    expect(screen.getByTestId("the-sidebar")).toBeTruthy()
  })

  it("the new shell still offers a way out, and says whose session it is", () => {
    limitedToAreas = ["payroll"]
    renderShell()
    expect(screen.getByTestId("limited-shell-who").textContent).toContain("Probe")
    expect(screen.getByText("Sunnycrest Precast")).toBeTruthy()
    expect(screen.getByRole("button", { name: "Sign Out" })).toBeTruthy()
  })
})
