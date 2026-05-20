/**
 * computeAlignTargets — sub-arc FF-7.
 *
 * Pure helper that computes target X/Y positions for a multi-select
 * align action per Q-17 (b). Align is computed against the selection
 * bounding box (NOT the canvas) — operator intent is "align THESE
 * widgets to each other," not "align them to the canvas."
 *
 * Action vocabulary (6 total):
 *   - left              x → min(p.x)
 *   - right             x → max(p.x + p.width) - p.width
 *   - center-horizontal x → bboxCenterX - p.width / 2
 *   - top               y → min(p.y)
 *   - bottom            y → max(p.y + p.height) - p.height
 *   - center-vertical   y → bboxCenterY - p.height / 2
 *
 * Per Q-18 (a): align is the only multi-select inspector action.
 * Distribute deferred post-arc.
 */

export type AlignAction =
  | "left"
  | "right"
  | "center-horizontal"
  | "top"
  | "bottom"
  | "center-vertical"

export interface AlignablePlacement {
  id: string
  x: number
  y: number
  width: number
  height: number
}

export interface AlignTarget {
  id: string
  x?: number
  y?: number
}

export function computeAlignTargets(
  placements: AlignablePlacement[],
  action: AlignAction,
): AlignTarget[] {
  if (placements.length === 0) return []

  switch (action) {
    case "left": {
      const targetX = Math.min(...placements.map((p) => p.x))
      return placements.map((p) => ({ id: p.id, x: targetX }))
    }
    case "right": {
      const maxRight = Math.max(...placements.map((p) => p.x + p.width))
      return placements.map((p) => ({ id: p.id, x: maxRight - p.width }))
    }
    case "center-horizontal": {
      const minLeft = Math.min(...placements.map((p) => p.x))
      const maxRight = Math.max(...placements.map((p) => p.x + p.width))
      const centerX = (minLeft + maxRight) / 2
      return placements.map((p) => ({ id: p.id, x: centerX - p.width / 2 }))
    }
    case "top": {
      const targetY = Math.min(...placements.map((p) => p.y))
      return placements.map((p) => ({ id: p.id, y: targetY }))
    }
    case "bottom": {
      const maxBottom = Math.max(...placements.map((p) => p.y + p.height))
      return placements.map((p) => ({ id: p.id, y: maxBottom - p.height }))
    }
    case "center-vertical": {
      const minTop = Math.min(...placements.map((p) => p.y))
      const maxBottom = Math.max(...placements.map((p) => p.y + p.height))
      const centerY = (minTop + maxBottom) / 2
      return placements.map((p) => ({ id: p.id, y: centerY - p.height / 2 }))
    }
  }
}
