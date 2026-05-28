/**
 * node-shapes — Phase B sub-arc B-3 (canvas render-from-config, §(b)).
 *
 * Renders the 9 declared `nodeShape` values (workflow-nodes registry
 * configurableProps) as an SVG backdrop behind the node card content,
 * + exposes per-shape edge-anchor points.
 *
 * Why an SVG backdrop (not clip-path on the card): clipping the card
 * would clip its text content (type badge / id / label) into the shape
 * and cut it off for angular shapes (diamond / hexagon). Instead the
 * shape renders as a filled+stroked SVG layer; the card content sits on
 * top in a transparent container and stays legible. The shape carries
 * the visual treatment + accent; the content carries the text.
 *
 * EDGE-ANCHOR GEOMETRY: B-1's `computeEdgePath` (canvas-layout.ts)
 * anchors edges at the bounding-box CENTER-top / CENTER-bottom (NOT the
 * corners). All 9 shapes here are vertically-symmetric and inscribed in
 * the bounding box, so each shape's actual visual top/bottom point sits
 * exactly at box-center-top / box-center-bottom — i.e. the B-1 anchors
 * are already correct for every shape. `nodeShapeAnchors` exposes this
 * explicitly (and would let a future non-centered shape override),
 * confirming no edge-geometry rewrite is needed for the 9 current shapes.
 */

export type NodeShape =
  | "rounded-rect"
  | "pill"
  | "circle"
  | "diamond"
  | "hexagon"
  | "bar"
  | "parallelogram"
  | "envelope"
  | "document"

export const KNOWN_NODE_SHAPES: readonly NodeShape[] = [
  "rounded-rect",
  "pill",
  "circle",
  "diamond",
  "hexagon",
  "bar",
  "parallelogram",
  "envelope",
  "document",
]

/** Coerce an arbitrary config value to a known shape, defaulting to
 *  rounded-rect (B-1's pre-§(b) fixed shape). Pure (value-only) — used
 *  where only the explicit value matters. `resolveNodeShape` layers the
 *  registry per-type default on top. */
export function toNodeShape(value: unknown): NodeShape {
  return typeof value === "string" &&
    (KNOWN_NODE_SHAPES as readonly string[]).includes(value)
    ? (value as NodeShape)
    : "rounded-rect"
}

/**
 * B-3 completion (type-default fallback): resolve the shape a node should
 * render, in precedence order:
 *
 *   1. node.config.nodeShape   — explicit operator override (if a known shape)
 *   2. typeDefault             — the genre convention the registry declares
 *      per node type (decision → diamond, start/end → circle,
 *      parallel_split/join → bar) at `configurableProps.nodeShape.default`,
 *      INJECTED by the caller (this helper stays registry-free)
 *   3. "rounded-rect"          — hard fallback (no type default / invalid)
 *
 * B-3b rendered shape from `node.config.nodeShape` ONLY, so the genre
 * defaults declared in the registry never reached the canvas (every node
 * fell to rounded-rect). This layers the type default on top WITHOUT
 * materializing nodeShape into node.config — the shape stays derived from
 * type; config remains override-only.
 *
 * Dependency-injected (typeDefault passed in) rather than reading the
 * registry here: this keeps node-shapes a pure leaf utility with no
 * registry import. The single registry consumer is WorkflowEditorPage
 * (which already imports the registry for the B-2 palette); it threads a
 * resolver down to the canvas. Pulling the registry into this leaf
 * regressed an unrelated full-suite test via module-graph reshuffling —
 * keeping it pure avoids that entirely.
 *
 * Defensive: a missing/invalid typeDefault falls through to rounded-rect.
 */
export function resolveNodeShape(
  configValue: unknown,
  typeDefault?: unknown,
): NodeShape {
  // 1. Explicit override.
  if (
    typeof configValue === "string" &&
    (KNOWN_NODE_SHAPES as readonly string[]).includes(configValue)
  ) {
    return configValue as NodeShape
  }
  // 2. Injected per-type default.
  if (
    typeof typeDefault === "string" &&
    (KNOWN_NODE_SHAPES as readonly string[]).includes(typeDefault)
  ) {
    return typeDefault as NodeShape
  }
  // 3. Hard fallback.
  return "rounded-rect"
}

export interface Point {
  x: number
  y: number
}

/**
 * Per-shape top/bottom edge-anchor points. All 9 current shapes are
 * vertically symmetric + inscribed, so anchors coincide with box
 * center-top / center-bottom — matching B-1's computeEdgePath. Exposed
 * so the coincidence is explicit + a future shape could override.
 */
export function nodeShapeAnchors(
  _shape: NodeShape,
  width: number,
  height: number,
): { top: Point; bottom: Point } {
  return {
    top: { x: width / 2, y: 0 },
    bottom: { x: width / 2, y: height },
  }
}


interface NodeShapeBackdropProps {
  shape: NodeShape
  width: number
  height: number
  /** Fill (surface) — keeps content legible on top. */
  fill: string
  /** Stroke (border / accent). */
  stroke: string
}

/**
 * SVG backdrop drawing the shape. Rendered absolutely-positioned behind
 * the node card content (pointer-events none so drag/click pass through
 * to the card).
 */
export function NodeShapeBackdrop({
  shape,
  width,
  height,
  fill,
  stroke,
}: NodeShapeBackdropProps) {
  const w = width
  const h = height
  const common = {
    fill,
    stroke,
    strokeWidth: 1.5,
    vectorEffect: "non-scaling-stroke" as const,
  }

  let body: React.ReactNode
  switch (shape) {
    case "pill":
      body = <rect x={0.75} y={0.75} width={w - 1.5} height={h - 1.5} rx={h / 2} {...common} />
      break
    case "circle":
      body = (
        <ellipse
          cx={w / 2}
          cy={h / 2}
          rx={w / 2 - 0.75}
          ry={h / 2 - 0.75}
          {...common}
        />
      )
      break
    case "diamond":
      body = (
        <polygon
          points={`${w / 2},1 ${w - 1},${h / 2} ${w / 2},${h - 1} 1,${h / 2}`}
          {...common}
        />
      )
      break
    case "hexagon":
      body = (
        <polygon
          points={`${w * 0.25},1 ${w * 0.75},1 ${w - 1},${h / 2} ${w * 0.75},${h - 1} ${w * 0.25},${h - 1} 1,${h / 2}`}
          {...common}
        />
      )
      break
    case "bar":
      body = <rect x={0.75} y={0.75} width={w - 1.5} height={h - 1.5} rx={2} {...common} />
      break
    case "parallelogram":
      body = (
        <polygon
          points={`${w * 0.15},1 ${w - 1},1 ${w * 0.85},${h - 1} 1,${h - 1}`}
          {...common}
        />
      )
      break
    case "envelope":
      body = (
        <g>
          <rect x={0.75} y={0.75} width={w - 1.5} height={h - 1.5} rx={2} {...common} />
          <polyline
            points={`1,1 ${w / 2},${h * 0.55} ${w - 1},1`}
            fill="none"
            stroke={stroke}
            strokeWidth={1}
          />
        </g>
      )
      break
    case "document":
      body = (
        <path
          d={`M 1 1 H ${w - 14} L ${w - 1} 14 V ${h - 1} H 1 Z`}
          {...common}
        />
      )
      break
    case "rounded-rect":
    default:
      body = <rect x={0.75} y={0.75} width={w - 1.5} height={h - 1.5} rx={6} {...common} />
      break
  }

  return (
    <svg
      className="pointer-events-none absolute inset-0"
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      data-testid={`node-shape-${shape}`}
      aria-hidden
    >
      {body}
    </svg>
  )
}
