/**
 * Phase R-1.5 — Widget operational-handler safety specs.
 *
 * One assertion per registered R-1 widget: when `_editMode={true}`,
 * the widget's primary operational handler does NOT fire on click.
 *
 * The architectural gate is SelectionOverlay's capture-phase click
 * suppression (validated separately in `runtime-host/SelectionOverlay.test.tsx`).
 * These specs verify the defense-in-depth layer — the widget itself
 * checks `_editMode` and short-circuits its navigate / mutation
 * handlers regardless of the capture-phase gate.
 *
 * Six widgets in scope:
 *   1. TodayWidget (Brief variant, onNavigate)
 *   2. OperatorProfileWidget (Glance variant, onSummon)
 *   3. RecentActivityWidget (Brief variant, onRowClick / onViewAll)
 *   4. AnomaliesWidget (Brief variant, onInvestigate)
 *   5. VaultScheduleWidget (Glance variant, onClick)
 *   6. LineStatusWidget (Brief variant, onClick row CTA)
 */
import { render, fireEvent, cleanup } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"


// Shared mock for navigate — re-imported per test via vi.mock factory.
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


// Shared mock for useWidgetData — each test sets per-widget data.
let mockData: unknown = null
vi.mock("@/components/widgets/useWidgetData", () => ({
  useWidgetData: () => ({
    data: mockData,
    isLoading: false,
    error: null,
    refresh: vi.fn(),
    lastUpdated: new Date(),
  }),
}))


// Mock apiClient.post for AnomaliesWidget's acknowledge action.
const mockApiPost = vi.fn((..._args: unknown[]) => Promise.resolve({ data: {} }))
vi.mock("@/lib/api-client", () => ({
  default: {
    post: (url: string, body?: unknown) => mockApiPost(url, body),
  },
}))


// Mock auth + spaces contexts for OperatorProfileWidget.
vi.mock("@/contexts/auth-context", () => ({
  useAuth: () => ({
    user: {
      id: "u-1",
      first_name: "Test",
      last_name: "User",
      email: "test@example.com",
      role_slug: "admin",
      role_id: "r-admin",
      is_active: true,
      module_count: 0,
      permission_count: 0,
      extension_count: 0,
    },
    company: null,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
  }),
}))
vi.mock("@/contexts/space-context", () => ({
  useSpacesOptional: () => null,
}))


beforeEach(() => {
  mockNavigate.mockClear()
  mockApiPost.mockClear()
  mockData = null
})


afterEach(() => {
  cleanup()
})


describe("R-1.5 widget operational-handler safety", () => {
  it("TodayWidget Brief — onNavigate no-ops when _editMode=true", async () => {
    mockData = {
      date: "2026-06-06",
      total_count: 3,
      categories: [
        {
          key: "deliveries",
          label: "Deliveries",
          count: 3,
          navigation_target: "/dispatch",
        },
      ],
      primary_navigation_target: "/dispatch",
    }
    const { TodayWidget } = await import(
      "@/components/widgets/foundation/TodayWidget"
    )
    render(
      <MemoryRouter>
        <TodayWidget _editMode={true} variant_id="brief" />
      </MemoryRouter>,
    )
    // Click any per-row CTA — TodayBriefCard renders category rows
    // with click-through; the dispatcher Open in Vault Schedule
    // button at the bottom is also gated.
    const buttons = document.querySelectorAll("button")
    buttons.forEach((b) => fireEvent.click(b))
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it("OperatorProfileWidget Glance — onSummon no-ops when _editMode=true", async () => {
    const { OperatorProfileWidget } = await import(
      "@/components/widgets/foundation/OperatorProfileWidget"
    )
    render(
      <MemoryRouter>
        <OperatorProfileWidget _editMode={true} variant_id="glance" />
      </MemoryRouter>,
    )
    const buttons = document.querySelectorAll("button")
    buttons.forEach((b) => fireEvent.click(b))
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it("RecentActivityWidget Brief — onRowClick no-ops when _editMode=true", async () => {
    mockData = {
      activities: [
        {
          id: "a-1",
          activity_type: "manual",
          actor_name: "Tester",
          activity_title: "logged a note",
          body: "Hopkins FH",
          company_id: "co-1",
          company_name: "Hopkins",
          created_at: new Date().toISOString(),
        },
      ],
      total: 1,
    }
    const { RecentActivityWidget } = await import(
      "@/components/widgets/foundation/RecentActivityWidget"
    )
    render(
      <MemoryRouter>
        <RecentActivityWidget _editMode={true} variant_id="brief" />
      </MemoryRouter>,
    )
    const buttons = document.querySelectorAll("button")
    buttons.forEach((b) => fireEvent.click(b))
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it("AnomaliesWidget Brief — onInvestigate + onAcknowledge no-op when _editMode=true", async () => {
    mockData = {
      total_count: 1,
      anomalies: [
        {
          id: "a-1",
          severity: "warning",
          anomaly_type: "test_anomaly",
          description: "Test description",
          amount: null,
          period_start: null,
          period_end: null,
          related_entity_type: null,
          related_entity_id: null,
          created_at: new Date().toISOString(),
          source: { agent_job_id: "j-1", job_type: "test" },
        },
      ],
      severity_counts: { critical: 0, warning: 1, info: 0 },
    }
    const { AnomaliesWidget } = await import(
      "@/components/widgets/foundation/AnomaliesWidget"
    )
    render(
      <MemoryRouter>
        <AnomaliesWidget _editMode={true} variant_id="brief" />
      </MemoryRouter>,
    )
    const buttons = document.querySelectorAll("button")
    buttons.forEach((b) => fireEvent.click(b))
    expect(mockNavigate).not.toHaveBeenCalled()
    expect(mockApiPost).not.toHaveBeenCalled()
  })

  it("VaultScheduleWidget Glance — onClick no-ops when _editMode=true", async () => {
    mockData = {
      target_date: "2026-06-06",
      operating_mode: "production",
      is_vault_enabled: true,
      production: {
        total_count: 5,
        assigned_count: 3,
        unassigned_count: 2,
        driver_count: 2,
        deliveries: [],
      },
      purchase: null,
      primary_navigation_target: "/dispatch",
    }
    const { VaultScheduleWidget } = await import(
      "@/components/widgets/manufacturing/VaultScheduleWidget"
    )
    render(
      <MemoryRouter>
        <VaultScheduleWidget _editMode={true} variant_id="glance" />
      </MemoryRouter>,
    )
    const buttons = document.querySelectorAll("button")
    buttons.forEach((b) => fireEvent.click(b))
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it("LineStatusWidget Brief — onClick no-ops when _editMode=true", async () => {
    mockData = {
      total_active_lines: 1,
      lines: [
        {
          line_key: "vault",
          display_name: "Vault",
          status: "on_track",
          headline: "All on track",
          operating_mode: "production",
          metrics: {},
          navigation_target: "/dispatch",
        },
      ],
    }
    const { LineStatusWidget } = await import(
      "@/components/widgets/manufacturing/LineStatusWidget"
    )
    render(
      <MemoryRouter>
        <LineStatusWidget _editMode={true} variant_id="brief" />
      </MemoryRouter>,
    )
    const buttons = document.querySelectorAll("button")
    buttons.forEach((b) => fireEvent.click(b))
    expect(mockNavigate).not.toHaveBeenCalled()
  })
})


describe("R-1.5 control: handlers DO fire when _editMode=false", () => {
  // Sanity check that the test plumbing is wired correctly — without
  // _editMode, navigate IS called. If this fails, the gate test above
  // would be passing for the wrong reason.
  it("TodayWidget Brief — onNavigate fires when _editMode is omitted", async () => {
    mockData = {
      date: "2026-06-06",
      total_count: 3,
      categories: [
        {
          key: "deliveries",
          label: "Deliveries",
          count: 3,
          navigation_target: "/dispatch",
        },
      ],
      primary_navigation_target: "/dispatch",
    }
    const { TodayWidget } = await import(
      "@/components/widgets/foundation/TodayWidget"
    )
    render(
      <MemoryRouter>
        <TodayWidget variant_id="brief" />
      </MemoryRouter>,
    )
    const buttons = document.querySelectorAll("button")
    buttons.forEach((b) => fireEvent.click(b))
    expect(mockNavigate).toHaveBeenCalled()
  })
})
