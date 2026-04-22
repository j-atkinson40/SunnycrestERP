/**
 * ModeDispatcher — vitest unit tests.
 *
 * Renders the right core for each registered mode; renders the
 * unknown-focus error state for ids not in the registry.
 */

import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { ModeDispatcher } from "./mode-dispatcher"


describe("ModeDispatcher — routes to the correct core by mode", () => {
  const cases: Array<{ id: string; expectedTitle: string; expectedEyebrow: string }> = [
    { id: "test-kanban", expectedTitle: "Kanban stub", expectedEyebrow: "kanban" },
    {
      id: "test-single-record",
      expectedTitle: "Single-record stub",
      expectedEyebrow: "singleRecord",
    },
    {
      id: "test-edit-canvas",
      expectedTitle: "Edit-canvas stub",
      expectedEyebrow: "editCanvas",
    },
    {
      id: "test-triage-queue",
      expectedTitle: "Triage-queue stub",
      expectedEyebrow: "triageQueue",
    },
    { id: "test-matrix", expectedTitle: "Matrix stub", expectedEyebrow: "matrix" },
  ]

  for (const { id, expectedTitle, expectedEyebrow } of cases) {
    it(`renders the core for id=${id}`, () => {
      render(<ModeDispatcher focusId={id} />)
      expect(screen.getByText(expectedTitle)).toBeInTheDocument()
      // Eyebrow includes the mode label — use getAllByText in case
      // the mode name appears elsewhere on the page.
      expect(
        screen.getByText(new RegExp(`Core mode.*${expectedEyebrow}`, "i")),
      ).toBeInTheDocument()
    })
  }
})


describe("ModeDispatcher — unknown id", () => {
  it("renders the unknown-focus error state (not a crash)", () => {
    render(<ModeDispatcher focusId="does-not-exist" />)
    expect(screen.getByText(/No Focus registered at this id/i)).toBeInTheDocument()
    expect(screen.getByText(/does-not-exist/)).toBeInTheDocument()
    expect(screen.getByText(/Unknown focus/i)).toBeInTheDocument()
  })

  it("error state includes the dismiss hint (Esc)", () => {
    render(<ModeDispatcher focusId="still-missing" />)
    expect(screen.getByText(/click outside to dismiss/i)).toBeInTheDocument()
  })
})
