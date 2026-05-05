/**
 * CanvasElement — canonical compositor element rendering for Phase 1B
 * Burial Vault Personalization Studio canvas.
 *
 * **Canonical Phase A Session 3.8.3 compositor pattern preserved**:
 *
 * - **Composite-only updates via `transform: translate3d(x, y, 0)`** at
 *   element root. During drag, drag delta composes into the transform
 *   string via CSS matrix multiplication — composite-only update path
 *   (GPU layer push, no layout, no paint per frame). Canonical
 *   compositor pattern preserved against Phase A 3.8.3 canonical
 *   reference.
 *
 * - **`left: 0, top: 0` explicit on element root** as canonical
 *   containing-block anchor — defensive against browser auto-placement
 *   quirks (Safari + some Chromium builds).
 *
 * - **Width/height stable during drag** — only x/y change per drag
 *   frame via translate3d. Element width/height is stored at canvas
 *   state shape level + does NOT mutate during drag (canonical canvas
 *   element resize is a separate canonical interaction; this component
 *   handles drag canonical only).
 *
 * **Canonical anti-pattern guards explicit**:
 * - §3.26.11.12.16 Anti-pattern 11 (UI-coupled Generation Focus design
 *   rejected): canonical canvas state lives at canonical Document
 *   substrate; this component renders canonical state without
 *   canonical state coupling to canonical interactive UI substrate
 * - §3.26.11.12.16 Anti-pattern 1 (auto-commit on extraction confidence
 *   rejected): drag-end triggers canonical applyDragEnd at canonical
 *   ephemeral state mutation boundary; canonical canvas commit happens
 *   at canonical operator-decision commit-affordance boundary (NOT
 *   here)
 *
 * **Element-type-aware rendering** dispatches to per-canonical-element-type
 * canonical visual treatment. Canvas element types per Phase 1B:
 * vault_product, emblem, nameplate, name_text, date_text,
 * legacy_print_artifact. Each renders distinct canonical chrome per
 * §14.14.2 canonical canvas + palette visual canon.
 */

import { useCallback, useRef } from "react"

import { cn } from "@/lib/utils"
import type { CanvasElement as CanvasElementType } from "@/types/personalization-studio"

import { usePersonalizationCanvasState } from "./canvas-state-context"

interface CanvasElementProps {
  element: CanvasElementType
  /** Canonical canvas viewport zoom factor — composes into element
   *  scale at render time per canvas viewport canonical. */
  zoom?: number
}

export function CanvasElement({ element, zoom = 1 }: CanvasElementProps) {
  const {
    selectedElementId,
    setSelectedElementId,
    dragInProgress,
    setDragInProgress,
    applyDragEnd,
    setEditing,
  } = usePersonalizationCanvasState()

  const isSelected = selectedElementId === element.id
  const isDragging = dragInProgress?.elementId === element.id

  // Canonical compositor pattern: drag-in-progress translate composes
  // into transform string. dx/dy from canvas-state-context's
  // dragInProgress; zero when not dragging.
  const dragDx = isDragging ? dragInProgress!.dx : 0
  const dragDy = isDragging ? dragInProgress!.dy : 0

  // Canonical translate3d composition per Phase A Session 3.8.3
  // canonical pattern. Composed transform string = base position
  // translate3d + drag-in-progress translate3d (composes via matrix
  // multiplication). zoom factor composes via scale at viewport
  // canonical level (handled at canvas root); per-element scale
  // inherited.
  const composedTransform = [
    `translate3d(${element.x}px, ${element.y}px, 0)`,
    isDragging ? `translate3d(${dragDx}px, ${dragDy}px, 0)` : null,
    isDragging ? "scale(1.02)" : null,
  ]
    .filter(Boolean)
    .join(" ")

  // Pointer-event drag tracking (canonical custom pointer-event-based
  // drag, not @dnd-kit, because Phase 1B canvas substrate is bespoke
  // canvas authoring surface — Phase A's @dnd-kit pattern is for Focus
  // canvas widget chrome, distinct canonical scope).
  const dragStartRef = useRef<{ x: number; y: number } | null>(null)

  const handlePointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      // Skip drag for non-primary buttons.
      if (e.button !== 0) return
      e.preventDefault()
      e.stopPropagation()
      ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
      dragStartRef.current = { x: e.clientX, y: e.clientY }
      setSelectedElementId(element.id)
      setDragInProgress({ elementId: element.id, dx: 0, dy: 0 })
    },
    [element.id, setDragInProgress, setSelectedElementId],
  )

  const handlePointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!dragStartRef.current) return
      const dx = (e.clientX - dragStartRef.current.x) / zoom
      const dy = (e.clientY - dragStartRef.current.y) / zoom
      setDragInProgress({ elementId: element.id, dx, dy })
    },
    [element.id, setDragInProgress, zoom],
  )

  const handlePointerUp = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!dragStartRef.current) return
      const dx = (e.clientX - dragStartRef.current.x) / zoom
      const dy = (e.clientY - dragStartRef.current.y) / zoom
      ;(e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId)
      dragStartRef.current = null
      // Canonical drag-end commits dx/dy to canvas state via canonical
      // applyDragEnd helper (applyDragEnd also clears dragInProgress).
      // Threshold: only commit if drag distance > 1px to distinguish
      // from click selection.
      if (Math.abs(dx) > 1 || Math.abs(dy) > 1) {
        applyDragEnd(element.id, dx, dy)
      } else {
        setDragInProgress(null)
      }
    },
    [applyDragEnd, element.id, setDragInProgress, zoom],
  )

  const handleDoubleClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      e.stopPropagation()
      // Canonical edit-finish surface dispatch per element_type.
      const editorType = mapElementTypeToEditor(element.element_type)
      if (editorType) {
        setEditing({ elementId: element.id, editorType })
      }
    },
    [element.id, element.element_type, setEditing],
  )

  return (
    <div
      data-slot="personalization-canvas-element"
      data-element-id={element.id}
      data-element-type={element.element_type}
      data-selected={isSelected ? "true" : "false"}
      data-dragging={isDragging ? "true" : "false"}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onDoubleClick={handleDoubleClick}
      className={cn(
        "absolute select-none",
        // Canonical selection chrome per §14.14.2: selected elements
        // render with `border-accent` outline + `bg-accent-subtle/30`
        // highlight per §6 selection canonical chrome.
        isSelected && "ring-2 ring-accent",
        // Canonical interaction chrome — cursor changes drive
        // affordance per §6 restraint principle.
        !isDragging && "cursor-grab",
        isDragging && "cursor-grabbing",
        // Subtle elevation during drag for canonical visual lift.
        isDragging && "shadow-level-2",
      )}
      style={{
        // Anchor at (0,0) of containing canvas — canonical pattern
        // matches Phase A WidgetChrome.tsx line 230.
        left: 0,
        top: 0,
        width: element.width ?? "auto",
        height: element.height ?? "auto",
        transform: composedTransform,
        zIndex: isDragging ? 100 : isSelected ? 10 : 1,
        // Touch-action: none ensures pointer events fire reliably on
        // touch devices (canonical per Phase A canvas pattern).
        touchAction: "none",
      }}
    >
      <CanvasElementContent element={element} />
    </div>
  )
}

function mapElementTypeToEditor(
  elementType: CanvasElementType["element_type"],
): "font" | "emblem" | "date" | "nameplate_text" | null {
  switch (elementType) {
    case "name_text":
      return "font"
    case "emblem":
      return "emblem"
    case "date_text":
      return "date"
    case "nameplate":
      return "nameplate_text"
    default:
      return null
  }
}

/** Per-canonical-element-type rendering dispatch. Each canonical
 *  element type renders canonical chrome per §14.14.2. */
function CanvasElementContent({ element }: { element: CanvasElementType }) {
  switch (element.element_type) {
    case "vault_product":
      return <VaultProductElement element={element} />
    case "urn_product":
      return <UrnProductElement element={element} />
    case "emblem":
      return <EmblemElement element={element} />
    case "nameplate":
      return <NameplateElement element={element} />
    case "name_text":
      return <NameTextElement element={element} />
    case "date_text":
      return <DateTextElement element={element} />
    case "legacy_print_artifact":
      return <LegacyPrintArtifactElement element={element} />
    default:
      return <UnknownElement element={element} />
  }
}

// ─────────────────────────────────────────────────────────────────────
// Per-element-type canonical visual treatment (Phase 1B canonical
// canvas + palette visual canon per §14.14.2)
// ─────────────────────────────────────────────────────────────────────

function VaultProductElement({ element }: { element: CanvasElementType }) {
  const config = element.config as
    | { vault_product_name?: string }
    | undefined
  return (
    <div className="rounded-md border border-border-base bg-surface-elevated p-4 shadow-level-1">
      <div className="text-caption font-medium uppercase tracking-wider text-content-muted">
        Vault product
      </div>
      <div className="mt-1 text-body-sm font-medium text-content-strong">
        {config?.vault_product_name || "(no product selected)"}
      </div>
    </div>
  )
}

function UrnProductElement({ element }: { element: CanvasElementType }) {
  // Step 2 substrate-consumption-follower: urn product element renders
  // via shared CanvasElement dispatch. Visual treatment parallels
  // VaultProductElement per §3.26.11.12.19.6 scope freeze (4-options
  // vocabulary at category scope; product-slot chrome shape symmetric).
  const config = element.config as
    | { urn_product_name?: string }
    | undefined
  return (
    <div className="rounded-md border border-border-base bg-surface-elevated p-4 shadow-level-1">
      <div className="text-caption font-medium uppercase tracking-wider text-content-muted">
        Urn product
      </div>
      <div className="mt-1 text-body-sm font-medium text-content-strong">
        {config?.urn_product_name || "(no product selected)"}
      </div>
    </div>
  )
}

function EmblemElement({ element }: { element: CanvasElementType }) {
  const config = element.config as { emblem_key?: string } | undefined
  return (
    <div className="flex h-16 w-16 items-center justify-center rounded-md border border-border-base bg-surface-raised">
      <span className="text-caption font-plex-mono text-content-muted">
        {config?.emblem_key || "emblem"}
      </span>
    </div>
  )
}

function NameplateElement({ element }: { element: CanvasElementType }) {
  const config = element.config as { nameplate_text?: string } | undefined
  return (
    <div className="rounded-md border border-border-base bg-surface-base px-3 py-2 font-plex-serif text-body text-content-strong">
      {config?.nameplate_text || "Nameplate"}
    </div>
  )
}

function NameTextElement({ element }: { element: CanvasElementType }) {
  const config = element.config as
    | { name_display?: string; font?: string }
    | undefined
  return (
    <div
      className={cn(
        "px-2 py-1 text-body font-medium text-content-strong",
        config?.font === "italic" ? "italic" : null,
      )}
    >
      {config?.name_display || "Name"}
    </div>
  )
}

function DateTextElement({ element }: { element: CanvasElementType }) {
  const config = element.config as
    | { birth_date_display?: string; death_date_display?: string }
    | undefined
  return (
    <div className="px-2 py-1 font-plex-mono text-body-sm text-content-strong">
      {config?.birth_date_display || "—"}
      <span className="mx-2 text-content-muted">·</span>
      {config?.death_date_display || "—"}
    </div>
  )
}

function LegacyPrintArtifactElement({ element }: { element: CanvasElementType }) {
  const config = element.config as { print_name?: string } | undefined
  return (
    <div className="rounded-sm border border-dashed border-border-strong bg-surface-base p-3 text-caption text-content-muted">
      Legacy print: {config?.print_name || "(unnamed)"}
    </div>
  )
}

function UnknownElement({ element }: { element: CanvasElementType }) {
  return (
    <div className="rounded-sm border border-dashed border-status-warning bg-status-warning-muted p-2 text-caption text-status-warning">
      Unknown element type: {element.element_type}
    </div>
  )
}
