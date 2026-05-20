/**
 * computeZIndexCommit — sub-arc FF-5.
 *
 * Pure helper that translates a z-order action (front / back / forward
 * / backward) against a current placement and the set of other widget
 * placements into a single resulting `z_index` integer to commit on
 * the target placement via the hook's `updateWidget` mutator.
 *
 * Companion to FF-2's `computeFreeFormDropPosition`, FF-3's
 * `computeDragMoveCommit`, and FF-4's `computeResizeCommit`. All four
 * pure helpers share the same shape: take an immutable input snapshot,
 * return the next-state geometry/index, no React, no DOM, no @dnd-kit.
 *
 * Per investigation Q-6: explicit per-placement `z_index: number` field
 * (already shipped in FF-1's WidgetPlacement; FF-5 wires the operator-
 * facing actions).
 *
 * Per Q-7: locked NO. Click-to-front does not promote z-order; only
 * explicit send-to-X actions mutate z_index.
 *
 * Per Q-22: widgets may overlap the inherited core; core is structurally
 * anchored and never the target of z-order actions. The caller (the
 * hook helper `setWidgetZIndex`) filters out the core from
 * `allPlacements` before calling this helper. The helper is agnostic
 * to "what is a placement vs. what is core" — it treats every entry in
 * `allPlacements` as a fellow widget.
 *
 * Per Q-31 (c): both inspector buttons AND right-click context menu
 * dispatch the same action vocabulary; this helper is the single
 * z-order math seam they share.
 *
 * Semantics:
 *   - Treats `z_index === undefined` as 0.
 *   - Filters `currentPlacement` out of `allPlacements` (by id) before
 *     computing max/min for front/back.
 *   - "front": max(others.z_index) + 1; if there are no others, 1.
 *   - "back":  min(others.z_index) - 1; if there are no others, -1.
 *   - "forward":  currentPlacement.z_index + 1.
 *   - "backward": currentPlacement.z_index - 1.
 *
 * No normalization. z_index values can grow unbounded across many
 * send-to-X operations. CSS `z-index` handles arbitrary integers fine.
 *
 * Aspect-symmetry with the other three FF helpers: pure-function shape
 * keeps this unit-testable without React state or @dnd-kit gestures.
 */

export type ZIndexAction = "front" | "back" | "forward" | "backward"

export interface ZIndexCommitInput {
  /** The placement being targeted by the z-order action. */
  currentPlacement: { id: string; z_index?: number }
  /** All widget placements (NOT including the inherited core; caller
   * pre-filters). The helper filters currentPlacement out of this list
   * before computing front/back so a single z_index value isn't
   * compared against itself. */
  allPlacements: Array<{ id: string; z_index?: number }>
  action: ZIndexAction
}

export interface ZIndexCommitResult {
  z_index: number
}

function zOf(p: { z_index?: number }): number {
  return typeof p.z_index === "number" ? p.z_index : 0
}

export function computeZIndexCommit(
  input: ZIndexCommitInput,
): ZIndexCommitResult {
  const { currentPlacement, allPlacements, action } = input
  const current = zOf(currentPlacement)
  const others = allPlacements.filter((p) => p.id !== currentPlacement.id)

  if (action === "front") {
    if (others.length === 0) return { z_index: 1 }
    let max = zOf(others[0])
    for (let i = 1; i < others.length; i += 1) {
      const z = zOf(others[i])
      if (z > max) max = z
    }
    return { z_index: max + 1 }
  }
  if (action === "back") {
    if (others.length === 0) return { z_index: -1 }
    let min = zOf(others[0])
    for (let i = 1; i < others.length; i += 1) {
      const z = zOf(others[i])
      if (z < min) min = z
    }
    return { z_index: min - 1 }
  }
  if (action === "forward") {
    return { z_index: current + 1 }
  }
  // backward
  return { z_index: current - 1 }
}
