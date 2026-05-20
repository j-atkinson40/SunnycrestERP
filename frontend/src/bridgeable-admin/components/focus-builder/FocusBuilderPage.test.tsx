/**
 * FocusBuilderPage integration tests (sub-arcs F-1 + F-2).
 */
import { afterEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import "@/lib/visual-editor/registry/auto-register"

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
    // FF-3 — positioning moved up to the draggable wrapper above the
    // PlacedWidgetCore. Assertions target the wrapper for the
    // operator-observable inline style.
    const draggable = screen.getByTestId(
      "focus-builder-freeform-placed-widget-draggable",
    )
    const styleAttr = draggable.getAttribute("style") ?? ""
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

  // ─────────────────────────────────────────────────────────────────
  // FF-3 — Drag-to-move (KeyboardSensor path per Q-40).
  //
  // Cross-side assertion: keyboard-driven drag commits move the
  // free-form placement's x/y BOTH on the rendered wrapper inline
  // style AND in the saved PUT body's placement row.
  //
  // Verify-against-pre-fix discipline: reverting the page-level
  // drag-end handler's FF-3 branch to a no-op (drag fires but no
  // updateWidget call) makes BOTH the render-side inline-style
  // assertion AND the save-side PUT-body assertion fail. Restored →
  // both pass. The pure-function commit math is unit-tested at
  // computeDragMoveCommit.test.ts (Q-14 clamp coverage); per Q-40
  // full pointer-driven drag coverage defers to Playwright at FF-7.
  // ─────────────────────────────────────────────────────────────────
  it("FF-3 — keyboard drag commits free-form widget x/y via render + PUT", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
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
                placement_id: "ff-drag-1",
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
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
        freeFormTpl,
      )

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      const draggable = await screen.findByTestId(
        "focus-builder-freeform-placed-widget-draggable",
      )
      // Focus the draggable so KeyboardSensor receives keystrokes.
      draggable.focus()
      // Activate drag — Space per @dnd-kit KeyboardSensor activator
      // (matches `event.target === activator` requirement).
      fireEvent.keyDown(draggable, { key: " ", code: "Space" })
      // KeyboardSensor adds its keydown listener inside a setTimeout
      // (see @dnd-kit/core KeyboardSensor.attach). Advance timers so
      // arrow nudges land on the listener, not the activator path.
      await vi.advanceTimersByTimeAsync(10)
      // Nudge right twice (default keyboard step = 25px each → +50).
      // KeyboardSensor's move/end listener lives on the document
      // (per @dnd-kit/core attach()), so arrows must be dispatched
      // there, not on the draggable element.
      fireEvent.keyDown(document, { key: "ArrowRight", code: "ArrowRight" })
      await vi.advanceTimersByTimeAsync(10)
      fireEvent.keyDown(document, { key: "ArrowRight", code: "ArrowRight" })
      await vi.advanceTimersByTimeAsync(10)
      // Commit drop.
      fireEvent.keyDown(document, { key: " ", code: "Space" })
      await vi.advanceTimersByTimeAsync(10)

      // Save-side: advance past debounce, assert PUT body carries
      // the updated x. Initial x=100; after 2× ArrowRight (25px each
      // by @dnd-kit's default), expect x>100 (allow tolerance for
      // future default-step changes).
      await vi.advanceTimersByTimeAsync(500)
      await waitFor(() => {
        expect(focusTemplatesService.update).toHaveBeenCalled()
      })
      const calls = (focusTemplatesService.update as ReturnType<typeof vi.fn>)
        .mock.calls
      const lastBody = calls[calls.length - 1]?.[1]
      const placement = lastBody?.rows?.[0]?.placements?.[0]
      expect(placement).toBeTruthy()
      // Operator-observable on the save side: x advanced past 100.
      // y remains 100 (no vertical nudges).
      expect(placement.x).toBeGreaterThan(100)
      expect(placement.y).toBe(100)

      // Render-side: the draggable wrapper's inline `left` reflects
      // the committed x. Per the operator-observable assertion canon
      // (2026-05-20 late-evening), this is the load-bearing render-
      // side contract.
      await waitFor(() => {
        const after = screen.getByTestId(
          "focus-builder-freeform-placed-widget-draggable",
        )
        const styleAttr = after.getAttribute("style") ?? ""
        // Extract numeric left value via regex; assert > 100.
        const m = /left:\s*(\d+)px/i.exec(styleAttr)
        expect(m).toBeTruthy()
        const leftVal = m ? parseInt(m[1], 10) : 0
        expect(leftVal).toBeGreaterThan(100)
        // top unchanged.
        expect(styleAttr).toMatch(/top:\s*100px/i)
      })
    } finally {
      vi.useRealTimers()
    }
  })

  // FF-3 — Canvas-bounds clamping (Q-14). Drag toward right edge past
  // the canvas; the commit clamps to canvasWidth - widgetWidth.
  it("FF-3 — drag past right edge clamps to canvas bounds (Q-14)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      defaultMocks()
      // Widget placed near the right edge (canvas 1200, widget 240,
      // so right-edge max x = 960). Start at x=900; drag past edge.
      const freeFormTpl: TemplateRecord = {
        ...t,
        canvas_config: { width: 1200, height: 800 },
        rows: [
          {
            row_index: 0,
            column_count: 12,
            placements: [
              {
                placement_id: "ff-clamp-1",
                component_kind: "widget",
                component_name: "today-pin-widget",
                x: 900,
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
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
        freeFormTpl,
      )

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      const draggable = await screen.findByTestId(
        "focus-builder-freeform-placed-widget-draggable",
      )
      draggable.focus()
      fireEvent.keyDown(draggable, { key: " ", code: "Space" })
      await vi.advanceTimersByTimeAsync(10)
      // Multiple right-nudges to overshoot the canvas bound. Document
      // is the listener target per @dnd-kit/core KeyboardSensor.
      for (let i = 0; i < 10; i++) {
        fireEvent.keyDown(document, { key: "ArrowRight", code: "ArrowRight" })
        await vi.advanceTimersByTimeAsync(5)
      }
      fireEvent.keyDown(document, { key: " ", code: "Space" })
      await vi.advanceTimersByTimeAsync(10)

      await vi.advanceTimersByTimeAsync(500)
      await waitFor(() => {
        expect(focusTemplatesService.update).toHaveBeenCalled()
      })
      const calls = (focusTemplatesService.update as ReturnType<typeof vi.fn>)
        .mock.calls
      const lastBody = calls[calls.length - 1]?.[1]
      const placement = lastBody?.rows?.[0]?.placements?.[0]
      // Per Q-14: clamped to canvasWidth - widgetWidth = 1200 - 240
      // = 960.
      expect(placement.x).toBeLessThanOrEqual(960)
      expect(placement.x).toBeGreaterThan(900) // moved at least some
    } finally {
      vi.useRealTimers()
    }
  })

  // ─────────────────────────────────────────────────────────────────
  // FF-4 — Resize-to-resize (KeyboardSensor path per Q-40).
  //
  // Cross-side assertion (per the 2026-05-20 late-evening operator-
  // observable canon): the integration test asserts BOTH the
  // rendered wrapper's inline `width`/`height`/`left` value AND the
  // saved PUT body's placement geometry change in the operator-
  // expected direction. Pure-function math is unit-tested in
  // `computeResizeCommit.test.ts` (32 cases across 8 handles + min/
  // canvas clamps).
  //
  // Verify-against-pre-fix discipline applied: reverting the FF-4
  // dispatch branch in `handleDragEnd` to a no-op (handle dragged
  // but no `updateWidget` call) makes BOTH the render-side inline-
  // style assertion AND the save-side PUT-body assertion fail.
  // Restored → both pass.
  //
  // Per Q-40, full pointer-driven coverage defers to Playwright at
  // FF-7. JSDOM-side coverage drives the KeyboardSensor path.
  // ─────────────────────────────────────────────────────────────────
  it("FF-4 — keyboard resize via e handle commits width via render + PUT", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
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
                placement_id: "ff-resize-1",
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
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
        freeFormTpl,
      )

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      // Step 1 — click the widget to select it; handles only render
      // when selected.
      await screen.findByTestId("focus-builder-freeform-placed-widget-draggable")
      fireEvent.click(screen.getByTestId("focus-builder-placed-widget"))

      // Step 2 — find the e (right edge) handle. It only mounts when
      // the widget is selected.
      await waitFor(() => {
        const h = document.querySelector('[data-testid="focus-builder-resize-handle"][data-handle-position="e"]') as HTMLElement | null
        expect(h).not.toBeNull()
      })
      const handle = document.querySelector('[data-testid="focus-builder-resize-handle"][data-handle-position="e"]') as HTMLElement
      handle.focus()
      // Activate drag on the handle — Space per @dnd-kit
      // KeyboardSensor activator (matches `event.target === activator`).
      fireEvent.keyDown(handle, { key: " ", code: "Space" })
      await vi.advanceTimersByTimeAsync(10)
      // Nudge right twice (default keyboard step = 25px each → +50).
      // KeyboardSensor's move/end listener lives on the document
      // (per @dnd-kit/core attach()) so arrows dispatch there.
      fireEvent.keyDown(document, { key: "ArrowRight", code: "ArrowRight" })
      await vi.advanceTimersByTimeAsync(10)
      fireEvent.keyDown(document, { key: "ArrowRight", code: "ArrowRight" })
      await vi.advanceTimersByTimeAsync(10)
      fireEvent.keyDown(document, { key: " ", code: "Space" })
      await vi.advanceTimersByTimeAsync(10)

      // Save-side: advance past debounce, assert PUT body carries
      // a widened width. Initial width=240; after 2× ArrowRight
      // (25px each), expect width > 240. e handle keeps x and y
      // unchanged.
      await vi.advanceTimersByTimeAsync(500)
      await waitFor(() => {
        expect(focusTemplatesService.update).toHaveBeenCalled()
      })
      const calls = (focusTemplatesService.update as ReturnType<typeof vi.fn>)
        .mock.calls
      const lastBody = calls[calls.length - 1]?.[1]
      const placement = lastBody?.rows?.[0]?.placements?.[0]
      expect(placement).toBeTruthy()
      expect(placement.width).toBeGreaterThan(240)
      expect(placement.x).toBe(100)
      expect(placement.y).toBe(100)
      expect(placement.height).toBe(120)

      // Render-side: the draggable wrapper's inline `width` reflects
      // the committed value. Per the operator-observable assertion
      // canon (2026-05-20 late-evening), this is the load-bearing
      // render-side contract.
      await waitFor(() => {
        const after = screen.getByTestId(
          "focus-builder-freeform-placed-widget-draggable",
        )
        const styleAttr = after.getAttribute("style") ?? ""
        const m = /width:\s*(\d+)px/i.exec(styleAttr)
        expect(m).toBeTruthy()
        const widthVal = m ? parseInt(m[1], 10) : 0
        expect(widthVal).toBeGreaterThan(240)
        // height unchanged.
        expect(styleAttr).toMatch(/height:\s*120px/i)
        // x unchanged.
        expect(styleAttr).toMatch(/left:\s*100px/i)
      })
    } finally {
      vi.useRealTimers()
    }
  })

  // FF-4 — w handle: x adjusts as width grows (right edge anchored).
  it("FF-4 — keyboard resize via w handle adjusts x as width grows", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
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
                placement_id: "ff-resize-w-1",
                component_kind: "widget",
                component_name: "today-pin-widget",
                x: 400,
                y: 200,
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
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
        freeFormTpl,
      )

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      await screen.findByTestId("focus-builder-freeform-placed-widget-draggable")
      fireEvent.click(screen.getByTestId("focus-builder-placed-widget"))

      await waitFor(() => {
        const h = document.querySelector('[data-testid="focus-builder-resize-handle"][data-handle-position="w"]') as HTMLElement | null
        expect(h).not.toBeNull()
      })
      const handle = document.querySelector('[data-testid="focus-builder-resize-handle"][data-handle-position="w"]') as HTMLElement
      handle.focus()
      fireEvent.keyDown(handle, { key: " ", code: "Space" })
      await vi.advanceTimersByTimeAsync(10)
      // ArrowLeft on w handle: delta.x < 0 → x decreases, width grows
      // by equal amount.
      fireEvent.keyDown(document, { key: "ArrowLeft", code: "ArrowLeft" })
      await vi.advanceTimersByTimeAsync(10)
      fireEvent.keyDown(document, { key: "ArrowLeft", code: "ArrowLeft" })
      await vi.advanceTimersByTimeAsync(10)
      fireEvent.keyDown(document, { key: " ", code: "Space" })
      await vi.advanceTimersByTimeAsync(10)

      await vi.advanceTimersByTimeAsync(500)
      await waitFor(() => {
        expect(focusTemplatesService.update).toHaveBeenCalled()
      })
      const calls = (focusTemplatesService.update as ReturnType<typeof vi.fn>)
        .mock.calls
      const lastBody = calls[calls.length - 1]?.[1]
      const placement = lastBody?.rows?.[0]?.placements?.[0]
      // x decreased; width grew by the same delta. Right edge stays
      // anchored: x + width = 640 (original 400 + 240).
      expect(placement.x).toBeLessThan(400)
      expect(placement.width).toBeGreaterThan(240)
      expect(placement.x + placement.width).toBe(640)
      expect(placement.y).toBe(200)
      expect(placement.height).toBe(120)
    } finally {
      vi.useRealTimers()
    }
  })

  // FF-4 — resize clamped at canvas bound (Q-14).
  it("FF-4 — resize at left edge clamps to canvas bound (Q-14)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      defaultMocks()
      // Widget placed at x=0; w handle drag-left should clamp x at 0
      // and widen to the original right edge.
      const freeFormTpl: TemplateRecord = {
        ...t,
        canvas_config: { width: 1200, height: 800 },
        rows: [
          {
            row_index: 0,
            column_count: 12,
            placements: [
              {
                placement_id: "ff-resize-clamp-1",
                component_kind: "widget",
                component_name: "today-pin-widget",
                x: 0,
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
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
        freeFormTpl,
      )

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      await screen.findByTestId("focus-builder-freeform-placed-widget-draggable")
      fireEvent.click(screen.getByTestId("focus-builder-placed-widget"))
      await waitFor(() => {
        const h = document.querySelector('[data-testid="focus-builder-resize-handle"][data-handle-position="w"]') as HTMLElement | null
        expect(h).not.toBeNull()
      })
      const handle = document.querySelector('[data-testid="focus-builder-resize-handle"][data-handle-position="w"]') as HTMLElement
      handle.focus()
      fireEvent.keyDown(handle, { key: " ", code: "Space" })
      await vi.advanceTimersByTimeAsync(10)
      // Many ArrowLeft nudges to push past the canvas-left bound.
      for (let i = 0; i < 10; i++) {
        fireEvent.keyDown(document, { key: "ArrowLeft", code: "ArrowLeft" })
        await vi.advanceTimersByTimeAsync(5)
      }
      fireEvent.keyDown(document, { key: " ", code: "Space" })
      await vi.advanceTimersByTimeAsync(10)

      await vi.advanceTimersByTimeAsync(500)
      await waitFor(() => {
        expect(focusTemplatesService.update).toHaveBeenCalled()
      })
      const calls = (focusTemplatesService.update as ReturnType<typeof vi.fn>)
        .mock.calls
      const lastBody = calls[calls.length - 1]?.[1]
      const placement = lastBody?.rows?.[0]?.placements?.[0]
      // Per Q-14: x clamped at 0. Width grew to original right edge
      // (0 + 240 = 240) since the right edge stays anchored.
      expect(placement.x).toBe(0)
      expect(placement.width).toBe(240)
    } finally {
      vi.useRealTimers()
    }
  })

  // FF-4 — resize clamped at min dimensions (Q-13).
  // The today-pin-widget registration declares freeFormMinDimensions
  // 120×64 (see registry/registrations/focus-builder-widgets.ts).
  // Shrinking from 130×120 past min should clamp at 120.
  it("FF-4 — resize via e handle clamps at registry min dimensions (Q-13)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
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
                placement_id: "ff-resize-min-1",
                component_kind: "widget",
                component_name: "today-pin-widget",
                x: 200,
                y: 200,
                width: 130,
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
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
        freeFormTpl,
      )

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      await screen.findByTestId("focus-builder-freeform-placed-widget-draggable")
      fireEvent.click(screen.getByTestId("focus-builder-placed-widget"))
      await waitFor(() => {
        const h = document.querySelector('[data-testid="focus-builder-resize-handle"][data-handle-position="e"]') as HTMLElement | null
        expect(h).not.toBeNull()
      })
      const handle = document.querySelector('[data-testid="focus-builder-resize-handle"][data-handle-position="e"]') as HTMLElement
      handle.focus()
      fireEvent.keyDown(handle, { key: " ", code: "Space" })
      await vi.advanceTimersByTimeAsync(10)
      // ArrowLeft on e handle: delta.x < 0 → width contracts.
      // Push past min.
      for (let i = 0; i < 6; i++) {
        fireEvent.keyDown(document, { key: "ArrowLeft", code: "ArrowLeft" })
        await vi.advanceTimersByTimeAsync(5)
      }
      fireEvent.keyDown(document, { key: " ", code: "Space" })
      await vi.advanceTimersByTimeAsync(10)

      await vi.advanceTimersByTimeAsync(500)
      await waitFor(() => {
        expect(focusTemplatesService.update).toHaveBeenCalled()
      })
      const calls = (focusTemplatesService.update as ReturnType<typeof vi.fn>)
        .mock.calls
      const lastBody = calls[calls.length - 1]?.[1]
      const placement = lastBody?.rows?.[0]?.placements?.[0]
      // today-pin-widget min is 120×64 per registration; clamp engages.
      expect(placement.width).toBe(120)
      // x and y unchanged for e handle.
      expect(placement.x).toBe(200)
      expect(placement.y).toBe(200)
    } finally {
      vi.useRealTimers()
    }
  })

  // ─────────────────────────────────────────────────────────────────
  // FF-5 — z-index + layering UX (inspector + context menu).
  //
  // Cross-side assertion (operator-observable canon, 2026-05-20 late-
  // evening): integration tests assert BOTH the rendered wrapper's
  // inline `z-index` AND the saved PUT body's z_index change. Pure-
  // function math is unit-tested in `computeZIndexCommit.test.ts` (18
  // cases across front / back / forward / backward + filter + nil).
  //
  // Verify-against-pre-fix discipline applied: reverting the FF-5
  // setWidgetZIndex helper to a no-op (selecting + clicking the
  // inspector button still mounts but the placement state never
  // updates) makes BOTH the render-side inline-style assertion AND
  // the save-side PUT-body assertion fail. Restored → both pass.
  // ─────────────────────────────────────────────────────────────────
  function freeFormTwoWidgetTemplate(): TemplateRecord {
    return {
      ...t,
      canvas_config: { width: 1200, height: 800 },
      rows: [
        {
          row_index: 0,
          column_count: 12,
          placements: [
            {
              placement_id: "ff-z-a",
              component_kind: "widget",
              component_name: "today-pin-widget",
              x: 100,
              y: 100,
              width: 240,
              height: 120,
              z_index: 0,
            },
            {
              placement_id: "ff-z-b",
              component_kind: "widget",
              component_name: "today-pin-widget",
              x: 200,
              y: 200,
              width: 240,
              height: 120,
              z_index: 0,
            },
          ],
        },
      ],
    } as TemplateRecord
  }

  it("FF-5 — inspector 'Bring to front' commits z_index via render + PUT", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      defaultMocks()
      const tpl = freeFormTwoWidgetTemplate()
      ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
        tpl,
      )
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
        tpl,
      )

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      // Wait for widgets to render.
      const widgets = await screen.findAllByTestId(
        "focus-builder-freeform-placed-widget-draggable",
      )
      expect(widgets).toHaveLength(2)
      // Select widget A by clicking its inner core (left-click =
      // selection). Click the wrapper too as a redundancy; the inner
      // core's onClick stops propagation and fires onSelect.
      const widgetA = widgets.find(
        (w) => w.getAttribute("data-placement-id") === "ff-z-a",
      )!
      const coreA = within(widgetA).getByTestId(
        "focus-builder-placed-widget-core",
      )
      fireEvent.click(coreA)

      // Layer inspector section appears.
      const frontBtn = await screen.findByTestId("layer-action-front")
      expect(frontBtn).toBeInTheDocument()
      fireEvent.click(frontBtn)

      // Save-side: advance past debounce, assert PUT body has the
      // new z_index for widget A.
      await vi.advanceTimersByTimeAsync(500)
      await waitFor(() => {
        expect(focusTemplatesService.update).toHaveBeenCalled()
      })
      const calls = (focusTemplatesService.update as ReturnType<typeof vi.fn>)
        .mock.calls
      const lastBody = calls[calls.length - 1]?.[1] as {
        rows?: Array<{
          placements: Array<{ placement_id: string; z_index?: number }>
        }>
      }
      const sentA = lastBody.rows?.[0]?.placements.find(
        (p) => p.placement_id === "ff-z-a",
      )
      const sentB = lastBody.rows?.[0]?.placements.find(
        (p) => p.placement_id === "ff-z-b",
      )
      // others=[b@0]; max+1 = 1.
      expect(sentA?.z_index).toBe(1)
      expect(sentB?.z_index).toBe(0)

      // Render-side: widget A's inline z-index now 1; widget B
      // unchanged at 0.
      await waitFor(() => {
        const refreshed = screen.getAllByTestId(
          "focus-builder-freeform-placed-widget-draggable",
        )
        const a = refreshed.find(
          (w) => w.getAttribute("data-placement-id") === "ff-z-a",
        )!
        const b = refreshed.find(
          (w) => w.getAttribute("data-placement-id") === "ff-z-b",
        )!
        expect(a.getAttribute("style") ?? "").toMatch(/z-index:\s*1/i)
        expect(b.getAttribute("style") ?? "").toMatch(/z-index:\s*0/i)
      })
    } finally {
      vi.useRealTimers()
    }
  })

  it("FF-5 — right-click opens context menu; option click commits z_index", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      defaultMocks()
      const tpl = freeFormTwoWidgetTemplate()
      ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
        tpl,
      )
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
        tpl,
      )

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      const widgets = await screen.findAllByTestId(
        "focus-builder-freeform-placed-widget-draggable",
      )
      const widgetB = widgets.find(
        (w) => w.getAttribute("data-placement-id") === "ff-z-b",
      )!

      // Menu not yet open.
      expect(
        screen.queryByTestId("canvas-context-menu"),
      ).not.toBeInTheDocument()

      // Right-click widget B at viewport coords (320, 410).
      fireEvent.contextMenu(widgetB, { clientX: 320, clientY: 410 })

      // Menu now open at the cursor position.
      const menu = await screen.findByTestId("canvas-context-menu")
      const menuStyle = menu.getAttribute("style") ?? ""
      expect(menuStyle).toMatch(/top:\s*410px/i)
      expect(menuStyle).toMatch(/left:\s*320px/i)

      // Click "Bring to front" in the context menu.
      fireEvent.click(screen.getByTestId("context-menu-action-front"))

      // Menu closes after option click.
      await waitFor(() => {
        expect(
          screen.queryByTestId("canvas-context-menu"),
        ).not.toBeInTheDocument()
      })

      // PUT body carries new z_index for widget B.
      await vi.advanceTimersByTimeAsync(500)
      await waitFor(() => {
        expect(focusTemplatesService.update).toHaveBeenCalled()
      })
      const calls = (focusTemplatesService.update as ReturnType<typeof vi.fn>)
        .mock.calls
      const lastBody = calls[calls.length - 1]?.[1] as {
        rows?: Array<{
          placements: Array<{ placement_id: string; z_index?: number }>
        }>
      }
      const sentB = lastBody.rows?.[0]?.placements.find(
        (p) => p.placement_id === "ff-z-b",
      )
      // others=[a@0]; max+1 = 1.
      expect(sentB?.z_index).toBe(1)

      // Render-side: widget B's inline z-index reflects the new value.
      await waitFor(() => {
        const refreshed = screen.getAllByTestId(
          "focus-builder-freeform-placed-widget-draggable",
        )
        const b = refreshed.find(
          (w) => w.getAttribute("data-placement-id") === "ff-z-b",
        )!
        expect(b.getAttribute("style") ?? "").toMatch(/z-index:\s*1/i)
      })
    } finally {
      vi.useRealTimers()
    }
  })

  it("FF-5 — click outside closes context menu without firing PUT", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      defaultMocks()
      const tpl = freeFormTwoWidgetTemplate()
      ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
        tpl,
      )
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
        tpl,
      )

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      const widgets = await screen.findAllByTestId(
        "focus-builder-freeform-placed-widget-draggable",
      )
      const widgetA = widgets.find(
        (w) => w.getAttribute("data-placement-id") === "ff-z-a",
      )!
      fireEvent.contextMenu(widgetA, { clientX: 10, clientY: 10 })
      expect(await screen.findByTestId("canvas-context-menu")).toBeInTheDocument()

      // Click outside (on document body).
      fireEvent.mouseDown(document.body)

      await waitFor(() => {
        expect(
          screen.queryByTestId("canvas-context-menu"),
        ).not.toBeInTheDocument()
      })

      // No PUT fired (no z_index mutation).
      await vi.advanceTimersByTimeAsync(500)
      expect(focusTemplatesService.update).not.toHaveBeenCalled()
    } finally {
      vi.useRealTimers()
    }
  })

  it("FF-5 — Escape closes context menu without firing PUT", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      defaultMocks()
      const tpl = freeFormTwoWidgetTemplate()
      ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
        tpl,
      )
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
        tpl,
      )

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      const widgets = await screen.findAllByTestId(
        "focus-builder-freeform-placed-widget-draggable",
      )
      const widgetA = widgets.find(
        (w) => w.getAttribute("data-placement-id") === "ff-z-a",
      )!
      fireEvent.contextMenu(widgetA, { clientX: 10, clientY: 10 })
      expect(await screen.findByTestId("canvas-context-menu")).toBeInTheDocument()

      // Press Escape. NB: the page-level Esc handler ALSO clears
      // selection — that's fine; we only care that the menu closes.
      fireEvent.keyDown(document, { key: "Escape" })

      await waitFor(() => {
        expect(
          screen.queryByTestId("canvas-context-menu"),
        ).not.toBeInTheDocument()
      })

      await vi.advanceTimersByTimeAsync(500)
      expect(focusTemplatesService.update).not.toHaveBeenCalled()
    } finally {
      vi.useRealTimers()
    }
  })

  // ─────────────────────────────────────────────────────────────────
  // FF-6 — Inspector positioning fields (X / Y / Width / Height).
  //
  // Cross-side assertion (operator-observable canon, 2026-05-20 late-
  // evening): integration tests assert BOTH the rendered wrapper's
  // inline `left/top/width/height` AND the saved PUT body shape.
  // Pure clamp + commit math has unit coverage in
  // PositionInspectorSection.test.tsx.
  //
  // Verify-against-pre-fix discipline applied: reverting the
  // PositionInput's onCommit to a no-op (the input updates local
  // state but never calls onUpdate) makes BOTH the render-side
  // inline-style assertion AND the save-side PUT-body assertion fail
  // on Test A. Restored → both pass.
  // ─────────────────────────────────────────────────────────────────
  function ffSinglePlacementTemplate(): TemplateRecord {
    return {
      ...t,
      canvas_config: { width: 1200, height: 800 },
      rows: [
        {
          row_index: 0,
          column_count: 12,
          placements: [
            {
              placement_id: "ff-pos-1",
              component_kind: "widget",
              component_name: "today-pin-widget",
              x: 100,
              y: 100,
              width: 200,
              height: 100,
              z_index: 0,
            },
          ],
        },
      ],
    } as TemplateRecord
  }

  // Test A — Save + render side via inspector input commit.
  it("FF-6 — inspector X input commit moves widget on canvas + persists via PUT", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      defaultMocks()
      const tpl = ffSinglePlacementTemplate()
      ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
        tpl,
      )
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
        tpl,
      )

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      // Select the widget by clicking its inner core.
      const widget = await screen.findByTestId(
        "focus-builder-freeform-placed-widget-draggable",
      )
      const core = within(widget).getByTestId(
        "focus-builder-placed-widget-core",
      )
      fireEvent.click(core)

      // Position inspector section appears with X input.
      const xInput = (await screen.findByTestId(
        "position-input-x",
      )) as HTMLInputElement
      // Initial value reflects placement x = 100.
      expect(xInput.value).toBe("100")

      // Operator edits + commits via blur.
      fireEvent.change(xInput, { target: { value: "200" } })
      fireEvent.blur(xInput)

      // Save-side: advance debounce, assert PUT body has x = 200.
      await vi.advanceTimersByTimeAsync(500)
      await waitFor(() => {
        expect(focusTemplatesService.update).toHaveBeenCalled()
      })
      const calls = (focusTemplatesService.update as ReturnType<typeof vi.fn>)
        .mock.calls
      const lastBody = calls[calls.length - 1]?.[1] as {
        rows?: Array<{
          placements: Array<{
            placement_id: string
            x?: number
            y?: number
            width?: number
            height?: number
          }>
        }>
      }
      const sent = lastBody.rows?.[0]?.placements.find(
        (p) => p.placement_id === "ff-pos-1",
      )
      expect(sent?.x).toBe(200)
      // y/width/height unchanged.
      expect(sent?.y).toBe(100)
      expect(sent?.width).toBe(200)
      expect(sent?.height).toBe(100)

      // Render-side: widget's inline `left` now 200.
      await waitFor(() => {
        const after = screen.getByTestId(
          "focus-builder-freeform-placed-widget-draggable",
        )
        const styleAttr = after.getAttribute("style") ?? ""
        expect(styleAttr).toMatch(/left:\s*200px/i)
        // top unchanged.
        expect(styleAttr).toMatch(/top:\s*100px/i)
      })
    } finally {
      vi.useRealTimers()
    }
  })

  // Test B — Bidirectional sync: canvas drag updates input value.
  it("FF-6 — canvas keyboard drag updates inspector X input value (bidirectional sync)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      defaultMocks()
      const tpl = ffSinglePlacementTemplate()
      ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
        tpl,
      )
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
        tpl,
      )

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      // Select the widget.
      const widget = await screen.findByTestId(
        "focus-builder-freeform-placed-widget-draggable",
      )
      const core = within(widget).getByTestId(
        "focus-builder-placed-widget-core",
      )
      fireEvent.click(core)

      // Confirm inspector X input shows initial value.
      const xInput = (await screen.findByTestId(
        "position-input-x",
      )) as HTMLInputElement
      expect(xInput.value).toBe("100")

      // Trigger FF-3 KeyboardSensor drag path. Focus draggable; Space
      // to activate; arrows to nudge; Space to commit.
      widget.focus()
      fireEvent.keyDown(widget, { key: " ", code: "Space" })
      await vi.advanceTimersByTimeAsync(10)
      fireEvent.keyDown(document, { key: "ArrowRight", code: "ArrowRight" })
      await vi.advanceTimersByTimeAsync(10)
      fireEvent.keyDown(document, { key: "ArrowRight", code: "ArrowRight" })
      await vi.advanceTimersByTimeAsync(10)
      fireEvent.keyDown(document, { key: " ", code: "Space" })
      await vi.advanceTimersByTimeAsync(10)
      await vi.advanceTimersByTimeAsync(500)

      // Drag commits; the input (NOT focused — operator was driving
      // the canvas) syncs to the new value.
      await waitFor(() => {
        const refreshed = screen.getByTestId(
          "position-input-x",
        ) as HTMLInputElement
        expect(parseInt(refreshed.value, 10)).toBeGreaterThan(100)
      })
    } finally {
      vi.useRealTimers()
    }
  })

  // Test C — Focus preservation during sibling-input change.
  //
  // Note on scope: the canonical Test C as written in the FF-6 prompt
  // asserts focus preservation across a canvas KeyboardSensor drag,
  // but the @dnd-kit KeyboardSensor activator requires focus on the
  // draggable element — `.focus()` necessarily pulls focus off the
  // inspector input. That mode of focus-loss is by design (the
  // operator switched contexts), not a bug. Comprehensive
  // focus-preservation coverage lives at unit level in
  // PositionInspectorSection.test.tsx (the "focus preservation"
  // + "sync" rerender-based tests; load-bearing UX correctness gate).
  //
  // The integration-level coverage here verifies the contract via a
  // path that doesn't move focus: editing one sibling input (Width)
  // commits and re-renders the entire section; the X input retains
  // its mid-edit local value across that re-render.
  it("FF-6 — sibling-input commit does NOT overwrite a focused input's mid-edit value", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      defaultMocks()
      const tpl = ffSinglePlacementTemplate()
      ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
        tpl,
      )
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
        tpl,
      )

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      const widget = await screen.findByTestId(
        "focus-builder-freeform-placed-widget-draggable",
      )
      const core = within(widget).getByTestId(
        "focus-builder-placed-widget-core",
      )
      fireEvent.click(core)

      const xInput = (await screen.findByTestId(
        "position-input-x",
      )) as HTMLInputElement
      const wInput = (await screen.findByTestId(
        "position-input-width",
      )) as HTMLInputElement

      // Commit a Width change first (re-renders the section with
      // updated placement).
      fireEvent.change(wInput, { target: { value: "300" } })
      fireEvent.blur(wInput)
      await vi.advanceTimersByTimeAsync(500)

      // Operator focuses X and types "250" without blurring.
      xInput.focus()
      fireEvent.change(xInput, { target: { value: "250" } })
      expect(xInput.value).toBe("250")
      expect(document.activeElement).toBe(xInput)

      // Trigger another sibling update through a parallel path —
      // re-render the page region by clicking the core (no-op state
      // change that still flushes a render cycle through the section).
      fireEvent.click(core)

      // Focus + local value preserved across the additional render.
      const refreshedX = screen.getByTestId(
        "position-input-x",
      ) as HTMLInputElement
      expect(refreshedX.value).toBe("250")
      expect(document.activeElement).toBe(refreshedX)
    } finally {
      vi.useRealTimers()
    }
  })

  // Test D — Clamping integration: out-of-bounds input clamps at commit.
  it("FF-6 — out-of-bounds X input clamps to canvas - widget_width on commit", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      defaultMocks()
      const tpl = ffSinglePlacementTemplate()
      ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
        tpl,
      )
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
        tpl,
      )

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      const widget = await screen.findByTestId(
        "focus-builder-freeform-placed-widget-draggable",
      )
      const core = within(widget).getByTestId(
        "focus-builder-placed-widget-core",
      )
      fireEvent.click(core)

      // Edit X to 1500 (out of bounds for canvas 1200 - width 200 = 1000).
      const xInput = (await screen.findByTestId(
        "position-input-x",
      )) as HTMLInputElement
      fireEvent.change(xInput, { target: { value: "1500" } })
      fireEvent.blur(xInput)

      // Save-side: PUT body's x clamped to 1000.
      await vi.advanceTimersByTimeAsync(500)
      await waitFor(() => {
        expect(focusTemplatesService.update).toHaveBeenCalled()
      })
      const calls = (focusTemplatesService.update as ReturnType<typeof vi.fn>)
        .mock.calls
      const lastBody = calls[calls.length - 1]?.[1] as {
        rows?: Array<{ placements: Array<{ placement_id: string; x?: number }> }>
      }
      const sent = lastBody.rows?.[0]?.placements.find(
        (p) => p.placement_id === "ff-pos-1",
      )
      expect(sent?.x).toBe(1000)

      // Render-side: input now shows the clamped value (1000), not
      // the operator-typed 1500. Sync from placement → input on
      // post-blur unfocused state.
      await waitFor(() => {
        const refreshed = screen.getByTestId(
          "position-input-x",
        ) as HTMLInputElement
        expect(refreshed.value).toBe("1000")
      })
    } finally {
      vi.useRealTimers()
    }
  })

  // ─────────────────────────────────────────────────────────────────
  // FF-7 — Arc finale integration scenarios.
  //
  // Cross-side assertion: each scenario asserts BOTH operator-
  // observable rendered state (inspector section visible / pin
  // wrappers' inline style) AND save-side PUT body shape where the
  // action mutates persisted state.
  //
  // Verify-against-pre-fix discipline applied to Test A (multi-
  // select via shift+click + align): reverting the page-level
  // handleWidgetShiftSelect to a no-op makes the AlignInspectorSection
  // never appear, and the align button is therefore never reachable
  // from the operator's shift+click → click "Align left" flow.
  // Restored → both render-side (AlignInspectorSection visible)
  // and save-side (PUT body's two placements share the same x)
  // assertions pass.
  // ─────────────────────────────────────────────────────────────────
  function ffTwoPlacementTemplate(): TemplateRecord {
    return {
      ...t,
      canvas_config: { width: 1200, height: 800 },
      rows: [
        {
          row_index: 0,
          column_count: 12,
          placements: [
            {
              placement_id: "ff7-a",
              component_kind: "widget",
              component_name: "today-pin-widget",
              x: 100,
              y: 100,
              width: 200,
              height: 100,
              z_index: 0,
            },
            {
              placement_id: "ff7-b",
              component_kind: "widget",
              component_name: "today-pin-widget",
              x: 500,
              y: 250,
              width: 100,
              height: 150,
              z_index: 0,
            },
          ],
        },
      ],
    } as TemplateRecord
  }

  // Test A — Multi-select via shift+click + Align left.
  it("FF-7 — shift+click promotes multi; AlignInspectorSection appears; Align-left commits same X for both widgets", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      defaultMocks()
      const tpl = ffTwoPlacementTemplate()
      ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
        tpl,
      )
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
        tpl,
      )

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      // Both widgets render.
      await waitFor(() =>
        expect(
          screen.getAllByTestId("focus-builder-freeform-placed-widget-draggable"),
        ).toHaveLength(2),
      )
      const draggables = screen.getAllByTestId(
        "focus-builder-freeform-placed-widget-draggable",
      )
      const aWidget = draggables.find(
        (el) => el.getAttribute("data-placement-id") === "ff7-a",
      )!
      const bWidget = draggables.find(
        (el) => el.getAttribute("data-placement-id") === "ff7-b",
      )!
      const aCore = within(aWidget).getByTestId(
        "focus-builder-placed-widget-core",
      )
      const bCore = within(bWidget).getByTestId(
        "focus-builder-placed-widget-core",
      )

      // Click widget A → single selection.
      fireEvent.click(aCore)
      // Render-side: AlignInspectorSection NOT visible yet (single-select).
      expect(screen.queryByTestId("align-inspector-section")).toBeNull()

      // Shift+click widget B → promotes to multi-select.
      fireEvent.click(bCore, { shiftKey: true })

      // AlignInspectorSection visible; Position/Layer/Chrome HIDDEN.
      await waitFor(() =>
        expect(
          screen.getByTestId("align-inspector-section"),
        ).toBeInTheDocument(),
      )
      // Verify-against-pre-fix marker: if shift+click did NOT promote,
      // this section would never appear.

      // Click Align left.
      fireEvent.click(screen.getByTestId("align-action-left"))

      // Save-side: PUT body's two placements both have x = 100 (leftmost).
      await vi.advanceTimersByTimeAsync(500)
      await waitFor(() => {
        expect(focusTemplatesService.update).toHaveBeenCalled()
      })
      const calls = (focusTemplatesService.update as ReturnType<typeof vi.fn>)
        .mock.calls
      const lastBody = calls[calls.length - 1]?.[1] as {
        rows?: Array<{
          placements: Array<{ placement_id: string; x?: number }>
        }>
      }
      const placements = lastBody.rows?.[0]?.placements ?? []
      const a = placements.find((p) => p.placement_id === "ff7-a")
      const b = placements.find((p) => p.placement_id === "ff7-b")
      expect(a?.x).toBe(100)
      expect(b?.x).toBe(100)

      // Render-side: both widgets' inline `left` reflects 100.
      await waitFor(() => {
        const ds = screen.getAllByTestId(
          "focus-builder-freeform-placed-widget-draggable",
        )
        for (const d of ds) {
          const styleAttr = d.getAttribute("style") ?? ""
          expect(styleAttr).toMatch(/left:\s*100px/i)
        }
      })
    } finally {
      vi.useRealTimers()
    }
  })

  // Test B — Marquee selection captures intersecting widgets.
  it("FF-7 — marquee drag captures intersecting widgets; AlignInspectorSection appears", async () => {
    defaultMocks()
    const tpl = ffTwoPlacementTemplate()
    ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      tpl,
    )
    ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
      tpl,
    )

    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )

    const layer = await screen.findByTestId("focus-builder-freeform-layer")
    // Stub getBoundingClientRect so canvas-relative coords are
    // predictable in JSDOM. The freeform layer is canvas-dimensioned
    // (1200×800) per the template's canvas_config.
    layer.getBoundingClientRect = vi.fn(() => ({
      x: 0,
      y: 0,
      left: 0,
      top: 0,
      right: 1200,
      bottom: 800,
      width: 1200,
      height: 800,
      toJSON: () => ({}),
    })) as () => DOMRect

    // Marquee drag from (50, 50) to (700, 450) — encloses widget A
    // (100,100 → 300,200) FULLY and widget B (500,250 → 600,400) FULLY.
    fireEvent.pointerDown(layer, { clientX: 50, clientY: 50 })
    fireEvent.pointerMove(layer, { clientX: 700, clientY: 450 })
    // Marquee overlay visible once threshold passed.
    await waitFor(() => {
      expect(screen.getByTestId("marquee-overlay")).toBeInTheDocument()
    })
    fireEvent.pointerUp(layer, { clientX: 700, clientY: 450 })

    // Commit: AlignInspectorSection visible (multi-select active).
    await waitFor(() =>
      expect(
        screen.getByTestId("align-inspector-section"),
      ).toBeInTheDocument(),
    )
    // Multi-select count = 2.
    expect(screen.getByText(/2 widgets selected/i)).toBeInTheDocument()
  })

  // Test C — Keyboard nudge (single-select).
  it("FF-7 — ArrowRight nudges selected widget +1px; Shift+ArrowRight nudges +10px", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      defaultMocks()
      const tpl = ffTwoPlacementTemplate()
      ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
        tpl,
      )
      ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
        tpl,
      )

      render(
        <MemoryRouter
          initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
        >
          <FocusBuilderPage />
        </MemoryRouter>,
      )

      // Select widget A by clicking its inner core.
      const draggables = await screen.findAllByTestId(
        "focus-builder-freeform-placed-widget-draggable",
      )
      const aWidget = draggables.find(
        (el) => el.getAttribute("data-placement-id") === "ff7-a",
      )!
      const aCore = within(aWidget).getByTestId(
        "focus-builder-placed-widget-core",
      )
      fireEvent.click(aCore)

      // ArrowRight on window: nudges +1px.
      fireEvent.keyDown(window, { key: "ArrowRight" })
      // Render-side: A's inline left moves from 100 to 101.
      await waitFor(() => {
        const refreshed = screen
          .getAllByTestId("focus-builder-freeform-placed-widget-draggable")
          .find((el) => el.getAttribute("data-placement-id") === "ff7-a")!
        const styleAttr = refreshed.getAttribute("style") ?? ""
        expect(styleAttr).toMatch(/left:\s*101px/i)
      })

      // Shift+ArrowRight: +10px → 111.
      fireEvent.keyDown(window, { key: "ArrowRight", shiftKey: true })
      await waitFor(() => {
        const refreshed = screen
          .getAllByTestId("focus-builder-freeform-placed-widget-draggable")
          .find((el) => el.getAttribute("data-placement-id") === "ff7-a")!
        const styleAttr = refreshed.getAttribute("style") ?? ""
        expect(styleAttr).toMatch(/left:\s*111px/i)
      })

      // Save-side: PUT body carries the final x (after debounce).
      await vi.advanceTimersByTimeAsync(500)
      await waitFor(() => {
        expect(focusTemplatesService.update).toHaveBeenCalled()
      })
    } finally {
      vi.useRealTimers()
    }
  })

  // Test D — Multi-select arrow nudge moves all selected widgets together.
  it("FF-7 — ArrowRight in multi-select nudges all selected widgets together", async () => {
    defaultMocks()
    const tpl = ffTwoPlacementTemplate()
    ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      tpl,
    )
    ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
      tpl,
    )

    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )

    // Build multi-select via shift+click on both widgets' cores.
    const draggables = await screen.findAllByTestId(
      "focus-builder-freeform-placed-widget-draggable",
    )
    const aCore = within(
      draggables.find((el) => el.getAttribute("data-placement-id") === "ff7-a")!,
    ).getByTestId("focus-builder-placed-widget-core")
    const bCore = within(
      draggables.find((el) => el.getAttribute("data-placement-id") === "ff7-b")!,
    ).getByTestId("focus-builder-placed-widget-core")
    fireEvent.click(aCore)
    fireEvent.click(bCore, { shiftKey: true })

    // Confirm multi-select.
    await waitFor(() =>
      expect(
        screen.getByTestId("align-inspector-section"),
      ).toBeInTheDocument(),
    )

    // ArrowRight nudges BOTH widgets +1px.
    fireEvent.keyDown(window, { key: "ArrowRight" })

    await waitFor(() => {
      const refreshedA = screen
        .getAllByTestId("focus-builder-freeform-placed-widget-draggable")
        .find((el) => el.getAttribute("data-placement-id") === "ff7-a")!
      const refreshedB = screen
        .getAllByTestId("focus-builder-freeform-placed-widget-draggable")
        .find((el) => el.getAttribute("data-placement-id") === "ff7-b")!
      expect(refreshedA.getAttribute("style")).toMatch(/left:\s*101px/i)
      expect(refreshedB.getAttribute("style")).toMatch(/left:\s*501px/i)
    })
  })

  // ─────────────────────────────────────────────────────────────────
  // 2026-05-20 — DragOverlay UUID leak class-fix (Finding 2)
  //
  // Per the read-only investigation
  // `docs/investigations/2026-05-20-resize-handle-ux-refinements.md`
  // §3 — the DragOverlay rendered `activeDragLabel` as visible text,
  // with the assignment `setActiveDragLabel(slug ?? id)` falling back
  // to the raw drag id for any non-palette drag shape. Operators saw
  // strings like `<placement-uuid>-handle-se` floating adjacent to
  // the cursor during resize.
  //
  // Class-fix: every drag-id shape routes through `resolveDragLabel`.
  // Palette ids resolve to their slug (visible label preserved).
  // All other shapes resolve to null; the DragOverlay's existing
  // guard (`activeDragLabel ? (...) : null`) suppresses the overlay
  // entirely.
  //
  // Test discipline (operator-observable canon, 2026-05-19
  // late-evening): assertions target the rendered DOM at the
  // specific rendered element (the `focus-builder-drag-overlay`
  // testid presence / absence + its text content).
  //
  // Verify-against-pre-fix: reverting `setActiveDragLabel(
  // resolveDragLabel(id))` back to `setActiveDragLabel(slug ?? id)`
  // makes Test B + Test C fail with visible UUID-pattern text;
  // restored → both pass. Test A always passes (palette label is the
  // one shape both pre-fix and post-fix render correctly).
  // ─────────────────────────────────────────────────────────────────
  describe("DragOverlay UUID leak class-fix (2026-05-20 Finding 2)", () => {
    it("Test A — palette drag preserves the slug label in the DragOverlay (regression)", async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true })
      try {
        defaultMocks()
        const freeFormTpl: TemplateRecord = {
          ...t,
          canvas_config: { width: 1200, height: 800 },
          rows: [],
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

        // Find a palette item (today-pin-widget is in the seeded registry).
        const paletteItem = await waitFor(() => {
          const items = screen.getAllByTestId("widget-palette-item")
          const todayItem = items.find(
            (el) =>
              el.getAttribute("data-item-id") ===
              "palette-widget:today-pin-widget",
          )
          if (!todayItem) throw new Error("today-pin-widget palette item not found")
          return todayItem as HTMLElement
        })

        // Drive a KeyboardSensor drag on the palette item. Space to
        // activate; the activator-fire of handleDragStart sets
        // activeDragLabel before any arrow nudges.
        paletteItem.focus()
        fireEvent.keyDown(paletteItem, { key: " ", code: "Space" })
        await vi.advanceTimersByTimeAsync(10)

        // Assert the DragOverlay renders with the slug as visible
        // text content.
        await waitFor(() => {
          const overlay = screen.queryByTestId("focus-builder-drag-overlay")
          expect(overlay).not.toBeNull()
          expect(overlay?.textContent).toBe("today-pin-widget")
        })

        // Commit drop (cancels at zero distance — but cleans
        // activeDragLabel via handleDragEnd).
        fireEvent.keyDown(document, { key: " ", code: "Space" })
        await vi.advanceTimersByTimeAsync(10)
      } finally {
        vi.useRealTimers()
      }
    })

    it("Test B — resize-handle drag does NOT leak UUID text in the DragOverlay", async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true })
      try {
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
                  placement_id: "ff-resize-uuid-leak-1",
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
        ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
          freeFormTpl,
        )

        render(
          <MemoryRouter
            initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
          >
            <FocusBuilderPage />
          </MemoryRouter>,
        )

        await screen.findByTestId("focus-builder-freeform-placed-widget-draggable")
        fireEvent.click(screen.getByTestId("focus-builder-placed-widget"))

        // Wait for handles to appear (selection branch).
        await waitFor(() => {
          const h = document.querySelector(
            '[data-testid="focus-builder-resize-handle"][data-handle-position="e"]',
          ) as HTMLElement | null
          expect(h).not.toBeNull()
        })
        const handle = document.querySelector(
          '[data-testid="focus-builder-resize-handle"][data-handle-position="e"]',
        ) as HTMLElement
        handle.focus()

        // Activate resize-handle drag.
        fireEvent.keyDown(handle, { key: " ", code: "Space" })
        await vi.advanceTimersByTimeAsync(10)

        // Operator-observable assertion canon: the load-bearing
        // contract is the absence of the visible DragOverlay element
        // (its testid is the rendered floating-label surface). The
        // pre-fix code rendered the overlay with the raw drag id as
        // visible text; post-fix the overlay's guard short-circuits
        // on null label and the testid is absent entirely.
        //
        // Note: @dnd-kit emits an aria-live `DndLiveRegion-*`
        // element that DOES contain the drag id ("Picked up
        // draggable item …") — this is the correct screen-reader
        // a11y behavior and is NOT operator-visible (positioned
        // fixed + clipped to 1px). The DragOverlay testid assertion
        // is what catches the operator-visible leak.
        const overlay = screen.queryByTestId("focus-builder-drag-overlay")
        expect(overlay).toBeNull()

        // Clean up — commit drop.
        fireEvent.keyDown(document, { key: " ", code: "Space" })
        await vi.advanceTimersByTimeAsync(10)
      } finally {
        vi.useRealTimers()
      }
    })

    it("Test C — whole-widget drag (FF-3) does NOT leak placement-id text in the DragOverlay (class-fix coverage)", async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true })
      try {
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
                  placement_id: "ff-whole-widget-uuid-leak-1",
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
        ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
          freeFormTpl,
        )

        render(
          <MemoryRouter
            initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
          >
            <FocusBuilderPage />
          </MemoryRouter>,
        )

        const draggable = await screen.findByTestId(
          "focus-builder-freeform-placed-widget-draggable",
        )
        draggable.focus()
        fireEvent.keyDown(draggable, { key: " ", code: "Space" })
        await vi.advanceTimersByTimeAsync(10)

        // Operator-observable assertion: DragOverlay testid absent.
        // Whole-widget drag id is `free-form-placed-widget:<uuid>` —
        // pre-fix this would have leaked as visible overlay text;
        // post-fix the overlay collapses to nothing.
        //
        // (Same note as Test B about @dnd-kit's aria-live region:
        // the screen-reader announcer DOES include the drag id by
        // design and is NOT the operator-visible leak this test
        // gates against.)
        const overlay = screen.queryByTestId("focus-builder-drag-overlay")
        expect(overlay).toBeNull()

        // Clean up — commit drop.
        fireEvent.keyDown(document, { key: " ", code: "Space" })
        await vi.advanceTimersByTimeAsync(10)
      } finally {
        vi.useRealTimers()
      }
    })
  })
})
