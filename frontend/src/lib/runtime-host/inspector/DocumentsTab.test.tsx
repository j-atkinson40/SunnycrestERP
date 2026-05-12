/**
 * Arc 3b — DocumentsTab tests.
 *
 * Verifies:
 * - Documents tab renders in inspector tab strip + activates on click
 * - Template list loads with default scope + populates rows
 * - Scope pill switches scope → list re-fetches with new scope
 * - Document-type filter pill switches type → list re-fetches with filter
 * - Mode-stack push level 1 (list) → 2 (template-edit) → 3 (block-detail)
 * - Mode-stack pop level 3 → 2 → 1
 * - Per-block immediate write on block save (Q-DOCS-2)
 * - Per-block error UX on failure (inline error + preserved input)
 * - Conditional_wrapper child management (add/remove)
 * - Deep-link to standalone editor (canonical adminPath)
 *
 * Mocks both `documentsV2Service` (templates list / detail / version)
 * and `documentBlocksService` (blocks list / add / update / remove +
 * block kinds + document types) so tests don't hit the network.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import {
  fireEvent,
  render,
  waitFor,
  type RenderResult,
} from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { useEffect, useRef } from "react"

import "@/lib/visual-editor/registry/auto-register"

import { EditModeProvider, useEditMode } from "../edit-mode-context"
import { InspectorPanel } from "./InspectorPanel"
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


// ── Mocks ─────────────────────────────────────────────────────


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


const mockListTemplates = documentsV2Service.listTemplates as unknown as ReturnType<
  typeof vi.fn
>
const mockGetTemplate = documentsV2Service.getTemplate as unknown as ReturnType<
  typeof vi.fn
>
const mockGetTemplateVersion =
  documentsV2Service.getTemplateVersion as unknown as ReturnType<typeof vi.fn>

const mockListBlocks = documentBlocksService.list as unknown as ReturnType<
  typeof vi.fn
>
const mockAddBlock = documentBlocksService.add as unknown as ReturnType<
  typeof vi.fn
>
const mockUpdateBlock = documentBlocksService.update as unknown as ReturnType<
  typeof vi.fn
>
const mockRemoveBlock = documentBlocksService.remove as unknown as ReturnType<
  typeof vi.fn
>
const mockListBlockKinds =
  documentBlocksService.listBlockKinds as unknown as ReturnType<typeof vi.fn>
const mockListDocumentTypes =
  documentBlocksService.listDocumentTypes as unknown as ReturnType<typeof vi.fn>


// ── Fixtures ──────────────────────────────────────────────────


function makeTemplate(
  overrides: Partial<DocumentTemplateListItem> = {},
): DocumentTemplateListItem {
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
    has_draft: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  }
}


function makeListResponse(
  items: DocumentTemplateListItem[],
): DocumentTemplateListResponse {
  return { items, total: items.length, limit: 500, offset: 0 }
}


function makeVersion(
  overrides: Partial<DocumentTemplateVersion> = {},
): DocumentTemplateVersion {
  return {
    id: "ver-1",
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


function makeDetail(
  overrides: Partial<DocumentTemplateDetail> = {},
): DocumentTemplateDetail {
  const draft = makeVersion({ id: "ver-draft", status: "draft" })
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
    ...overrides,
  }
}


function makeBlock(overrides: Partial<TemplateBlock> = {}): TemplateBlock {
  return {
    id: "blk-1",
    template_version_id: "ver-draft",
    block_kind: "header",
    position: 0,
    config: { title: "Hello" },
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
      description: "Document header block.",
      config_schema: {},
      accepts_children: false,
    },
    {
      kind: "conditional_wrapper",
      display_name: "Conditional",
      description: "Wraps child blocks with a Jinja condition.",
      config_schema: {},
      accepts_children: true,
    },
  ]
}


function makeCatalog(): DocumentTypeCatalog {
  return {
    categories: [
      { category_id: "invoices", display_name: "Invoices" },
      { category_id: "statements", display_name: "Statements" },
    ],
    types: [
      {
        type_id: "invoice",
        display_name: "Invoice",
        category: "invoices",
        description: "Customer invoice.",
        starter_blocks: [],
        recommended_variables: [],
      },
      {
        type_id: "statement",
        display_name: "Statement",
        category: "statements",
        description: "Monthly statement.",
        starter_blocks: [],
        recommended_variables: [],
      },
    ],
  }
}


// ── Mount helpers ─────────────────────────────────────────────


function SelectionDriver() {
  const ctx = useEditMode()
  const inited = useRef(false)
  useEffect(() => {
    if (inited.current) return
    inited.current = true
    ctx.selectComponent("today")
  }, [ctx])
  return null
}


function MountInspector() {
  return (
    <MemoryRouter initialEntries={["/dashboard"]}>
      <EditModeProvider
        tenantSlug="t1"
        impersonatedUserId="u1"
        initialMode="edit"
      >
        <SelectionDriver />
        <InspectorPanel
          vertical="manufacturing"
          tenantId={null}
          themeMode="light"
        />
      </EditModeProvider>
    </MemoryRouter>
  )
}


function MountTab() {
  return (
    <MemoryRouter initialEntries={["/dashboard"]}>
      <DocumentsTab vertical="manufacturing" />
    </MemoryRouter>
  )
}


async function activateDocumentsTab(result: RenderResult): Promise<void> {
  const tab = result.getByTestId("runtime-inspector-tab-documents")
  fireEvent.click(tab)
  await waitFor(() => {
    expect(tab.getAttribute("data-active")).toBe("true")
  })
}


// ── Setup ─────────────────────────────────────────────────────


beforeEach(() => {
  mockListTemplates.mockReset()
  mockGetTemplate.mockReset()
  mockGetTemplateVersion.mockReset()
  mockListBlocks.mockReset()
  mockAddBlock.mockReset()
  mockUpdateBlock.mockReset()
  mockRemoveBlock.mockReset()
  mockListBlockKinds.mockReset()
  mockListDocumentTypes.mockReset()

  // Sensible defaults
  mockListTemplates.mockResolvedValue(
    makeListResponse([
      makeTemplate({ id: "tpl-1", template_key: "invoice.standard" }),
      makeTemplate({
        id: "tpl-2",
        template_key: "statement.monthly",
        document_type: "statement",
      }),
    ]),
  )
  mockListDocumentTypes.mockResolvedValue(makeCatalog())
  mockListBlockKinds.mockResolvedValue(makeBlockKinds())
})


afterEach(() => {
  vi.clearAllMocks()
})


// ─────────────────────────────────────────────────────────────────
// Inspector integration
// ─────────────────────────────────────────────────────────────────


describe("Arc 3b — Documents tab in inspector tab strip", () => {
  it("renders Documents tab in inner tab strip", () => {
    const result = render(<MountInspector />)
    expect(
      result.getByTestId("runtime-inspector-tab-documents"),
    ).toBeTruthy()
  })

  it("activates Documents tab on click", async () => {
    const result = render(<MountInspector />)
    await activateDocumentsTab(result)
    expect(
      result.getByTestId("runtime-inspector-documents-tab"),
    ).toBeTruthy()
  })

  it("calls documentsV2Service.listTemplates with default scope on mount", async () => {
    const result = render(<MountInspector />)
    await activateDocumentsTab(result)
    await waitFor(() => {
      expect(mockListTemplates).toHaveBeenCalled()
    })
    const firstCall =
      mockListTemplates.mock.calls[mockListTemplates.mock.calls.length - 1]
    expect(firstCall[0]).toMatchObject({ scope: "both", limit: 500 })
  })
})


// ─────────────────────────────────────────────────────────────────
// Level 1 — List view
// ─────────────────────────────────────────────────────────────────


describe("Arc 3b — DocumentsTab level 1: template list", () => {
  it("renders loading state then populated rows", async () => {
    const result = render(<MountTab />)
    expect(
      result.getByTestId("runtime-inspector-documents-loading"),
    ).toBeTruthy()
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-document-row-tpl-1"),
      ).toBeTruthy()
      expect(
        result.getByTestId("runtime-inspector-document-row-tpl-2"),
      ).toBeTruthy()
    })
  })

  it("scope pill switches scope + re-fetches", async () => {
    const result = render(<MountTab />)
    await waitFor(() => expect(mockListTemplates).toHaveBeenCalledTimes(1))
    const firstCall = mockListTemplates.mock.calls[0][0]
    expect(firstCall.scope).toBe("both")

    // Open scope pill
    const pill = result.getByTestId("runtime-inspector-documents-scope-pill")
    fireEvent.click(pill)
    expect(
      result.getByTestId("runtime-inspector-documents-scope-menu"),
    ).toBeTruthy()

    // Click platform option
    const option = result.getByTestId(
      "runtime-inspector-documents-scope-option-platform",
    )
    fireEvent.click(option)

    await waitFor(() => {
      expect(mockListTemplates).toHaveBeenCalledTimes(2)
    })
    const secondCall = mockListTemplates.mock.calls[1][0]
    expect(secondCall.scope).toBe("platform")

    await waitFor(() => {
      expect(pill.getAttribute("data-scope")).toBe("platform")
    })
  })

  it("document_type filter switches type + re-fetches with filter", async () => {
    const result = render(<MountTab />)
    await waitFor(() => expect(mockListTemplates).toHaveBeenCalledTimes(1))

    // Wait for catalog
    await waitFor(() => {
      expect(mockListDocumentTypes).toHaveBeenCalled()
    })

    // Open type filter
    const filterPill = result.getByTestId(
      "runtime-inspector-documents-type-filter",
    )
    fireEvent.click(filterPill)
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-documents-type-menu"),
      ).toBeTruthy()
    })
    // Pick "invoice"
    const invoiceOption = result.getByTestId(
      "runtime-inspector-documents-type-option-invoice",
    )
    fireEvent.click(invoiceOption)

    await waitFor(() => {
      expect(mockListTemplates).toHaveBeenCalledTimes(2)
    })
    const secondCall = mockListTemplates.mock.calls[1][0]
    expect(secondCall.document_type).toBe("invoice")
  })

  it("deep-link button uses canonical adminPath URL with target=_blank", async () => {
    const result = render(<MountTab />)
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-document-row-tpl-1"),
      ).toBeTruthy()
    })
    const openLink = result.getByTestId(
      "runtime-inspector-document-row-tpl-1-open",
    ) as HTMLAnchorElement
    expect(openLink.target).toBe("_blank")
    expect(openLink.href).toContain("/visual-editor/documents")
  })

  it("empty state renders when zero templates", async () => {
    mockListTemplates.mockResolvedValue(makeListResponse([]))
    const result = render(<MountTab />)
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-documents-empty"),
      ).toBeTruthy()
    })
  })
})


// ─────────────────────────────────────────────────────────────────
// Mode-stack push + pop
// ─────────────────────────────────────────────────────────────────


describe("Arc 3b — Mode-stack push level 1 → 2 → 3 and pop", () => {
  beforeEach(() => {
    mockGetTemplate.mockResolvedValue(makeDetail())
    mockGetTemplateVersion.mockResolvedValue(
      makeVersion({ id: "ver-draft", status: "draft" }),
    )
    mockListBlocks.mockResolvedValue([
      makeBlock({ id: "blk-1", block_kind: "header" }),
    ])
  })

  it("clicking template row pushes to level 2 (template-edit)", async () => {
    const result = render(<MountTab />)
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-document-row-tpl-1"),
      ).toBeTruthy()
    })
    const rowButton = result.getByTestId(
      "runtime-inspector-document-row-tpl-1-edit",
    )
    fireEvent.click(rowButton)

    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-documents-template-edit"),
      ).toBeTruthy()
    })
    // service.getTemplate fired for the selected template
    expect(mockGetTemplate).toHaveBeenCalledWith("tpl-1")
  })

  it("clicking block row pushes to level 3 (block-detail)", async () => {
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
        result.getByTestId("runtime-inspector-documents-block-blk-1"),
      ).toBeTruthy()
    })
    fireEvent.click(
      result.getByTestId("runtime-inspector-documents-block-blk-1-select"),
    )
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-documents-block-detail"),
      ).toBeTruthy()
    })
  })

  it("back from level 3 returns to level 2", async () => {
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
        result.getByTestId("runtime-inspector-documents-block-blk-1"),
      ).toBeTruthy()
    })
    fireEvent.click(
      result.getByTestId("runtime-inspector-documents-block-blk-1-select"),
    )
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-documents-block-detail"),
      ).toBeTruthy()
    })
    fireEvent.click(
      result.getByTestId(
        "runtime-inspector-documents-block-detail-back",
      ),
    )
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-documents-template-edit"),
      ).toBeTruthy()
    })
  })

  it("back from level 2 returns to level 1", async () => {
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
    fireEvent.click(
      result.getByTestId(
        "runtime-inspector-documents-template-edit-back",
      ),
    )
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-documents-tab"),
      ).toBeTruthy()
    })
  })
})


// ─────────────────────────────────────────────────────────────────
// Per-block immediate writes + error UX
// ─────────────────────────────────────────────────────────────────


describe("Arc 3b — Per-block immediate writes (Q-DOCS-2)", () => {
  beforeEach(() => {
    mockGetTemplate.mockResolvedValue(makeDetail())
    mockGetTemplateVersion.mockResolvedValue(
      makeVersion({ id: "ver-draft", status: "draft" }),
    )
    mockListBlocks.mockResolvedValue([
      makeBlock({ id: "blk-1", block_kind: "header" }),
    ])
  })

  it("Save fires documentBlocksService.update immediately", async () => {
    mockUpdateBlock.mockResolvedValue(
      makeBlock({ id: "blk-1", config: { title: "New" } }),
    )
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
        result.getByTestId("runtime-inspector-documents-block-blk-1"),
      ).toBeTruthy()
    })
    fireEvent.click(
      result.getByTestId("runtime-inspector-documents-block-blk-1-select"),
    )
    await waitFor(() => {
      expect(
        result.getByTestId("documents-block-config-textarea-blk-1"),
      ).toBeTruthy()
    })

    // Mutate JSON
    const textarea = result.getByTestId(
      "documents-block-config-textarea-blk-1",
    ) as HTMLTextAreaElement
    fireEvent.change(textarea, {
      target: { value: JSON.stringify({ title: "Updated" }, null, 2) },
    })
    fireEvent.click(result.getByTestId("documents-block-save-blk-1"))

    await waitFor(() => {
      expect(mockUpdateBlock).toHaveBeenCalledTimes(1)
    })
    const updateCall = mockUpdateBlock.mock.calls[0]
    expect(updateCall[0]).toBe("tpl-1") // templateId
    expect(updateCall[1]).toBe("ver-draft") // versionId
    expect(updateCall[2]).toBe("blk-1") // blockId
    expect(updateCall[3]).toEqual({ config: { title: "Updated" } })
  })

  it("update failure surfaces inline error + preserves operator input", async () => {
    mockUpdateBlock.mockRejectedValue(new Error("save broke"))
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
        result.getByTestId("runtime-inspector-documents-block-blk-1"),
      ).toBeTruthy()
    })
    fireEvent.click(
      result.getByTestId("runtime-inspector-documents-block-blk-1-select"),
    )
    await waitFor(() => {
      expect(
        result.getByTestId("documents-block-config-textarea-blk-1"),
      ).toBeTruthy()
    })

    const textarea = result.getByTestId(
      "documents-block-config-textarea-blk-1",
    ) as HTMLTextAreaElement
    fireEvent.change(textarea, {
      target: { value: JSON.stringify({ title: "Updated" }, null, 2) },
    })
    fireEvent.click(result.getByTestId("documents-block-save-blk-1"))

    // Wait for error to surface
    await waitFor(() => {
      expect(
        result.getByTestId("documents-block-config-error-blk-1"),
      ).toBeTruthy()
    })
    // Input preserved (textarea still shows updated JSON)
    expect(textarea.value).toContain("Updated")
  })

  it("add block fires documentBlocksService.add immediately", async () => {
    mockAddBlock.mockResolvedValue(
      makeBlock({ id: "blk-2", block_kind: "body_section" }),
    )
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
        result.getByTestId("runtime-inspector-documents-add-block"),
      ).toBeTruthy()
    })
    fireEvent.click(
      result.getByTestId("runtime-inspector-documents-add-block"),
    )
    await waitFor(() => {
      expect(
        result.getByTestId("documents-block-picker-modal"),
      ).toBeTruthy()
    })
    fireEvent.click(result.getByTestId("documents-block-picker-header"))

    await waitFor(() => {
      expect(mockAddBlock).toHaveBeenCalledTimes(1)
    })
    const addCall = mockAddBlock.mock.calls[0]
    expect(addCall[0]).toBe("tpl-1")
    expect(addCall[1]).toBe("ver-draft")
    expect(addCall[2]).toEqual({
      block_kind: "header",
      config: {},
      parent_block_id: null,
    })
  })
})


// ─────────────────────────────────────────────────────────────────
// Conditional_wrapper child management
// ─────────────────────────────────────────────────────────────────


describe("Arc 3b — Conditional_wrapper child management", () => {
  it("conditional_wrapper block detail surfaces children section + add-child", async () => {
    mockGetTemplate.mockResolvedValue(makeDetail())
    mockGetTemplateVersion.mockResolvedValue(
      makeVersion({ id: "ver-draft", status: "draft" }),
    )
    const wrapper = makeBlock({
      id: "blk-wrap",
      block_kind: "conditional_wrapper",
      config: { condition: "value > 0" },
    })
    const child = makeBlock({
      id: "blk-child",
      block_kind: "header",
      parent_block_id: "blk-wrap",
    })
    mockListBlocks.mockResolvedValue([wrapper, child])

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
        result.getByTestId("runtime-inspector-documents-block-blk-wrap"),
      ).toBeTruthy()
    })
    fireEvent.click(
      result.getByTestId("runtime-inspector-documents-block-blk-wrap-select"),
    )
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-documents-children-section"),
      ).toBeTruthy()
    })
    // Child block surfaces with remove affordance
    expect(
      result.getByTestId("runtime-inspector-documents-child-blk-child"),
    ).toBeTruthy()
    expect(
      result.getByTestId("runtime-inspector-documents-add-child"),
    ).toBeTruthy()
  })

  it("add-child fires documentBlocksService.add with parent_block_id", async () => {
    mockGetTemplate.mockResolvedValue(makeDetail())
    mockGetTemplateVersion.mockResolvedValue(
      makeVersion({ id: "ver-draft", status: "draft" }),
    )
    const wrapper = makeBlock({
      id: "blk-wrap",
      block_kind: "conditional_wrapper",
    })
    mockListBlocks.mockResolvedValue([wrapper])
    mockAddBlock.mockResolvedValue(
      makeBlock({
        id: "blk-new",
        block_kind: "header",
        parent_block_id: "blk-wrap",
      }),
    )

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
        result.getByTestId("runtime-inspector-documents-block-blk-wrap"),
      ).toBeTruthy()
    })
    fireEvent.click(
      result.getByTestId("runtime-inspector-documents-block-blk-wrap-select"),
    )
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-documents-add-child"),
      ).toBeTruthy()
    })
    fireEvent.click(
      result.getByTestId("runtime-inspector-documents-add-child"),
    )
    await waitFor(() => {
      expect(
        result.getByTestId("documents-block-picker-modal"),
      ).toBeTruthy()
    })
    fireEvent.click(result.getByTestId("documents-block-picker-header"))

    await waitFor(() => {
      expect(mockAddBlock).toHaveBeenCalledTimes(1)
    })
    const addCall = mockAddBlock.mock.calls[0]
    expect(addCall[2]).toEqual({
      block_kind: "header",
      config: {},
      parent_block_id: "blk-wrap",
    })
  })

  it("remove block fires documentBlocksService.remove immediately", async () => {
    mockGetTemplate.mockResolvedValue(makeDetail())
    mockGetTemplateVersion.mockResolvedValue(
      makeVersion({ id: "ver-draft", status: "draft" }),
    )
    mockListBlocks.mockResolvedValue([
      makeBlock({ id: "blk-1", block_kind: "header" }),
    ])
    mockRemoveBlock.mockResolvedValue(undefined)

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
        result.getByTestId("runtime-inspector-documents-block-blk-1-remove"),
      ).toBeTruthy()
    })
    fireEvent.click(
      result.getByTestId("runtime-inspector-documents-block-blk-1-remove"),
    )
    await waitFor(() => {
      expect(mockRemoveBlock).toHaveBeenCalledTimes(1)
    })
    expect(mockRemoveBlock.mock.calls[0]).toEqual([
      "tpl-1",
      "ver-draft",
      "blk-1",
    ])
  })
})
