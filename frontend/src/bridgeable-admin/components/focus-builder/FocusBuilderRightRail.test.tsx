/**
 * FocusBuilderRightRail tests (sub-arcs F-2 + F-3).
 *
 * F-2 shipped placeholder palette + theme. F-3 replaces the palette
 * placeholder with the real WidgetPalette wrapper; theme stays a
 * placeholder until F-4.
 */
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { DndContext } from "@dnd-kit/core"

import "@/lib/visual-editor/registry/auto-register"

import { BASE_TOKENS } from "@/lib/visual-editor/themes/base-tokens"

import { FocusBuilderRightRail } from "./FocusBuilderRightRail"
import { FocusBuilderSelectionProvider } from "./FocusBuilderSelectionContext"

function mount(mode: "core" | "template" | "empty" = "empty") {
  return render(
    <DndContext>
      <FocusBuilderSelectionProvider>
        <FocusBuilderRightRail
          mode={mode}
          themeTokens={{ ...BASE_TOKENS.light }}
          coreHook={null}
          templateHook={null}
          inheritedCore={null}
          sources={null}
        />
      </FocusBuilderSelectionProvider>
    </DndContext>,
  )
}

describe("FocusBuilderRightRail", () => {
  it("mounts three sections (inspector + palette + theme placeholder)", () => {
    mount("empty")
    expect(
      screen.getByTestId("focus-builder-inspector-region"),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("focus-builder-widget-palette-region"),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("focus-builder-theme-region"),
    ).toBeInTheDocument()
  })

  it("renders the real widget palette in F-3", () => {
    mount("template")
    expect(screen.getByTestId("widget-palette")).toBeInTheDocument()
  })

  it("theme region keeps the F-4 placeholder", () => {
    mount("empty")
    expect(screen.getByText(/Arrives in F-4/)).toBeInTheDocument()
  })

  it("palette is disabled when subject is a core", () => {
    mount("core")
    const palette = screen.getByTestId("widget-palette")
    expect(palette.getAttribute("data-disabled")).toBe("true")
    expect(
      screen.getByTestId("focus-builder-palette-disabled-hint"),
    ).toBeInTheDocument()
  })

  it("palette is enabled when subject is a template", () => {
    mount("template")
    const palette = screen.getByTestId("widget-palette")
    expect(palette.getAttribute("data-disabled")).toBe("false")
  })
})
