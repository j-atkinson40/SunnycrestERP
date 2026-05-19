/**
 * FocusBuilderRightRail tests (sub-arc F-2).
 */
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"

import { BASE_TOKENS } from "@/lib/visual-editor/themes/base-tokens"

import { FocusBuilderRightRail } from "./FocusBuilderRightRail"
import { FocusBuilderSelectionProvider } from "./FocusBuilderSelectionContext"

describe("FocusBuilderRightRail", () => {
  it("mounts three sections (inspector + palette + theme placeholders)", () => {
    render(
      <FocusBuilderSelectionProvider>
        <FocusBuilderRightRail
          mode="empty"
          themeTokens={{ ...BASE_TOKENS.light }}
          coreHook={null}
          templateHook={null}
          inheritedCore={null}
          sources={null}
        />
      </FocusBuilderSelectionProvider>,
    )
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

  it("placeholders announce future sub-arc names", () => {
    render(
      <FocusBuilderSelectionProvider>
        <FocusBuilderRightRail
          mode="empty"
          themeTokens={{ ...BASE_TOKENS.light }}
          coreHook={null}
          templateHook={null}
          inheritedCore={null}
          sources={null}
        />
      </FocusBuilderSelectionProvider>,
    )
    expect(screen.getByText(/Arrives in F-3/)).toBeInTheDocument()
    expect(screen.getByText(/Arrives in F-4/)).toBeInTheDocument()
  })
})
