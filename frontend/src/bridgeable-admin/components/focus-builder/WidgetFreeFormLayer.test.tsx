/**
 * WidgetFreeFormLayer unit tests (sub-arc FF-2).
 *
 * Validates:
 *   - one FreeFormPlacedWidget rendered per placement
 *   - inherited core rendered at canonical anchored position per Q-20
 *     formula (`core_width = canvas_width * span/12`,
 *     `core_x = (canvas_width - core_width)/2`, `core_y = 40`)
 *   - defensive canvas-dimension fallback to 1200×800 when
 *     `canvasWidth` / `canvasHeight` absent (Q-2 refinement)
 *
 * Operator-observable assertion canon (2026-05-20 late-evening):
 * assertions target inline style values at rendered elements.
 */
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"

import "@/lib/visual-editor/registry/auto-register"

import { BASE_TOKENS } from "@/lib/visual-editor/themes/base-tokens"

import { WidgetFreeFormLayer } from "./WidgetFreeFormLayer"
import { FocusBuilderSelectionProvider } from "./FocusBuilderSelectionContext"
import type { WidgetPlacement } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"

const tokens = { ...BASE_TOKENS.light }

const identity = {
  kind: "INHERITED CORE",
  title: "Scheduling Kanban",
  slug: "scheduling-kanban-core",
  version: 9,
  presetLabel: "card" as string | null,
  description: "Edit chrome on the right.",
}

describe("WidgetFreeFormLayer", () => {
  it("renders one FreeFormPlacedWidget per placement", () => {
    const placements: WidgetPlacement[] = [
      {
        id: "w-1",
        widget_slug: "today-pin-widget",
        x: 100,
        y: 100,
        width: 240,
        height: 120,
        chrome: {},
      },
      {
        id: "w-2",
        widget_slug: "day-strip-widget",
        x: 400,
        y: 200,
        width: 240,
        height: 120,
        chrome: {},
      },
    ]
    render(
      <FocusBuilderSelectionProvider>
        <WidgetFreeFormLayer
          placements={placements}
          themeTokens={tokens}
          canvasWidth={1200}
          canvasHeight={800}
          coreDefaultColumnSpan={12}
          coreIdentity={identity}
          coreCardStyle={{}}
          headingStyle={undefined}
          bodyStyle={undefined}
        />
      </FocusBuilderSelectionProvider>,
    )
    const placed = screen.getAllByTestId("focus-builder-placed-widget")
    expect(placed).toHaveLength(2)
    expect(placed[0].getAttribute("data-widget-id")).toBe("w-1")
    expect(placed[1].getAttribute("data-widget-id")).toBe("w-2")
  })

  it("emits canvas-dimensioned container with width/height from canvas_config", () => {
    render(
      <FocusBuilderSelectionProvider>
        <WidgetFreeFormLayer
          placements={[]}
          themeTokens={tokens}
          canvasWidth={1400}
          canvasHeight={900}
          coreDefaultColumnSpan={12}
          coreIdentity={identity}
          coreCardStyle={{}}
          headingStyle={undefined}
          bodyStyle={undefined}
        />
      </FocusBuilderSelectionProvider>,
    )
    const layer = screen.getByTestId("focus-builder-freeform-layer")
    const styleAttr = layer.getAttribute("style") ?? ""
    expect(styleAttr).toMatch(/width:\s*1400px/i)
    expect(styleAttr).toMatch(/height:\s*900px/i)
    expect(layer.getAttribute("data-canvas-width")).toBe("1400")
    expect(layer.getAttribute("data-canvas-height")).toBe("900")
  })

  it("defensive fallback to 1200×800 when canvas dimensions absent (Q-2 refinement)", () => {
    // Verify-against-pre-fix: if WidgetFreeFormLayer omitted the
    // defensive fallback, this test would fail with NaN-driven CSS
    // values or a 0×0 container.
    render(
      <FocusBuilderSelectionProvider>
        <WidgetFreeFormLayer
          placements={[]}
          themeTokens={tokens}
          canvasWidth={undefined}
          canvasHeight={undefined}
          coreDefaultColumnSpan={12}
          coreIdentity={identity}
          coreCardStyle={{}}
          headingStyle={undefined}
          bodyStyle={undefined}
        />
      </FocusBuilderSelectionProvider>,
    )
    const layer = screen.getByTestId("focus-builder-freeform-layer")
    const styleAttr = layer.getAttribute("style") ?? ""
    expect(styleAttr).toMatch(/width:\s*1200px/i)
    expect(styleAttr).toMatch(/height:\s*800px/i)
  })

  it("renders inherited core at canonical position per Q-20 formula (span=12, full-width-centered)", () => {
    render(
      <FocusBuilderSelectionProvider>
        <WidgetFreeFormLayer
          placements={[]}
          themeTokens={tokens}
          canvasWidth={1200}
          canvasHeight={800}
          coreDefaultColumnSpan={12}
          coreIdentity={identity}
          coreCardStyle={{}}
          headingStyle={undefined}
          bodyStyle={undefined}
        />
      </FocusBuilderSelectionProvider>,
    )
    const core = screen.getByTestId("focus-builder-core-placement")
    const styleAttr = core.getAttribute("style") ?? ""
    // span=12 → core_width=1200; core_x=(1200-1200)/2=0; core_y=40.
    expect(styleAttr).toMatch(/position:\s*absolute/i)
    expect(styleAttr).toMatch(/left:\s*0px/i)
    expect(styleAttr).toMatch(/top:\s*40px/i)
    expect(styleAttr).toMatch(/width:\s*1200px/i)
  })

  it("renders inherited core at canonical position per Q-20 formula (span=8, narrower-centered)", () => {
    render(
      <FocusBuilderSelectionProvider>
        <WidgetFreeFormLayer
          placements={[]}
          themeTokens={tokens}
          canvasWidth={1200}
          canvasHeight={800}
          coreDefaultColumnSpan={8}
          coreIdentity={identity}
          coreCardStyle={{}}
          headingStyle={undefined}
          bodyStyle={undefined}
        />
      </FocusBuilderSelectionProvider>,
    )
    const core = screen.getByTestId("focus-builder-core-placement")
    const styleAttr = core.getAttribute("style") ?? ""
    // span=8 → core_width=1200*8/12=800; core_x=(1200-800)/2=200; core_y=40.
    expect(styleAttr).toMatch(/left:\s*200px/i)
    expect(styleAttr).toMatch(/top:\s*40px/i)
    expect(styleAttr).toMatch(/width:\s*800px/i)
  })

  it("falls back to span=12 when coreDefaultColumnSpan absent", () => {
    render(
      <FocusBuilderSelectionProvider>
        <WidgetFreeFormLayer
          placements={[]}
          themeTokens={tokens}
          canvasWidth={1200}
          canvasHeight={800}
          coreDefaultColumnSpan={undefined}
          coreIdentity={identity}
          coreCardStyle={{}}
          headingStyle={undefined}
          bodyStyle={undefined}
        />
      </FocusBuilderSelectionProvider>,
    )
    const core = screen.getByTestId("focus-builder-core-placement")
    const styleAttr = core.getAttribute("style") ?? ""
    expect(styleAttr).toMatch(/width:\s*1200px/i)
  })

  it("emits data-canvas-inherited-core marker on the core element", () => {
    render(
      <FocusBuilderSelectionProvider>
        <WidgetFreeFormLayer
          placements={[]}
          themeTokens={tokens}
          canvasWidth={1200}
          canvasHeight={800}
          coreDefaultColumnSpan={12}
          coreIdentity={identity}
          coreCardStyle={{}}
          headingStyle={undefined}
          bodyStyle={undefined}
        />
      </FocusBuilderSelectionProvider>,
    )
    const core = screen.getByTestId("focus-builder-core-placement")
    expect(core.getAttribute("data-canvas-inherited-core")).toBe("true")
  })

  it("renders core identity (kind/title/slug/version/preset)", () => {
    render(
      <FocusBuilderSelectionProvider>
        <WidgetFreeFormLayer
          placements={[]}
          themeTokens={tokens}
          canvasWidth={1200}
          canvasHeight={800}
          coreDefaultColumnSpan={12}
          coreIdentity={identity}
          coreCardStyle={{}}
          headingStyle={undefined}
          bodyStyle={undefined}
        />
      </FocusBuilderSelectionProvider>,
    )
    expect(screen.getByText(/INHERITED CORE/)).toBeInTheDocument()
    expect(screen.getByText("Scheduling Kanban")).toBeInTheDocument()
    expect(
      screen.getByText(/scheduling-kanban-core.*v9.*preset: card/),
    ).toBeInTheDocument()
  })
})
