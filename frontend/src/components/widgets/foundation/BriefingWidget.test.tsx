/**
 * BriefingWidget — vitest unit tests (Phase W-3b).
 *
 * Phase W-3b contract:
 *   • Glance + Brief + Detail variants per §12.10
 *   • Per-user scoping via existing `useBriefing` hook (mocked here;
 *     server-side enforcement covered by Phase 6 endpoint tests)
 *   • Briefing-type ("morning" | "evening") via `config.briefing_type`
 *   • View-only per §12.6a — Read full link routes to /briefing
 *   • Empty + loading + error states render coherent placeholder
 */

import { render } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest"

import type { BriefingSummary, BriefingType } from "@/types/briefing"


// Mock the useBriefing hook — drives all variant rendering decisions.
// Each test sets `mockResult` before render to control the path.
let mockResult: {
  briefing: BriefingSummary | null
  loading: boolean
  error: string | null
} = { briefing: null, loading: false, error: null }
const mockReload = vi.fn(async () => {})
const mockUseBriefing = vi.fn((_type: BriefingType) => ({
  ...mockResult,
  reload: mockReload,
}))

vi.mock("@/hooks/useBriefing", () => ({
  useBriefing: (type: BriefingType) => mockUseBriefing(type),
}))


import { BriefingWidget } from "./BriefingWidget"


function renderWidget(props: Parameters<typeof BriefingWidget>[0]) {
  return render(
    <MemoryRouter>
      <BriefingWidget {...props} />
    </MemoryRouter>,
  )
}


function makeBriefing(
  overrides: Partial<BriefingSummary> = {},
): BriefingSummary {
  return {
    id: "br-123",
    briefing_type: "morning",
    generated_at: "2026-04-27T07:00:00Z",
    delivered_at: "2026-04-27T07:00:01Z",
    delivery_channels: ["in_app"],
    narrative_text:
      "Good morning. Three deliveries scheduled today; ancillary " +
      "pool has 2 items waiting; one critical anomaly flagged for " +
      "production review. Hopkins case follow-up due this afternoon.",
    structured_sections: {
      queue_summaries: [
        {
          queue_id: "q-1",
          queue_name: "Task triage",
          pending_count: 4,
          estimated_time_minutes: 15,
        },
        {
          queue_id: "q-2",
          queue_name: "SS cert approval",
          pending_count: 2,
          estimated_time_minutes: 6,
        },
      ],
      flags: [
        {
          severity: "critical",
          title: "Anomaly: balance mismatch on Hopkins invoice",
        },
        { severity: "warning", title: "Training expires in 5 days" },
      ],
      pending_decisions: [
        { title: "Approve Hopkins disinterment release form" },
      ],
    },
    active_space_id: "sp-1",
    active_space_name: "Production",
    role_slug: "admin",
    generation_duration_ms: 250,
    input_tokens: 1024,
    output_tokens: 512,
    read_at: null,
    created_at: "2026-04-27T07:00:00Z",
    ...overrides,
  }
}


beforeEach(() => {
  mockResult = { briefing: null, loading: false, error: null }
  mockUseBriefing.mockClear()
  mockReload.mockClear()
})


afterEach(() => {
  vi.clearAllMocks()
})


// ── Config plumbing — briefing_type ────────────────────────────────


describe("BriefingWidget — briefing_type config", () => {
  it("defaults to morning when config undefined", () => {
    mockResult = { briefing: makeBriefing(), loading: false, error: null }
    renderWidget({})
    expect(mockUseBriefing).toHaveBeenCalledWith("morning")
    expect(
      document.querySelector('[data-briefing-type="morning"]'),
    ).toBeInTheDocument()
  })

  it("defaults to morning when config has no briefing_type", () => {
    mockResult = { briefing: makeBriefing(), loading: false, error: null }
    renderWidget({ config: {} })
    expect(mockUseBriefing).toHaveBeenCalledWith("morning")
  })

  it("uses evening when config.briefing_type='evening'", () => {
    mockResult = {
      briefing: makeBriefing({ briefing_type: "evening" }),
      loading: false,
      error: null,
    }
    renderWidget({ config: { briefing_type: "evening" } })
    expect(mockUseBriefing).toHaveBeenCalledWith("evening")
    expect(
      document.querySelector('[data-briefing-type="evening"]'),
    ).toBeInTheDocument()
  })

  it("falls back to morning for unknown briefing_type values", () => {
    mockResult = { briefing: makeBriefing(), loading: false, error: null }
    renderWidget({ config: { briefing_type: "afternoon" } })
    // readBriefingType returns "morning" for any value other than
    // "evening" — defensive against legacy/malformed config.
    expect(mockUseBriefing).toHaveBeenCalledWith("morning")
  })
})


// ── Glance variant ──────────────────────────────────────────────────


describe("BriefingWidget — Glance variant", () => {
  it("renders Glance with sunrise icon + title for morning", () => {
    mockResult = { briefing: makeBriefing(), loading: false, error: null }
    renderWidget({ variant_id: "glance" })

    const tablet = document.querySelector(
      '[data-slot="briefing-widget"][data-variant="glance"]',
    )
    expect(tablet).toBeInTheDocument()
    expect(tablet?.textContent).toContain("Morning briefing")
  })

  it("Glance shows unread dot when briefing.read_at is null", () => {
    mockResult = {
      briefing: makeBriefing({ read_at: null }),
      loading: false,
      error: null,
    }
    renderWidget({ variant_id: "glance" })

    expect(
      document.querySelector('[data-slot="briefing-unread-dot"]'),
    ).toBeInTheDocument()
  })

  it("Glance hides unread dot when briefing.read_at set", () => {
    mockResult = {
      briefing: makeBriefing({ read_at: "2026-04-27T08:00:00Z" }),
      loading: false,
      error: null,
    }
    renderWidget({ variant_id: "glance" })

    expect(
      document.querySelector('[data-slot="briefing-unread-dot"]'),
    ).toBeNull()
  })

  it("Glance click-through routes to /briefing/{id} when briefing exists", () => {
    mockResult = {
      briefing: makeBriefing({ id: "br-xyz" }),
      loading: false,
      error: null,
    }
    renderWidget({ variant_id: "glance" })

    const link = document.querySelector(
      '[data-slot="briefing-widget"][data-variant="glance"]',
    ) as HTMLAnchorElement
    expect(link?.getAttribute("href")).toBe("/briefing/br-xyz")
  })

  it("Glance click-through routes to /briefing when no briefing", () => {
    mockResult = { briefing: null, loading: false, error: null }
    renderWidget({ variant_id: "glance" })

    const link = document.querySelector(
      '[data-slot="briefing-widget"][data-variant="glance"]',
    ) as HTMLAnchorElement
    expect(link?.getAttribute("href")).toBe("/briefing")
    expect(link?.textContent).toContain("No briefing")
  })

  it("Glance evening variant renders sunset path (briefing-type attr)", () => {
    mockResult = {
      briefing: makeBriefing({ briefing_type: "evening" }),
      loading: false,
      error: null,
    }
    renderWidget({
      variant_id: "glance",
      config: { briefing_type: "evening" },
    })

    const tablet = document.querySelector(
      '[data-slot="briefing-widget"][data-variant="glance"][data-briefing-type="evening"]',
    )
    expect(tablet).toBeInTheDocument()
    expect(tablet?.textContent).toContain("End of day summary")
  })
})


// ── Brief variant ──────────────────────────────────────────────────


describe("BriefingWidget — Brief variant", () => {
  it("default variant (no variant_id) renders Brief", () => {
    mockResult = { briefing: makeBriefing(), loading: false, error: null }
    renderWidget({})

    expect(
      document.querySelector(
        '[data-slot="briefing-widget"][data-variant="brief"]',
      ),
    ).toBeInTheDocument()
  })

  it("Brief renders narrative excerpt + active space pill + read full", () => {
    mockResult = { briefing: makeBriefing(), loading: false, error: null }
    renderWidget({ variant_id: "brief" })

    const narrative = document.querySelector(
      '[data-slot="briefing-narrative"]',
    )
    expect(narrative?.textContent).toContain("Good morning")
    expect(
      document.querySelector('[data-slot="briefing-space-badge"]')
        ?.textContent,
    ).toContain("Production")
    expect(
      document.querySelector('[data-slot="briefing-unread-badge"]'),
    ).toBeInTheDocument()
    const readFull = document.querySelector(
      '[data-slot="briefing-read-full"]',
    ) as HTMLAnchorElement
    expect(readFull?.getAttribute("href")).toBe("/briefing/br-123")
  })

  it("Brief truncates narrative beyond 320 chars with ellipsis", () => {
    const longNarrative = "x".repeat(500)
    mockResult = {
      briefing: makeBriefing({ narrative_text: longNarrative }),
      loading: false,
      error: null,
    }
    renderWidget({ variant_id: "brief" })

    const narrative = document.querySelector(
      '[data-slot="briefing-narrative"]',
    )
    expect(narrative?.textContent?.endsWith("…")).toBe(true)
    expect(narrative?.textContent?.length).toBeLessThan(longNarrative.length)
  })

  it("Brief renders empty state when briefing is null", () => {
    mockResult = { briefing: null, loading: false, error: null }
    renderWidget({ variant_id: "brief" })

    expect(
      document.querySelector('[data-slot="briefing-widget-empty"]'),
    ).toBeInTheDocument()
    const cta = document.querySelector(
      '[data-slot="briefing-widget-empty-cta"]',
    ) as HTMLAnchorElement
    expect(cta?.getAttribute("href")).toBe("/briefing")
  })

  it("Brief renders error state when error is set", () => {
    mockResult = {
      briefing: null,
      loading: false,
      error: "Network error",
    }
    renderWidget({ variant_id: "brief" })

    const err = document.querySelector('[data-slot="briefing-error"]')
    expect(err?.textContent).toContain("Network error")
  })

  it("Brief renders loading skeleton when loading=true", () => {
    mockResult = { briefing: null, loading: true, error: null }
    renderWidget({ variant_id: "brief" })

    // SkeletonLines emits multiple skeleton divs
    const skeletons = document.querySelectorAll('[data-slot="skeleton"]')
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it("Brief hides unread badge when briefing has read_at", () => {
    mockResult = {
      briefing: makeBriefing({ read_at: "2026-04-27T08:30:00Z" }),
      loading: false,
      error: null,
    }
    renderWidget({ variant_id: "brief" })

    expect(
      document.querySelector('[data-slot="briefing-unread-badge"]'),
    ).toBeNull()
  })
})


// ── Detail variant ─────────────────────────────────────────────────


describe("BriefingWidget — Detail variant", () => {
  it("Detail renders full narrative (no truncation)", () => {
    const longNarrative = "Detailed narrative " + "x".repeat(500)
    mockResult = {
      briefing: makeBriefing({ narrative_text: longNarrative }),
      loading: false,
      error: null,
    }
    renderWidget({ variant_id: "detail" })

    const narrative = document.querySelector(
      '[data-slot="briefing-narrative"]',
    )
    expect(narrative?.textContent).toBe(longNarrative)
  })

  it("Detail renders queue_summaries section when present", () => {
    mockResult = { briefing: makeBriefing(), loading: false, error: null }
    renderWidget({ variant_id: "detail" })

    const queues = document.querySelector(
      '[data-slot="briefing-queues-section"]',
    )
    expect(queues).toBeInTheDocument()
    expect(queues?.textContent).toContain("Task triage")
    expect(queues?.textContent).toContain("4")
    expect(queues?.textContent).toContain("SS cert approval")
  })

  it("Detail renders flags section with severity dots", () => {
    mockResult = { briefing: makeBriefing(), loading: false, error: null }
    renderWidget({ variant_id: "detail" })

    const flags = document.querySelector(
      '[data-slot="briefing-flags-section"]',
    )
    expect(flags).toBeInTheDocument()
    expect(flags?.textContent).toContain("Anomaly: balance mismatch")
    expect(flags?.textContent).toContain("Training expires")
  })

  it("Detail renders pending_decisions section", () => {
    mockResult = { briefing: makeBriefing(), loading: false, error: null }
    renderWidget({ variant_id: "detail" })

    const decisions = document.querySelector(
      '[data-slot="briefing-decisions-section"]',
    )
    expect(decisions).toBeInTheDocument()
    expect(decisions?.textContent).toContain(
      "Approve Hopkins disinterment release form",
    )
  })

  it("Detail silently skips structured sections when missing", () => {
    mockResult = {
      briefing: makeBriefing({ structured_sections: {} }),
      loading: false,
      error: null,
    }
    renderWidget({ variant_id: "detail" })

    expect(
      document.querySelector('[data-slot="briefing-queues-section"]'),
    ).toBeNull()
    expect(
      document.querySelector('[data-slot="briefing-flags-section"]'),
    ).toBeNull()
    expect(
      document.querySelector('[data-slot="briefing-decisions-section"]'),
    ).toBeNull()
  })

  it("Detail empty state routes to /briefing", () => {
    mockResult = { briefing: null, loading: false, error: null }
    renderWidget({ variant_id: "detail" })

    const cta = document.querySelector(
      '[data-slot="briefing-widget-empty-cta"]',
    ) as HTMLAnchorElement
    expect(cta?.getAttribute("href")).toBe("/briefing")
  })
})


// ── Surface awareness ──────────────────────────────────────────────


describe("BriefingWidget — surface awareness", () => {
  it("spaces_pin surface with glance variant_id renders Glance", () => {
    mockResult = { briefing: makeBriefing(), loading: false, error: null }
    renderWidget({
      surface: "spaces_pin",
      variant_id: "glance",
    })

    expect(
      document.querySelector(
        '[data-slot="briefing-widget"][data-variant="glance"]',
      ),
    ).toBeInTheDocument()
  })

  it("focus_canvas surface with detail variant_id renders Detail", () => {
    mockResult = { briefing: makeBriefing(), loading: false, error: null }
    renderWidget({
      surface: "focus_canvas",
      variant_id: "detail",
    })

    expect(
      document.querySelector(
        '[data-slot="briefing-widget"][data-variant="detail"]',
      ),
    ).toBeInTheDocument()
  })

  it("deep variant_id (defensive — briefing declares no Deep) falls back to Brief", () => {
    mockResult = { briefing: makeBriefing(), loading: false, error: null }
    renderWidget({ variant_id: "deep" })

    expect(
      document.querySelector(
        '[data-slot="briefing-widget"][data-variant="brief"]',
      ),
    ).toBeInTheDocument()
  })
})


// ── Per-user scoping regression ────────────────────────────────────


describe("BriefingWidget — per-user scoping (Phase 6 contract)", () => {
  it("widget delegates fetch to useBriefing hook — no widget-level user filtering", () => {
    // The widget itself MUST NOT filter by user — it relies on the
    // Phase 6 /briefings/v2/latest endpoint which enforces
    // user_id == current_user.id server-side. This test asserts the
    // hook is the only data source.
    mockResult = { briefing: makeBriefing(), loading: false, error: null }
    renderWidget({ variant_id: "brief" })

    expect(mockUseBriefing).toHaveBeenCalled()
    // Hook called exactly with the briefing_type from config (no
    // user_id, no extra params — Phase 6 endpoint owns scoping).
    expect(mockUseBriefing).toHaveBeenCalledWith("morning")
  })
})
