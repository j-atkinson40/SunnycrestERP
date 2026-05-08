/**
 * R-4.0 — RegisteredButton render-tier vitest coverage.
 *
 * Mocks at module scope:
 *   - `react-router-dom` — supplies useNavigate / useParams /
 *     useSearchParams without a router context.
 *   - `@/contexts/auth-context` — supplies useAuth().
 *   - `@/contexts/focus-context` — supplies useFocus() including
 *     open() spy.
 *   - `@/lib/visual-editor/registry` — supplies getByName lookup
 *     stub returning controlled fixture metadata.
 *   - `sonner` — supplies toast.success / toast.error spies.
 *   - `@/lib/api-client` — POST stub for backend-touching handlers.
 *
 * Tests cover the click→dispatch→success-behavior pipeline plus
 * the missing-registration error state and confirm-flow gating.
 */
import { render, screen, act } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"

// ─── Module mocks ─────────────────────────────────────────────────


const mockNavigate = vi.fn()
const mockSetSearchParams = vi.fn()

vi.mock("react-router-dom", async () => {
  return {
    useNavigate: () => mockNavigate,
    useParams: () => ({ id: "case-42" }),
    useSearchParams: () => [
      new URLSearchParams("?date=2026-05-08"),
      mockSetSearchParams,
    ],
  }
})


const mockOpenFocus = vi.fn()

vi.mock("@/contexts/focus-context", () => ({
  useFocus: () => ({
    currentFocus: null,
    isOpen: false,
    lastClosedFocus: null,
    open: mockOpenFocus,
    close: vi.fn(),
    dismissReturnPill: vi.fn(),
  }),
  // R-5.0.3 — RegisteredButton now consumes useFocusOptional for
  // null-safe admin-tree previews. Tests mock both — the optional
  // variant returns the same shape so handler logic exercises the
  // not-null path identically to pre-R-5.0.3.
  useFocusOptional: () => ({
    currentFocus: null,
    isOpen: false,
    lastClosedFocus: null,
    open: mockOpenFocus,
    close: vi.fn(),
    dismissReturnPill: vi.fn(),
  }),
}))


vi.mock("@/contexts/auth-context", () => ({
  useAuth: () => ({
    user: {
      id: "user-1",
      email: "u@example.com",
      role_slug: "admin",
    },
    company: {
      id: "tenant-1",
      slug: "testco",
      vertical: "manufacturing",
    },
  }),
  // R-5.0.4 — RegisteredButton consumes useAuthOptional for null-safe
  // admin-tree previews. Mock returns the same shape so handler logic
  // exercises the not-null path identically to pre-R-5.0.4. Returning
  // null here would simulate the admin-preview path; tests for that
  // branch are scoped to spec 28's structural verification.
  useAuthOptional: () => ({
    user: {
      id: "user-1",
      email: "u@example.com",
      role_slug: "admin",
    },
    company: {
      id: "tenant-1",
      slug: "testco",
      vertical: "manufacturing",
    },
  }),
}))


vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))


vi.mock("@/lib/api-client", () => ({
  __esModule: true,
  default: { post: vi.fn() },
}))


// Stub registry lookup. The default returns null (missing registration);
// per-test calls mockReturnValueOnce to inject controlled fixtures.
const mockGetByName = vi.fn()

vi.mock("@/lib/visual-editor/registry", () => ({
  getByName: (...args: unknown[]) => mockGetByName(...args),
}))


// Lazy-import the component AFTER mocks register so module-level
// imports resolve to mocks.
import { RegisteredButton } from "./RegisteredButton"
import { toast } from "sonner"


function fixtureEntry(overrides?: {
  contract?: Record<string, unknown>
  configurableProps?: Record<string, unknown>
  displayName?: string
}) {
  return {
    component: () => null,
    metadata: {
      type: "button",
      name: "test-button",
      displayName: overrides?.displayName ?? "Test Button",
      description: "fixture",
      category: "test",
      verticals: ["manufacturing"],
      userParadigms: [],
      consumedTokens: [],
      configurableProps: overrides?.configurableProps ?? {
        label: { default: "Default Label" },
        variant: { default: "default" },
        size: { default: "default" },
      },
      schemaVersion: 1,
      componentVersion: 1,
      extensions: {
        r4: overrides?.contract ?? {
          actionType: "navigate",
          actionConfig: { route: "/home" },
          parameterBindings: [],
          successBehavior: "stay",
        },
      },
    },
  }
}


beforeEach(() => {
  mockNavigate.mockReset()
  mockOpenFocus.mockReset()
  mockGetByName.mockReset()
  ;(toast.success as ReturnType<typeof vi.fn>).mockReset?.()
  ;(toast.error as ReturnType<typeof vi.fn>).mockReset?.()
})


describe("R-4.0 RegisteredButton", () => {
  it("renders <Button> with registered displayName as label fallback", () => {
    mockGetByName.mockReturnValue(
      fixtureEntry({
        configurableProps: {}, // no label default → falls back to displayName
      }),
    )
    render(<RegisteredButton componentName="test-button" />)
    expect(screen.getByText("Test Button")).toBeInTheDocument()
  })

  it("uses prop-override label over registration default", () => {
    mockGetByName.mockReturnValue(fixtureEntry())
    render(
      <RegisteredButton
        componentName="test-button"
        propOverrides={{ label: "Override Label" }}
      />,
    )
    expect(screen.getByText("Override Label")).toBeInTheDocument()
  })

  it("renders missing-registration error state when slug not found", () => {
    mockGetByName.mockReturnValue(undefined)
    render(<RegisteredButton componentName="ghost-button" />)
    expect(
      screen.getByTestId("r4-button-missing-registration"),
    ).toBeInTheDocument()
    expect(screen.getByText(/ghost-button/)).toBeInTheDocument()
  })

  it("renders missing-registration error state when entry has no R-4 contract", () => {
    mockGetByName.mockReturnValue({
      ...fixtureEntry(),
      metadata: {
        ...fixtureEntry().metadata,
        extensions: {}, // no r4
      },
    })
    render(<RegisteredButton componentName="orphan-button" />)
    expect(
      screen.getByTestId("r4-button-missing-registration"),
    ).toBeInTheDocument()
  })

  it("click without confirmBeforeFire dispatches the action immediately", async () => {
    mockGetByName.mockReturnValue(
      fixtureEntry({
        contract: {
          actionType: "navigate",
          actionConfig: { route: "/home" },
          parameterBindings: [],
          successBehavior: "stay",
        },
      }),
    )
    render(<RegisteredButton componentName="test-button" />)
    await act(async () => {
      screen.getByTestId("r4-button-test-button").click()
    })
    expect(mockNavigate).toHaveBeenCalledWith("/home")
  })

  it("click with confirmBeforeFire opens Dialog without dispatching", async () => {
    mockGetByName.mockReturnValue(
      fixtureEntry({
        contract: {
          actionType: "navigate",
          actionConfig: { route: "/home" },
          parameterBindings: [],
          confirmBeforeFire: true,
          confirmCopy: "Are you sure?",
          successBehavior: "stay",
        },
      }),
    )
    render(<RegisteredButton componentName="test-button" />)
    await act(async () => {
      screen.getByTestId("r4-button-test-button").click()
    })
    // Dialog opens (Cancel + Confirm visible).
    expect(screen.getByTestId("r4-button-confirm-cancel")).toBeInTheDocument()
    expect(screen.getByTestId("r4-button-confirm-fire")).toBeInTheDocument()
    // Action did NOT fire yet.
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it("Cancel in confirm dialog closes without firing", async () => {
    mockGetByName.mockReturnValue(
      fixtureEntry({
        contract: {
          actionType: "navigate",
          actionConfig: { route: "/home" },
          parameterBindings: [],
          confirmBeforeFire: true,
          successBehavior: "stay",
        },
      }),
    )
    render(<RegisteredButton componentName="test-button" />)
    await act(async () => {
      screen.getByTestId("r4-button-test-button").click()
    })
    await act(async () => {
      screen.getByTestId("r4-button-confirm-cancel").click()
    })
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it("successBehavior=toast fires toast.success with configured message", async () => {
    mockGetByName.mockReturnValue(
      fixtureEntry({
        contract: {
          actionType: "navigate",
          actionConfig: { route: "/home" },
          parameterBindings: [],
          successBehavior: "toast",
          successToastMessage: "Done.",
        },
      }),
    )
    render(<RegisteredButton componentName="test-button" />)
    await act(async () => {
      screen.getByTestId("r4-button-test-button").click()
    })
    expect(toast.success).toHaveBeenCalledWith("Done.")
  })

  it("successBehavior=navigate calls navigate with successNavigateRoute", async () => {
    mockGetByName.mockReturnValue(
      fixtureEntry({
        contract: {
          actionType: "navigate",
          actionConfig: { route: "/home" },
          parameterBindings: [],
          successBehavior: "navigate",
          successNavigateRoute: "/post-success",
        },
      }),
    )
    render(<RegisteredButton componentName="test-button" />)
    await act(async () => {
      screen.getByTestId("r4-button-test-button").click()
    })
    // Action's own navigate fired ("/home"), then success navigate ("/post-success").
    expect(mockNavigate).toHaveBeenCalledWith("/home")
    expect(mockNavigate).toHaveBeenCalledWith("/post-success")
  })

  it("dispatch error fires toast.error", async () => {
    mockGetByName.mockReturnValue(
      fixtureEntry({
        contract: {
          actionType: "navigate",
          actionConfig: {}, // missing route → handler returns error
          parameterBindings: [],
          successBehavior: "stay",
        },
      }),
    )
    render(<RegisteredButton componentName="test-button" />)
    await act(async () => {
      screen.getByTestId("r4-button-test-button").click()
    })
    expect(toast.error).toHaveBeenCalled()
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it("data-component-slug + data-action-type attributes set", () => {
    mockGetByName.mockReturnValue(
      fixtureEntry({
        contract: {
          actionType: "open_focus",
          actionConfig: { focusId: "x" },
          parameterBindings: [],
        },
      }),
    )
    render(<RegisteredButton componentName="test-button" />)
    const btn = screen.getByTestId("r4-button-test-button")
    expect(btn).toHaveAttribute("data-component-slug", "test-button")
    expect(btn).toHaveAttribute("data-action-type", "open_focus")
  })
})
