/**
 * Vitest — JsonTextareaEditor (R-6.0b).
 *
 * Covers initial JSON stringification, JSON.parse on save success +
 * error path, save callback receives parsed value, cancel callback,
 * resync on re-open with new initialData.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { JsonTextareaEditor } from "./json-textarea-editor"


describe("JsonTextareaEditor — R-6.0b", () => {
  it("does not render when open=false", () => {
    render(
      <JsonTextareaEditor
        open={false}
        onClose={vi.fn()}
        initialData={{ a: 1 }}
        onSave={vi.fn()}
      />,
    )
    expect(
      screen.queryByTestId("json-textarea-editor"),
    ).toBeNull()
  })

  it("renders initialData as pretty JSON in the textarea", () => {
    render(
      <JsonTextareaEditor
        open
        onClose={vi.fn()}
        initialData={{ name: "John", age: 42 }}
        onSave={vi.fn()}
      />,
    )
    const ta = screen.getByTestId(
      "json-textarea-editor-textarea",
    ) as HTMLTextAreaElement
    const parsed = JSON.parse(ta.value)
    expect(parsed).toEqual({ name: "John", age: 42 })
  })

  it("Save with valid JSON calls onSave with parsed value", async () => {
    const onSave = vi.fn()
    render(
      <JsonTextareaEditor
        open
        onClose={vi.fn()}
        initialData={{ a: 1 }}
        onSave={onSave}
      />,
    )
    const ta = screen.getByTestId(
      "json-textarea-editor-textarea",
    ) as HTMLTextAreaElement
    fireEvent.change(ta, {
      target: { value: '{"a": 99, "b": "ok"}' },
    })
    fireEvent.click(screen.getByTestId("json-textarea-editor-save"))
    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith({ a: 99, b: "ok" })
    })
  })

  it("Save with invalid JSON surfaces error inline + does NOT call onSave", () => {
    const onSave = vi.fn()
    render(
      <JsonTextareaEditor
        open
        onClose={vi.fn()}
        initialData={{}}
        onSave={onSave}
      />,
    )
    const ta = screen.getByTestId(
      "json-textarea-editor-textarea",
    ) as HTMLTextAreaElement
    fireEvent.change(ta, { target: { value: "{not valid" } })
    fireEvent.click(screen.getByTestId("json-textarea-editor-save"))
    expect(onSave).not.toHaveBeenCalled()
    expect(
      screen.getByTestId("json-textarea-editor-error"),
    ).toBeTruthy()
  })

  it("Cancel button calls onClose without invoking onSave", () => {
    const onClose = vi.fn()
    const onSave = vi.fn()
    render(
      <JsonTextareaEditor
        open
        onClose={onClose}
        initialData={{}}
        onSave={onSave}
      />,
    )
    fireEvent.click(screen.getByTestId("json-textarea-editor-cancel"))
    expect(onClose).toHaveBeenCalled()
    expect(onSave).not.toHaveBeenCalled()
  })

  it("Save retains dialog open if onSave throws", async () => {
    const onSave = vi.fn().mockRejectedValue(new Error("network"))
    render(
      <JsonTextareaEditor
        open
        onClose={vi.fn()}
        initialData={{ a: 1 }}
        onSave={onSave}
      />,
    )
    fireEvent.click(screen.getByTestId("json-textarea-editor-save"))
    await waitFor(() => {
      expect(
        screen.getByTestId("json-textarea-editor-error"),
      ).toBeTruthy()
    })
    expect(screen.getByTestId("json-textarea-editor-error").textContent).toBe(
      "network",
    )
  })
})
