/**
 * CreateTierTwoTemplateModal tests — sub-arc C-2.2c.
 *
 * Mirrors CreateTierOneCoreModal.test.tsx with Tier 2 adaptations:
 *   - "Inherit from core" picker is the load-bearing required field
 *   - Scope radio toggle + conditional Vertical dropdown
 *   - default-vertical prop pre-selects scope + vertical
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

vi.mock("@/bridgeable-admin/services/verticals-service", () => ({
  verticalsService: {
    list: vi.fn(),
    get: vi.fn(),
    update: vi.fn(),
  },
}))

import { focusTemplatesService } from "@/bridgeable-admin/services/focus-templates-service"
import { focusCoresService } from "@/bridgeable-admin/services/focus-cores-service"
import { verticalsService } from "@/bridgeable-admin/services/verticals-service"
import { CreateTierTwoTemplateModal } from "./CreateTierTwoTemplateModal"

const onClose = vi.fn()
const onCreated = vi.fn()

const CORE = {
  id: "core-1",
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
  chrome: {},
  version: 3,
  is_active: true,
  created_at: "",
  updated_at: "",
}

const VERTICAL_FH = {
  slug: "funeral_home",
  display_name: "Funeral Home",
  description: null,
  status: "published" as const,
  icon: null,
  sort_order: 0,
  created_at: "",
  updated_at: "",
}

const VERTICAL_MFG = {
  slug: "manufacturing",
  display_name: "Manufacturing",
  description: null,
  status: "published" as const,
  icon: null,
  sort_order: 1,
  created_at: "",
  updated_at: "",
}

beforeEach(() => {
  vi.clearAllMocks()
  ;(focusCoresService.list as ReturnType<typeof vi.fn>).mockResolvedValue([
    CORE,
  ])
  ;(verticalsService.list as ReturnType<typeof vi.fn>).mockResolvedValue([
    VERTICAL_FH,
    VERTICAL_MFG,
  ])
})

afterEach(() => {
  vi.clearAllMocks()
})

describe("CreateTierTwoTemplateModal", () => {
  it("does not render when open=false", () => {
    const { container } = render(
      <CreateTierTwoTemplateModal
        open={false}
        onClose={onClose}
        onCreated={onCreated}
      />,
    )
    expect(container.firstChild).toBeNull()
  })

  it("renders modal chrome + form fields when open=true", async () => {
    render(
      <CreateTierTwoTemplateModal
        open={true}
        onClose={onClose}
        onCreated={onCreated}
      />,
    )
    expect(
      screen.getByTestId("create-tier-two-template-modal"),
    ).toBeInTheDocument()
    expect(screen.getByTestId("inherits-from-core-select")).toBeInTheDocument()
    expect(screen.getByTestId("template-slug-input")).toBeInTheDocument()
    expect(screen.getByTestId("template-display-name-input")).toBeInTheDocument()
    expect(screen.getByTestId("scope-platform-default")).toBeInTheDocument()
    expect(screen.getByTestId("scope-vertical-default")).toBeInTheDocument()
    expect(
      screen.getByTestId("create-tier-two-template-submit"),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("create-tier-two-template-cancel"),
    ).toBeInTheDocument()
    // The core list fetch fires on open.
    await waitFor(() => {
      expect(focusCoresService.list).toHaveBeenCalled()
    })
  })

  it("Cancel button invokes onClose", () => {
    render(
      <CreateTierTwoTemplateModal
        open={true}
        onClose={onClose}
        onCreated={onCreated}
      />,
    )
    fireEvent.click(screen.getByTestId("create-tier-two-template-cancel"))
    expect(onClose).toHaveBeenCalled()
  })

  it("submit with empty fields shows core + slug + display-name errors", async () => {
    render(
      <CreateTierTwoTemplateModal
        open={true}
        onClose={onClose}
        onCreated={onCreated}
      />,
    )
    fireEvent.click(screen.getByTestId("create-tier-two-template-submit"))
    await waitFor(() => {
      expect(screen.queryByTestId("inherits-from-core-error")).toBeTruthy()
      expect(screen.queryByTestId("template-slug-error")).toBeTruthy()
    })
    expect(focusTemplatesService.create).not.toHaveBeenCalled()
  })

  it("rejects malformed slug", async () => {
    render(
      <CreateTierTwoTemplateModal
        open={true}
        onClose={onClose}
        onCreated={onCreated}
      />,
    )
    // Wait for cores to populate.
    await waitFor(() => {
      const select = screen.getByTestId(
        "inherits-from-core-select",
      ) as HTMLSelectElement
      expect(select.options.length).toBeGreaterThan(1)
    })
    fireEvent.change(screen.getByTestId("inherits-from-core-select"), {
      target: { value: "core-1" },
    })
    fireEvent.change(screen.getByTestId("template-slug-input"), {
      target: { value: "Bad Slug!" },
    })
    fireEvent.change(screen.getByTestId("template-display-name-input"), {
      target: { value: "Bad" },
    })
    fireEvent.click(screen.getByTestId("create-tier-two-template-submit"))
    await waitFor(() => {
      const err = screen.queryByTestId("template-slug-error")
      expect(err).toBeTruthy()
      expect(err?.textContent ?? "").toMatch(/lowercase/)
    })
  })

  it("submits successfully when fields are valid (platform default scope)", async () => {
    ;(focusTemplatesService.create as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      {
        id: "tpl-new-1",
        scope: "platform_default",
        vertical: null,
        template_slug: "new-template",
        display_name: "New Template",
        description: null,
        inherits_from_core_id: "core-1",
        inherits_from_core_version: 3,
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
    )
    render(
      <CreateTierTwoTemplateModal
        open={true}
        onClose={onClose}
        onCreated={onCreated}
      />,
    )
    await waitFor(() => {
      const select = screen.getByTestId(
        "inherits-from-core-select",
      ) as HTMLSelectElement
      expect(select.options.length).toBeGreaterThan(1)
    })
    fireEvent.change(screen.getByTestId("inherits-from-core-select"), {
      target: { value: "core-1" },
    })
    fireEvent.change(screen.getByTestId("template-slug-input"), {
      target: { value: "new-template" },
    })
    fireEvent.change(screen.getByTestId("template-display-name-input"), {
      target: { value: "New Template" },
    })
    fireEvent.click(screen.getByTestId("scope-platform-default"))
    fireEvent.click(screen.getByTestId("create-tier-two-template-submit"))
    await waitFor(() => {
      expect(focusTemplatesService.create).toHaveBeenCalled()
    })
    const call = (focusTemplatesService.create as ReturnType<typeof vi.fn>).mock
      .calls[0][0]
    expect(call.scope).toBe("platform_default")
    expect(call.vertical).toBeNull()
    expect(call.inherits_from_core_id).toBe("core-1")
    expect(call.template_slug).toBe("new-template")
    expect(call.chrome_overrides).toEqual({})
    expect(call.substrate).toEqual({})
    expect(call.typography).toEqual({})
    await waitFor(() => {
      expect(onCreated).toHaveBeenCalled()
    })
  })

  it("displays slug collision error on 409-shaped response", async () => {
    ;(focusTemplatesService.create as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error("slug already exists"),
    )
    render(
      <CreateTierTwoTemplateModal
        open={true}
        onClose={onClose}
        onCreated={onCreated}
      />,
    )
    await waitFor(() => {
      const select = screen.getByTestId(
        "inherits-from-core-select",
      ) as HTMLSelectElement
      expect(select.options.length).toBeGreaterThan(1)
    })
    fireEvent.change(screen.getByTestId("inherits-from-core-select"), {
      target: { value: "core-1" },
    })
    fireEvent.change(screen.getByTestId("template-slug-input"), {
      target: { value: "duplicate" },
    })
    fireEvent.change(screen.getByTestId("template-display-name-input"), {
      target: { value: "Dup" },
    })
    fireEvent.click(screen.getByTestId("create-tier-two-template-submit"))
    await waitFor(() => {
      const err = screen.queryByTestId("template-slug-error")
      expect(err?.textContent ?? "").toMatch(/already/i)
    })
  })

  it("shows _form error banner for non-slug failures", async () => {
    ;(focusTemplatesService.create as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error("Internal server error"),
    )
    render(
      <CreateTierTwoTemplateModal
        open={true}
        onClose={onClose}
        onCreated={onCreated}
      />,
    )
    await waitFor(() => {
      const select = screen.getByTestId(
        "inherits-from-core-select",
      ) as HTMLSelectElement
      expect(select.options.length).toBeGreaterThan(1)
    })
    fireEvent.change(screen.getByTestId("inherits-from-core-select"), {
      target: { value: "core-1" },
    })
    fireEvent.change(screen.getByTestId("template-slug-input"), {
      target: { value: "valid-slug" },
    })
    fireEvent.change(screen.getByTestId("template-display-name-input"), {
      target: { value: "Valid" },
    })
    fireEvent.click(screen.getByTestId("create-tier-two-template-submit"))
    await waitFor(() => {
      const banner = screen.queryByTestId("create-tier-two-template-error")
      expect(banner).toBeTruthy()
      expect(banner?.textContent).toMatch(/Internal server error/)
    })
  })

  it("defaultVertical pre-selects scope=vertical_default + vertical dropdown", async () => {
    render(
      <CreateTierTwoTemplateModal
        open={true}
        onClose={onClose}
        onCreated={onCreated}
        defaultVertical="funeral_home"
      />,
    )
    // scope=vertical_default radio is pre-checked
    expect(
      (screen.getByTestId("scope-vertical-default") as HTMLInputElement).checked,
    ).toBe(true)
    // vertical select is visible AND populated with FH preselected
    await waitFor(() => {
      const sel = screen.getByTestId(
        "template-vertical-select",
      ) as HTMLSelectElement
      expect(sel).toBeInTheDocument()
      expect(sel.value).toBe("funeral_home")
    })
  })

  it("vertical scope without vertical selected shows vertical error on submit", async () => {
    render(
      <CreateTierTwoTemplateModal
        open={true}
        onClose={onClose}
        onCreated={onCreated}
      />,
    )
    await waitFor(() => {
      const select = screen.getByTestId(
        "inherits-from-core-select",
      ) as HTMLSelectElement
      expect(select.options.length).toBeGreaterThan(1)
    })
    fireEvent.click(screen.getByTestId("scope-vertical-default"))
    fireEvent.change(screen.getByTestId("inherits-from-core-select"), {
      target: { value: "core-1" },
    })
    fireEvent.change(screen.getByTestId("template-slug-input"), {
      target: { value: "needs-vertical" },
    })
    fireEvent.change(screen.getByTestId("template-display-name-input"), {
      target: { value: "Needs" },
    })
    fireEvent.click(screen.getByTestId("create-tier-two-template-submit"))
    await waitFor(() => {
      expect(screen.queryByTestId("template-vertical-error")).toBeTruthy()
    })
    expect(focusTemplatesService.create).not.toHaveBeenCalled()
  })

  it("submits with vertical_default scope + vertical slug", async () => {
    ;(focusTemplatesService.create as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      {
        id: "tpl-new-fh",
        scope: "vertical_default",
        vertical: "funeral_home",
        template_slug: "fh-template",
        display_name: "FH Template",
        description: null,
        inherits_from_core_id: "core-1",
        inherits_from_core_version: 3,
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
    )
    render(
      <CreateTierTwoTemplateModal
        open={true}
        onClose={onClose}
        onCreated={onCreated}
        defaultVertical="funeral_home"
      />,
    )
    await waitFor(() => {
      const select = screen.getByTestId(
        "inherits-from-core-select",
      ) as HTMLSelectElement
      expect(select.options.length).toBeGreaterThan(1)
    })
    fireEvent.change(screen.getByTestId("inherits-from-core-select"), {
      target: { value: "core-1" },
    })
    fireEvent.change(screen.getByTestId("template-slug-input"), {
      target: { value: "fh-template" },
    })
    fireEvent.change(screen.getByTestId("template-display-name-input"), {
      target: { value: "FH Template" },
    })
    fireEvent.click(screen.getByTestId("create-tier-two-template-submit"))
    await waitFor(() => {
      expect(focusTemplatesService.create).toHaveBeenCalled()
    })
    const call = (focusTemplatesService.create as ReturnType<typeof vi.fn>).mock
      .calls[0][0]
    expect(call.scope).toBe("vertical_default")
    expect(call.vertical).toBe("funeral_home")
  })
})
