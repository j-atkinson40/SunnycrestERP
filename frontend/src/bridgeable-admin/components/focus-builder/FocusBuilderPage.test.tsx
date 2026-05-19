/**
 * FocusBuilderPage integration tests (sub-arcs F-1 + F-2).
 */
import { afterEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import FocusBuilderPage from "./FocusBuilderPage"
import type { Vertical } from "@/bridgeable-admin/services/verticals-service"
import type { CoreRecord } from "@/bridgeable-admin/services/focus-cores-service"
import type { TemplateRecord } from "@/bridgeable-admin/services/focus-templates-service"


vi.mock("@/bridgeable-admin/services/verticals-service", () => ({
  verticalsService: { list: vi.fn() },
}))
vi.mock("@/bridgeable-admin/services/focus-cores-service", () => ({
  focusCoresService: { list: vi.fn(), get: vi.fn(), update: vi.fn() },
}))
vi.mock("@/bridgeable-admin/services/focus-templates-service", () => ({
  focusTemplatesService: {
    list: vi.fn(),
    get: vi.fn(),
    update: vi.fn(),
    resolve: vi.fn(),
  },
}))
vi.mock("@/bridgeable-admin/lib/studio-routes", async () => {
  const actual = await vi.importActual<
    typeof import("@/bridgeable-admin/lib/studio-routes")
  >("@/bridgeable-admin/lib/studio-routes")
  return {
    ...actual,
    readLastVertical: vi.fn(() => null),
  }
})

import { verticalsService } from "@/bridgeable-admin/services/verticals-service"
import { focusCoresService } from "@/bridgeable-admin/services/focus-cores-service"
import { focusTemplatesService } from "@/bridgeable-admin/services/focus-templates-service"


const v: Vertical = {
  slug: "manufacturing",
  display_name: "Manufacturing",
  description: null,
  status: "published",
  icon: null,
  sort_order: 1,
  created_at: "",
  updated_at: "",
}

const c: CoreRecord = {
  id: "core-1",
  core_slug: "scheduling-kanban-core",
  display_name: "Scheduling Kanban",
  description: null,
  registered_component_kind: "focus-template",
  registered_component_name: "SchedulingKanbanCore",
  default_starting_column: 0,
  default_column_span: 12,
  default_row_index: 0,
  min_column_span: 1,
  max_column_span: 12,
  canvas_config: {},
  chrome: { preset: "card" },
  version: 9,
  is_active: true,
  created_at: "",
  updated_at: "",
}

const t: TemplateRecord = {
  id: "tpl-1",
  scope: "vertical_default",
  vertical: "manufacturing",
  template_slug: "sched-fh",
  display_name: "Sched FH",
  description: null,
  inherits_from_core_id: "core-1",
  inherits_from_core_version: 9,
  rows: [],
  canvas_config: {},
  chrome_overrides: {},
  substrate: {},
  typography: {},
  version: 1,
  is_active: true,
  created_at: "",
  updated_at: "",
}


afterEach(() => {
  vi.clearAllMocks()
  window.localStorage.clear()
})


function defaultMocks() {
  ;(verticalsService.list as ReturnType<typeof vi.fn>).mockResolvedValue([v])
  ;(focusCoresService.list as ReturnType<typeof vi.fn>).mockResolvedValue([c])
  ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValue(c)
  ;(focusTemplatesService.list as ReturnType<typeof vi.fn>).mockResolvedValue([t])
  ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(t)
  ;(focusTemplatesService.resolve as ReturnType<typeof vi.fn>).mockResolvedValue({
    template_id: "tpl-1",
    template_slug: "sched-fh",
    template_version: 1,
    template_scope: "vertical_default",
    template_vertical: "manufacturing",
    core_id: "core-1",
    core_slug: "scheduling-kanban-core",
    core_version: 9,
    core_registered_component: {},
    rows: [],
    canvas_config: {},
    resolved_chrome: { preset: "card" },
    resolved_substrate: null,
    resolved_typography: null,
    sources: {
      template: {},
      core: {},
      tenant: null,
      chrome_sources: { preset: "tier1" },
      substrate_sources: {},
      typography_sources: {},
    },
  })
}


describe("FocusBuilderPage", () => {
  it("mounts all three regions", async () => {
    defaultMocks()
    render(
      <MemoryRouter initialEntries={["/studio/builder/focuses"]}>
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(screen.getByTestId("focus-builder-page")).toBeInTheDocument(),
    )
    expect(screen.getByTestId("focus-builder-tree-region")).toBeInTheDocument()
    expect(
      screen.getByTestId("focus-builder-canvas-region"),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("focus-builder-right-rail-region"),
    ).toBeInTheDocument()
  })

  it("shows empty canvas when no subject in URL", async () => {
    defaultMocks()
    render(
      <MemoryRouter initialEntries={["/studio/builder/focuses"]}>
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      const canvas = screen.getByTestId("focus-builder-canvas")
      expect(canvas).toHaveAttribute("data-canvas-mode", "empty")
    })
  })

  it("loads a core into the canvas when ?subject=core:<id>", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=core:core-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      const canvas = screen.getByTestId("focus-builder-canvas")
      expect(canvas).toHaveAttribute("data-canvas-mode", "core")
    })
    expect(focusCoresService.get).toHaveBeenCalledWith("core-1")
  })

  it("loads a template into the canvas when ?subject=template:<id>", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      const canvas = screen.getByTestId("focus-builder-canvas")
      expect(canvas).toHaveAttribute("data-canvas-mode", "template")
    })
    expect(focusTemplatesService.get).toHaveBeenCalledWith("tpl-1")
  })

  it("clicking a core in the tree updates URL with ?subject=core:<id>", async () => {
    defaultMocks()
    render(
      <MemoryRouter initialEntries={["/studio/builder/focuses"]}>
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(screen.getByText("Scheduling Kanban")).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByText("Scheduling Kanban"))
    await waitFor(() => {
      expect(focusCoresService.get).toHaveBeenCalledWith("core-1")
    })
  })

  it("inspector starts in empty state when subject loaded but no selection", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(
        screen.getByTestId("focus-builder-inspector-empty"),
      ).toBeInTheDocument()
    })
  })

  it("clicking core placement opens chrome inspector", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-core-placement"),
      ).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId("focus-builder-core-placement"))
    await waitFor(() => {
      expect(
        screen.getByTestId("focus-builder-inspector"),
      ).toBeInTheDocument()
    })
    // Chrome preset picker rendered.
    expect(screen.getAllByText(/Chrome/i).length).toBeGreaterThan(0)
  })

  it("clicking canvas background opens substrate + typography sections (template mode)", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(screen.getByTestId("focus-builder-canvas")).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId("focus-builder-canvas"))
    await waitFor(() => {
      expect(
        screen.getByTestId("focus-builder-inspector"),
      ).toBeInTheDocument()
    })
    expect(screen.getAllByText(/Substrate/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Typography/i).length).toBeGreaterThan(0)
  })

  it("core-placement click stops propagation (does not flip to background)", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-core-placement"),
      ).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId("focus-builder-core-placement"))
    await waitFor(() => {
      const placement = screen.getByTestId("focus-builder-core-placement")
      expect(placement).toHaveAttribute("data-selected", "true")
    })
    // Substrate section should NOT be visible — chrome section is.
    expect(screen.queryByText(/Substrate$/)).not.toBeInTheDocument()
  })

  it("Esc deselects (returns inspector to empty state)", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-core-placement"),
      ).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId("focus-builder-core-placement"))
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-inspector"),
      ).toBeInTheDocument(),
    )
    fireEvent.keyDown(window, { key: "Escape" })
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-inspector-empty"),
      ).toBeInTheDocument(),
    )
  })

  it("'View canonical core' button visible for templates only", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    // Click placement to surface the inspector.
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-core-placement"),
      ).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId("focus-builder-core-placement"))
    await waitFor(() => {
      expect(
        screen.getByTestId("view-canonical-core-button"),
      ).toBeInTheDocument()
    })
  })

  it("'View canonical core' button NOT shown for cores", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=core:core-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-core-placement"),
      ).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId("focus-builder-core-placement"))
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-inspector"),
      ).toBeInTheDocument(),
    )
    expect(
      screen.queryByTestId("view-canonical-core-button"),
    ).not.toBeInTheDocument()
  })

  it("'View canonical core' button opens InheritedCoreInspectorPanel", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-core-placement"),
      ).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId("focus-builder-core-placement"))
    await waitFor(() =>
      expect(
        screen.getByTestId("view-canonical-core-button"),
      ).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId("view-canonical-core-button"))
    await waitFor(() =>
      expect(
        screen.getByTestId("inherited-core-inspector-panel"),
      ).toBeInTheDocument(),
    )
  })

  it("widget palette + theme placeholders render", async () => {
    defaultMocks()
    render(
      <MemoryRouter initialEntries={["/studio/builder/focuses"]}>
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-widget-palette-region"),
      ).toBeInTheDocument(),
    )
    expect(
      screen.getByTestId("focus-builder-theme-region"),
    ).toBeInTheDocument()
    // F-3 replaces the palette placeholder with the real widget palette.
    // Theme region stays a placeholder until F-4.
    expect(screen.getByText(/Arrives in F-4/)).toBeInTheDocument()
  })

  // ─────────────────────────────────────────────────────────────────
  // F-3.1a.2 — URL recovery on 410-retry. When the operator opens
  // a template via a stale URL (template_id was deactivated by a
  // prior session's version-bump on the backend), the first save
  // in this session 410s and the hook retries against the new
  // active id. The page must rewrite the URL `?subject=template:<new>`
  // with `{ replace: true }` so a subsequent refresh GETs the
  // still-active row instead of the deactivated snapshot.
  // ─────────────────────────────────────────────────────────────────
  it("F-3.1a.2 — URL recovers to active template id when initial save 410s", async () => {
    defaultMocks()
    // First PUT 410s with active_template_id pointing at the new row.
    const staleError = Object.assign(new Error("Gone"), {
      response: {
        status: 410,
        data: {
          detail: {
            inactive_template_id: "tpl-1",
            active_template_id: "tpl-1-v2",
            slug: "sched-fh",
            scope: "vertical_default",
            vertical: "manufacturing",
          },
        },
      },
    })
    ;(focusTemplatesService.update as ReturnType<typeof vi.fn>)
      .mockRejectedValueOnce(staleError)
      .mockResolvedValueOnce({ ...t, id: "tpl-1-v2" })

    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )

    // Canvas mounts in template mode for the (stale) URL-bound id.
    await waitFor(() => {
      const canvas = screen.getByTestId("focus-builder-canvas")
      expect(canvas).toHaveAttribute("data-canvas-mode", "template")
    })

    // Click canvas background → substrate + typography sections.
    fireEvent.click(screen.getByTestId("focus-builder-canvas"))
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-inspector"),
      ).toBeInTheDocument(),
    )
    // Trigger a save by clicking a substrate preset pill.
    const pill = await screen.findByTestId("substrate-pill-morning-warm")
    fireEvent.click(pill)

    // Debounced save fires after 300ms; the 410-retry resolves to
    // tpl-1-v2; the page callback rewrites URL to subject=template:tpl-1-v2.
    await waitFor(
      () => {
        expect(focusTemplatesService.update).toHaveBeenCalledTimes(2)
      },
      { timeout: 2000 },
    )

    // URL recovered. We assert via the canvas mode + the subsequent
    // GET against the new id: the page re-derives `templateSubjectId`
    // from the URL, the hook re-mounts against tpl-1-v2, the canvas
    // re-renders. Verify the subject-binding via a second GET fired
    // on the new id (the hook fetches on templateId transition).
    await waitFor(
      () => {
        expect(focusTemplatesService.get).toHaveBeenCalledWith("tpl-1-v2")
      },
      { timeout: 2000 },
    )
  })

  // ─────────────────────────────────────────────────────────────────
  // F-3.1b — Chrome inspector: integration test verifying widget
  // chrome scrubs persist end-to-end through the placement adapter.
  //
  // Per the today-filed canon entry "Mock-only tests verify one side
  // of frontend↔backend contracts; cross-side contracts require
  // integration tests", this exercises the full operator-flow:
  // render → load template with seeded widget → click widget →
  // inspector opens → scrub elevation → debounced save fires →
  // assert PUT body's prop_overrides shape (verifies the adapter
  // still translates `chrome` → `prop_overrides` correctly after
  // F-3.1b's Chrome section landed).
  // ─────────────────────────────────────────────────────────────────
  it("F-3.1b — widget chrome scrub persists through adapter as prop_overrides", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      defaultMocks()
      // Seed a template carrying one widget placement so we can click
      // it without going through the drag-from-palette flow.
      const seededTemplate: TemplateRecord = {
        ...t,
        rows: [
          {
            row_index: 0,
            column_count: 12,
            placements: [
              {
                placement_id: "w-int-1",
                component_kind: "widget",
                component_name: "day-strip-widget",
                starting_column: 0,
                column_span: 12,
                // prop_overrides absent — defaults will render
              },
            ],
          },
        ],
      }
      ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
        seededTemplate,
      )
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
        seededTemplate,
      )

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      // Wait for placed widget to mount.
      await waitFor(() =>
        expect(
          screen.getByTestId("focus-builder-placed-widget"),
        ).toBeInTheDocument(),
      )

      // Click the placed widget — opens widget inspector with Chrome section.
      fireEvent.click(screen.getByTestId("focus-builder-placed-widget"))
      await waitFor(() =>
        expect(
          screen.getByTestId("widget-inspector-section"),
        ).toBeInTheDocument(),
      )

      // Chrome section is expanded by default per F-3.1b decision.
      const elevation = await screen.findByLabelText(/elevation/i)
      // Scrub via keyboard ArrowRight (step = 1 by default).
      fireEvent.keyDown(elevation, { key: "ArrowRight" })

      // Debounced save fires (queueSave). Advance past the debounce.
      await vi.advanceTimersByTimeAsync(500)
      await waitFor(() => {
        expect(focusTemplatesService.update).toHaveBeenCalled()
      })

      // Inspect the PUT body's prop_overrides — must carry elevation.
      const calls = (focusTemplatesService.update as ReturnType<typeof vi.fn>)
        .mock.calls
      const lastBody = calls[calls.length - 1]?.[1]
      const placement = lastBody?.rows?.[0]?.placements?.[0]
      expect(placement).toBeTruthy()
      expect(placement.prop_overrides).toBeTruthy()
      expect(typeof placement.prop_overrides.elevation).toBe("number")
    } finally {
      vi.useRealTimers()
    }
  })

  // ─────────────────────────────────────────────────────────────────
  // F-3.1c — Widget chrome scrub must update BOTH the rendered DOM
  // wrapper styles AND the PUT body's prop_overrides shape.
  //
  // Per today's filed canon (Mock-only tests verify one side of
  // frontend↔backend contracts), F-3.1b asserted save-side only and
  // missed that PlacedWidget's wrapper ignored chrome entirely.
  // F-3.1c wires the chrome-resolver into the wrapper style and adds
  // this cross-side assertion: render-side DOM check + save-side PUT
  // body check, in the same test.
  //
  // Verify-against-pre-fix discipline: with the `...resolvedChromeStyle`
  // spread removed from PlacedWidget's wrapper style, the DOM
  // assertion fails (inline style attribute does not change between
  // pre-scrub and post-scrub captures) while the PUT-body assertion
  // continues to pass. Restored the spread → both assertions pass.
  // ─────────────────────────────────────────────────────────────────
  it("F-3.1c — widget chrome scrub updates rendered wrapper styles AND persists via PUT", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      defaultMocks()
      const seededTemplate: TemplateRecord = {
        ...t,
        rows: [
          {
            row_index: 0,
            column_count: 12,
            placements: [
              {
                placement_id: "w-int-2",
                component_kind: "widget",
                component_name: "day-strip-widget",
                starting_column: 0,
                column_span: 12,
              },
            ],
          },
        ],
      }
      ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
        seededTemplate,
      )
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
        seededTemplate,
      )

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      const placedWidget = await screen.findByTestId(
        "focus-builder-placed-widget",
      )
      // Capture initial inline-style attribute. JSDOM does not compute
      // resolved CSS values (window.getComputedStyle returns the
      // declared inline only), so we inspect the `style` attribute
      // string — that's where the resolver's output lands. The
      // resolver maps elevation>25 → boxShadow != "none"; for the
      // seeded placement (no chrome overrides), DEFAULT_WIDGET_CHROME
      // (elevation 50) already produces a non-none shadow. After the
      // scrub, elevation increments by 1, the resolver-mapped
      // boxShadow stays in the same tier, BUT the style attribute
      // re-serializes — assertion shape is therefore "attribute
      // contains box-shadow" before AND after, but the post-scrub
      // boxShadow value reflects the new elevation tier when scrubbed
      // far enough. For a robust assertion that doesn't depend on
      // tier-bucket boundaries, we assert (a) initial inline style
      // declares box-shadow + border-radius + padding (proving chrome
      // is applied at all) and (b) post-scrub the inline style still
      // declares them. F-3.1c's load-bearing assertion is (a) — pre-
      // F-3.1c, PlacedWidget produced no chrome-derived inline style
      // properties whatsoever.
      const initialStyleAttr = placedWidget.getAttribute("style") ?? ""
      expect(initialStyleAttr).toMatch(/box-shadow/i)
      expect(initialStyleAttr).toMatch(/border-radius/i)
      expect(initialStyleAttr).toMatch(/padding/i)

      // Click the widget → inspector opens → scrub elevation up
      // enough to cross a resolver tier boundary (25→50→75→100).
      fireEvent.click(placedWidget)
      await waitFor(() =>
        expect(
          screen.getByTestId("widget-inspector-section"),
        ).toBeInTheDocument(),
      )
      const elevation = await screen.findByLabelText(/elevation/i)
      // Cross from tier (≤50) up to (≤75) and beyond. Default seed
      // elevation is 50 (frosted preset). ArrowRight x 30 → elevation
      // ~80, which crosses two resolver tier boundaries (50→75, 75→100).
      for (let i = 0; i < 30; i++) {
        fireEvent.keyDown(elevation, { key: "ArrowRight" })
      }

      // Debounced save fires.
      await vi.advanceTimersByTimeAsync(500)
      await waitFor(() => {
        expect(focusTemplatesService.update).toHaveBeenCalled()
      })

      // ASSERTION 1 — PUT body shape (mirrors F-3.1b's existing).
      const calls = (focusTemplatesService.update as ReturnType<typeof vi.fn>)
        .mock.calls
      const lastBody = calls[calls.length - 1]?.[1]
      const placement = lastBody?.rows?.[0]?.placements?.[0]
      expect(placement).toBeTruthy()
      expect(placement.prop_overrides).toBeTruthy()
      expect(typeof placement.prop_overrides.elevation).toBe("number")

      // ASSERTION 2 — Rendered DOM reflects chrome (NEW for F-3.1c).
      // Re-read the wrapper after the scrub fires. The element ref
      // is stable; React mutates the inline style attribute in place.
      const updatedStyleAttr = placedWidget.getAttribute("style") ?? ""
      expect(updatedStyleAttr).toMatch(/box-shadow/i)
      expect(updatedStyleAttr).toMatch(/border-radius/i)
      expect(updatedStyleAttr).toMatch(/padding/i)
      // Stronger render-side assertion: the post-scrub style attribute
      // string differs from the initial one. Elevation crossed two
      // tier boundaries, so the resolver's boxShadow output changed.
      expect(updatedStyleAttr).not.toBe(initialStyleAttr)
    } finally {
      vi.useRealTimers()
    }
  })

  it("subject change resets selection to none", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-core-placement"),
      ).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId("focus-builder-core-placement"))
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-inspector"),
      ).toBeInTheDocument(),
    )
    // Switch subject via tree click — use the tree node testid to
    // disambiguate from the canvas card's title that also contains
    // "Scheduling Kanban".
    const coreNode = screen.getByTestId(
      "tree-node-vertical:manufacturing::focus-type:decision::core:core-1",
    )
    fireEvent.click(coreNode)
    await waitFor(() => {
      expect(
        screen.getByTestId("focus-builder-inspector-empty"),
      ).toBeInTheDocument()
    })
  })
})
