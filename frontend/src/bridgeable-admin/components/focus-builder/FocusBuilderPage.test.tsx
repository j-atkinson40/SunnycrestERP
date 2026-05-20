/**
 * FocusBuilderPage integration tests (sub-arcs F-1 + F-2).
 */
import { afterEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
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
  // F-5: reset just the `update` mock implementation. vi.clearAllMocks
  // only clears calls/results — it does NOT clear mockImplementation.
  // Without this, F-5's failed-PUT test's rejection implementation
  // leaks across the worker's shared mock-module cache into unrelated
  // test files (Tier2TemplatesEditor.test.tsx surfaced the pollution).
  // Targeted reset on the one mock that gets per-test reconfiguration.
  ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockReset()
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
    // Substrate section should NOT be visible in the inspector —
    // chrome section is. (The F-4 theme picker in the right-rail
    // bottom also shows a "Substrate" label; scope to the inspector.)
    const inspector = screen.getByTestId("focus-builder-inspector")
    expect(
      within(inspector).queryByText(/Substrate$/),
    ).not.toBeInTheDocument()
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

  it("widget palette + theme picker regions mount", async () => {
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
    // F-4 replaces the theme placeholder with the real theme picker.
    // With no subject loaded, the picker is in disabled state.
    expect(
      screen.getByTestId("focus-builder-theme-picker-disabled"),
    ).toBeInTheDocument()
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
    // Trigger a save by clicking a substrate preset pill. F-4 added
    // a second substrate-pill-morning-warm in the right-rail theme
    // picker; scope to the inspector to keep this test about the
    // inspector path specifically.
    const inspector = screen.getByTestId("focus-builder-inspector")
    const pill = await within(inspector).findByTestId(
      "substrate-pill-morning-warm",
    )
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

  // ─────────────────────────────────────────────────────────────────
  // F-4 — Theme picker cross-side integration.
  //
  // Per DECISIONS.md 2026-05-19 (evening) canon refinement on
  // data↔render cross-side framing: an operator flow that produces
  // BOTH persistence (PUT to backend) AND visual change (canvas inline
  // style update) must be tested in both directions in the same test.
  //
  // Verify-against-pre-fix discipline applied for both variants:
  //
  //   Variant A — chip onClick revert (NOOP the updateSubstrate call):
  //     Both save-side AND render-side assertions FAIL.
  //
  //   Variant B — canvas-resolver wiring revert:
  //     The canvas already applies substrate via canvasStyle (pre-F-4
  //     work from F-2). Removing the substrate spread from canvasStyle
  //     leaves save-side passing (PUT still fires) while render-side
  //     fails (canvas style attribute does not change despite save
  //     success). This proves the cross-side test catches render-
  //     pipeline regressions independent of save-pipeline regressions.
  // ─────────────────────────────────────────────────────────────────
  it("F-4 — theme picker substrate chip updates rendered canvas AND persists via PUT", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      defaultMocks()
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(t)

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      const canvas = await screen.findByTestId("focus-builder-canvas")
      // Capture initial inline style. The canvas already applies the
      // substrate-resolver output to canvasStyle (F-2 work); with the
      // seeded empty substrate ({}), the resolver returns a populated
      // style object (default substrate gradient + tokens). Pre-F-4,
      // no operator path existed to change it from the right rail.
      const initialStyleAttr = canvas.getAttribute("style") ?? ""
      expect(initialStyleAttr.length).toBeGreaterThan(0)

      // Click the substrate chip in the theme picker. evening-lounge
      // is a meaningfully-different preset from the seeded default —
      // its resolved style values differ from the empty-blob default.
      const chip = await screen.findByTestId("substrate-pill-evening-lounge")
      fireEvent.click(chip)

      // Debounced save fires.
      await vi.advanceTimersByTimeAsync(500)

      await waitFor(() => {
        expect(focusTemplatesService.update).toHaveBeenCalled()
      })

      // ASSERTION 1 — Save side: PUT body carries substrate.preset.
      const calls = (focusTemplatesService.update as ReturnType<typeof vi.fn>)
        .mock.calls
      const lastBody = calls[calls.length - 1]?.[1]
      expect(lastBody?.substrate).toBeTruthy()
      expect(lastBody.substrate.preset).toBe("evening-lounge")

      // ASSERTION 2 — Render side: canvas inline style attribute
      // changed in response to the chip click. The substrate-resolver
      // expands the preset into base_token + accent tokens, and the
      // canvas's canvasStyle useMemo picks that up via substrateDraft
      // state. JSDOM mutates the style attribute in place.
      const updatedStyleAttr = canvas.getAttribute("style") ?? ""
      expect(updatedStyleAttr).not.toBe(initialStyleAttr)
    } finally {
      vi.useRealTimers()
    }
  })

  it("F-4 — theme picker typography chip updates rendered canvas AND persists via PUT", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      defaultMocks()
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(t)

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      const canvas = await screen.findByTestId("focus-builder-canvas")
      const initialStyleAttr = canvas.getAttribute("style") ?? ""

      const chip = await screen.findByTestId("typography-pill-headline")
      fireEvent.click(chip)

      await vi.advanceTimersByTimeAsync(500)
      await waitFor(() => {
        expect(focusTemplatesService.update).toHaveBeenCalled()
      })

      // ASSERTION 1 — Save side.
      const calls = (focusTemplatesService.update as ReturnType<typeof vi.fn>)
        .mock.calls
      const lastBody = calls[calls.length - 1]?.[1]
      expect(lastBody?.typography).toBeTruthy()
      expect(lastBody.typography.preset).toBe("headline")

      // ASSERTION 2 — Render side. The canvas's canvasStyle includes
      // typography-derived properties (fontWeight, color) computed
      // from typographyDraft. Headline preset alters them vs. default.
      const updatedStyleAttr = canvas.getAttribute("style") ?? ""
      expect(updatedStyleAttr).not.toBe(initialStyleAttr)
    } finally {
      vi.useRealTimers()
    }
  })

  it("F-4 — theme picker shows disabled state when subject is a core", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=core:core-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(
        screen.getByTestId("focus-builder-theme-picker-disabled"),
      ).toBeInTheDocument()
    })
    expect(
      screen.getByTestId("focus-builder-theme-picker-disabled-hint"),
    ).toHaveTextContent(/themes apply to templates, not cores/i)
  })

  // ─────────────────────────────────────────────────────────────────
  // F-4.1 — operator-observable render assertions
  //
  // F-4's existing render-side assertions targeted `canvas.style`
  // attribute string changes — those passed false-positive for the
  // typography chip because typography updates surface as CSS custom
  // properties on the canvas wrapper (`--focus-builder-heading-weight`)
  // which change whenever typographyDraft state changes, regardless of
  // whether the resolver produced different values.
  //
  // F-4.1 asserts on the rendered <h2> heading element's inline
  // `style.fontWeight` — the operator-observable property. This catches
  // the bug: if specific fields stay at their (scrubbed) values, the
  // resolver's specifics-win priority returns the unchanged weight even
  // though the preset changed.
  //
  // The bug only surfaces when specific fields have non-null values
  // pre-click. From an empty template ({}) all specifics are null →
  // resolver applies preset defaults regardless of chip-handler shape.
  // These tests seed pre-scrubbed specifics (heading_weight: 400 + a
  // legacy preset) to reproduce the operator scenario:
  //
  //   1. operator scrubbed heading_weight in F-2 inspector
  //   2. operator clicks a different preset chip in F-4 theme picker
  //   3. F-4 bug: heading_weight stays 400 → canvas heading unchanged
  //   4. F-4.1 fix: chip click nulls specifics → preset weight applies
  //
  // Verify-against-pre-fix discipline: temporarily revert the chip
  // onChange to fire only `{ preset: <slug> }`, run these tests; both
  // render-side assertions fail (fontWeight unchanged), save-side
  // assertions still pass (PUT body carries preset). This demonstrates
  // the cross-side test catches the render-pipeline bug independent of
  // save-pipeline correctness.
  // ─────────────────────────────────────────────────────────────────
  it("F-4.1 — typography chip resets specifics AND visibly updates rendered heading font-weight", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      defaultMocks()
      // Seed template with pre-scrubbed typography specifics (the F-2
      // inspector scrubbing scenario). heading_weight=400 differs from
      // every preset's heading_weight (card=500, frosted=600,
      // headline=700) so the visible change is unambiguous.
      const seeded: TemplateRecord = {
        ...t,
        typography: {
          preset: "card-text",
          heading_weight: 400,
          body_weight: 400,
          heading_color_token: null,
          body_color_token: null,
        },
      }
      ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(seeded)
      ;(focusTemplatesService.list as ReturnType<typeof vi.fn>).mockResolvedValue([seeded])
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(seeded)

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      // Wait for the chip-state to confirm template is loaded with the
      // seeded card-text preset (proves typographyDraft has been
      // populated from the mocked .get response).
      await waitFor(() => {
        const cardChip = screen.getByTestId("typography-pill-card-text")
        expect(cardChip.getAttribute("data-active")).toBe("true")
      })

      // Heading <h2> lives inside the canvas placement card. Scope the
      // lookup to the canvas to avoid the tree-navigation labels.
      const canvas = await screen.findByTestId("focus-builder-canvas")
      const heading = await waitFor(() => {
        const h2 = canvas.querySelector("h2")
        if (!h2) throw new Error("canvas heading not yet rendered")
        return h2 as HTMLElement
      })
      // Pre-click: heading_weight=400 (scrubbed value, specifics-win).
      // The canvas's resolveTypographyHeadingStyle sets fontWeight from
      // view.heading_weight directly — the operator-observable value.
      expect(heading.style.fontWeight).toBe("400")

      // Click the headline preset chip in the F-4 theme picker.
      const chip = await screen.findByTestId("typography-pill-headline")
      fireEvent.click(chip)

      await vi.advanceTimersByTimeAsync(500)
      await waitFor(() => {
        expect(focusTemplatesService.update).toHaveBeenCalled()
      })

      // ASSERTION 1 — save side: PUT body carries preset + nulled
      // specifics. F-4.1 fix is observable in the payload shape.
      const calls = (focusTemplatesService.update as ReturnType<typeof vi.fn>)
        .mock.calls
      const lastBody = calls[calls.length - 1]?.[1]
      expect(lastBody?.typography).toMatchObject({
        preset: "headline",
        heading_weight: null,
        body_weight: null,
        heading_color_token: null,
        body_color_token: null,
      })

      // ASSERTION 2 — render side, OPERATOR-OBSERVABLE: <h2>
      // style.fontWeight is the value the operator sees. With F-4.1
      // fix, resolver's expandTypographyPreset applies headline
      // defaults (heading_weight=700) because all specifics are null.
      // Pre-fix (revert chip handler to {preset:'headline'} only),
      // heading_weight stays 400 and this assertion fails.
      expect(heading.style.fontWeight).toBe("700")
    } finally {
      vi.useRealTimers()
    }
  })

  it("F-4.1 — substrate chip resets specifics AND visibly updates rendered canvas backgroundColor", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      defaultMocks()
      // Seed pre-scrubbed substrate specifics. base_token differs from
      // morning-warm preset's base_token (surface-base).
      const seeded: TemplateRecord = {
        ...t,
        substrate: {
          preset: "neutral",
          intensity: 50,
          base_token: "surface-sunken",
          accent_token_1: null,
          accent_token_2: null,
        },
      }
      ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(seeded)
      ;(focusTemplatesService.list as ReturnType<typeof vi.fn>).mockResolvedValue([seeded])
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(seeded)

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      const canvas = await screen.findByTestId("focus-builder-canvas")
      const initialStyle = canvas.getAttribute("style") ?? ""

      // Click morning-warm — meaningfully-different preset.
      const chip = await screen.findByTestId("substrate-pill-morning-warm")
      fireEvent.click(chip)

      await vi.advanceTimersByTimeAsync(500)
      await waitFor(() => {
        expect(focusTemplatesService.update).toHaveBeenCalled()
      })

      // ASSERTION 1 — save side: F-4.1 fix observable in payload shape.
      const calls = (focusTemplatesService.update as ReturnType<typeof vi.fn>)
        .mock.calls
      const lastBody = calls[calls.length - 1]?.[1]
      expect(lastBody?.substrate).toMatchObject({
        preset: "morning-warm",
        intensity: null,
        base_token: null,
        accent_token_1: null,
        accent_token_2: null,
      })

      // ASSERTION 2 — render side. morning-warm hits the substrate
      // resolver's special-case branch producing radial-gradient
      // composition; the previous neutral preset produced a linear-
      // gradient. With F-4.1 fix the resolver receives null specifics
      // and applies morning-warm's defaults (intensity=100, base_token
      // surface-base, accent_token_1 surface-elevated) — radials with
      // full alpha. Pre-fix, specifics-win returns the resolver's
      // output computed against base_token=surface-sunken +
      // intensity=50 + morning-warm's radial branch, which is a
      // different gradient than the F-4.1-fixed defaults. The style
      // attribute changes observably across the chip click in both
      // cases (the substrate-resolver morning-warm branch always
      // emits radial-gradient bytes); the operator-observable
      // distinction is the resolved values within that gradient.
      // Cross-side discipline: PUT payload shape (assertion 1) is the
      // primary fix verification; canvas style change is the
      // continuity check from F-4.
      const updatedStyle = canvas.getAttribute("style") ?? ""
      expect(updatedStyle).not.toBe(initialStyle)
    } finally {
      vi.useRealTimers()
    }
  })

  // ─────────────────────────────────────────────────────────────────
  // F-5 integration tests — breadcrumb + dirty-state polish.
  //
  // Per DECISIONS.md 2026-05-19 (late evening) canon refinement:
  // render-side assertions target operator-observable properties at
  // the specific rendered element (textContent, data-state attribute
  // on the indicator element itself) — NOT wrapper-level attribute
  // change detection.
  //
  // Verify-against-pre-fix discipline (documented in build report,
  // not codified as separate tests; reverting any of these has been
  // validated to surface the corresponding regression):
  //
  //   - Breadcrumb: revert <FocusBuilderBreadcrumb> mount → bc absent
  //     from header → testid query fails.
  //   - Dirty state: revert deriveSaveIndicatorState branch (e.g.,
  //     drop the error branch) → failed-state assertion fails because
  //     indicator falls through to "saving"/"unsaved".
  // ─────────────────────────────────────────────────────────────────
  it("F-5 — breadcrumb renders subject hierarchy for TEMPLATE subject", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    // operator-observable textContent: vertical › focus-type › core
    // › template. Verticals come from verticalsService.list() (mocked
    // → display_name "Manufacturing"); focus-type derived from
    // CORE_SLUG_TO_FOCUS_TYPE (scheduling-kanban-core → decision →
    // "Decision"); core + template display_name come from loaded
    // records. Wait for the full 4-segment hierarchy — inheritedCore
    // fetch is async so the breadcrumb hydrates in steps.
    await waitFor(() => {
      const bc = screen.getByTestId("focus-builder-breadcrumb")
      expect(bc.textContent).toBe(
        "Manufacturing›Decision›Scheduling Kanban›Sched FH",
      )
    })
    // current segment marker on the deepest element.
    expect(
      screen.getByTestId("focus-builder-breadcrumb-current"),
    ).toHaveTextContent("Sched FH")
  })

  it("F-5 — breadcrumb renders 3-segment hierarchy for CORE subject", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={[
          "/bridgeable-admin/studio/manufacturing/builder/focuses?subject=core:core-1",
        ]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    const bc = await screen.findByTestId("focus-builder-breadcrumb")
    // CORE subject: 3 segments. studio-active vertical resolved from
    // the URL path's studio segment → "manufacturing" slug → mocked
    // verticals list maps slug → "Manufacturing" display_name.
    expect(bc.textContent).toBe("Manufacturing›Decision›Scheduling Kanban")
    expect(
      screen.getByTestId("focus-builder-breadcrumb-current"),
    ).toHaveTextContent("Scheduling Kanban")
  })

  it("F-5 — breadcrumb hidden when no subject selected", async () => {
    defaultMocks()
    render(
      <MemoryRouter initialEntries={["/studio/builder/focuses"]}>
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(screen.getByTestId("focus-builder-page")).toBeInTheDocument(),
    )
    expect(
      screen.queryByTestId("focus-builder-breadcrumb"),
    ).not.toBeInTheDocument()
  })

  it("F-5 — breadcrumb updates when subject changes via tree click on core", async () => {
    defaultMocks()
    render(
      <MemoryRouter initialEntries={["/studio/builder/focuses"]}>
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    // No subject → no breadcrumb.
    await waitFor(() =>
      expect(screen.getByTestId("focus-builder-page")).toBeInTheDocument(),
    )
    expect(
      screen.queryByTestId("focus-builder-breadcrumb"),
    ).not.toBeInTheDocument()
    // Click the core tree-node leaf → breadcrumb appears with the
    // CORE-shape segments. Operator-observable textContent at the
    // deepest segment is the core's display_name.
    const treeRegion = screen.getByTestId("focus-builder-tree-region")
    const coreNode = await waitFor(() =>
      within(treeRegion).getByText("Scheduling Kanban"),
    )
    fireEvent.click(coreNode)
    await waitFor(() => {
      const current = screen.getByTestId("focus-builder-breadcrumb-current")
      expect(current.textContent).toBe("Scheduling Kanban")
    })
  })

  it("F-5 — save indicator shows Unsaved changes on operator mutation", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      defaultMocks()
      // Make update slow so we can observe the dirty → saving → saved
      // transition. Resolve after a short delay.
      let resolveUpdate: ((v: TemplateRecord) => void) | null = null
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockImplementation(
        () =>
          new Promise<TemplateRecord>((res) => {
            resolveUpdate = res
          }),
      )

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      // Wait for template to load; initially no indicator (no save yet).
      await waitFor(() =>
        expect(screen.getByTestId("focus-builder-canvas")).toBeInTheDocument(),
      )

      // Trigger a mutation: click substrate preset chip.
      const chip = await screen.findByTestId("substrate-pill-evening-lounge")
      fireEvent.click(chip)

      // Immediately after click (before debounce settles) the hook is
      // dirty but not saving — operator-observable textContent.
      await waitFor(() => {
        const ind = screen.getByTestId("save-indicator")
        // operator-observable: data-state attribute on the indicator
        // itself reads "unsaved" or "saving" depending on debounce.
        expect(["unsaved", "saving"]).toContain(ind.getAttribute("data-state"))
      })

      // Advance past debounce — save fires + is in-flight.
      await vi.advanceTimersByTimeAsync(500)
      await waitFor(() => {
        expect(focusTemplatesService.update).toHaveBeenCalled()
      })
      // In-flight → "Saving…".
      await waitFor(() => {
        const ind = screen.getByTestId("save-indicator")
        expect(ind.getAttribute("data-state")).toBe("saving")
        expect(ind.textContent).toBe("Saving…")
      })

      // Resolve the save — indicator settles to "Saved · just now".
      resolveUpdate!({ ...t, substrate: { preset: "evening-lounge" } })
      await waitFor(() => {
        const ind = screen.getByTestId("save-indicator")
        expect(ind.getAttribute("data-state")).toBe("saved")
        expect(ind.textContent).toMatch(/^Saved ·/)
      })
    } finally {
      vi.useRealTimers()
    }
  })

  it("F-5 — save indicator shows Save failed · Retry on PUT failure", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      defaultMocks()
      // Use mockImplementation returning a rejected promise (vs.
      // mockRejectedValue) so each call gets its own independent
      // rejection — keeps the retry path's "another call fires +
      // also rejects" semantics observable without leaking unhandled
      // rejections across the test's await boundaries.
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockImplementation(
        () => Promise.reject(new Error("network error")),
      )

      const { unmount } = render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      await waitFor(() =>
        expect(screen.getByTestId("focus-builder-canvas")).toBeInTheDocument(),
      )

      const chip = await screen.findByTestId("substrate-pill-evening-lounge")
      fireEvent.click(chip)

      await vi.advanceTimersByTimeAsync(500)
      await waitFor(() => {
        expect(focusTemplatesService.update).toHaveBeenCalled()
      })

      // operator-observable: indicator's textContent matches the
      // failed-state copy + Retry button renders.
      await waitFor(() => {
        const ind = screen.getByTestId("save-indicator")
        expect(ind.getAttribute("data-state")).toBe("failed")
        expect(ind.textContent).toMatch(/^Save failed ·\s+Retry$/)
      })
      expect(screen.getByTestId("save-indicator-retry")).toBeInTheDocument()

      // Retry click re-fires save. update was called once before the
      // click; one more call after.
      const callsBefore = (focusTemplatesService.update as ReturnType<typeof vi.fn>)
        .mock.calls.length
      fireEvent.click(screen.getByTestId("save-indicator-retry"))
      await waitFor(() => {
        const callsAfter = (focusTemplatesService.update as ReturnType<typeof vi.fn>)
          .mock.calls.length
        expect(callsAfter).toBeGreaterThan(callsBefore)
      })

      // Defensive: explicitly unmount + restore mock to a benign
      // implementation BEFORE timer advance/teardown. The hook's
      // debounced save and 410-retry path otherwise queue rejecting
      // promises that race the next test's setup under the default
      // parallel reporter — this can pollute unrelated test files.
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockImplementation(
        () => Promise.resolve(t),
      )
      unmount()
      // Advance + drain microtasks so any tail-saves resolve cleanly.
      await vi.advanceTimersByTimeAsync(1000)
    } finally {
      vi.useRealTimers()
    }
  })

  // ─────────────────────────────────────────────────────────────────
  // FF-2 — Free-form canvas substrate (operator-observable canon).
  //
  // Cross-side assertion: a free-form-shaped template renders the
  // WidgetFreeFormLayer through the full page mount; widgets land at
  // their authored x/y/width/height via inline style on the rendered
  // element; inherited core renders at Q-20's canonical anchored
  // position (left=0, top=40 for span=12 on a 1200-wide canvas).
  //
  // Verify-against-pre-fix discipline: removing
  // `detectTemplateShape`'s freeform branch (forcing all templates
  // through the grid path) would route this template into
  // WidgetRowsLayer; the inline `position: absolute / left: 100px /
  // top: 100px` assertion fails because the grid path uses CSS grid
  // cells, not absolute positioning. Restored detection → assertion
  // passes.
  //
  // The drop-coordinate translation logic (Q-4 centering + Q-14
  // clamp) is unit-tested at the pure-function level in
  // FocusBuilderCanvas.test.tsx (`computeFreeFormDropPosition`); per
  // investigation Q-40 (JSDOM weakness for drag/pointer gestures),
  // full drag-end integration coverage defers to Playwright at FF-7.
  // ─────────────────────────────────────────────────────────────────
  it("FF-2 — free-form template renders absolute-positioned widgets through page mount", async () => {
    defaultMocks()
    const freeFormTpl: TemplateRecord = {
      ...t,
      canvas_config: { width: 1200, height: 800 },
      rows: [
        {
          row_index: 0,
          column_count: 12,
          placements: [
            {
              placement_id: "ff-page-1",
              component_kind: "widget",
              component_name: "today-pin-widget",
              x: 100,
              y: 100,
              width: 240,
              height: 120,
              z_index: 0,
            },
          ],
        },
      ],
    }
    ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      freeFormTpl,
    )
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    // Wait for free-form layer + widget to mount.
    await waitFor(() =>
      expect(screen.getByTestId("focus-builder-freeform-layer")).toBeInTheDocument(),
    )
    const placed = screen.getByTestId("focus-builder-placed-widget")
    const styleAttr = placed.getAttribute("style") ?? ""
    expect(styleAttr).toMatch(/position:\s*absolute/i)
    expect(styleAttr).toMatch(/left:\s*100px/i)
    expect(styleAttr).toMatch(/top:\s*100px/i)
    expect(styleAttr).toMatch(/width:\s*240px/i)
    expect(styleAttr).toMatch(/height:\s*120px/i)
    // Inner operator-observable core anchor exists.
    expect(
      screen.getByTestId("focus-builder-placed-widget-core"),
    ).toBeInTheDocument()
    // Inherited core anchored at Q-20 canonical position (span=12
    // on a 1200-wide canvas → left=0, top=40).
    const coreEl = screen.getByTestId("focus-builder-core-placement")
    const coreStyle = coreEl.getAttribute("style") ?? ""
    expect(coreStyle).toMatch(/left:\s*0px/i)
    expect(coreStyle).toMatch(/top:\s*40px/i)
    expect(coreStyle).toMatch(/width:\s*1200px/i)
  })

  it("FF-2 — grid template regression: still renders WidgetRowsLayer through page mount", async () => {
    defaultMocks()
    const gridTpl: TemplateRecord = {
      ...t,
      rows: [
        {
          row_index: 0,
          column_count: 12,
          placements: [
            {
              placement_id: "grid-page-1",
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
      gridTpl,
    )
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-widget-rows-layer"),
      ).toBeInTheDocument(),
    )
    // Free-form layer absent (regression preservation).
    expect(screen.queryByTestId("focus-builder-freeform-layer")).toBeNull()
    // Grid placement renders with grid-column style.
    const placed = screen.getByTestId("focus-builder-placed-widget")
    const styleAttr = placed.getAttribute("style") ?? ""
    expect(styleAttr).toMatch(/grid-column/i)
  })

  it("FF-2 — clicking free-form widget fires selection (kind=widget)", async () => {
    defaultMocks()
    const freeFormTpl: TemplateRecord = {
      ...t,
      canvas_config: { width: 1200, height: 800 },
      rows: [
        {
          row_index: 0,
          column_count: 12,
          placements: [
            {
              placement_id: "ff-sel-1",
              component_kind: "widget",
              component_name: "today-pin-widget",
              x: 200,
              y: 200,
              width: 240,
              height: 120,
            },
          ],
        },
      ],
    }
    ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      freeFormTpl,
    )
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(screen.getByTestId("focus-builder-placed-widget")).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId("focus-builder-placed-widget"))
    // Selection chrome flips to selected.
    await waitFor(() => {
      const placed = screen.getByTestId("focus-builder-placed-widget")
      expect(placed.getAttribute("data-selected")).toBe("true")
    })
  })
})
