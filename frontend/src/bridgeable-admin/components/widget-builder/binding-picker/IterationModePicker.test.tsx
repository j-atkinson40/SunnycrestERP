/**
 * IterationModePicker tests — WB-6 auto-inferred read-only display.
 */
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"

import {
  IterationModePicker,
  inferIterationMode,
} from "./IterationModePicker"


describe("inferIterationMode", () => {
  it("repeater_atom → per_row locked", () => {
    const r = inferIterationMode({ atomType: "repeater_atom", presentationMode: "list" })
    expect(r.mode).toBe("per_row")
    expect(r.locked).toBe(true)
  })

  it("chart presentation → single_summary locked", () => {
    const r = inferIterationMode({ atomType: "value_display", presentationMode: "chart" })
    expect(r.mode).toBe("single_summary")
    expect(r.locked).toBe(true)
  })

  it("stat presentation → single_summary locked", () => {
    const r = inferIterationMode({ atomType: "value_display", presentationMode: "stat" })
    expect(r.mode).toBe("single_summary")
    expect(r.locked).toBe(true)
  })

  it("list presentation → single_record default, not locked", () => {
    const r = inferIterationMode({ atomType: "value_display", presentationMode: "list" })
    expect(r.mode).toBe("single_record")
    expect(r.locked).toBe(false)
  })

  it("null presentation → single_record default", () => {
    const r = inferIterationMode({ atomType: "text_label", presentationMode: null })
    expect(r.mode).toBe("single_record")
    expect(r.locked).toBe(false)
  })
})


describe("IterationModePicker", () => {
  it("renders locked badge for repeater_atom", () => {
    render(
      <IterationModePicker
        atomType="repeater_atom"
        presentationMode="list"
        value="per_row"
        onChange={() => {}}
        testId="im-picker"
      />,
    )
    expect(screen.getByTestId("im-picker")).toHaveTextContent("per row")
    expect(screen.getByTestId("im-picker")).toHaveTextContent("auto")
  })

  it("renders locked badge for chart presentation", () => {
    render(
      <IterationModePicker
        atomType="value_display"
        presentationMode="chart"
        value="single_summary"
        onChange={() => {}}
        testId="im-picker"
      />,
    )
    expect(screen.getByTestId("im-picker")).toHaveTextContent("single summary")
    expect(screen.getByTestId("im-picker")).toHaveTextContent("auto")
  })

  it("renders a Select for the list-presentation case", () => {
    render(
      <IterationModePicker
        atomType="value_display"
        presentationMode="list"
        value="single_record"
        onChange={() => {}}
        testId="im-picker"
      />,
    )
    // Select trigger surfaces with the testid.
    expect(screen.getByTestId("im-picker")).toBeInTheDocument()
  })
})
