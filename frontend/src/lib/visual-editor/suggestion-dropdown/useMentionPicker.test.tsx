/**
 * Arc 4b.2b — useMentionPicker hook unit tests.
 *
 * Drives the hook via a thin harness component that wires
 * value/onChange to a textarea and exercises the trigger detection
 * + state machine + insertion logic.
 */
import { describe, expect, it } from "vitest"
import { act } from "react"
import { fireEvent, render } from "@testing-library/react"
import { useRef, useState } from "react"

import { useMentionPicker } from "./useMentionPicker"


/** Test harness — controlled textarea wired to the hook. Exposes
 *  state via data attributes for assertion. */
function Harness({ initial = "" }: { initial?: string }) {
  const [value, setValue] = useState(initial)
  const fieldRef = useRef<HTMLTextAreaElement | null>(null)
  const picker = useMentionPicker({
    value,
    onValueChange: setValue,
    fieldRef,
  })
  return (
    <div>
      <textarea
        ref={fieldRef}
        data-testid="field"
        value={value}
        onChange={picker.handleInputChange}
        onKeyDown={picker.handleKeyDown}
      />
      <div data-testid="value">{value}</div>
      <div
        data-testid="picker-state"
        data-open={picker.pickerState.open ? "true" : "false"}
        data-trigger-pos={String(picker.pickerState.triggerPosition)}
        data-query={picker.pickerState.query}
        data-entity-type={picker.pickerState.entityType}
      />
      <button
        type="button"
        data-testid="select-case"
        onClick={() =>
          picker.handleSelectCandidate({
            entity_type: "case",
            entity_id: "abc-123",
          })
        }
      />
      <button
        type="button"
        data-testid="cancel-erase"
        onClick={() => picker.handleCancelEraseText()}
      />
      <button
        type="button"
        data-testid="cancel-keep"
        onClick={() => picker.handleCancelKeepText()}
      />
      <button
        type="button"
        data-testid="switch-order"
        onClick={() => picker.setEntityType("order")}
      />
    </div>
  )
}


/** Helper: simulate typing N characters into the textarea by
 *  firing change events at each step. Per testing-library semantics,
 *  fireEvent.change(field, { target: { value } }) sets field.value
 *  AND fires the change event; jsdom advances selectionStart to the
 *  end of the new value automatically. */
function type(
  field: HTMLTextAreaElement,
  text: string,
  startingValue = "",
) {
  let value = startingValue
  for (const ch of text) {
    value = value + ch
    fireEvent.change(field, { target: { value } })
  }
}


describe("useMentionPicker — trigger detection", () => {
  it("opens picker when `@` is typed at start of empty field", () => {
    const { getByTestId } = render(<Harness />)
    const field = getByTestId("field") as HTMLTextAreaElement
    type(field, "@")
    expect(getByTestId("picker-state").getAttribute("data-open")).toBe("true")
    expect(getByTestId("picker-state").getAttribute("data-trigger-pos")).toBe("0")
    expect(getByTestId("picker-state").getAttribute("data-query")).toBe("")
  })

  it("opens picker when `@` is typed after whitespace", () => {
    const { getByTestId } = render(<Harness initial="hello " />)
    const field = getByTestId("field") as HTMLTextAreaElement
    // Initial value "hello " — type "@" to advance to "hello @"
    type(field, "@", "hello ")
    expect(getByTestId("picker-state").getAttribute("data-open")).toBe("true")
    expect(getByTestId("picker-state").getAttribute("data-trigger-pos")).toBe("6")
  })

  it("does NOT open picker when `@` is mid-word (email-like)", () => {
    const { getByTestId } = render(<Harness initial="user" />)
    const field = getByTestId("field") as HTMLTextAreaElement
    // Initial value "user" — type "@" to advance to "user@"
    type(field, "@", "user")
    expect(getByTestId("picker-state").getAttribute("data-open")).toBe("false")
  })

  it("captures query characters typed after `@`", () => {
    const { getByTestId } = render(<Harness />)
    const field = getByTestId("field") as HTMLTextAreaElement
    type(field, "@Hop")
    expect(getByTestId("picker-state").getAttribute("data-open")).toBe("true")
    expect(getByTestId("picker-state").getAttribute("data-query")).toBe("Hop")
  })

  it("closes picker on whitespace in query", () => {
    const { getByTestId } = render(<Harness />)
    const field = getByTestId("field") as HTMLTextAreaElement
    type(field, "@Hop ")
    expect(getByTestId("picker-state").getAttribute("data-open")).toBe("false")
  })

  it("closes picker when `@` is deleted via backspace", () => {
    const { getByTestId } = render(<Harness />)
    const field = getByTestId("field") as HTMLTextAreaElement
    type(field, "@H")
    expect(getByTestId("picker-state").getAttribute("data-open")).toBe("true")
    // Simulate backspace twice — once removes H, once removes @.
    fireEvent.change(field, { target: { value: "@" } })
    // Picker still open after first backspace.
    expect(getByTestId("picker-state").getAttribute("data-open")).toBe("true")
    fireEvent.change(field, { target: { value: "" } })
    expect(getByTestId("picker-state").getAttribute("data-open")).toBe("false")
  })
})


describe("useMentionPicker — selection", () => {
  it("inserts canonical Jinja token replacing `@<query>`", () => {
    const { getByTestId } = render(<Harness initial="" />)
    const field = getByTestId("field") as HTMLTextAreaElement
    type(field, "@Hop")
    act(() => {
      getByTestId("select-case").click()
    })
    const value = getByTestId("value").textContent
    expect(value).toBe('{{ ref("case", "abc-123") }}')
    expect(getByTestId("picker-state").getAttribute("data-open")).toBe("false")
  })

  it("inserts token mid-content preserving prefix", () => {
    const Harness2 = () => {
      const [value, setValue] = useState("prefix ")
      const fieldRef = useRef<HTMLTextAreaElement | null>(null)
      const picker = useMentionPicker({
        value,
        onValueChange: setValue,
        fieldRef,
      })
      return (
        <div>
          <textarea
            ref={fieldRef}
            data-testid="field"
            value={value}
            onChange={picker.handleInputChange}
          />
          <div data-testid="value">{value}</div>
          <button
            type="button"
            data-testid="select"
            onClick={() =>
              picker.handleSelectCandidate({
                entity_type: "order",
                entity_id: "SO-100",
              })
            }
          />
        </div>
      )
    }
    const { getByTestId } = render(<Harness2 />)
    const field = getByTestId("field") as HTMLTextAreaElement
    // Append "@Mar" to "prefix " → "prefix @Mar"
    fireEvent.change(field, { target: { value: "prefix @" } })
    fireEvent.change(field, { target: { value: "prefix @M" } })
    fireEvent.change(field, { target: { value: "prefix @Ma" } })
    fireEvent.change(field, { target: { value: "prefix @Mar" } })
    act(() => {
      getByTestId("select").click()
    })
    expect(getByTestId("value").textContent).toBe(
      'prefix {{ ref("order", "SO-100") }}',
    )
  })
})


describe("useMentionPicker — Escape (β semantics)", () => {
  it("Escape erases `@<query>` and closes", () => {
    const { getByTestId } = render(<Harness />)
    const field = getByTestId("field") as HTMLTextAreaElement
    type(field, "hello @Hop")
    expect(getByTestId("picker-state").getAttribute("data-open")).toBe("true")
    fireEvent.keyDown(field, { key: "Escape" })
    expect(getByTestId("picker-state").getAttribute("data-open")).toBe("false")
    // β semantics: `@Hop` erased; result is "hello "
    expect(getByTestId("value").textContent).toBe("hello ")
  })

  it("cancel-keep-text does NOT erase typed content (α semantics)", () => {
    const { getByTestId } = render(<Harness />)
    const field = getByTestId("field") as HTMLTextAreaElement
    type(field, "hello @Hop")
    expect(getByTestId("picker-state").getAttribute("data-open")).toBe("true")
    act(() => {
      getByTestId("cancel-keep").click()
    })
    expect(getByTestId("picker-state").getAttribute("data-open")).toBe("false")
    expect(getByTestId("value").textContent).toBe("hello @Hop")
  })

  it("cancel-erase explicit call erases like Escape", () => {
    const { getByTestId } = render(<Harness />)
    const field = getByTestId("field") as HTMLTextAreaElement
    type(field, "@xyz")
    act(() => {
      getByTestId("cancel-erase").click()
    })
    expect(getByTestId("picker-state").getAttribute("data-open")).toBe("false")
    expect(getByTestId("value").textContent).toBe("")
  })
})


describe("useMentionPicker — entity-type switching", () => {
  it("setEntityType switches without closing", () => {
    const { getByTestId } = render(<Harness />)
    const field = getByTestId("field") as HTMLTextAreaElement
    type(field, "@")
    expect(getByTestId("picker-state").getAttribute("data-entity-type")).toBe(
      "case",
    )
    act(() => {
      getByTestId("switch-order").click()
    })
    expect(getByTestId("picker-state").getAttribute("data-entity-type")).toBe(
      "order",
    )
    expect(getByTestId("picker-state").getAttribute("data-open")).toBe("true")
  })

  it("setEntityType is a no-op when picker closed", () => {
    const { getByTestId } = render(<Harness />)
    expect(getByTestId("picker-state").getAttribute("data-open")).toBe("false")
    act(() => {
      getByTestId("switch-order").click()
    })
    // Still closed; entity_type unchanged (default = case).
    expect(getByTestId("picker-state").getAttribute("data-open")).toBe("false")
    expect(getByTestId("picker-state").getAttribute("data-entity-type")).toBe(
      "case",
    )
  })
})
