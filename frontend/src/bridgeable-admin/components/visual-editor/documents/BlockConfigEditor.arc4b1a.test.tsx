/**
 * Arc 4b.1a — BlockConfigEditor canonical dispatch tests.
 *
 * Covers:
 *   - Each of the 6 canonical block kinds dispatches through
 *     PropControlDispatcher (no JSON textarea path).
 *   - Unknown block kinds fall back to JSON textarea (forward-compat).
 *   - conditional_wrapper threads row-column condition writes through
 *     onUpdateCondition (separate from onUpdateConfig).
 *   - Per-block immediate-write semantics preserved (Q-DOCS-2).
 *   - Save / Reset / Delete buttons behave per existing contract.
 */
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { BlockConfigEditor } from "./BlockConfigEditor"
import type {
  BlockKindMetadata,
  TemplateBlock,
} from "@/bridgeable-admin/services/document-blocks-service"


function makeBlock(overrides: Partial<TemplateBlock> = {}): TemplateBlock {
  return {
    id: "block-1",
    template_version_id: "v-1",
    block_kind: "header",
    position: 0,
    config: {},
    condition: null,
    parent_block_id: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  }
}

const BLOCK_KINDS: BlockKindMetadata[] = [
  {
    kind: "header",
    display_name: "Header",
    description: "Document header.",
    config_schema: {},
    accepts_children: false,
  },
  {
    kind: "body_section",
    display_name: "Body Section",
    description: "Body section.",
    config_schema: {},
    accepts_children: false,
  },
  {
    kind: "line_items",
    display_name: "Line Items",
    description: "Line items.",
    config_schema: {},
    accepts_children: false,
  },
  {
    kind: "totals",
    display_name: "Totals",
    description: "Totals.",
    config_schema: {},
    accepts_children: false,
  },
  {
    kind: "signature",
    display_name: "Signature",
    description: "Signature.",
    config_schema: {},
    accepts_children: false,
  },
  {
    kind: "conditional_wrapper",
    display_name: "Conditional Wrapper",
    description: "Conditional wrapper.",
    config_schema: {},
    accepts_children: true,
  },
]


describe("BlockConfigEditor — Arc 4b.1a canonical dispatch", () => {
  it("renders canonical path for header kind (NOT JSON textarea)", () => {
    const block = makeBlock({
      block_kind: "header",
      config: { title: "Test Doc", show_logo: true },
    })
    render(
      <BlockConfigEditor
        block={block}
        blockKinds={BLOCK_KINDS}
        onUpdateConfig={() => undefined}
        onDelete={() => undefined}
        canEdit
      />,
    )
    expect(
      screen.getByTestId(`documents-block-config-canonical-${block.id}`),
    ).toBeInTheDocument()
    // No JSON textarea
    expect(
      screen.queryByTestId(`documents-block-config-textarea-${block.id}`),
    ).not.toBeInTheDocument()
  })

  it("renders canonical path for body_section kind", () => {
    const block = makeBlock({
      block_kind: "body_section",
      config: { heading: "About", body: "..." },
    })
    render(
      <BlockConfigEditor
        block={block}
        blockKinds={BLOCK_KINDS}
        onUpdateConfig={() => undefined}
        onDelete={() => undefined}
        canEdit
      />,
    )
    expect(
      screen.getByTestId(`documents-block-config-canonical-${block.id}`),
    ).toBeInTheDocument()
  })

  it("renders canonical tableOfColumns control for line_items.columns", () => {
    const block = makeBlock({
      block_kind: "line_items",
      config: {
        items_variable: "items",
        columns: [{ header: "Qty", field: "qty" }],
      },
    })
    render(
      <BlockConfigEditor
        block={block}
        blockKinds={BLOCK_KINDS}
        onUpdateConfig={() => undefined}
        onDelete={() => undefined}
        canEdit
      />,
    )
    // The tableOfColumns control renders inside the field for `columns`
    expect(
      screen.getByTestId(
        `documents-block-field-${block.id}-columns-control`,
      ),
    ).toBeInTheDocument()
  })

  it("renders canonical tableOfRows control for totals.rows", () => {
    const block = makeBlock({
      block_kind: "totals",
      config: {
        rows: [{ label: "Subtotal", variable: "subtotal" }],
      },
    })
    render(
      <BlockConfigEditor
        block={block}
        blockKinds={BLOCK_KINDS}
        onUpdateConfig={() => undefined}
        onDelete={() => undefined}
        canEdit
      />,
    )
    expect(
      screen.getByTestId(`documents-block-field-${block.id}-rows-control`),
    ).toBeInTheDocument()
  })

  it("renders canonical listOfParties for signature.parties + boolean for show_dates", () => {
    const block = makeBlock({
      block_kind: "signature",
      config: {
        parties: [{ role: "Customer" }],
        show_dates: true,
      },
    })
    render(
      <BlockConfigEditor
        block={block}
        blockKinds={BLOCK_KINDS}
        onUpdateConfig={() => undefined}
        onDelete={() => undefined}
        canEdit
      />,
    )
    expect(
      screen.getByTestId(`documents-block-field-${block.id}-parties-control`),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId(
        `documents-block-field-${block.id}-show_dates-control`,
      ),
    ).toBeInTheDocument()
  })

  it("renders conditionalRule control for conditional_wrapper when onUpdateCondition provided", () => {
    const block = makeBlock({
      block_kind: "conditional_wrapper",
      config: { label: "If cremation" },
      condition: JSON.stringify({
        field: "case.disposition",
        operator: "equals",
        value: "cremation",
      }),
    })
    render(
      <BlockConfigEditor
        block={block}
        blockKinds={BLOCK_KINDS}
        onUpdateConfig={() => undefined}
        onUpdateCondition={() => undefined}
        onDelete={() => undefined}
        canEdit
      />,
    )
    expect(
      screen.getByTestId(
        `documents-block-field-${block.id}-__condition__-control`,
      ),
    ).toBeInTheDocument()
  })

  it("omits __condition__ field when onUpdateCondition NOT provided", () => {
    const block = makeBlock({
      block_kind: "conditional_wrapper",
      config: { label: "If cremation" },
      condition: null,
    })
    render(
      <BlockConfigEditor
        block={block}
        blockKinds={BLOCK_KINDS}
        onUpdateConfig={() => undefined}
        onDelete={() => undefined}
        canEdit
        // onUpdateCondition omitted
      />,
    )
    expect(
      screen.queryByTestId(
        `documents-block-field-${block.id}-__condition__-control`,
      ),
    ).not.toBeInTheDocument()
  })

  it("falls back to JSON textarea for unknown block kinds", () => {
    const block = makeBlock({
      block_kind: "unknown_future_kind" as TemplateBlock["block_kind"],
      config: { foo: "bar" },
    })
    const blockKinds = [
      ...BLOCK_KINDS,
      {
        kind: "unknown_future_kind",
        display_name: "Future Kind",
        description: "Substrate ahead of frontend.",
        config_schema: {},
        accepts_children: false,
      },
    ]
    render(
      <BlockConfigEditor
        block={block}
        blockKinds={blockKinds}
        onUpdateConfig={() => undefined}
        onDelete={() => undefined}
        canEdit
      />,
    )
    expect(
      screen.getByTestId(`documents-block-config-fallback-${block.id}`),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId(`documents-block-config-textarea-${block.id}`),
    ).toBeInTheDocument()
  })

  it("Save button calls onUpdateConfig with config minus synthetic __condition__", () => {
    const onUpdateConfig = vi.fn()
    const onUpdateCondition = vi.fn()
    const block = makeBlock({
      block_kind: "conditional_wrapper",
      config: { label: "" },
      condition: null,
    })
    render(
      <BlockConfigEditor
        block={block}
        blockKinds={BLOCK_KINDS}
        onUpdateConfig={onUpdateConfig}
        onUpdateCondition={onUpdateCondition}
        onDelete={() => undefined}
        canEdit
      />,
    )
    // Edit the label field to dirty the draft. StringControl renders
    // <input data-testid="{testid}-input"> per PropControls.tsx.
    fireEvent.change(
      screen.getByTestId(
        `documents-block-field-${block.id}-label-control-input`,
      ),
      { target: { value: "Cremation rider" } },
    )
    fireEvent.click(screen.getByTestId(`documents-block-save-${block.id}`))
    expect(onUpdateConfig).toHaveBeenCalledTimes(1)
    const cfg = onUpdateConfig.mock.calls[0][0]
    expect(cfg).toHaveProperty("label", "Cremation rider")
    expect(cfg).not.toHaveProperty("__condition__")
  })

  it("Save threads condition to onUpdateCondition (serialized) when conditional_wrapper edited", () => {
    const onUpdateConfig = vi.fn()
    const onUpdateCondition = vi.fn()
    const block = makeBlock({
      block_kind: "conditional_wrapper",
      config: { label: "If cremation" },
      condition: JSON.stringify({
        field: "",
        operator: "equals",
        value: "",
      }),
    })
    render(
      <BlockConfigEditor
        block={block}
        blockKinds={BLOCK_KINDS}
        onUpdateConfig={onUpdateConfig}
        onUpdateCondition={onUpdateCondition}
        onDelete={() => undefined}
        canEdit
      />,
    )
    // Edit the condition field
    fireEvent.change(
      screen.getByTestId(
        `documents-block-field-${block.id}-__condition__-control-field`,
      ),
      { target: { value: "case.disposition" } },
    )
    fireEvent.click(screen.getByTestId(`documents-block-save-${block.id}`))
    expect(onUpdateCondition).toHaveBeenCalledTimes(1)
    const serialized = onUpdateCondition.mock.calls[0][0]
    const parsed = JSON.parse(serialized!)
    expect(parsed.field).toBe("case.disposition")
    expect(parsed.operator).toBe("equals")
  })

  it("Reset reverts draft to saved snapshot", () => {
    const block = makeBlock({
      block_kind: "header",
      config: { title: "Original" },
    })
    render(
      <BlockConfigEditor
        block={block}
        blockKinds={BLOCK_KINDS}
        onUpdateConfig={() => undefined}
        onDelete={() => undefined}
        canEdit
      />,
    )
    const titleInputId = `documents-block-field-${block.id}-title-control-input`
    fireEvent.change(screen.getByTestId(titleInputId), {
      target: { value: "Modified" },
    })
    fireEvent.click(screen.getByTestId(`documents-block-reset-${block.id}`))
    expect(
      (screen.getByTestId(titleInputId) as HTMLInputElement).value,
    ).toBe("Original")
  })

  it("Delete button calls onDelete", () => {
    const onDelete = vi.fn()
    const block = makeBlock({ block_kind: "header" })
    render(
      <BlockConfigEditor
        block={block}
        blockKinds={BLOCK_KINDS}
        onUpdateConfig={() => undefined}
        onDelete={onDelete}
        canEdit
      />,
    )
    fireEvent.click(screen.getByTestId(`documents-block-delete-${block.id}`))
    expect(onDelete).toHaveBeenCalledTimes(1)
  })

  it("Inputs disabled when canEdit=false", () => {
    const block = makeBlock({ block_kind: "header", config: { title: "X" } })
    render(
      <BlockConfigEditor
        block={block}
        blockKinds={BLOCK_KINDS}
        onUpdateConfig={() => undefined}
        onDelete={() => undefined}
        canEdit={false}
      />,
    )
    expect(screen.getByTestId(`documents-block-save-${block.id}`)).toBeDisabled()
  })

  it("isSaving prop shows Saving… on Save button", () => {
    const block = makeBlock({ block_kind: "header", config: { title: "Modified" } })
    render(
      <BlockConfigEditor
        block={block}
        blockKinds={BLOCK_KINDS}
        onUpdateConfig={() => undefined}
        onDelete={() => undefined}
        canEdit
        isSaving
      />,
    )
    expect(screen.getByTestId(`documents-block-save-${block.id}`)).toHaveTextContent(
      /Saving/i,
    )
  })

  it("Error message renders when errorMessage prop provided", () => {
    const block = makeBlock({ block_kind: "header" })
    render(
      <BlockConfigEditor
        block={block}
        blockKinds={BLOCK_KINDS}
        onUpdateConfig={() => undefined}
        onDelete={() => undefined}
        canEdit
        errorMessage="Server rejected."
      />,
    )
    expect(
      screen.getByTestId(`documents-block-config-error-${block.id}`),
    ).toHaveTextContent("Server rejected.")
  })

  it("Block kind display name + description render", () => {
    const block = makeBlock({ block_kind: "header" })
    render(
      <BlockConfigEditor
        block={block}
        blockKinds={BLOCK_KINDS}
        onUpdateConfig={() => undefined}
        onDelete={() => undefined}
        canEdit
      />,
    )
    expect(screen.getByText("Header")).toBeInTheDocument()
    expect(screen.getByText("Document header.")).toBeInTheDocument()
  })

  it("Per-block immediate-write contract: dispatcher does not delay onUpdateConfig", () => {
    // Q-DOCS-2 canon — when Save fires, onUpdateConfig must be called
    // synchronously (no debounce / no autosave wrapping inside this
    // component). Parent owns the immediate-write semantics.
    const onUpdateConfig = vi.fn()
    const block = makeBlock({
      block_kind: "header",
      config: { title: "A" },
    })
    render(
      <BlockConfigEditor
        block={block}
        blockKinds={BLOCK_KINDS}
        onUpdateConfig={onUpdateConfig}
        onDelete={() => undefined}
        canEdit
      />,
    )
    fireEvent.change(
      screen.getByTestId(
        `documents-block-field-${block.id}-title-control-input`,
      ),
      { target: { value: "B" } },
    )
    fireEvent.click(screen.getByTestId(`documents-block-save-${block.id}`))
    expect(onUpdateConfig).toHaveBeenCalledTimes(1)
  })
})
