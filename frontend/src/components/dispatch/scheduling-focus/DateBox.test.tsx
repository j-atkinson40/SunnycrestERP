/**
 * DateBox — vitest unit tests. Phase B Session 4.4.3.
 *
 * Covers pure-function helpers (label formatting), the rendering
 * contract (data-slot, data-date, data-active, aria-pressed), the
 * onClick wiring, and tooltip content shape.
 *
 * Tooltip-open behavior: vitest+jsdom doesn't fire pointer events
 * the way real browsers do, and base-ui's Tooltip relies on hover
 * events. We assert the tooltip TRIGGER attributes + the data-slot
 * structure but don't manually open the popover. Visual verification
 * happens via Preview MCP.
 */

import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { TooltipProvider } from "@/components/ui/tooltip"

import {
  DateBox,
  formatFullLabel,
  formatMonthDayShort,
  formatWeekdayShort,
} from "./DateBox"


// Mock dispatch-service so the useDaySummary hook doesn't fire real
// network calls during component tests.
vi.mock("@/services/dispatch-service", () => ({
  fetchDaySummary: vi.fn(),
}))

// Import the mock so individual tests can program return values.
import { fetchDaySummary } from "@/services/dispatch-service"


function Harness({ children }: { children: React.ReactNode }) {
  return <TooltipProvider delay={0}>{children}</TooltipProvider>
}


// ── Pure function tests ─────────────────────────────────────────────


describe("DateBox label formatters", () => {
  // These tests are timezone-deterministic because the parser
  // constructs Date objects from explicit y/m/d local components.
  // The output strings depend on the runtime locale's
  // Intl.DateTimeFormat — vitest runs with system locale (en-US in
  // the CI environment), so the assertions match en-US conventions.

  it("formatWeekdayShort returns 3-letter abbreviation", () => {
    // 2026-04-25 is a Saturday.
    expect(formatWeekdayShort("2026-04-25")).toBe("Sat")
  })

  it("formatMonthDayShort returns abbreviated month + numeric day", () => {
    expect(formatMonthDayShort("2026-04-25")).toBe("Apr 25")
  })

  it("formatMonthDayShort handles single-digit days", () => {
    expect(formatMonthDayShort("2026-04-05")).toBe("Apr 5")
  })

  it("formatFullLabel returns weekday + month + day", () => {
    expect(formatFullLabel("2026-04-25")).toBe("Saturday, April 25")
  })

  it("formatters return empty string on malformed input", () => {
    expect(formatWeekdayShort("not-a-date")).toBe("")
    expect(formatMonthDayShort("")).toBe("")
  })
})


// ── Rendering contract ──────────────────────────────────────────────


describe("DateBox rendering", () => {
  beforeEach(() => {
    vi.mocked(fetchDaySummary).mockResolvedValue({
      date: "2026-04-25",
      total_deliveries: 0,
      unassigned_count: 0,
      finalize_status: "draft",
      finalized_at: null,
    })
  })

  afterEach(async () => {
    vi.clearAllMocks()
    const { _resetDaySummaryCache } = await import("@/hooks/useDaySummary")
    _resetDaySummaryCache()
  })

  it("renders weekday + month-day labels", () => {
    render(
      <Harness>
        <DateBox date="2026-04-25" active={false} onClick={() => {}} />
      </Harness>,
    )
    // Saturday → "Sat"
    expect(screen.getByText("Sat")).toBeInTheDocument()
    expect(screen.getByText("Apr 25")).toBeInTheDocument()
  })

  it("carries data-slot, data-date, data-active attributes", () => {
    const { container } = render(
      <Harness>
        <DateBox date="2026-04-25" active={false} onClick={() => {}} />
      </Harness>,
    )
    const box = container.querySelector(
      '[data-slot="scheduling-focus-date-box"]',
    ) as HTMLElement
    expect(box).toBeInTheDocument()
    expect(box.getAttribute("data-date")).toBe("2026-04-25")
    expect(box.getAttribute("data-active")).toBe("false")
    expect(box.getAttribute("aria-pressed")).toBe("false")
  })

  it("flips data-active + aria-pressed when active=true", () => {
    const { container } = render(
      <Harness>
        <DateBox date="2026-04-25" active={true} onClick={() => {}} />
      </Harness>,
    )
    const box = container.querySelector(
      '[data-slot="scheduling-focus-date-box"]',
    ) as HTMLElement
    expect(box.getAttribute("data-active")).toBe("true")
    expect(box.getAttribute("aria-pressed")).toBe("true")
    // Active-state visual chrome includes brass border (jewelry on).
    expect(box.className).toMatch(/border-brass/)
  })

  it("calls onClick when the box is clicked", async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(
      <Harness>
        <DateBox date="2026-04-25" active={false} onClick={onClick} />
      </Harness>,
    )
    const box = screen.getByRole("button")
    await user.click(box)
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it("uses the ariaLabel override when provided", () => {
    render(
      <Harness>
        <DateBox
          date="2026-04-25"
          active={false}
          onClick={() => {}}
          ariaLabel="Peek Saturday, April 25"
        />
      </Harness>,
    )
    const box = screen.getByRole("button", { name: "Peek Saturday, April 25" })
    expect(box).toBeInTheDocument()
  })

  it("falls back to formatted full label when no ariaLabel given", () => {
    render(
      <Harness>
        <DateBox date="2026-04-25" active={false} onClick={() => {}} />
      </Harness>,
    )
    const box = screen.getByRole("button", { name: "Saturday, April 25" })
    expect(box).toBeInTheDocument()
  })

  it("fires fetchDaySummary on mount with the box's date", async () => {
    render(
      <Harness>
        <DateBox date="2026-04-25" active={false} onClick={() => {}} />
      </Harness>,
    )
    await waitFor(() => {
      expect(fetchDaySummary).toHaveBeenCalledWith("2026-04-25")
    })
  })

  it("calibration: surface uses elevated + subtle-bordered + sharp corners (no SaaS chip drift)", () => {
    // Aesthetic-coherence regression. DESIGN_LANGUAGE Section 0
    // calibration: bg-surface-elevated (material lift) +
    // border-border-subtle (perimeter affordance) + rounded-sm
    // (4px sharp corners, NOT pillowy-full). If a future refactor
    // drifts to bg-muted (generic SaaS) or rounded-full (consumer
    // chip), this test fails.
    const { container } = render(
      <Harness>
        <DateBox date="2026-04-25" active={false} onClick={() => {}} />
      </Harness>,
    )
    const box = container.querySelector(
      '[data-slot="scheduling-focus-date-box"]',
    ) as HTMLElement
    const cls = box.className
    expect(cls).toMatch(/bg-surface-elevated/)
    expect(cls).toMatch(/border-border-subtle/)
    expect(cls).toMatch(/rounded-sm/)
    // Drift guards — these tokens MUST NOT appear at rest.
    expect(cls).not.toMatch(/bg-muted\b/)
    expect(cls).not.toMatch(/rounded-full/)
    expect(cls).not.toMatch(/shadow-md/)
  })

  it("active state composition uses brass border + brass-subtle wash (jewelry on)", () => {
    const { container } = render(
      <Harness>
        <DateBox date="2026-04-25" active={true} onClick={() => {}} />
      </Harness>,
    )
    const box = container.querySelector(
      '[data-slot="scheduling-focus-date-box"]',
    ) as HTMLElement
    const cls = box.className
    // Brass border is the jewelry signal — Detail Concentration
    // Translation Principle 4.
    expect(cls).toMatch(/border-brass/)
    // brass-subtle wash + brass border — same composition the
    // AncillaryPoolPin uses for its active drop-target chrome
    // (cross-surface vocabulary consistency).
    expect(cls).toMatch(/brass-subtle/)
  })
})
