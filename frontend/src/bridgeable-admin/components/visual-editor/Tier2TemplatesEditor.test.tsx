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
    expect(screen.getByTestId("tier2-inspector-placeholder")).toBeInTheDocument()
  })

  it("reports false dirty + null last-saved on mount (read-only)", async () => {
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
    // The inspector placeholder always renders alongside the preview.
    expect(
      screen.getByTestId("tier2-inspector-placeholder"),
    ).toBeInTheDocument()
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
