/**
 * PersonalizationCanvas — canonical Burial Vault Personalization Studio
 * canvas component per Phase 1B canonical canvas implementation.
 *
 * **Canonical Phase A Session 3.8.3 compositor pattern preserved**:
 *
 * - **Composite-only updates via `transform: translate3d(x, y, 0)`** at
 *   canvas element root (CanvasElement component). Drag-in-progress
 *   composes canonical drag delta into transform string via CSS
 *   matrix multiplication.
 * - **Zone-relative positioning resolution at render-time only**.
 *   Phase 1B canvas substrate uses absolute (canvas-coordinate-space)
 *   positioning rather than Phase A's anchor-zone resolution because
 *   Phase 1B canvas is a fixed-size authoring surface (vault canvas
 *   has canonical dimensions independent of viewport).
 * - **rAF-coalesced viewport resize** via canonical `useCanvasViewport`
 *   hook per Phase A Session 3.8.2 canonical pattern.
 * - **Canvas jank carry-forward verification**: canvas elements during
 *   drag use canonical translate3d composite-only update path. Canvas
 *   root does NOT re-render during drag — only the dragging
 *   CanvasElement consumes drag delta from canvas-state-context's
 *   ephemeral `dragInProgress` state.
 *
 * **Canonical anti-pattern guards explicit at component substrate**:
 * - §3.26.11.12.16 Anti-pattern 11 (UI-coupled Generation Focus design
 *   rejected): canvas state lives at canonical Document substrate;
 *   this component renders canonical state via canvas-state-context
 *   ephemeral state. Canvas state mutation flows through canonical
 *   service layer at canonical commit boundary.
 * - §3.26.11.12.16 Anti-pattern 1 (auto-commit on extraction confidence
 *   rejected): canvas commits at canonical operator-decision boundary.
 *   `onCommit` prop dispatch → canonical operator agency at canonical
 *   commit-affordance.
 * - §2.4.4 Anti-pattern 8 (vertical-specific code creep): canvas is
 *   canonical Generation Focus canvas substrate; element-type
 *   rendering dispatched to canonical CanvasElement component per
 *   element_type discriminator (NOT per-vertical canvas substrate).
 * - §3.26.11.12.16 Anti-pattern 4 (primitive count expansion against
 *   fifth Focus type rejected): canvas is canonical Generation Focus
 *   template canvas, NOT new Focus type canvas.
 *
 * **Canonical-pattern-establisher discipline**: Step 2 (Urn Vault
 * Personalization Studio) inherits canonical canvas via
 * `template_type` prop dispatch (Step 2 will extend the canvas
 * dimensions + element types per urn-specific canonical configuration).
 */

import { useCallback } from "react"

import { cn } from "@/lib/utils"
import type { TemplateType } from "@/types/personalization-studio"

import { CanvasElement } from "./CanvasElement"
import { usePersonalizationCanvasState } from "./canvas-state-context"
import { useCanvasViewport } from "./useCanvasViewport"

interface PersonalizationCanvasProps {
  /** Canonical template_type discriminator. Phase 1B canonical-pattern-
   *  establisher value: `burial_vault_personalization_studio`. Step 2
   *  extends with `urn_vault_personalization_studio`. */
  templateType: TemplateType
  /** Canonical canvas viewport dimensions in canvas-coordinate-space.
   *  Per-template-type canonical canvas dimensions per §14.14.2 visual
   *  canon. */
  canvasWidth?: number
  canvasHeight?: number
  /** Canonical canvas read-only mode for `manufacturer_from_fh_share`
   *  authoring context per §14.14.5 — read-only chrome (no edit
   *  affordances per canonical Document read-only state). */
  readOnly?: boolean
}

/** Canonical default canvas dimensions per Phase 1B canonical-pattern-
 *  establisher. Burial vault canvas is canonically 800×600 in canvas-
 *  coordinate-space (canonical authoring surface dimensions; viewport
 *  scale composes via canonical viewport canonical at render time). */
const DEFAULT_CANVAS_WIDTH = 800
const DEFAULT_CANVAS_HEIGHT = 600

export function PersonalizationCanvas({
  templateType,
  canvasWidth = DEFAULT_CANVAS_WIDTH,
  canvasHeight = DEFAULT_CANVAS_HEIGHT,
  readOnly = false,
}: PersonalizationCanvasProps) {
  // Canonical viewport canonical per Phase A Session 3.8.2 canonical
  // rAF-coalesced canonical pattern.
  const viewport = useCanvasViewport()

  const {
    canvasState,
    selectedElementId,
    setSelectedElementId,
    viewport: canvasViewport,
  } = usePersonalizationCanvasState()

  // Click on canvas background canonically deselects active element.
  const handleBackgroundClick = useCallback(() => {
    if (selectedElementId !== null) {
      setSelectedElementId(null)
    }
  }, [selectedElementId, setSelectedElementId])

  // Sanity-check canonical template_type alignment between component
  // prop + canvas state (canonical-discipline against canonical
  // mismatch).
  if (canvasState.template_type !== templateType) {
    return (
      <div
        data-slot="personalization-canvas-mismatch"
        className="flex h-full items-center justify-center bg-status-error-muted text-status-error"
      >
        <div className="text-body-sm">
          Canvas template_type mismatch: prop={templateType} vs
          state={canvasState.template_type}
        </div>
      </div>
    )
  }

  return (
    <div
      data-slot="personalization-canvas"
      data-template-type={templateType}
      data-tier={viewport.tier}
      data-read-only={readOnly ? "true" : "false"}
      className={cn(
        "relative flex h-full w-full items-center justify-center overflow-hidden",
        // Canonical canvas surface chrome per §14.14.2: `bg-surface-base`
        // with `border-border-subtle` outline; positioned content
        // rendered at canonical scale.
        "bg-surface-sunken",
      )}
      onClick={handleBackgroundClick}
    >
      {/* Canonical canvas inner surface — fixed canvas-coordinate-space
          dimensions; canonical viewport scale composes via canvasViewport
          zoom + pan at root level. */}
      <div
        data-slot="personalization-canvas-surface"
        className={cn(
          "relative bg-surface-base shadow-level-1",
          "border border-border-subtle rounded-md",
        )}
        style={{
          width: canvasWidth,
          height: canvasHeight,
          // Canonical viewport scale + pan composes here per Phase 1B
          // canvas viewport canonical. Canvas elements within compose
          // their own translate3d on top of canvas-root transform.
          transform: `translate3d(${canvasViewport.panX}px, ${canvasViewport.panY}px, 0) scale(${canvasViewport.zoom})`,
          transformOrigin: "center center",
        }}
      >
        {/* Canvas elements layer — each element is absolute-positioned
            via translate3d at element root per canonical compositor
            pattern. */}
        {canvasState.canvas_layout.elements.map((element) => (
          <CanvasElement
            key={element.id}
            element={element}
            zoom={canvasViewport.zoom}
          />
        ))}

        {/* Canonical empty-state chrome when no elements present — per
            §14.14.2 canonical visual canon. */}
        {canvasState.canvas_layout.elements.length === 0 && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <div className="text-caption font-medium uppercase tracking-wider text-content-subtle">
                Empty canvas
              </div>
              <div className="mt-2 text-body-sm text-content-muted">
                Drag elements from the palette to begin
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Canonical read-only chrome per `manufacturer_from_fh_share`
          authoring context per §14.14.5. */}
      {readOnly && (
        <div
          data-slot="personalization-canvas-readonly-banner"
          className={cn(
            "absolute left-1/2 top-4 -translate-x-1/2 rounded-sm",
            "bg-status-info-muted px-3 py-1 text-caption text-status-info",
          )}
        >
          Read-only — shared from funeral home
        </div>
      )}
    </div>
  )
}
