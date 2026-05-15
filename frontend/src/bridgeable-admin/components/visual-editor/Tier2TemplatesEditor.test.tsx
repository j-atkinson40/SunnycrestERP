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

vi.mock("@/bridgeable-admin/services/focus-templates-service", () => ({
  focusTemplatesService: {
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    usage: vi.fn(),
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
      <Tier2TemplatesEditor
        selectedTemplateId={null}
        onSelectTemplate={onSelectTemplate}
        onDirtyChange={onDirtyChange}
        onLastSavedChange={onLastSavedChange}
      />,
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
      <Tier2TemplatesEditor
        selectedTemplateId={null}
        onSelectTemplate={onSelectTemplate}
        onDirtyChange={onDirtyChange}
        onLastSavedChange={onLastSavedChange}
      />,
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
      <Tier2TemplatesEditor
        selectedTemplateId={null}
        onSelectTemplate={onSelectTemplate}
        onDirtyChange={onDirtyChange}
        onLastSavedChange={onLastSavedChange}
      />,
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
      <Tier2TemplatesEditor
        selectedTemplateId="tpl-2"
        onSelectTemplate={onSelectTemplate}
        onDirtyChange={onDirtyChange}
        onLastSavedChange={onLastSavedChange}
      />,
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
      <Tier2TemplatesEditor
        selectedTemplateId="tpl-canvas-1"
        onSelectTemplate={onSelectTemplate}
        onDirtyChange={onDirtyChange}
        onLastSavedChange={onLastSavedChange}
      />,
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
      <Tier2TemplatesEditor
        selectedTemplateId="tpl-canvas-2"
        onSelectTemplate={onSelectTemplate}
        onDirtyChange={onDirtyChange}
        onLastSavedChange={onLastSavedChange}
      />,
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
      <Tier2TemplatesEditor
        selectedTemplateId="tpl-live"
        onSelectTemplate={onSelectTemplate}
        onDirtyChange={onDirtyChange}
        onLastSavedChange={onLastSavedChange}
      />,
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
      <Tier2TemplatesEditor
        selectedTemplateId="tpl-live"
        onSelectTemplate={onSelectTemplate}
        onDirtyChange={onDirtyChange}
        onLastSavedChange={onLastSavedChange}
      />,
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
      <Tier2TemplatesEditor
        selectedTemplateId="tpl-live"
        onSelectTemplate={onSelectTemplate}
        onDirtyChange={onDirtyChange}
        onLastSavedChange={onLastSavedChange}
      />,
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
      <Tier2TemplatesEditor
        selectedTemplateId="tpl-live"
        onSelectTemplate={onSelectTemplate}
        onDirtyChange={onDirtyChange}
        onLastSavedChange={onLastSavedChange}
      />,
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
      <Tier2TemplatesEditor
        selectedTemplateId={null}
        onSelectTemplate={onSelectTemplate}
        onDirtyChange={onDirtyChange}
        onLastSavedChange={onLastSavedChange}
      />,
    )
    expect(await screen.findByTestId("templates-error")).toHaveTextContent(
      "boom",
    )
  })
})
