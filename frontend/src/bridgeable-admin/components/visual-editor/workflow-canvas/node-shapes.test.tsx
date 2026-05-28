/**
 * node-shapes.test — Phase B sub-arc B-3 §(b) (shape helper).
 *
 * Covers the 9-shape coercion + per-shape edge anchors + the SVG
 * backdrop rendering. Anchors are the load-bearing edge-geometry claim:
 * every shape anchors at box center-top / center-bottom (matching B-1's
 * computeEdgePath), so no edge-geometry rewrite is needed.
 */

import { describe, it, expect } from "vitest"
import { render } from "@testing-library/react"

import {
  KNOWN_NODE_SHAPES,
  NodeShapeBackdrop,
  nodeShapeAnchors,
  toNodeShape,
  type NodeShape,
} from "./node-shapes"

describe("node-shapes — toNodeShape coercion", () => {
  it("passes through every known shape", () => {
    for (const s of KNOWN_NODE_SHAPES) {
      expect(toNodeShape(s)).toBe(s)
    }
  })

  it("defaults unknown / non-string to rounded-rect (B-1's fixed shape)", () => {
    expect(toNodeShape("not-a-shape")).toBe("rounded-rect")
    expect(toNodeShape(undefined)).toBe("rounded-rect")
    expect(toNodeShape(42)).toBe("rounded-rect")
    expect(toNodeShape(null)).toBe("rounded-rect")
  })

  it("declares exactly 9 known shapes", () => {
    expect(KNOWN_NODE_SHAPES.length).toBe(9)
  })
})

describe("node-shapes — nodeShapeAnchors (edge-geometry claim)", () => {
  it("every shape anchors at box center-top / center-bottom", () => {
    for (const s of KNOWN_NODE_SHAPES) {
      const a = nodeShapeAnchors(s, 200, 72)
      expect(a.top).toEqual({ x: 100, y: 0 })
      expect(a.bottom).toEqual({ x: 100, y: 72 })
    }
  })

  it("anchors scale with width/height", () => {
    const a = nodeShapeAnchors("diamond", 300, 100)
    expect(a.top).toEqual({ x: 150, y: 0 })
    expect(a.bottom).toEqual({ x: 150, y: 100 })
  })
})

describe("node-shapes — NodeShapeBackdrop render", () => {
  it.each(KNOWN_NODE_SHAPES.map((s) => [s]))(
    "renders an SVG backdrop for %s",
    (shape) => {
      const { getByTestId } = render(
        <NodeShapeBackdrop
          shape={shape as NodeShape}
          width={200}
          height={72}
          fill="var(--surface-elevated)"
          stroke="var(--border-subtle)"
        />,
      )
      const svg = getByTestId(`node-shape-${shape}`)
      expect(svg.tagName.toLowerCase()).toBe("svg")
      // Each shape draws at least one geometry primitive.
      expect(
        svg.querySelector("rect, polygon, ellipse, path"),
      ).toBeInTheDocument()
    },
  )

  it("applies the stroke (accent) to the shape primitive", () => {
    const { getByTestId } = render(
      <NodeShapeBackdrop
        shape="diamond"
        width={200}
        height={72}
        fill="var(--surface-elevated)"
        stroke="var(--accent)"
      />,
    )
    const polygon = getByTestId("node-shape-diamond").querySelector("polygon")
    expect(polygon?.getAttribute("stroke")).toBe("var(--accent)")
  })
})
