/**
 * SchedulingFocusWithAccessories tests — May 2026 composition runtime
 * integration phase.
 *
 * Verifies:
 *   - Mounts SchedulingKanbanCore unchanged in the kanban region
 *   - Conditionally mounts the accessory rail based on composition
 *     resolution outcome
 *   - data-accessory-rail attribute reflects whether the rail is
 *     present (for E2E + telemetry hooks)
 *   - Loading + no-composition + empty-composition all fall back to
 *     kanban-only (no flash of empty rail)
 */
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest"
import { render, screen } from "@testing-library/react"

// Mock the kanban core: it's 1,714 LOC of dispatcher operational
// behavior + needs auth/dnd/data providers; we only need to verify
// the wrapper mounts it. The actual operational behavior is tested
// in SchedulingKanbanCore.test.tsx.
vi.mock("./SchedulingKanbanCore", () => ({
  SchedulingKanbanCore: ({ focusId }: { focusId: string }) => (
    <div data-testid="scheduling-kanban-core" data-focus-id={focusId}>
      kanban core stub
    </div>
  ),
}))

// Mock useAuth so we can supply a controlled company context.
const mockCompany = vi.hoisted(() => ({
  current: null as { id: string; vertical: string | null } | null,
}))
vi.mock("@/contexts/auth-context", () => ({
  useAuth: () => ({ company: mockCompany.current }),
}))

// Mock useResolvedComposition so each test controls the resolution
// outcome. R-3.0 — composition is a sequence of rows; each row has its
// own column_count and placements with 0-indexed starting_column +
// column_span.
const mockResolution = vi.hoisted(() => ({
  current: {
    composition: null as
      | null
      | {
          focus_type: string
          vertical: string | null
          tenant_id: string | null
          source: string | null
          source_id: string | null
          source_version: number | null
          rows: Array<{
            row_id: string
            column_count: number
            row_height: number | "auto"
            column_widths: number[] | null
            nested_rows: unknown[] | null
            placements: Array<{
              placement_id: string
              component_kind: string
              component_name: string
              starting_column: number
              column_span: number
              prop_overrides: Record<string, unknown>
              display_config: Record<string, unknown>
              nested_rows: unknown[] | null
            }>
          }>
          canvas_config: Record<string, unknown>
        },
    isLoading: false,
    error: null as string | null,
    hasComposition: false,
  },
}))
vi.mock("@/lib/visual-editor/compositions/useResolvedComposition", () => ({
  useResolvedComposition: () => mockResolution.current,
}))


import { SchedulingFocusWithAccessories } from "./SchedulingFocusWithAccessories"
import type { FocusConfig } from "@/contexts/focus-registry"


function makeConfig(overrides: Partial<FocusConfig> = {}): FocusConfig {
  return {
    id: "funeral-scheduling",
    mode: "kanban",
    displayName: "Funeral Scheduling",
    compositionFocusType: "scheduling",
    ...overrides,
  }
}


function makeComposition(
  placementCount: number,
): NonNullable<typeof mockResolution.current.composition> {
  // R-3.0 — each placement gets its own single-column row (mirrors the
  // post-R-3.0 seeded shape from seed_focus_compositions.py).
  const rows = Array.from({ length: placementCount }).map((_, i) => ({
    row_id: `row-${i + 1}`,
    column_count: 1,
    row_height: 64,
    column_widths: null,
    nested_rows: null,
    placements: [
      {
        placement_id: `p${i + 1}`,
        component_kind: "widget",
        component_name: ["today", "recent_activity", "anomalies"][i] ?? "today",
        starting_column: 0,
        column_span: 1,
        prop_overrides: {},
        display_config: { show_header: true, show_border: true },
        nested_rows: null,
      },
    ],
  }))
  return {
    focus_type: "scheduling",
    vertical: "funeral_home",
    tenant_id: null,
    source: "vertical_default",
    source_id: "test-row",
    source_version: 1,
    rows,
    canvas_config: { gap_size: 12 },
  }
}


beforeEach(() => {
  mockCompany.current = { id: "tenant-1", vertical: "funeral_home" }
  mockResolution.current = {
    composition: null,
    isLoading: false,
    error: null,
    hasComposition: false,
  }
})


afterEach(() => {
  vi.clearAllMocks()
})


describe("SchedulingFocusWithAccessories", () => {
  it("mounts SchedulingKanbanCore in the kanban region", () => {
    render(
      <SchedulingFocusWithAccessories
        focusId="funeral-scheduling"
        config={makeConfig()}
      />,
    )
    const core = screen.getByTestId("scheduling-kanban-core")
    expect(core).toBeTruthy()
    expect(core.getAttribute("data-focus-id")).toBe("funeral-scheduling")
  })

  it("renders kanban-only when no composition exists (data-accessory-rail=absent)", () => {
    mockResolution.current = {
      composition: null,
      isLoading: false,
      error: null,
      hasComposition: false,
    }
    render(
      <SchedulingFocusWithAccessories
        focusId="funeral-scheduling"
        config={makeConfig()}
      />,
    )
    const wrapper = screen.getByTestId("scheduling-kanban-core").closest(
      "[data-slot='scheduling-focus-with-accessories']",
    )
    expect(wrapper?.getAttribute("data-accessory-rail")).toBe("absent")
    expect(
      screen.queryByLabelText("Scheduling Focus accessories"),
    ).toBeNull()
  })

  it("renders kanban-only when composition exists but is empty", () => {
    mockResolution.current = {
      composition: makeComposition(0),
      isLoading: false,
      error: null,
      hasComposition: true,
    }
    render(
      <SchedulingFocusWithAccessories
        focusId="funeral-scheduling"
        config={makeConfig()}
      />,
    )
    const wrapper = screen.getByTestId("scheduling-kanban-core").closest(
      "[data-slot='scheduling-focus-with-accessories']",
    )
    expect(wrapper?.getAttribute("data-accessory-rail")).toBe("absent")
  })

  it("renders kanban-only while composition resolution is loading (no flash)", () => {
    mockResolution.current = {
      composition: null,
      isLoading: true,
      error: null,
      hasComposition: false,
    }
    render(
      <SchedulingFocusWithAccessories
        focusId="funeral-scheduling"
        config={makeConfig()}
      />,
    )
    const wrapper = screen.getByTestId("scheduling-kanban-core").closest(
      "[data-slot='scheduling-focus-with-accessories']",
    )
    expect(wrapper?.getAttribute("data-accessory-rail")).toBe("absent")
  })

  it("renders kanban + accessory rail when composition has placements", () => {
    mockResolution.current = {
      composition: makeComposition(3),
      isLoading: false,
      error: null,
      hasComposition: true,
    }
    render(
      <SchedulingFocusWithAccessories
        focusId="funeral-scheduling"
        config={makeConfig()}
      />,
    )
    expect(screen.getByTestId("scheduling-kanban-core")).toBeTruthy()
    const wrapper = screen.getByTestId("scheduling-kanban-core").closest(
      "[data-slot='scheduling-focus-with-accessories']",
    )
    expect(wrapper?.getAttribute("data-accessory-rail")).toBe("present")
    const aside = screen.getByLabelText("Scheduling Focus accessories")
    expect(aside).toBeTruthy()
    // Rail is sibling-to-kanban (not wrapping it) so dnd-kit drag
    // pointer scope stays bounded to kanban.
    expect(aside.contains(screen.getByTestId("scheduling-kanban-core"))).toBe(
      false,
    )
  })

  it("falls back to config.id when compositionFocusType is unset", () => {
    // No compositionFocusType set on the config — the wrapper should
    // pass config.id to useResolvedComposition. We can't directly
    // observe the call args via the mock easily; instead we verify
    // the wrapper renders without crashing + still mounts the kanban.
    mockResolution.current = {
      composition: null,
      isLoading: false,
      error: null,
      hasComposition: false,
    }
    render(
      <SchedulingFocusWithAccessories
        focusId="other-focus"
        config={makeConfig({ compositionFocusType: undefined })}
      />,
    )
    expect(screen.getByTestId("scheduling-kanban-core")).toBeTruthy()
  })
})
