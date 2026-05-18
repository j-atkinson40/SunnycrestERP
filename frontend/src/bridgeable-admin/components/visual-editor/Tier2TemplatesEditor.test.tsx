/**
 * Tier2TemplatesEditor smoke tests (sub-arc C-2.2a).
 *
 * Verifies the READ-ONLY canvas seam:
 *   - empty state renders when the API returns no templates
 *   - browser list renders + selection wires through to the preview
 *   - inspector placeholder mounts (no inspector content yet)
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

vi.mock("@/bridgeable-admin/services/focus-templates-service", () => ({
  focusTemplatesService: {
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    usage: vi.fn(),
    // Sub-arc C-2.3 — default resolve mock surfaces empty sources so
    // the inheritance chrome renders neutral by default. Per-test
    // overrides set this to a richer payload to exercise the
    // dimmed/explicit treatment + reset ↺ affordance.
    resolve: vi.fn().mockResolvedValue({
      template_id: "tpl-1",
      template_slug: "stub",
      template_version: 1,
      template_scope: "platform_default",
      template_vertical: null,
      core_id: "core-1",
      core_slug: "stub-core",
      core_version: 1,
      core_registered_component: {},
      rows: [],
      canvas_config: {},
      resolved_chrome: null,
      resolved_substrate: null,
      resolved_typography: null,
      sources: {
        template: {},
        core: {},
        tenant: null,
        chrome_sources: {},
        substrate_sources: {},
        typography_sources: {},
      },
    }),
  },
}))

vi.mock("@/bridgeable-admin/services/focus-cores-service", () => ({
  focusCoresService: {
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
  },
}))

vi.mock("@/bridgeable-admin/lib/admin-api", () => ({
  adminApi: {
    get: vi.fn().mockResolvedValue({ data: { tokens: {} } }),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock("@/bridgeable-admin/services/verticals-service", () => ({
  verticalsService: {
    list: vi.fn().mockResolvedValue([
      {
        slug: "funeral_home",
        display_name: "Funeral Home",
        description: null,
        status: "published",
        icon: null,
        sort_order: 0,
        created_at: "",
        updated_at: "",
      },
    ]),
    get: vi.fn(),
    update: vi.fn(),
  },
}))

import { focusTemplatesService } from "@/bridgeable-admin/services/focus-templates-service"
import { focusCoresService } from "@/bridgeable-admin/services/focus-cores-service"
import { Tier2TemplatesEditor } from "./Tier2TemplatesEditor"

const onSelectTemplate = vi.fn()
const onDirtyChange = vi.fn()
const onLastSavedChange = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.clearAllMocks()
})

describe("Tier2TemplatesEditor — empty state", () => {
  it("renders the templates-empty CTA when the API returns no rows", async () => {
    ;(focusTemplatesService.list as ReturnType<typeof vi.fn>).mockResolvedValue(
      [],
    )
    render(
      <MemoryRouter><Tier2TemplatesEditor
        selectedTemplateId={null}
        onSelectTemplate={onSelectTemplate}
        onDirtyChange={onDirtyChange}
        onLastSavedChange={onLastSavedChange}
      /></MemoryRouter>,
    )
    expect(await screen.findByTestId("templates-empty")).toBeInTheDocument()
    expect(screen.getByTestId("tier2-no-selection")).toBeInTheDocument()
    // Post-C-2.2b: inspector is now the editable three-section panel
    // when a template is selected. With no selection, the right rail
    // renders an empty-state hint instead.
    expect(screen.getByTestId("tier2-inspector-empty")).toBeInTheDocument()
  })

  it("reports false dirty + null last-saved on mount (no template selected)", async () => {
    ;(focusTemplatesService.list as ReturnType<typeof vi.fn>).mockResolvedValue(
      [],
    )
    render(
      <MemoryRouter><Tier2TemplatesEditor
        selectedTemplateId={null}
        onSelectTemplate={onSelectTemplate}
        onDirtyChange={onDirtyChange}
        onLastSavedChange={onLastSavedChange}
      /></MemoryRouter>,
    )
    await screen.findByTestId("templates-empty")
    expect(onDirtyChange).toHaveBeenCalledWith(false)
    expect(onLastSavedChange).toHaveBeenCalledWith(null)
  })
})

describe("Tier2TemplatesEditor — browser + preview", () => {
  it("renders the template row + wires click through to onSelectTemplate", async () => {
    ;(focusTemplatesService.list as ReturnType<typeof vi.fn>).mockResolvedValue(
      [
        {
          id: "tpl-1",
          scope: "platform_default",
          vertical: null,
          template_slug: "default-scribe",
          display_name: "Default Scribe",
          description: "scribe variant",
          inherits_from_core_id: "core-1",
          inherits_from_core_version: 1,
          rows: [],
          canvas_config: {},
          chrome_overrides: {},
          substrate: {},
          typography: {},
          version: 1,
          is_active: true,
          created_at: "",
          updated_at: "",
        },
      ],
    )
    render(
      <MemoryRouter><Tier2TemplatesEditor
        selectedTemplateId={null}
        onSelectTemplate={onSelectTemplate}
        onDirtyChange={onDirtyChange}
        onLastSavedChange={onLastSavedChange}
      /></MemoryRouter>,
    )
    const row = await screen.findByTestId("template-row-default-scribe")
    expect(row).toBeInTheDocument()
    fireEvent.click(row)
    expect(onSelectTemplate).toHaveBeenCalledWith("tpl-1")
  })

  it("renders the preview card when a template is selected", async () => {
    ;(focusTemplatesService.list as ReturnType<typeof vi.fn>).mockResolvedValue(
      [
        {
          id: "tpl-2",
          scope: "platform_default",
          vertical: null,
          template_slug: "frosted-scribe",
          display_name: "Frosted Scribe",
          description: "atmospheric",
          inherits_from_core_id: "core-2",
          inherits_from_core_version: 3,
          rows: [],
          canvas_config: {},
          chrome_overrides: { preset: "frosted" },
          substrate: { preset: "morning-warm", intensity: 70 },
          typography: { preset: "headline" },
          version: 2,
          is_active: true,
          created_at: "",
          updated_at: "",
        },
      ],
    )
    ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "tpl-2",
      scope: "platform_default",
      vertical: null,
      template_slug: "frosted-scribe",
      display_name: "Frosted Scribe",
      description: "atmospheric",
      inherits_from_core_id: "core-2",
      inherits_from_core_version: 3,
      rows: [],
      canvas_config: {},
      chrome_overrides: { preset: "frosted" },
      substrate: { preset: "morning-warm", intensity: 70 },
      typography: { preset: "headline" },
      version: 2,
      is_active: true,
      created_at: "",
      updated_at: "",
    })
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "core-2",
      core_slug: "scribe",
      display_name: "Scribe Core",
      description: null,
      registered_component_kind: "focus",
      registered_component_name: "scribe",
      default_starting_column: 1,
      default_column_span: 6,
      default_row_index: 0,
      min_column_span: 4,
      max_column_span: 12,
      canvas_config: {},
      chrome: { preset: "card", elevation: 37 },
      version: 1,
      is_active: true,
      created_at: "",
      updated_at: "",
    })
    render(
      <MemoryRouter><Tier2TemplatesEditor
        selectedTemplateId="tpl-2"
        onSelectTemplate={onSelectTemplate}
        onDirtyChange={onDirtyChange}
        onLastSavedChange={onLastSavedChange}
      /></MemoryRouter>,
    )
    await waitFor(() =>
      expect(screen.getByTestId("tier2-preview-card")).toBeInTheDocument(),
    )
    // "Frosted Scribe" appears in both the browser row + preview card.
    expect(screen.getAllByText("Frosted Scribe").length).toBeGreaterThan(0)
    // Post-C-2.2b: three-section editable inspector replaces the
    // C-2.2a "Coming in sub-arc C-2.2b" placeholder.
    expect(screen.getByTestId("chrome-preset-picker")).toBeInTheDocument()
    expect(screen.getByTestId("substrate-preset-picker")).toBeInTheDocument()
    expect(screen.getByTestId("typography-preset-picker")).toBeInTheDocument()
  })
})

describe("Tier2TemplatesEditor — canvas substrate + typography wiring (C-2.2a.1)", () => {
  // Integration test: the load-bearing addition closing the C-2.2a gap.
  //
  // C-2.2a shipped substrate-resolver + typography-resolver as new
  // modules with 47 unit tests passing. But no test verified the
  // editor's canvas ACTUALLY rendered with those resolved styles
  // applied — the same class of gap as C-2.1.4 (resolver works in
  // isolation; wiring to DOM was never asserted).
  //
  // This suite asserts the rendered DOM carries:
  //   - data-testid="tier2-canvas" on the substrate-bearing wrapper
  //   - background inline style containing "gradient" when the
  //     template carries an atmospheric substrate preset
  //   - typography CSS custom properties / font-weight on the
  //     heading + body nodes inside the canvas
  it("applies substrate gradient to data-testid=tier2-canvas when template has morning-warm preset", async () => {
    ;(focusTemplatesService.list as ReturnType<typeof vi.fn>).mockResolvedValue(
      [
        {
          id: "tpl-canvas-1",
          scope: "vertical_default",
          vertical: "funeral_home",
          template_slug: "scheduling-fh",
          display_name: "Scheduling FH",
          description: "atmospheric canvas",
          inherits_from_core_id: "core-canvas-1",
          inherits_from_core_version: 1,
          rows: [],
          canvas_config: {},
          chrome_overrides: {},
          substrate: { preset: "morning-warm", intensity: 70 },
          typography: { preset: "frosted-text" },
          version: 1,
          is_active: true,
          created_at: "",
          updated_at: "",
        },
      ],
    )
    ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "tpl-canvas-1",
      scope: "vertical_default",
      vertical: "funeral_home",
      template_slug: "scheduling-fh",
      display_name: "Scheduling FH",
      description: "atmospheric canvas",
      inherits_from_core_id: "core-canvas-1",
      inherits_from_core_version: 1,
      rows: [],
      canvas_config: {},
      chrome_overrides: {},
      substrate: { preset: "morning-warm", intensity: 70 },
      typography: { preset: "frosted-text" },
      version: 1,
      is_active: true,
      created_at: "",
      updated_at: "",
    })
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "core-canvas-1",
      core_slug: "scheduling",
      display_name: "Scheduling Core",
      description: null,
      registered_component_kind: "focus",
      registered_component_name: "scheduling",
      default_starting_column: 1,
      default_column_span: 6,
      default_row_index: 0,
      min_column_span: 4,
      max_column_span: 12,
      canvas_config: {},
      chrome: { preset: "card" },
      version: 1,
      is_active: true,
      created_at: "",
      updated_at: "",
    })
    render(
      <MemoryRouter><Tier2TemplatesEditor
        selectedTemplateId="tpl-canvas-1"
        onSelectTemplate={onSelectTemplate}
        onDirtyChange={onDirtyChange}
        onLastSavedChange={onLastSavedChange}
      /></MemoryRouter>,
    )
    const canvas = await screen.findByTestId("tier2-canvas")
    expect(canvas).toBeInTheDocument()
    // resolveSubstrateStyle composes background as a linear-gradient
    // when intensity > 0 and accent tokens resolve. With morning-warm
    // (intensity 70, accent-subtle + status-warning-muted) the
    // gradient string must appear in the inline background style.
    const bg = canvas.style.background || canvas.style.backgroundImage
    expect(bg).toMatch(/gradient/i)
  })

  it("renders the preview card with heading + body typography styles applied", async () => {
    ;(focusTemplatesService.list as ReturnType<typeof vi.fn>).mockResolvedValue(
      [
        {
          id: "tpl-canvas-2",
          scope: "vertical_default",
          vertical: "funeral_home",
          template_slug: "frosted-fh",
          display_name: "Frosted FH",
          description: "typography test",
          inherits_from_core_id: "core-canvas-2",
          inherits_from_core_version: 1,
          rows: [],
          canvas_config: {},
          chrome_overrides: {},
          substrate: { preset: "morning-warm" },
          typography: { preset: "frosted-text" },
          version: 1,
          is_active: true,
          created_at: "",
          updated_at: "",
        },
      ],
    )
    ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "tpl-canvas-2",
      scope: "vertical_default",
      vertical: "funeral_home",
      template_slug: "frosted-fh",
      display_name: "Frosted FH",
      description: "typography test",
      inherits_from_core_id: "core-canvas-2",
      inherits_from_core_version: 1,
      rows: [],
      canvas_config: {},
      chrome_overrides: {},
      substrate: { preset: "morning-warm" },
      typography: { preset: "frosted-text" },
      version: 1,
      is_active: true,
      created_at: "",
      updated_at: "",
    })
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "core-canvas-2",
      core_slug: "scheduling",
      display_name: "Scheduling Core",
      description: null,
      registered_component_kind: "focus",
      registered_component_name: "scheduling",
      default_starting_column: 1,
      default_column_span: 6,
      default_row_index: 0,
      min_column_span: 4,
      max_column_span: 12,
      canvas_config: {},
      chrome: { preset: "card" },
      version: 1,
      is_active: true,
      created_at: "",
      updated_at: "",
    })
    render(
      <MemoryRouter><Tier2TemplatesEditor
        selectedTemplateId="tpl-canvas-2"
        onSelectTemplate={onSelectTemplate}
        onDirtyChange={onDirtyChange}
        onLastSavedChange={onLastSavedChange}
      /></MemoryRouter>,
    )
    await waitFor(() =>
      expect(screen.getByTestId("tier2-preview-card")).toBeInTheDocument(),
    )
    // The canvas wrapper must exist alongside the preview card.
    expect(screen.getByTestId("tier2-canvas")).toBeInTheDocument()
    // Typography preset "frosted-text" resolves heading_weight: 600,
    // body_weight: 500. The heading + body styles are applied inline
    // to the h2 + p inside the preview card.
    const heading = screen.getByText("Frosted FH", { selector: "h2" })
    expect(heading.style.fontWeight).toBe("600")
    const body = screen.getByText("typography test", { selector: "p" })
    expect(body.style.fontWeight).toBe("500")
  })
})

describe("Tier2TemplatesEditor — inspector → canvas live cascade (C-2.2b)", () => {
  /**
   * Integration test locking the editor → canvas wiring contract.
   *
   * The C-2.2b inspector reads from the same useFocusTemplateDraft
   * hook state as the canvas — so any inspector edit must propagate
   * to the rendered DOM in the same React render cycle. These tests
   * assert the wiring is intact: click a substrate preset → canvas
   * background changes; toggle a typography preset → preview card
   * font-weights change; toggle a chrome preset → preview card
   * style changes.
   *
   * Test-fails-against-pre-fix verification (per build prompt
   * requirement): manually rewired the editor to read views from
   * `template.<blob>` instead of the draft variables — the live-
   * cascade tests fail because the canvas no longer responds to
   * inspector edits. Restored the draft-reading wiring to make the
   * tests pass.
   */
  const TEMPLATE_BASE = {
    id: "tpl-live",
    scope: "platform_default" as const,
    vertical: null,
    template_slug: "live-template",
    display_name: "Live Template",
    description: "live cascade test",
    inherits_from_core_id: "core-live",
    inherits_from_core_version: 1,
    rows: [],
    canvas_config: {},
    chrome_overrides: {} as Record<string, unknown>,
    substrate: { preset: "neutral", intensity: 15 } as Record<string, unknown>,
    typography: { preset: "card-text" } as Record<string, unknown>,
    version: 1,
    is_active: true,
    created_at: "",
    updated_at: "",
  }
  const CORE_LIVE = {
    id: "core-live",
    core_slug: "scheduling",
    display_name: "Scheduling Core",
    description: null,
    registered_component_kind: "focus",
    registered_component_name: "scheduling",
    default_starting_column: 1,
    default_column_span: 6,
    default_row_index: 0,
    min_column_span: 4,
    max_column_span: 12,
    canvas_config: {},
    chrome: { preset: "card" } as Record<string, unknown>,
    version: 1,
    is_active: true,
    created_at: "",
    updated_at: "",
  }

  it("canvas substrate updates live when operator picks a substrate preset", async () => {
    ;(focusTemplatesService.list as ReturnType<typeof vi.fn>).mockResolvedValue(
      [TEMPLATE_BASE],
    )
    ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      TEMPLATE_BASE,
    )
    ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
      TEMPLATE_BASE,
    )
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      CORE_LIVE,
    )
    render(
      <MemoryRouter><Tier2TemplatesEditor
        selectedTemplateId="tpl-live"
        onSelectTemplate={onSelectTemplate}
        onDirtyChange={onDirtyChange}
        onLastSavedChange={onLastSavedChange}
      /></MemoryRouter>,
    )
    const canvas = await screen.findByTestId("tier2-canvas")
    const initialBg = canvas.style.background || canvas.style.backgroundImage
    // Neutral preset @ intensity 15 — no accents → plain base.
    expect(initialBg).not.toMatch(/gradient/i)

    // Operator clicks the morning-warm substrate pill.
    fireEvent.click(screen.getByTestId("substrate-pill-morning-warm"))

    // Same render cycle: canvas reflects the new substrate.
    await waitFor(() => {
      const updated = canvas.style.background || canvas.style.backgroundImage
      expect(updated).toMatch(/gradient/i)
    })
  })

  it("preview-card heading weight updates live when typography preset switches", async () => {
    ;(focusTemplatesService.list as ReturnType<typeof vi.fn>).mockResolvedValue(
      [TEMPLATE_BASE],
    )
    ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      TEMPLATE_BASE,
    )
    ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
      TEMPLATE_BASE,
    )
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      CORE_LIVE,
    )
    render(
      <MemoryRouter><Tier2TemplatesEditor
        selectedTemplateId="tpl-live"
        onSelectTemplate={onSelectTemplate}
        onDirtyChange={onDirtyChange}
        onLastSavedChange={onLastSavedChange}
      /></MemoryRouter>,
    )
    await waitFor(() =>
      expect(screen.getByTestId("tier2-preview-card")).toBeInTheDocument(),
    )
    const heading = screen.getByText("Live Template", { selector: "h2" })
    // card-text preset → heading_weight 500.
    expect(heading.style.fontWeight).toBe("500")

    // Switch to headline preset → heading_weight 700.
    fireEvent.click(screen.getByTestId("typography-pill-headline"))

    await waitFor(() => {
      expect(heading.style.fontWeight).toBe("700")
    })
  })

  it("preview-card chrome preset updates live when chrome pill clicked", async () => {
    ;(focusTemplatesService.list as ReturnType<typeof vi.fn>).mockResolvedValue(
      [TEMPLATE_BASE],
    )
    ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      TEMPLATE_BASE,
    )
    ;(focusTemplatesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(
      TEMPLATE_BASE,
    )
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      CORE_LIVE,
    )
    render(
      <MemoryRouter><Tier2TemplatesEditor
        selectedTemplateId="tpl-live"
        onSelectTemplate={onSelectTemplate}
        onDirtyChange={onDirtyChange}
        onLastSavedChange={onLastSavedChange}
      /></MemoryRouter>,
    )
    await waitFor(() =>
      expect(screen.getByTestId("tier2-preview-card")).toBeInTheDocument(),
    )
    // Inherited core has preset=card; no chrome_overrides → cascade = "card".
    // The footer caption renders the active preset slug. Switching to
    // "frosted" must rewrite the caption synchronously.
    expect(screen.getByText(/chrome: card/)).toBeInTheDocument()

    fireEvent.click(screen.getByTestId("preset-pill-frosted"))

    await waitFor(() => {
      expect(screen.getByText(/chrome: frosted/)).toBeInTheDocument()
    })
  })

  it("renders the three inspector sections with lineage hints when template selected", async () => {
    ;(focusTemplatesService.list as ReturnType<typeof vi.fn>).mockResolvedValue(
      [TEMPLATE_BASE],
    )
    ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      TEMPLATE_BASE,
    )
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      CORE_LIVE,
    )
    render(
      <MemoryRouter><Tier2TemplatesEditor
        selectedTemplateId="tpl-live"
        onSelectTemplate={onSelectTemplate}
        onDirtyChange={onDirtyChange}
        onLastSavedChange={onLastSavedChange}
      /></MemoryRouter>,
    )
    // All three preset pickers mount.
    await waitFor(() =>
      expect(screen.getByTestId("chrome-preset-picker")).toBeInTheDocument(),
    )
    expect(screen.getByTestId("substrate-preset-picker")).toBeInTheDocument()
    expect(screen.getByTestId("typography-preset-picker")).toBeInTheDocument()
    // Lineage hint surfaces the inherited core's slug under the Chrome
    // section header — wait for the async core fetch to resolve so the
    // slug appears.
    await waitFor(() => {
      const lineageHints = screen.getAllByTestId("property-section-lineage")
      expect(lineageHints.length).toBeGreaterThanOrEqual(1)
      expect(
        lineageHints.some((el) => el.textContent?.includes("scheduling")),
      ).toBe(true)
    })
  })
})

describe("Tier2TemplatesEditor — error surfacing", () => {
  it("renders templates-error when the list request fails", async () => {
    ;(focusTemplatesService.list as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error("boom"),
    )
    render(
      <MemoryRouter><Tier2TemplatesEditor
        selectedTemplateId={null}
        onSelectTemplate={onSelectTemplate}
        onDirtyChange={onDirtyChange}
        onLastSavedChange={onLastSavedChange}
      /></MemoryRouter>,
    )
    expect(await screen.findByTestId("templates-error")).toHaveTextContent(
      "boom",
    )
  })
})

describe("Tier2TemplatesEditor — sub-arc C-2.2c integration", () => {
  /**
   * Locked-decision #11: integration test for click-to-edit-core flow
   * is mandatory.
   *
   * These tests assert the wiring that makes C-2.2c operationally
   * complete:
   *
   *   - New template button opens CreateTierTwoTemplateModal
   *   - Clicking the inherited-core placement on the canvas opens
   *     the InheritedCoreInspectorPanel side panel
   *   - Side panel surfaces inherited Tier 1 core properties
   *   - Successful template creation closes the modal + selects the
   *     new template
   */
  const TEMPLATE_WITH_CORE = {
    id: "tpl-c22c",
    scope: "vertical_default" as const,
    vertical: "funeral_home",
    template_slug: "c22c-template",
    display_name: "C-2.2c Template",
    description: "integration",
    inherits_from_core_id: "core-c22c",
    inherits_from_core_version: 2,
    rows: [],
    canvas_config: {},
    chrome_overrides: {},
    substrate: { preset: "morning-warm" },
    typography: {},
    version: 1,
    is_active: true,
    created_at: "",
    updated_at: "",
  }
  const CORE_C22C = {
    id: "core-c22c",
    core_slug: "scheduling-kanban-core",
    display_name: "Scheduling Kanban Core",
    description: null,
    registered_component_kind: "focus-template",
    registered_component_name: "SchedulingKanbanCore",
    default_starting_column: 0,
    default_column_span: 12,
    default_row_index: 0,
    min_column_span: 6,
    max_column_span: 12,
    canvas_config: {},
    chrome: { preset: "card", elevation: 40 },
    version: 2,
    is_active: true,
    created_at: "",
    updated_at: "",
  }

  it("New template button opens CreateTierTwoTemplateModal", async () => {
    ;(focusTemplatesService.list as ReturnType<typeof vi.fn>).mockResolvedValue(
      [],
    )
    ;(focusCoresService.list as ReturnType<typeof vi.fn>).mockResolvedValue([
      CORE_C22C,
    ])
    render(
      <MemoryRouter>
        <Tier2TemplatesEditor
          selectedTemplateId={null}
          onSelectTemplate={onSelectTemplate}
          onDirtyChange={onDirtyChange}
          onLastSavedChange={onLastSavedChange}
        />
      </MemoryRouter>,
    )
    const btn = await screen.findByTestId("new-template-button")
    expect(btn).not.toBeDisabled()
    fireEvent.click(btn)
    expect(
      screen.getByTestId("create-tier-two-template-modal"),
    ).toBeInTheDocument()
  })

  it("clicking inherited-core placement opens InheritedCoreInspectorPanel", async () => {
    ;(focusTemplatesService.list as ReturnType<typeof vi.fn>).mockResolvedValue(
      [TEMPLATE_WITH_CORE],
    )
    ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      TEMPLATE_WITH_CORE,
    )
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      CORE_C22C,
    )
    render(
      <MemoryRouter>
        <Tier2TemplatesEditor
          selectedTemplateId="tpl-c22c"
          onSelectTemplate={onSelectTemplate}
          onDirtyChange={onDirtyChange}
          onLastSavedChange={onLastSavedChange}
        />
      </MemoryRouter>,
    )
    // Wait for core fetch to resolve (enables the inherited-core button).
    await waitFor(() => {
      const btn = screen.getByTestId(
        "inherited-core-placement",
      ) as HTMLButtonElement
      expect(btn).not.toBeDisabled()
    })
    fireEvent.click(screen.getByTestId("inherited-core-placement"))
    expect(
      screen.getByTestId("inherited-core-inspector-panel"),
    ).toBeInTheDocument()
    // Panel surfaces the inherited Tier 1 core's display name + slug.
    expect(
      screen.getByTestId("inherited-core-display-name").textContent,
    ).toBe("Scheduling Kanban Core")
    expect(
      screen.getByTestId("inherited-core-slug").textContent,
    ).toBe("scheduling-kanban-core · v2")
  })

  it("closing inherited-core side panel dismisses it without unmounting inspector", async () => {
    ;(focusTemplatesService.list as ReturnType<typeof vi.fn>).mockResolvedValue(
      [TEMPLATE_WITH_CORE],
    )
    ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      TEMPLATE_WITH_CORE,
    )
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      CORE_C22C,
    )
    render(
      <MemoryRouter>
        <Tier2TemplatesEditor
          selectedTemplateId="tpl-c22c"
          onSelectTemplate={onSelectTemplate}
          onDirtyChange={onDirtyChange}
          onLastSavedChange={onLastSavedChange}
        />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(
        (screen.getByTestId("inherited-core-placement") as HTMLButtonElement)
          .disabled,
      ).toBe(false)
    })
    fireEvent.click(screen.getByTestId("inherited-core-placement"))
    expect(
      screen.getByTestId("inherited-core-inspector-panel"),
    ).toBeInTheDocument()
    // Inspector (the always-mounted right rail) is still there.
    expect(screen.getByTestId("tier2-inspector")).toBeInTheDocument()
    fireEvent.click(screen.getByTestId("inherited-core-close"))
    expect(
      screen.queryByTestId("inherited-core-inspector-panel"),
    ).not.toBeInTheDocument()
    // Inspector stays mounted post-close.
    expect(screen.getByTestId("tier2-inspector")).toBeInTheDocument()
  })

  it("successful template creation closes modal + selects the new template", async () => {
    ;(focusTemplatesService.list as ReturnType<typeof vi.fn>).mockResolvedValue(
      [],
    )
    ;(focusCoresService.list as ReturnType<typeof vi.fn>).mockResolvedValue([
      CORE_C22C,
    ])
    ;(focusTemplatesService.create as ReturnType<typeof vi.fn>).mockResolvedValue(
      {
        ...TEMPLATE_WITH_CORE,
        id: "tpl-newly-created",
      },
    )
    render(
      <MemoryRouter>
        <Tier2TemplatesEditor
          selectedTemplateId={null}
          onSelectTemplate={onSelectTemplate}
          onDirtyChange={onDirtyChange}
          onLastSavedChange={onLastSavedChange}
        />
      </MemoryRouter>,
    )
    fireEvent.click(await screen.findByTestId("new-template-button"))
    expect(
      screen.getByTestId("create-tier-two-template-modal"),
    ).toBeInTheDocument()
    // Wait for the core list to populate the picker.
    await waitFor(() => {
      const sel = screen.getByTestId(
        "inherits-from-core-select",
      ) as HTMLSelectElement
      expect(sel.options.length).toBeGreaterThan(1)
    })
    fireEvent.change(screen.getByTestId("inherits-from-core-select"), {
      target: { value: "core-c22c" },
    })
    fireEvent.change(screen.getByTestId("template-slug-input"), {
      target: { value: "new-slug" },
    })
    fireEvent.change(screen.getByTestId("template-display-name-input"), {
      target: { value: "New" },
    })
    fireEvent.click(screen.getByTestId("scope-platform-default"))
    fireEvent.click(screen.getByTestId("create-tier-two-template-submit"))
    await waitFor(() => {
      expect(onSelectTemplate).toHaveBeenCalledWith("tpl-newly-created")
    })
    // Modal dismisses post-create.
    expect(
      screen.queryByTestId("create-tier-two-template-modal"),
    ).not.toBeInTheDocument()
  })

  it("surfaces inherited-core lineage upward via onInheritedCoreChange callback", async () => {
    const onInheritedCoreChange = vi.fn()
    ;(focusTemplatesService.list as ReturnType<typeof vi.fn>).mockResolvedValue(
      [TEMPLATE_WITH_CORE],
    )
    ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      TEMPLATE_WITH_CORE,
    )
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      CORE_C22C,
    )
    render(
      <MemoryRouter>
        <Tier2TemplatesEditor
          selectedTemplateId="tpl-c22c"
          onSelectTemplate={onSelectTemplate}
          onDirtyChange={onDirtyChange}
          onLastSavedChange={onLastSavedChange}
          onInheritedCoreChange={onInheritedCoreChange}
        />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(onInheritedCoreChange).toHaveBeenCalledWith({
        display_name: "Scheduling Kanban Core",
        core_slug: "scheduling-kanban-core",
        version: 2,
      })
    })
  })
})

// ─── Sub-arc C-2.3: per-row inheritance + reset ↺ + controlled panel ───

describe("Tier2TemplatesEditor — sub-arc C-2.3 inheritance chrome", () => {
  const TEMPLATE_C23 = {
    id: "tpl-c23",
    scope: "platform_default" as const,
    vertical: null,
    template_slug: "c23-template",
    display_name: "C-2.3 Template",
    description: null,
    inherits_from_core_id: "core-c23",
    inherits_from_core_version: 1,
    rows: [],
    canvas_config: {},
    // preset is explicit at Tier 2 (overrides core); elevation is
    // absent so it cascades from the inherited core.
    chrome_overrides: { preset: "frosted" } as Record<string, unknown>,
    substrate: {},
    typography: {},
    version: 1,
    is_active: true,
    created_at: "",
    updated_at: "",
  }
  const CORE_C23 = {
    id: "core-c23",
    core_slug: "default-core",
    display_name: "Default Core",
    description: null,
    registered_component_kind: "focus-template",
    registered_component_name: "DefaultCore",
    default_starting_column: 0,
    default_column_span: 12,
    default_row_index: 0,
    min_column_span: 6,
    max_column_span: 12,
    canvas_config: {},
    chrome: { preset: "card", elevation: 40 },
    version: 1,
    is_active: true,
    created_at: "",
    updated_at: "",
  }

  /**
   * Resolver payload — `preset` resolves at Tier 2 (operator-authored
   * override), `elevation` cascades down from the Tier 1 core. This
   * is the exact provenance the inspector must render:
   *   - preset row: full opacity + hover-reveal reset ↺
   *   - elevation row: dimmed + "↑ inherited from Tier 1 core" caption
   */
  const RESOLVE_PAYLOAD_C23 = {
    template_id: "tpl-c23",
    template_slug: "c23-template",
    template_version: 1,
    template_scope: "platform_default",
    template_vertical: null,
    core_id: "core-c23",
    core_slug: "default-core",
    core_version: 1,
    core_registered_component: {},
    rows: [],
    canvas_config: {},
    resolved_chrome: { preset: "frosted", elevation: 40 },
    resolved_substrate: null,
    resolved_typography: null,
    sources: {
      template: {},
      core: {},
      tenant: null,
      chrome_sources: {
        preset: "tier2",
        elevation: "tier1",
        corner_radius: "tier1",
        backdrop_blur: "tier1",
        background_token: "tier1",
        border_token: "tier1",
        padding_token: "tier1",
      },
      substrate_sources: {},
      typography_sources: {},
    },
  }

  beforeEach(() => {
    ;(focusTemplatesService.list as ReturnType<typeof vi.fn>).mockResolvedValue([
      TEMPLATE_C23,
    ])
    ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      TEMPLATE_C23,
    )
    ;(
      focusTemplatesService.resolve as ReturnType<typeof vi.fn>
    ).mockResolvedValue(RESOLVE_PAYLOAD_C23)
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      CORE_C23,
    )
  })

  it("renders the inherited-from caption for rows that cascade from Tier 1", async () => {
    render(
      <MemoryRouter>
        <Tier2TemplatesEditor
          selectedTemplateId="tpl-c23"
          onSelectTemplate={onSelectTemplate}
          onDirtyChange={onDirtyChange}
          onLastSavedChange={onLastSavedChange}
        />
      </MemoryRouter>,
    )
    await screen.findByTestId("tier2-preview-card")
    // At least one inherited row caption must appear once the
    // resolver call settles.
    await waitFor(() => {
      const captions = screen.queryAllByTestId(
        "property-row-inheritance-caption",
      )
      expect(captions.length).toBeGreaterThan(0)
      expect(captions[0].textContent).toMatch(/inherited from Tier 1 core/)
    })
  })

  it("only explicit rows carry the reset ↺ affordance", async () => {
    render(
      <MemoryRouter>
        <Tier2TemplatesEditor
          selectedTemplateId="tpl-c23"
          onSelectTemplate={onSelectTemplate}
          onDirtyChange={onDirtyChange}
          onLastSavedChange={onLastSavedChange}
        />
      </MemoryRouter>,
    )
    await screen.findByTestId("tier2-preview-card")
    await waitFor(() => {
      // Exactly one explicit row in the fixture: chrome.preset.
      const resets = screen.queryAllByTestId("property-row-reset")
      expect(resets.length).toBe(1)
    })
  })

  it("clicking reset ↺ clears the override + persists via update", async () => {
    ;(
      focusTemplatesService.update as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      ...TEMPLATE_C23,
      chrome_overrides: {},
      version: 2,
    })
    render(
      <MemoryRouter>
        <Tier2TemplatesEditor
          selectedTemplateId="tpl-c23"
          onSelectTemplate={onSelectTemplate}
          onDirtyChange={onDirtyChange}
          onLastSavedChange={onLastSavedChange}
        />
      </MemoryRouter>,
    )
    await screen.findByTestId("tier2-preview-card")
    const resetBtn = await screen.findByTestId("property-row-reset")
    fireEvent.click(resetBtn)
    await waitFor(() => {
      const calls = (
        focusTemplatesService.update as ReturnType<typeof vi.fn>
      ).mock.calls
      expect(calls.length).toBeGreaterThan(0)
      expect(calls[0][1].chrome_overrides).toEqual({})
    })
  })

  it("controlled panel: parent can open InheritedCoreInspectorPanel", async () => {
    const onPanelOpenChange = vi.fn()
    const { rerender } = render(
      <MemoryRouter>
        <Tier2TemplatesEditor
          selectedTemplateId="tpl-c23"
          onSelectTemplate={onSelectTemplate}
          onDirtyChange={onDirtyChange}
          onLastSavedChange={onLastSavedChange}
          inheritedCorePanelOpen={false}
          onInheritedCorePanelOpenChange={onPanelOpenChange}
        />
      </MemoryRouter>,
    )
    await screen.findByTestId("tier2-preview-card")
    expect(
      screen.queryByTestId("inherited-core-inspector-panel"),
    ).toBeNull()
    // Parent flips the controlled prop → panel mounts.
    rerender(
      <MemoryRouter>
        <Tier2TemplatesEditor
          selectedTemplateId="tpl-c23"
          onSelectTemplate={onSelectTemplate}
          onDirtyChange={onDirtyChange}
          onLastSavedChange={onLastSavedChange}
          inheritedCorePanelOpen={true}
          onInheritedCorePanelOpenChange={onPanelOpenChange}
        />
      </MemoryRouter>,
    )
    await screen.findByTestId("inherited-core-inspector-panel")
  })

  it("controlled panel: canvas placement click invokes onInheritedCorePanelOpenChange(true)", async () => {
    const onPanelOpenChange = vi.fn()
    render(
      <MemoryRouter>
        <Tier2TemplatesEditor
          selectedTemplateId="tpl-c23"
          onSelectTemplate={onSelectTemplate}
          onDirtyChange={onDirtyChange}
          onLastSavedChange={onLastSavedChange}
          inheritedCorePanelOpen={false}
          onInheritedCorePanelOpenChange={onPanelOpenChange}
        />
      </MemoryRouter>,
    )
    const placement = await screen.findByTestId("inherited-core-placement")
    // Wait for inheritedCore lookup to settle so disabled flips off.
    await waitFor(() => expect(placement).not.toBeDisabled())
    fireEvent.click(placement)
    expect(onPanelOpenChange).toHaveBeenCalledWith(true)
  })

  it("invokes onNavigateToTier1Core when 'Edit core in Tier 1' fires from the panel", async () => {
    const onNavigateToTier1Core = vi.fn()
    render(
      <MemoryRouter>
        <Tier2TemplatesEditor
          selectedTemplateId="tpl-c23"
          onSelectTemplate={onSelectTemplate}
          onDirtyChange={onDirtyChange}
          onLastSavedChange={onLastSavedChange}
          onNavigateToTier1Core={onNavigateToTier1Core}
          inheritedCorePanelOpen={true}
        />
      </MemoryRouter>,
    )
    // The InheritedCoreInspectorPanel's "Edit core in Tier 1" button.
    // The panel's internal testid is established in C-2.2c.
    const navBtn = await screen.findByTestId("inherited-core-edit-button")
    await waitFor(() => expect(navBtn).not.toBeDisabled())
    fireEvent.click(navBtn)
    await waitFor(() => {
      expect(onNavigateToTier1Core).toHaveBeenCalledWith("core-c23")
    })
  })
})
