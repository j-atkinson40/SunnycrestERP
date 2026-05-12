/**
 * AlignmentGuideOverlay tests — pure helpers + component rendering.
 *
 * Arc 4c — SVG overlay alignment guides for the standalone canvas
 * (Q-ARC4C-2 settled scope). Inspector canvas read-mostly per
 * Q-FOCUS-1; guides STANDALONE-ONLY by design.
 */
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import {
  AlignmentGuideOverlay,
  SNAP_THRESHOLD_PX,
  _alignmentInternals,
  type AlignmentGuide,
  type CanvasRect,
} from "./AlignmentGuideOverlay"


const { computeAlignmentGuides, resolveReferenceRectsForRow, liveDraggedRect } =
  _alignmentInternals


describe("SNAP_THRESHOLD_PX canonical value", () => {
  it("is 8px per DESIGN_LANGUAGE §5 space-2 spacing token", () => {
    expect(SNAP_THRESHOLD_PX).toBe(8)
  })
})


describe("computeAlignmentGuides pure helper", () => {
  const dragged: CanvasRect = { left: 100, top: 100, width: 200, height: 60 }

  it("returns empty array when no reference rects align", () => {
    const refs: CanvasRect[] = [
      { left: 500, top: 500, width: 100, height: 50 },
    ]
    const guides = computeAlignmentGuides(dragged, refs)
    expect(guides).toEqual([])
  })

  it("detects left-edge alignment when dragged.left ≈ candidate.left", () => {
    const refs: CanvasRect[] = [
      { left: 103, top: 500, width: 100, height: 50 }, // within 8px of dragged.left=100
    ]
    const guides = computeAlignmentGuides(dragged, refs)
    expect(guides).toContainEqual({
      axis: "vertical",
      position: 103,
      kind: "edge",
    })
  })

  it("detects right-edge alignment when dragged.right ≈ candidate.right", () => {
    // dragged.right = 100 + 200 = 300
    const refs: CanvasRect[] = [
      { left: 150, top: 500, width: 152, height: 50 }, // right = 302, within 8 of 300
    ]
    const guides = computeAlignmentGuides(dragged, refs)
    expect(guides).toContainEqual({
      axis: "vertical",
      position: 302,
      kind: "edge",
    })
  })

  it("detects center-X alignment between dragged + reference", () => {
    // dragged.centerX = 100 + 100 = 200
    const refs: CanvasRect[] = [
      { left: 150, top: 500, width: 100, height: 50 }, // centerX = 200 (exact)
    ]
    const guides = computeAlignmentGuides(dragged, refs)
    expect(guides).toContainEqual({
      axis: "vertical",
      position: 200,
      kind: "center",
    })
  })

  it("detects horizontal top-edge alignment", () => {
    const refs: CanvasRect[] = [
      { left: 500, top: 103, width: 100, height: 50 }, // top ≈ dragged.top=100
    ]
    const guides = computeAlignmentGuides(dragged, refs)
    expect(guides).toContainEqual({
      axis: "horizontal",
      position: 103,
      kind: "edge",
    })
  })

  it("respects custom threshold parameter", () => {
    const refs: CanvasRect[] = [
      { left: 110, top: 500, width: 100, height: 50 }, // diff = 10
    ]
    expect(computeAlignmentGuides(dragged, refs, 5)).toEqual([])
    expect(computeAlignmentGuides(dragged, refs, 12)).toContainEqual({
      axis: "vertical",
      position: 110,
      kind: "edge",
    })
  })

  it("deduplicates guides at the same (axis, position)", () => {
    const refs: CanvasRect[] = [
      { left: 100, top: 200, width: 100, height: 50 },
      { left: 100, top: 400, width: 100, height: 50 },
    ]
    const guides = computeAlignmentGuides(dragged, refs)
    const verticalAt100 = guides.filter(
      (g) => g.axis === "vertical" && Math.round(g.position) === 100,
    )
    expect(verticalAt100.length).toBeLessThanOrEqual(1)
  })

  it("detects edge-to-edge snapping (dragged.right ≈ ref.left)", () => {
    // dragged.right = 300; ref.left = 305 (within 8)
    const refs: CanvasRect[] = [
      { left: 305, top: 500, width: 100, height: 50 },
    ]
    const guides = computeAlignmentGuides(dragged, refs)
    expect(guides).toContainEqual({
      axis: "vertical",
      position: 305,
      kind: "edge",
    })
  })
})


describe("resolveReferenceRectsForRow", () => {
  const row = {
    row_id: "r1",
    column_count: 12,
    row_height: "auto" as const,
    column_widths: null,
    nested_rows: null,
    placements: [
      {
        placement_id: "p1",
        component_kind: "widget" as const,
        component_name: "a",
        starting_column: 0,
        column_span: 4,
        prop_overrides: {},
        display_config: {},
        nested_rows: null,
      },
      {
        placement_id: "p2",
        component_kind: "widget" as const,
        component_name: "b",
        starting_column: 4,
        column_span: 4,
        prop_overrides: {},
        display_config: {},
        nested_rows: null,
      },
    ],
  }

  it("excludes the dragged placement from the reference rects", () => {
    const rects = resolveReferenceRectsForRow(
      row,
      "p1",
      (id) => {
        if (id === "p2") {
          return { left: 100, top: 100, width: 200, height: 60 }
        }
        return null
      },
      null,
    )
    expect(rects).toHaveLength(1)
    expect(rects[0]).toEqual({ left: 100, top: 100, width: 200, height: 60 })
  })

  it("adds row left + right edge candidates when rowRect provided", () => {
    const rowRect: CanvasRect = {
      left: 50,
      top: 50,
      width: 800,
      height: 200,
    }
    const rects = resolveReferenceRectsForRow(row, "p1", () => null, rowRect)
    // Two row-edge degenerate rects (left edge + right edge)
    expect(rects.length).toBe(2)
    expect(rects[0].left).toBe(50) // row left edge
    expect(rects[1].left).toBe(850) // row right edge
  })

  it("returns empty rects array when getPlacementRect always returns null + no rowRect", () => {
    const rects = resolveReferenceRectsForRow(row, "p1", () => null, null)
    expect(rects).toEqual([])
  })
})


describe("liveDraggedRect", () => {
  it("applies live offset to start rect", () => {
    const startRect: CanvasRect = {
      left: 100,
      top: 50,
      width: 200,
      height: 60,
    }
    const live = liveDraggedRect(startRect, { dxPx: 25, dyPx: -10 })
    expect(live).toEqual({ left: 125, top: 40, width: 200, height: 60 })
  })

  it("preserves width + height (drag does not resize)", () => {
    const startRect: CanvasRect = {
      left: 0,
      top: 0,
      width: 100,
      height: 80,
    }
    const live = liveDraggedRect(startRect, { dxPx: 50, dyPx: 50 })
    expect(live.width).toBe(100)
    expect(live.height).toBe(80)
  })
})


describe("AlignmentGuideOverlay component", () => {
  it("renders nothing when guides array is empty", () => {
    const { container } = render(
      <AlignmentGuideOverlay
        guides={[]}
        canvasWidth={800}
        canvasHeight={600}
      />,
    )
    expect(container.querySelector("[data-testid='alignment-guide-overlay']")).toBeNull()
  })

  it("renders an SVG with one line per guide", () => {
    const guides: AlignmentGuide[] = [
      { axis: "vertical", position: 100, kind: "edge" },
      { axis: "horizontal", position: 200, kind: "center" },
    ]
    render(
      <AlignmentGuideOverlay
        guides={guides}
        canvasWidth={800}
        canvasHeight={600}
      />,
    )
    const overlay = screen.getByTestId("alignment-guide-overlay")
    expect(overlay).toBeDefined()
    expect(overlay.getAttribute("data-guide-count")).toBe("2")
    expect(screen.getByTestId("alignment-guide-vertical-0")).toBeDefined()
    expect(screen.getByTestId("alignment-guide-horizontal-1")).toBeDefined()
  })

  it("emits axis + kind data attributes for test assertions", () => {
    const guides: AlignmentGuide[] = [
      { axis: "vertical", position: 100, kind: "center" },
    ]
    render(
      <AlignmentGuideOverlay
        guides={guides}
        canvasWidth={800}
        canvasHeight={600}
      />,
    )
    const line = screen.getByTestId("alignment-guide-vertical-0")
    expect(line.getAttribute("data-guide-axis")).toBe("vertical")
    expect(line.getAttribute("data-guide-kind")).toBe("center")
  })

  it("sizes SVG to canvas dimensions", () => {
    const guides: AlignmentGuide[] = [
      { axis: "vertical", position: 100 },
    ]
    render(
      <AlignmentGuideOverlay
        guides={guides}
        canvasWidth={1200}
        canvasHeight={800}
      />,
    )
    const overlay = screen.getByTestId("alignment-guide-overlay")
    expect(overlay.getAttribute("width")).toBe("1200")
    expect(overlay.getAttribute("height")).toBe("800")
  })

  it("renders pointer-events: none so it does not intercept canvas events", () => {
    const guides: AlignmentGuide[] = [
      { axis: "vertical", position: 100 },
    ]
    render(
      <AlignmentGuideOverlay
        guides={guides}
        canvasWidth={800}
        canvasHeight={600}
      />,
    )
    const overlay = screen.getByTestId("alignment-guide-overlay")
    expect(overlay.getAttribute("style")).toMatch(/pointer-events:\s*none/)
  })
})
