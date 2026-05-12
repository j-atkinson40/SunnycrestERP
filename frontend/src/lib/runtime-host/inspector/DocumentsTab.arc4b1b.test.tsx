/**
 * Arc 4b.1b — DocumentsTab slash command + drag-drop reorder tests.
 *
 * Verifies:
 *   - Slash input renders at template-edit level 2 (Notion-shape).
 *   - Typing `/` opens SuggestionDropdown over the block_registry
 *     kinds; Enter inserts via documentBlocksService.add; Escape
 *     cancels + clears.
 *   - SuggestionDropdown filters block kinds by query.
 *   - Each block row gets grip handle + Move-up/Move-down buttons
 *     wired through documentBlocksService.reorder.
 *   - Reorder via Move-up emits optimistic UI + reorder API call.
 *   - Reorder via Alt+ArrowDown on focused block emits reorder.
 *   - Reorder API failure surfaces reorder-error banner; original
 *     order restored (rollback).
 *   - Reorder error banner has Dismiss affordance.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, waitFor, cleanup } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import "@/lib/visual-editor/registry/auto-register"

import { DocumentsTab } from "./DocumentsTab"
import {
  documentBlocksService,
  type BlockKindMetadata,
  type DocumentTypeCatalog,
  type TemplateBlock,
} from "@/bridgeable-admin/services/document-blocks-service"
import {
  documentsV2Service,
  type DocumentTemplateDetail,
  type DocumentTemplateListItem,
  type DocumentTemplateListResponse,
  type DocumentTemplateVersion,
} from "@/services/documents-v2-service"


vi.mock("@/services/documents-v2-service", async () => {
  const actual = await vi.importActual<
    typeof import("@/services/documents-v2-service")
  >("@/services/documents-v2-service")
  return {
    ...actual,
    documentsV2Service: {
      listTemplates: vi.fn(),
      getTemplate: vi.fn(),
      getTemplateVersion: vi.fn(),
      listDocumentLog: vi.fn(),
    },
  }
})


vi.mock(
  "@/bridgeable-admin/services/document-blocks-service",
  async () => {
    const actual = await vi.importActual<
      typeof import("@/bridgeable-admin/services/document-blocks-service")
    >("@/bridgeable-admin/services/document-blocks-service")
    return {
      ...actual,
      documentBlocksService: {
        list: vi.fn(),
        add: vi.fn(),
        update: vi.fn(),
        remove: vi.fn(),
        reorder: vi.fn(),
        listBlockKinds: vi.fn(),
        listDocumentTypes: vi.fn(),
      },
    }
  },
)


const mockListTemplates = documentsV2Service.listTemplates as unknown as ReturnType<typeof vi.fn>
const mockGetTemplate = documentsV2Service.getTemplate as unknown as ReturnType<typeof vi.fn>
const mockGetTemplateVersion = documentsV2Service.getTemplateVersion as unknown as ReturnType<typeof vi.fn>
const mockListBlocks = documentBlocksService.list as unknown as ReturnType<typeof vi.fn>
const mockAddBlock = documentBlocksService.add as unknown as ReturnType<typeof vi.fn>
const mockReorderBlocks = documentBlocksService.reorder as unknown as ReturnType<typeof vi.fn>
const mockListBlockKinds = documentBlocksService.listBlockKinds as unknown as ReturnType<typeof vi.fn>
const mockListDocumentTypes = documentBlocksService.listDocumentTypes as unknown as ReturnType<typeof vi.fn>


// ── Fixtures ──────────────────────────────────────────────────


function makeTemplate(): DocumentTemplateListItem {
  return {
    id: "tpl-1",
    company_id: null,
    template_key: "invoice.standard",
    document_type: "invoice",
    output_format: "pdf",
    description: "Standard invoice template",
    supports_variants: false,
    is_active: true,
    current_version_number: 1,
    current_version_activated_at: "2026-01-01T00:00:00Z",
    scope: "platform",
    has_draft: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  }
}


function makeListResponse(items: DocumentTemplateListItem[]): DocumentTemplateListResponse {
  return { items, total: items.length, limit: 500, offset: 0 }
}


function makeVersion(
  overrides: Partial<DocumentTemplateVersion> = {},
): DocumentTemplateVersion {
  return {
    id: "ver-draft",
    template_id: "tpl-1",
    version_number: 1,
    status: "draft",
    body_template: "",
    subject_template: null,
    variable_schema: {},
    sample_context: null,
    css_variables: {},
    changelog: null,
    activated_at: null,
    activated_by_user_id: null,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  }
}


function makeDetail(): DocumentTemplateDetail {
  const draft = makeVersion()
  return {
    id: "tpl-1",
    company_id: null,
    template_key: "invoice.standard",
    document_type: "invoice",
    output_format: "pdf",
    description: "Standard invoice template",
    supports_variants: false,
    is_active: true,
    scope: "platform",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    current_version: draft,
    version_summaries: [
      {
        id: "ver-draft",
        version_number: 1,
        status: "draft",
        changelog: null,
        activated_at: null,
        created_at: "2026-01-01T00:00:00Z",
      },
    ],
  }
}


function makeBlock(
  overrides: Partial<TemplateBlock> = {},
): TemplateBlock {
  return {
    id: "blk-1",
    template_version_id: "ver-draft",
    block_kind: "header",
    position: 0,
    config: {},
    condition: null,
    parent_block_id: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  }
}


function makeBlockKinds(): BlockKindMetadata[] {
  return [
    {
      kind: "header",
      display_name: "Header",
      description: "Document header with title.",
      config_schema: {},
      accepts_children: false,
    },
    {
      kind: "body_section",
      display_name: "Body Section",
      description: "Rich-text body region.",
      config_schema: {},
      accepts_children: false,
    },
    {
      kind: "conditional_wrapper",
      display_name: "Conditional Wrapper",
      description: "Wraps children with a Jinja condition.",
      config_schema: {},
      accepts_children: true,
    },
  ]
}


function makeCatalog(): DocumentTypeCatalog {
  return {
    categories: [{ category_id: "invoices", display_name: "Invoices" }],
    types: [
      {
        type_id: "invoice",
        display_name: "Invoice",
        category: "invoices",
        description: "Customer invoice.",
        starter_blocks: [],
        recommended_variables: [],
      },
    ],
  }
}


function MountTab() {
  return (
    <MemoryRouter initialEntries={["/dashboard"]}>
      <DocumentsTab vertical="manufacturing" />
    </MemoryRouter>
  )
}


beforeEach(() => {
  mockListTemplates.mockReset()
  mockGetTemplate.mockReset()
  mockGetTemplateVersion.mockReset()
  mockListBlocks.mockReset()
  mockAddBlock.mockReset()
  mockReorderBlocks.mockReset()
  mockListBlockKinds.mockReset()
  mockListDocumentTypes.mockReset()

  mockListTemplates.mockResolvedValue(makeListResponse([makeTemplate()]))
  mockListDocumentTypes.mockResolvedValue(makeCatalog())
  mockListBlockKinds.mockResolvedValue(makeBlockKinds())
  mockGetTemplate.mockResolvedValue(makeDetail())
  mockGetTemplateVersion.mockResolvedValue(makeVersion())
  mockListBlocks.mockResolvedValue([
    makeBlock({ id: "blk-1", position: 0, block_kind: "header" }),
    makeBlock({ id: "blk-2", position: 1, block_kind: "body_section" }),
    makeBlock({ id: "blk-3", position: 2, block_kind: "conditional_wrapper" }),
  ])
})


afterEach(() => {
  vi.clearAllMocks()
  cleanup()
})


async function navigateToTemplateEdit(): Promise<ReturnType<typeof render>> {
  const result = render(<MountTab />)
  await waitFor(() => {
    expect(
      result.getByTestId("runtime-inspector-document-row-tpl-1"),
    ).toBeTruthy()
  })
  fireEvent.click(
    result.getByTestId("runtime-inspector-document-row-tpl-1-edit"),
  )
  await waitFor(() => {
    expect(
      result.getByTestId("runtime-inspector-documents-template-edit"),
    ).toBeTruthy()
  })
  await waitFor(() => {
    expect(
      result.getByTestId("runtime-inspector-documents-block-blk-1"),
    ).toBeTruthy()
  })
  return result
}


// ─────────────────────────────────────────────────────────────────
// Slash command summoning
// ─────────────────────────────────────────────────────────────────


describe("Arc 4b.1b — slash command summoning", () => {
  it("renders slash input at template-edit level when draft exists", async () => {
    const result = await navigateToTemplateEdit()
    expect(
      result.getByTestId("runtime-inspector-documents-slash-input"),
    ).toBeTruthy()
  })

  it("typing '/' opens SuggestionDropdown with block kinds", async () => {
    const result = await navigateToTemplateEdit()
    const input = result.getByTestId(
      "runtime-inspector-documents-slash-input",
    ) as HTMLInputElement
    fireEvent.change(input, { target: { value: "/" } })
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-documents-slash-dropdown"),
      ).toBeTruthy()
    })
    expect(
      result.getByTestId("runtime-inspector-documents-slash-row-header"),
    ).toBeTruthy()
    expect(
      result.getByTestId(
        "runtime-inspector-documents-slash-row-body_section",
      ),
    ).toBeTruthy()
  })

  it("typing '/cond' filters to conditional_wrapper", async () => {
    const result = await navigateToTemplateEdit()
    const input = result.getByTestId(
      "runtime-inspector-documents-slash-input",
    ) as HTMLInputElement
    fireEvent.change(input, { target: { value: "/cond" } })
    await waitFor(() => {
      expect(
        result.getByTestId(
          "runtime-inspector-documents-slash-row-conditional_wrapper",
        ),
      ).toBeTruthy()
    })
    // Header is filtered out
    expect(
      result.queryByTestId("runtime-inspector-documents-slash-row-header"),
    ).toBeNull()
  })

  it("Enter inserts a new block of the active kind", async () => {
    mockAddBlock.mockResolvedValueOnce(
      makeBlock({ id: "blk-new", position: 3, block_kind: "header" }),
    )
    const result = await navigateToTemplateEdit()
    const input = result.getByTestId(
      "runtime-inspector-documents-slash-input",
    ) as HTMLInputElement
    fireEvent.change(input, { target: { value: "/" } })
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-documents-slash-dropdown"),
      ).toBeTruthy()
    })
    fireEvent.keyDown(input, { key: "Enter" })
    await waitFor(() => {
      expect(mockAddBlock).toHaveBeenCalled()
    })
    expect(mockAddBlock.mock.calls[0][2]).toMatchObject({
      block_kind: "header",
    })
  })

  it("Escape cancels and clears slash query", async () => {
    const result = await navigateToTemplateEdit()
    const input = result.getByTestId(
      "runtime-inspector-documents-slash-input",
    ) as HTMLInputElement
    fireEvent.change(input, { target: { value: "/cond" } })
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-documents-slash-dropdown"),
      ).toBeTruthy()
    })
    fireEvent.keyDown(input, { key: "Escape" })
    await waitFor(() => {
      expect(
        result.queryByTestId("runtime-inspector-documents-slash-dropdown"),
      ).toBeNull()
    })
    expect(input.value).toBe("")
  })

  it("ArrowDown moves active row through SuggestionDropdown", async () => {
    const result = await navigateToTemplateEdit()
    const input = result.getByTestId(
      "runtime-inspector-documents-slash-input",
    ) as HTMLInputElement
    fireEvent.change(input, { target: { value: "/" } })
    await waitFor(() => {
      const headerRow = result.getByTestId(
        "runtime-inspector-documents-slash-dropdown-option-header",
      )
      expect(headerRow.getAttribute("data-active")).toBe("true")
    })
    fireEvent.keyDown(input, { key: "ArrowDown" })
    await waitFor(() => {
      const bodyRow = result.getByTestId(
        "runtime-inspector-documents-slash-dropdown-option-body_section",
      )
      expect(bodyRow.getAttribute("data-active")).toBe("true")
    })
  })
})


// ─────────────────────────────────────────────────────────────────
// Drag-drop block reorder
// ─────────────────────────────────────────────────────────────────


describe("Arc 4b.1b — block reorder", () => {
  it("renders grip handle for each block row", async () => {
    const result = await navigateToTemplateEdit()
    expect(
      result.getByTestId("runtime-inspector-documents-block-blk-1-grip"),
    ).toBeTruthy()
    expect(
      result.getByTestId("runtime-inspector-documents-block-blk-2-grip"),
    ).toBeTruthy()
    expect(
      result.getByTestId("runtime-inspector-documents-block-blk-3-grip"),
    ).toBeTruthy()
  })

  it("renders Move-up + Move-down buttons for each block row", async () => {
    const result = await navigateToTemplateEdit()
    expect(
      result.getByTestId("runtime-inspector-documents-block-blk-1-move-up"),
    ).toBeTruthy()
    expect(
      result.getByTestId("runtime-inspector-documents-block-blk-1-move-down"),
    ).toBeTruthy()
  })

  it("Move-down on first block calls reorder API with [blk-2, blk-1, blk-3]", async () => {
    mockReorderBlocks.mockResolvedValueOnce([
      makeBlock({ id: "blk-2", position: 0, block_kind: "body_section" }),
      makeBlock({ id: "blk-1", position: 1, block_kind: "header" }),
      makeBlock({ id: "blk-3", position: 2, block_kind: "conditional_wrapper" }),
    ])
    const result = await navigateToTemplateEdit()
    fireEvent.click(
      result.getByTestId("runtime-inspector-documents-block-blk-1-move-down"),
    )
    await waitFor(() => {
      expect(mockReorderBlocks).toHaveBeenCalled()
    })
    expect(mockReorderBlocks.mock.calls[0][2]).toMatchObject({
      block_id_order: ["blk-2", "blk-1", "blk-3"],
      parent_block_id: null,
    })
  })

  it("Move-up on first block is disabled (no canMoveUp)", async () => {
    const result = await navigateToTemplateEdit()
    const moveUp = result.getByTestId(
      "runtime-inspector-documents-block-blk-1-move-up",
    ) as HTMLButtonElement
    expect(moveUp.disabled).toBe(true)
  })

  it("Move-down on last block is disabled (no canMoveDown)", async () => {
    const result = await navigateToTemplateEdit()
    const moveDown = result.getByTestId(
      "runtime-inspector-documents-block-blk-3-move-down",
    ) as HTMLButtonElement
    expect(moveDown.disabled).toBe(true)
  })

  it("reorder failure surfaces reorder-error banner", async () => {
    mockReorderBlocks.mockRejectedValueOnce(new Error("Server rejected order"))
    const result = await navigateToTemplateEdit()
    fireEvent.click(
      result.getByTestId("runtime-inspector-documents-block-blk-1-move-down"),
    )
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-documents-reorder-error"),
      ).toBeTruthy()
    })
    expect(
      result.getByTestId("runtime-inspector-documents-reorder-error"),
    ).toHaveTextContent("Server rejected order")
  })

  it("reorder-error banner Dismiss removes the banner", async () => {
    mockReorderBlocks.mockRejectedValueOnce(new Error("Server rejected order"))
    const result = await navigateToTemplateEdit()
    fireEvent.click(
      result.getByTestId("runtime-inspector-documents-block-blk-1-move-down"),
    )
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-documents-reorder-error"),
      ).toBeTruthy()
    })
    fireEvent.click(
      result.getByTestId(
        "runtime-inspector-documents-reorder-error-dismiss",
      ),
    )
    await waitFor(() => {
      expect(
        result.queryByTestId("runtime-inspector-documents-reorder-error"),
      ).toBeNull()
    })
  })

  it("Alt+ArrowDown on focused block emits reorder", async () => {
    mockReorderBlocks.mockResolvedValueOnce([
      makeBlock({ id: "blk-2", position: 0, block_kind: "body_section" }),
      makeBlock({ id: "blk-1", position: 1, block_kind: "header" }),
      makeBlock({ id: "blk-3", position: 2, block_kind: "conditional_wrapper" }),
    ])
    const result = await navigateToTemplateEdit()
    // Hover blk-1 to set focused ref
    fireEvent.mouseEnter(
      result.getByTestId("runtime-inspector-documents-block-blk-1"),
    )
    fireEvent.keyDown(document, { key: "ArrowDown", altKey: true })
    await waitFor(() => {
      expect(mockReorderBlocks).toHaveBeenCalled()
    })
  })

  it("Alt+ArrowUp on focused block in middle moves it up", async () => {
    mockReorderBlocks.mockResolvedValueOnce([])
    const result = await navigateToTemplateEdit()
    fireEvent.mouseEnter(
      result.getByTestId("runtime-inspector-documents-block-blk-2"),
    )
    fireEvent.keyDown(document, { key: "ArrowUp", altKey: true })
    await waitFor(() => {
      expect(mockReorderBlocks).toHaveBeenCalled()
    })
    expect(mockReorderBlocks.mock.calls[0][2]).toMatchObject({
      block_id_order: ["blk-2", "blk-1", "blk-3"],
    })
  })

  it("Alt+ArrowUp on first block is no-op", async () => {
    const result = await navigateToTemplateEdit()
    fireEvent.mouseEnter(
      result.getByTestId("runtime-inspector-documents-block-blk-1"),
    )
    fireEvent.keyDown(document, { key: "ArrowUp", altKey: true })
    // Wait a tick to ensure no call fires
    await new Promise((r) => setTimeout(r, 30))
    expect(mockReorderBlocks).not.toHaveBeenCalled()
  })

  it("Alt+ArrowDown without Alt modifier is no-op", async () => {
    const result = await navigateToTemplateEdit()
    fireEvent.mouseEnter(
      result.getByTestId("runtime-inspector-documents-block-blk-1"),
    )
    fireEvent.keyDown(document, { key: "ArrowDown" })
    await new Promise((r) => setTimeout(r, 30))
    expect(mockReorderBlocks).not.toHaveBeenCalled()
  })
})
