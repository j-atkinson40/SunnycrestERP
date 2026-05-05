/**
 * PersonalizationCanvasStateContext — canonical ephemeral canvas state
 * per Phase 1B canvas implementation.
 *
 * **Canonical-substrate-shape distinction**: this context owns the
 * canonical EPHEMERAL canvas state (drag-in-progress + selection +
 * zoom/pan + transient interactive state) that must NOT persist to
 * canonical Document substrate. Per §3.26.11.12.16 Anti-pattern 11
 * (UI-coupled Generation Focus design rejected): canonical canvas
 * state at canonical Document substrate is independent from canonical
 * interactive UI state at React-component substrate.
 *
 * Canonical Document substrate persistence:
 *   - Canonical canvas state JSON at canonical R2 substrate
 *   - DocumentVersion canonical versioning at canonical canvas commit
 *   - case_merchandise JSONB denormalization for FH-vertical
 *     authoring context (canonical post-r74 vocabulary)
 *
 * React component substrate ephemeral (this context):
 *   - drag-in-progress translate (composite-only via translate3d)
 *   - element selection (selected element id)
 *   - element editing surface (active editor + draft buffer)
 *   - zoom + pan canvas viewport (per-session canonical canvas viewport state)
 *   - hover state highlights
 *
 * **Canonical commit boundary** per Phase A Session 3.8.3 canonical:
 * canvas commits canonical at canonical edit-finish boundary. Drag-end
 * + edit-finish + commit-affordance triggers canonical
 * `commitCanvasState` service call. Canonical operator agency at
 * canonical commit affordance per §3.26.11.12.16 Anti-pattern 1.
 */

import { createContext, useCallback, useContext, useMemo, useState } from "react"
import type { ReactNode } from "react"

import type {
  CanvasElementId,
  CanvasState,
} from "@/types/personalization-studio"

// ─────────────────────────────────────────────────────────────────────
// Canonical ephemeral canvas state shape
// ─────────────────────────────────────────────────────────────────────

/** Canonical ephemeral drag-in-progress state. Composite-only via
 *  translate3d delta per Phase A Session 3.8.3 canonical compositor
 *  pattern. */
export interface DragInProgress {
  elementId: CanvasElementId
  /** Pixel delta from drag-start to current pointer position. */
  dx: number
  dy: number
}

/** Canonical canvas viewport state — zoom + pan. Per-session canonical;
 *  does NOT persist to canonical Document substrate per Phase 1B
 *  canonical viewport-state-not-persisted discipline. */
export interface CanvasViewport {
  /** Canonical zoom factor (1.0 = canonical 100%). */
  zoom: number
  /** Canonical pan offset (canvas-coordinate-space pixels). */
  panX: number
  panY: number
}

/** Canonical ephemeral element editing state. */
export interface ElementEditing {
  elementId: CanvasElementId
  /** Editor type for element-type-specific UI surface. */
  editorType: "font" | "emblem" | "date" | "nameplate_text"
}

export interface PersonalizationCanvasStateValue {
  /** Canonical canvas state from canonical Document substrate (read-side
   *  source-of-truth). The context exposes a setter for canonical
   *  optimistic updates pre-commit; server canonical state authoritative
   *  post-commit. */
  canvasState: CanvasState
  setCanvasState: (next: CanvasState) => void
  /** Canonical commit-pending flag — set by canvas-commit-service consumer
   *  during canonical commit-in-progress. */
  isCommitting: boolean
  setIsCommitting: (next: boolean) => void

  // Canonical ephemeral state — React-only, NOT persisted to substrate
  dragInProgress: DragInProgress | null
  setDragInProgress: (next: DragInProgress | null) => void
  selectedElementId: CanvasElementId | null
  setSelectedElementId: (next: CanvasElementId | null) => void
  editing: ElementEditing | null
  setEditing: (next: ElementEditing | null) => void
  viewport: CanvasViewport
  setViewport: (next: CanvasViewport) => void

  // Canonical ephemeral helper — apply canonical drag-end delta to
  // canvas state (composite-only update during drag; canonical state
  // mutation at drag-end only).
  applyDragEnd: (elementId: CanvasElementId, dx: number, dy: number) => void
  // Canonical helper — apply canonical edit-finish update to canvas state.
  applyElementUpdate: (
    elementId: CanvasElementId,
    update: Partial<CanvasState["canvas_layout"]["elements"][number]>,
  ) => void
}

const PersonalizationCanvasStateContext =
  createContext<PersonalizationCanvasStateValue | null>(null)

const DEFAULT_VIEWPORT: CanvasViewport = { zoom: 1, panX: 0, panY: 0 }

interface ProviderProps {
  initialCanvasState: CanvasState
  children: ReactNode
}

export function PersonalizationCanvasStateProvider({
  initialCanvasState,
  children,
}: ProviderProps) {
  const [canvasState, setCanvasState] = useState<CanvasState>(initialCanvasState)
  const [isCommitting, setIsCommitting] = useState(false)

  // Canonical ephemeral state — React-only; never persists to substrate
  // per §3.26.11.12.16 Anti-pattern 11.
  const [dragInProgress, setDragInProgress] = useState<DragInProgress | null>(
    null,
  )
  const [selectedElementId, setSelectedElementId] =
    useState<CanvasElementId | null>(null)
  const [editing, setEditing] = useState<ElementEditing | null>(null)
  const [viewport, setViewport] = useState<CanvasViewport>(DEFAULT_VIEWPORT)

  /** Canonical drag-end commit at canonical edit-finish boundary per
   *  Phase A Session 3.8.3 canonical: drag-in-progress is composite-only
   *  (translate3d on element root); canvas state mutation happens ONCE
   *  at drag-end via this canonical helper. */
  const applyDragEnd = useCallback(
    (elementId: CanvasElementId, dx: number, dy: number) => {
      setCanvasState((prev) => ({
        ...prev,
        canvas_layout: {
          elements: prev.canvas_layout.elements.map((el) =>
            el.id === elementId ? { ...el, x: el.x + dx, y: el.y + dy } : el,
          ),
        },
      }))
      setDragInProgress(null)
    },
    [],
  )

  /** Canonical edit-finish update — applies element-level canonical
   *  field updates to canvas state at canonical edit-finish boundary. */
  const applyElementUpdate = useCallback(
    (
      elementId: CanvasElementId,
      update: Partial<CanvasState["canvas_layout"]["elements"][number]>,
    ) => {
      setCanvasState((prev) => ({
        ...prev,
        canvas_layout: {
          elements: prev.canvas_layout.elements.map((el) =>
            el.id === elementId ? { ...el, ...update } : el,
          ),
        },
      }))
    },
    [],
  )

  const value = useMemo<PersonalizationCanvasStateValue>(
    () => ({
      canvasState,
      setCanvasState,
      isCommitting,
      setIsCommitting,
      dragInProgress,
      setDragInProgress,
      selectedElementId,
      setSelectedElementId,
      editing,
      setEditing,
      viewport,
      setViewport,
      applyDragEnd,
      applyElementUpdate,
    }),
    [
      canvasState,
      isCommitting,
      dragInProgress,
      selectedElementId,
      editing,
      viewport,
      applyDragEnd,
      applyElementUpdate,
    ],
  )

  return (
    <PersonalizationCanvasStateContext.Provider value={value}>
      {children}
    </PersonalizationCanvasStateContext.Provider>
  )
}

export function usePersonalizationCanvasState(): PersonalizationCanvasStateValue {
  const ctx = useContext(PersonalizationCanvasStateContext)
  if (!ctx) {
    throw new Error(
      "usePersonalizationCanvasState must be used inside PersonalizationCanvasStateProvider",
    )
  }
  return ctx
}

/** Optional variant — returns null when no provider is mounted. Useful
 *  for components that consume canvas state when canonical, but render
 *  outside canvas context too. */
export function usePersonalizationCanvasStateOptional():
  | PersonalizationCanvasStateValue
  | null {
  return useContext(PersonalizationCanvasStateContext)
}
