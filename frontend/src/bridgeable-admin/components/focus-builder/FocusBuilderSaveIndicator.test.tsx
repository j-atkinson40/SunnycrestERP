/**
 * FocusBuilderSaveIndicator unit tests (sub-arc F-5).
 */
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import {
  FocusBuilderSaveIndicator,
  deriveSaveIndicatorState,
} from "./FocusBuilderSaveIndicator"


describe("deriveSaveIndicatorState", () => {
  it("error wins over all other states", () => {
    expect(
      deriveSaveIndicatorState({
        isDirty: true,
        isSaving: true,
        error: "boom",
        lastSavedAt: new Date(),
      }),
    ).toEqual({ kind: "failed" })
  })

  it("saving wins over dirty + saved", () => {
    expect(
      deriveSaveIndicatorState({
        isDirty: true,
        isSaving: true,
        error: null,
        lastSavedAt: new Date(),
      }),
    ).toEqual({ kind: "saving" })
  })

  it("unsaved wins over saved when dirty", () => {
    expect(
      deriveSaveIndicatorState({
        isDirty: true,
        isSaving: false,
        error: null,
        lastSavedAt: new Date(),
      }),
    ).toEqual({ kind: "unsaved" })
  })

  it("saved when lastSavedAt set + not dirty + not saving + no error", () => {
    const when = new Date()
    expect(
      deriveSaveIndicatorState({
        isDirty: false,
        isSaving: false,
        error: null,
        lastSavedAt: when,
      }),
    ).toEqual({ kind: "saved", lastSavedAt: when })
  })

  it("empty when nothing has happened yet", () => {
    expect(
      deriveSaveIndicatorState({
        isDirty: false,
        isSaving: false,
        error: null,
        lastSavedAt: null,
      }),
    ).toEqual({ kind: "empty" })
  })
})


describe("FocusBuilderSaveIndicator", () => {
  const noop = () => {
    /* noop */
  }

  it("renders null in empty state", () => {
    const { container } = render(
      <FocusBuilderSaveIndicator
        isDirty={false}
        isSaving={false}
        error={null}
        lastSavedAt={null}
        onRetry={noop}
      />,
    )
    expect(container.firstChild).toBeNull()
  })

  it("renders Saved · Xs ago when saved", () => {
    const when = new Date(Date.now() - 3_000) // 3s ago — under "just now"=5s
    render(
      <FocusBuilderSaveIndicator
        isDirty={false}
        isSaving={false}
        error={null}
        lastSavedAt={when}
        onRetry={noop}
      />,
    )
    const ind = screen.getByTestId("save-indicator")
    expect(ind).toHaveAttribute("data-state", "saved")
    // operator-observable textContent matches "Saved · ..."
    expect(ind.textContent).toMatch(/^Saved ·\s+(just now|\d+s ago)$/)
  })

  it("renders Saving… when in-flight", () => {
    render(
      <FocusBuilderSaveIndicator
        isDirty
        isSaving
        error={null}
        lastSavedAt={null}
        onRetry={noop}
      />,
    )
    const ind = screen.getByTestId("save-indicator")
    expect(ind).toHaveAttribute("data-state", "saving")
    expect(ind.textContent).toBe("Saving…")
  })

  it("renders Unsaved changes when dirty + not saving", () => {
    render(
      <FocusBuilderSaveIndicator
        isDirty
        isSaving={false}
        error={null}
        lastSavedAt={null}
        onRetry={noop}
      />,
    )
    const ind = screen.getByTestId("save-indicator")
    expect(ind).toHaveAttribute("data-state", "unsaved")
    expect(ind.textContent).toBe("Unsaved changes")
  })

  it("renders Save failed · Retry when error", () => {
    render(
      <FocusBuilderSaveIndicator
        isDirty
        isSaving={false}
        error="boom"
        lastSavedAt={null}
        onRetry={noop}
      />,
    )
    const ind = screen.getByTestId("save-indicator")
    expect(ind).toHaveAttribute("data-state", "failed")
    expect(ind.textContent).toMatch(/^Save failed ·\s+Retry$/)
    expect(screen.getByTestId("save-indicator-retry")).toBeInTheDocument()
  })

  it("Retry click invokes onRetry", () => {
    const onRetry = vi.fn()
    render(
      <FocusBuilderSaveIndicator
        isDirty
        isSaving={false}
        error="boom"
        lastSavedAt={null}
        onRetry={onRetry}
      />,
    )
    fireEvent.click(screen.getByTestId("save-indicator-retry"))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })
})
