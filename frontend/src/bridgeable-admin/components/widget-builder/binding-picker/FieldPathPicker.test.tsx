/**
 * FieldPathPicker tests — WB-6 cascading combobox + free-text fallback.
 */
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { FieldPathPicker } from "./FieldPathPicker"
import type { EntityTypeMetadata } from "@/types/saved-views"


const ENTITY_TYPES: EntityTypeMetadata[] = [
  {
    entity_type: "invoice",
    display_name: "Invoice",
    icon: "file",
    navigate_url_template: "/invoices/{id}",
    available_fields: [
      {
        field_name: "number",
        display_name: "Number",
        field_type: "text",
      },
      {
        field_name: "total",
        display_name: "Total",
        field_type: "currency",
      },
      {
        field_name: "status",
        display_name: "Status",
        field_type: "enum",
        enum_values: ["draft", "sent", "paid"],
      },
    ],
    default_sort: [],
    default_columns: [],
  },
]


describe("FieldPathPicker", () => {
  it("is disabled when no entity type selected", () => {
    render(
      <FieldPathPicker
        entityType={null}
        entityTypes={ENTITY_TYPES}
        value={null}
        onChange={() => {}}
        testId="fp-picker"
      />,
    )
    const trigger = screen.getByTestId("fp-picker")
    expect(trigger).toBeDisabled()
    expect(trigger).toHaveTextContent("Pick a saved view first")
  })

  it("enables when entity type is set", () => {
    render(
      <FieldPathPicker
        entityType="invoice"
        entityTypes={ENTITY_TYPES}
        value={null}
        onChange={() => {}}
        testId="fp-picker"
      />,
    )
    expect(screen.getByTestId("fp-picker")).not.toBeDisabled()
  })

  it("lists available fields for the selected entity type", () => {
    render(
      <FieldPathPicker
        entityType="invoice"
        entityTypes={ENTITY_TYPES}
        value={null}
        onChange={() => {}}
        testId="fp-picker"
      />,
    )
    fireEvent.click(screen.getByTestId("fp-picker"))
    expect(screen.getByTestId("fp-picker-option-number")).toBeInTheDocument()
    expect(screen.getByTestId("fp-picker-option-total")).toBeInTheDocument()
    expect(screen.getByTestId("fp-picker-option-status")).toBeInTheDocument()
  })

  it("calls onChange when a field is picked", () => {
    const onChange = vi.fn()
    render(
      <FieldPathPicker
        entityType="invoice"
        entityTypes={ENTITY_TYPES}
        value={null}
        onChange={onChange}
        testId="fp-picker"
      />,
    )
    fireEvent.click(screen.getByTestId("fp-picker"))
    fireEvent.click(screen.getByTestId("fp-picker-option-total"))
    expect(onChange).toHaveBeenCalledWith("total")
  })

  it("filters fields via search input", () => {
    render(
      <FieldPathPicker
        entityType="invoice"
        entityTypes={ENTITY_TYPES}
        value={null}
        onChange={() => {}}
        testId="fp-picker"
      />,
    )
    fireEvent.click(screen.getByTestId("fp-picker"))
    fireEvent.change(screen.getByTestId("fp-picker-search"), {
      target: { value: "total" },
    })
    expect(screen.queryByTestId("fp-picker-option-number")).toBeNull()
    expect(screen.getByTestId("fp-picker-option-total")).toBeInTheDocument()
  })

  it("accepts free-text input for custom paths (Risk 1 fallback)", () => {
    const onChange = vi.fn()
    render(
      <FieldPathPicker
        entityType="invoice"
        entityTypes={ENTITY_TYPES}
        value={null}
        onChange={onChange}
        testId="fp-picker"
      />,
    )
    const freetext = screen.getByTestId("fp-picker-freetext")
    fireEvent.change(freetext, { target: { value: "metadata_json.line_items.0.total" } })
    fireEvent.blur(freetext)
    expect(onChange).toHaveBeenCalledWith("metadata_json.line_items.0.total")
  })
})
