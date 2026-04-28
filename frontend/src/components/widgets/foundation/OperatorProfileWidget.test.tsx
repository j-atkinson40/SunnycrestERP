/**
 * OperatorProfileWidget — vitest unit tests.
 *
 * Covers Phase W-3a contract:
 *   • Glance variant (spaces_pin) + Brief variant (default)
 *   • Auth context shapes the rendered identity
 *   • Active space surfaces in Brief variant when present
 *   • Click navigation to /settings/profile
 *   • Defensive null behavior when unauthenticated
 *   • Pattern 1 chrome (frosted-glass + bezel-grip) on Glance
 *   • Singular vs plural permission/module/extension labels
 */

import { render, fireEvent } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { User } from "@/types/auth"


// ── Mock auth + spaces contexts ─────────────────────────────────────


let mockUser: User | null = null
let mockActiveSpaceName: string | null = null


vi.mock("@/contexts/auth-context", () => ({
  useAuth: () => ({
    user: mockUser,
    isAuthenticated: !!mockUser,
    permissions: new Set(mockUser?.permissions ?? []),
    enabledModules: new Set(mockUser?.enabled_modules ?? []),
    functionalAreas: new Set(mockUser?.functional_areas ?? []),
    track: mockUser?.track ?? "office_management",
    consoleAccess: new Set(mockUser?.console_access ?? []),
    isAdmin: mockUser?.role_slug === "admin",
  }),
}))


vi.mock("@/contexts/space-context", () => ({
  useSpacesOptional: () => ({
    activeSpace: mockActiveSpaceName
      ? { name: mockActiveSpaceName }
      : null,
  }),
}))


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


import { OperatorProfileWidget } from "./OperatorProfileWidget"


function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: "u-1",
    email: "james@sunnycrest.com",
    first_name: "James",
    last_name: "Atkinson",
    role_id: "r-1",
    role_name: "Admin",
    role_slug: "admin",
    permissions: ["delivery.view", "delivery.assign", "invoice.approve"],
    enabled_modules: ["dispatch", "accounting"],
    enabled_extensions: ["urn_sales"],
    functional_areas: [],
    is_active: true,
    company_id: "co-sunnycrest",
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  }
}


function renderWidget(props: Parameters<typeof OperatorProfileWidget>[0]) {
  return render(
    <MemoryRouter>
      <OperatorProfileWidget {...props} />
    </MemoryRouter>,
  )
}


beforeEach(() => {
  mockUser = null
  mockActiveSpaceName = null
  mockNavigate.mockClear()
})


afterEach(() => {
  vi.clearAllMocks()
})


// ── Glance variant ──────────────────────────────────────────────────


describe("OperatorProfileWidget — Glance variant", () => {
  it("renders Glance when surface=spaces_pin", () => {
    mockUser = makeUser()
    renderWidget({ surface: "spaces_pin" })

    expect(
      document.querySelector(
        '[data-slot="operator-profile-widget"][data-variant="glance"]',
      ),
    ).toBeInTheDocument()
    // Pattern 1 chrome — bezel grip column
    expect(
      document.querySelector(
        '[data-slot="operator-profile-widget-bezel-grip"]',
      ),
    ).toBeInTheDocument()
  })

  it("Glance shows initials avatar + full name + role", () => {
    mockUser = makeUser({ first_name: "James", last_name: "Atkinson" })
    renderWidget({ surface: "spaces_pin" })

    const avatar = document.querySelector(
      '[data-slot="operator-profile-avatar"]',
    )
    expect(avatar?.getAttribute("data-initials")).toBe("JA")
    expect(avatar?.textContent).toBe("JA")

    const name = document.querySelector(
      '[data-slot="operator-profile-widget-name"]',
    )
    expect(name?.textContent).toBe("James Atkinson")

    const role = document.querySelector(
      '[data-slot="operator-profile-widget-role"]',
    )
    expect(role?.textContent).toBe("Admin")
  })

  it("Glance click navigates to /settings/profile", () => {
    mockUser = makeUser()
    renderWidget({ surface: "spaces_pin" })

    const tablet = document.querySelector(
      '[data-slot="operator-profile-widget"][data-variant="glance"]',
    ) as HTMLElement
    fireEvent.click(tablet)
    expect(mockNavigate).toHaveBeenCalledWith("/settings/profile")
  })

  it("Glance carries role=button + tabIndex=0 + aria-label", () => {
    mockUser = makeUser({ first_name: "Mary", last_name: "Lopez" })
    renderWidget({ surface: "spaces_pin" })

    const tablet = document.querySelector(
      '[data-slot="operator-profile-widget"][data-variant="glance"]',
    ) as HTMLElement
    expect(tablet.getAttribute("role")).toBe("button")
    expect(tablet.getAttribute("tabIndex")).toBe("0")
    expect(tablet.getAttribute("aria-label")).toContain("Mary Lopez")
    expect(tablet.getAttribute("aria-label")).toContain("Admin")
  })

  it("Glance falls back to '??' when both names empty", () => {
    mockUser = makeUser({ first_name: "", last_name: "" })
    renderWidget({ surface: "spaces_pin" })

    const avatar = document.querySelector(
      '[data-slot="operator-profile-avatar"]',
    )
    expect(avatar?.getAttribute("data-initials")).toBe("??")
  })
})


// ── Brief variant ──────────────────────────────────────────────────


describe("OperatorProfileWidget — Brief variant", () => {
  it("renders Brief by default (no surface, no variant_id)", () => {
    mockUser = makeUser()
    renderWidget({})

    expect(
      document.querySelector(
        '[data-slot="operator-profile-widget"][data-variant="brief"]',
      ),
    ).toBeInTheDocument()
  })

  it("Brief shows full identity (name + email + avatar)", () => {
    mockUser = makeUser({
      first_name: "James",
      last_name: "Atkinson",
      email: "james@sunnycrest.com",
    })
    renderWidget({})

    expect(
      document.querySelector(
        '[data-slot="operator-profile-widget-name"]',
      )?.textContent,
    ).toBe("James Atkinson")

    expect(
      document.querySelector(
        '[data-slot="operator-profile-widget-email"]',
      )?.textContent,
    ).toBe("james@sunnycrest.com")
  })

  it("Brief shows active space name when available", () => {
    mockUser = makeUser()
    mockActiveSpaceName = "Production"
    renderWidget({})

    const spaceRow = document.querySelector(
      '[data-slot="operator-profile-widget-space"]',
    )
    expect(spaceRow?.textContent).toContain("Production")
  })

  it("Brief shows '—' for active space when none", () => {
    mockUser = makeUser()
    mockActiveSpaceName = null
    renderWidget({})

    const spaceRow = document.querySelector(
      '[data-slot="operator-profile-widget-space"]',
    )
    expect(spaceRow?.textContent).toContain("—")
  })

  it("Brief access summary uses singular for count=1", () => {
    mockUser = makeUser({
      permissions: ["delivery.view"],
      enabled_modules: ["dispatch"],
      enabled_extensions: [],
    })
    renderWidget({})

    const accessRow = document.querySelector(
      '[data-slot="operator-profile-widget-access"]',
    )
    expect(accessRow?.textContent).toContain("1 permission")
    expect(accessRow?.textContent).not.toContain("permissions")
    expect(accessRow?.textContent).toContain("1 module")
    expect(accessRow?.textContent).not.toContain("modules")
  })

  it("Brief access summary uses plural for count > 1 and includes extensions", () => {
    mockUser = makeUser({
      permissions: ["a", "b", "c"],
      enabled_modules: ["m1", "m2"],
      enabled_extensions: ["urn_sales"],
    })
    renderWidget({})

    const accessRow = document.querySelector(
      '[data-slot="operator-profile-widget-access"]',
    )
    expect(accessRow?.textContent).toContain("3 permissions")
    expect(accessRow?.textContent).toContain("2 modules")
    expect(accessRow?.textContent).toContain("1 extension")
  })

  it("Brief access summary omits extensions when none enabled", () => {
    mockUser = makeUser({
      permissions: ["a"],
      enabled_modules: ["m1"],
      enabled_extensions: [],
    })
    renderWidget({})

    const accessRow = document.querySelector(
      '[data-slot="operator-profile-widget-access"]',
    )
    expect(accessRow?.textContent).not.toContain("extension")
  })

  it("Brief CTA navigates to /settings/profile", () => {
    mockUser = makeUser()
    renderWidget({})

    const cta = document.querySelector(
      '[data-slot="operator-profile-widget-cta"]',
    ) as HTMLElement
    fireEvent.click(cta)
    expect(mockNavigate).toHaveBeenCalledWith("/settings/profile")
  })
})


// ── Defensive: unauthenticated state ────────────────────────────────


describe("OperatorProfileWidget — defensive unauth", () => {
  it("Glance returns null when no user", () => {
    mockUser = null
    const { container } = renderWidget({ surface: "spaces_pin" })
    expect(container.firstChild).toBeNull()
  })

  it("Brief returns null when no user", () => {
    mockUser = null
    const { container } = renderWidget({})
    expect(container.firstChild).toBeNull()
  })
})
