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
    // Active-state visual chrome includes accent border (jewelry on).
    expect(box.className).toMatch(/border-accent/)
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

  it("calibration: subtle warm fill + full-strength border + sharp corners (Aesthetic Arc Session 3)", () => {
    // Aesthetic-coherence regression. Calibration journey across
    // sessions:
    //   Pre-Session-1.5: bg-surface-elevated full-opacity + full-
    //     strength border. Read as primary-nav weight, competing
    //     with H2.
    //   Session 1.5: TRANSPARENT + half-strength /50 border.
    //     Overcorrected — boxes barely visible.
    //   Session 1.6: TRANSPARENT + full-strength border. Better
    //     than 1.5 but still read as faint outline against the
    //     dimmed/blurred Focus substrate.
    //   Session 3 (current): bg-surface-elevated/50 warm fill +
    //     full-strength border. The fill establishes "interactive
    //     surface" presence comparable to AncillaryPoolPin (which
    //     uses bg-surface-elevated/85 because it's a floating card;
    //     DateBox is INLINE chrome so /50 is the right register).
    // The box reads as a discoverable peek affordance, subordinate
    // to H2 day label. Active state still applies accent jewelry
    // (separate test below). If a future refactor restores the
    // transparent rest state, drifts to bg-muted, or rounds to
    // rounded-full, this test fails.
    const { container } = render(
      <Harness>
        <DateBox date="2026-04-25" active={false} onClick={() => {}} />
      </Harness>,
    )
    const box = container.querySelector(
      '[data-slot="scheduling-focus-date-box"]',
    ) as HTMLElement
    const cls = box.className
    // Subtle warm fill at rest — surface-elevated at /50 alpha.
    // Quieter than Pin's /85, more present than Session 1.6's
    // transparent. Section 0 Detail Concentration: peripheral
    // interactive surface, jewelry only at active state.
    expect(cls).toMatch(/bg-surface-elevated\/50/)
    // Full-strength border (no /50 alpha modifier).
    expect(cls).toMatch(/\bborder-border-subtle\b(?!\/)/)
    expect(cls).toMatch(/rounded-sm/)
    // Drift guards — these tokens MUST NOT appear at rest.
    expect(cls).not.toMatch(/bg-muted\b/)
    expect(cls).not.toMatch(/rounded-full/)
    expect(cls).not.toMatch(/shadow-md/)
  })

  it("active state composition uses accent border + accent-subtle wash (jewelry on)", () => {
    const { container } = render(
      <Harness>
        <DateBox date="2026-04-25" active={true} onClick={() => {}} />
      </Harness>,
    )
    const box = container.querySelector(
      '[data-slot="scheduling-focus-date-box"]',
    ) as HTMLElement
    const cls = box.className
    // Accent border is the jewelry signal — Detail Concentration
    // Translation Principle 4.
    expect(cls).toMatch(/border-accent/)
    // accent-subtle wash + accent border — same composition the
    // AncillaryPoolPin uses for its active drop-target chrome
    // (cross-surface vocabulary consistency).
    expect(cls).toMatch(/accent-subtle/)
  })
})
