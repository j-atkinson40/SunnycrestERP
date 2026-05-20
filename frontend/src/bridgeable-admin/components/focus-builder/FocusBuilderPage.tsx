/**
 * FocusBuilderPage — top-level Focus Builder surface (sub-arc F-1 + F-2).
 *
 * F-1 shipped the layout shell + tree + URL state with placeholder
 * canvas + right rail. F-2 wires the selection-driven canvas + inspector
 * + auto-save + InheritedCoreInspectorPanel "View canonical core" flow.
 *
 * URL contract per investigation Q-40 LOCKED (b):
 *   `?subject=core:<id>` OR `?subject=template:<id>`
 *   `?return_to=` preserved for the back-link contract.
 *
 * Selection state lives in FocusBuilderSelectionContext, mounted at the
 * page root. Esc → deselect; URL subject change → selection reset to
 * { kind: 'none' }.
 */
import * as React from "react"
import { useLocation, useNavigate, useSearchParams } from "react-router-dom"
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragMoveEvent,
  type DragStartEvent,
} from "@dnd-kit/core"

import { parseStudioPath } from "@/bridgeable-admin/lib/studio-routes"
import { useFocusCoreDraft } from "@/bridgeable-admin/hooks/useFocusCoreDraft"
import { useFocusTemplateDraft } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"
import {
  focusCoresService,
  type CoreRecord,
} from "@/bridgeable-admin/services/focus-cores-service"
import {
  focusTemplatesService,
  type ResolveSources,
} from "@/bridgeable-admin/services/focus-templates-service"
import {
  verticalsService,
  type Vertical,
} from "@/bridgeable-admin/services/verticals-service"
import { focusTypeForCore, focusTypeLabel } from "@/lib/visual-editor/focus-types"
import { BASE_TOKENS } from "@/lib/visual-editor/themes/base-tokens"
import { InheritedCoreInspectorPanel } from "@/bridgeable-admin/components/visual-editor/InheritedCoreInspectorPanel"

import FocusBuilderTree, {
  type FocusBuilderSubject,
} from "./FocusBuilderTree"
import {
  FocusBuilderCanvas,
  CANVAS_DROP_ZONE_ID,
  detectTemplateShape,
  computeFreeFormDropPosition,
  flattenFreeFormPlacements,
} from "./FocusBuilderCanvas"
import { computeDragMoveCommit } from "./computeDragMoveCommit"
import { computeResizeCommit } from "./computeResizeCommit"
import { parseFreeFormDraggableId } from "./FreeFormPlacedWidget"
import { parseResizeHandleId } from "./ResizeHandleOverlay"
import {
  getFreeFormDefaultDimensions,
  getFreeFormMinDimensions,
  FREE_FORM_DEFAULT_DIMENSIONS,
} from "@/lib/visual-editor/registry"
import {
  FREE_FORM_DEFAULT_CANVAS_WIDTH,
  FREE_FORM_DEFAULT_CANVAS_HEIGHT,
} from "./WidgetFreeFormLayer"
import { CanvasContextMenu, type ContextMenuAction } from "./CanvasContextMenu"
import {
  computeSnapAdjustment,
  type SnapLine,
} from "./computeSnapAdjustment"
import {
  computeAlignTargets,
  type AlignAction,
} from "./computeAlignTargets"
import type { ZIndexAction } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"
import { FocusBuilderRightRail } from "./FocusBuilderRightRail"
import {
  FocusBuilderSelectionProvider,
  useFocusBuilderSelection,
} from "./FocusBuilderSelectionContext"
import { paletteItemIdToSlug } from "./FocusBuilderPalette"
import { FocusBuilderBreadcrumb } from "./FocusBuilderBreadcrumb"
import { FocusBuilderSaveIndicator } from "./FocusBuilderSaveIndicator"


function parseSubjectParam(raw: string | null): FocusBuilderSubject | null {
  if (!raw) return null
  const colon = raw.indexOf(":")
  if (colon <= 0) return null
  const kind = raw.slice(0, colon)
  const id = raw.slice(colon + 1)
  if (!id) return null
  if (kind === "core") return { kind: "core", id }
  if (kind === "template") return { kind: "template", id }
  return null
}


function subjectToParam(subject: FocusBuilderSubject): string {
  return `${subject.kind}:${subject.id}`
}


export function FocusBuilderPage() {
  return (
    <FocusBuilderSelectionProvider>
      <FocusBuilderPageInner />
    </FocusBuilderSelectionProvider>
  )
}


function FocusBuilderPageInner() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const location = useLocation()

  const subject = React.useMemo(
    () => parseSubjectParam(searchParams.get("subject")),
    [searchParams],
  )

  const studioActiveVertical = React.useMemo(() => {
    return parseStudioPath(
      location.pathname.replace(/^\/bridgeable-admin/, ""),
    ).vertical
  }, [location.pathname])

  const handleSelectSubject = React.useCallback(
    (next: FocusBuilderSubject) => {
      const params = new URLSearchParams(searchParams)
      params.set("subject", subjectToParam(next))
      setSearchParams(params, { replace: false })
    },
    [searchParams, setSearchParams],
  )

  // ── Hook layer — mount one or the other based on subject kind ─────
  const coreSubjectId = subject?.kind === "core" ? subject.id : null
  const templateSubjectId = subject?.kind === "template" ? subject.id : null

  const coreHook = useFocusCoreDraft(coreSubjectId)
  // F-3.1a.2 — URL recovery on 410-retry. When the first save of a
  // session 410s (because the URL-bound template_id was deactivated
  // by a prior session's version-bump on the backend), the hook
  // swaps to the active id and retries; the callback below rewrites
  // the URL `?subject=template:<new-id>` with `{ replace: true }` so
  // refresh GETs the still-active row instead of the deactivated
  // snapshot. `{ replace: true }` is mandatory — without it every
  // version-bump grows browser history.
  // F-3.1a.2 — URL recovery on 410-retry. When the first save of a
  // session 410s (because the URL-bound template_id was deactivated
  // by a prior session's version-bump on the backend), the hook
  // swaps to the active id and retries; the callback below rewrites
  // the URL `?subject=template:<new-id>` with `{ replace: true }` so
  // refresh GETs the still-active row instead of the deactivated
  // snapshot. `{ replace: true }` is mandatory — without it every
  // version-bump grows browser history.
  const handleActiveTemplateIdChange = React.useCallback(
    (newId: string) => {
      const params = new URLSearchParams(searchParams)
      params.set("subject", `template:${newId}`)
      setSearchParams(params, { replace: true })
    },
    [searchParams, setSearchParams],
  )
  const templateHook = useFocusTemplateDraft(templateSubjectId, {
    onActiveTemplateIdChange: handleActiveTemplateIdChange,
  })

  // ── Selection reset on subject change ─────────────────────────────
  const {
    selection,
    setSelection,
    addToSelection,
    removeFromSelection,
    clearSelection,
    setMultiSelection,
    isInSelection,
  } = useFocusBuilderSelection()
  const lastSubjectKey = React.useRef<string | null>(null)
  const currentSubjectKey = subject ? `${subject.kind}:${subject.id}` : null
  React.useEffect(() => {
    if (lastSubjectKey.current !== currentSubjectKey) {
      setSelection({ kind: "none" })
      lastSubjectKey.current = currentSubjectKey
    }
  }, [currentSubjectKey, setSelection])

  // ── Keyboard — Esc deselects; Delete removes selected widget ──────
  // F-3 extends F-2's Esc handler with Delete-on-widget-selection.
  const selectionRef = React.useRef(selection)
  React.useEffect(() => {
    selectionRef.current = selection
  }, [selection])
  React.useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setSelection({ kind: "none" })
        return
      }
      if (e.key === "Delete" || e.key === "Backspace") {
        const sel = selectionRef.current
        if (sel.kind === "widget") {
          // Guard: only when editing a template (cores have no widgets).
          if (templateSubjectId) {
            // Avoid stealing the key when an editable surface is focused.
            const target = e.target as HTMLElement | null
            const tag = target?.tagName
            const editable =
              tag === "INPUT" ||
              tag === "TEXTAREA" ||
              target?.isContentEditable
            if (editable) return
            templateHook.removeWidget(sel.id)
            setSelection({ kind: "none" })
          }
        }
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [setSelection, templateSubjectId, templateHook])

  // ── Inherited core fetch (template editing only) ──────────────────
  const [inheritedCore, setInheritedCore] = React.useState<CoreRecord | null>(
    null,
  )
  const inheritsFromCoreId =
    templateHook.template?.inherits_from_core_id ?? null
  const inheritsFromCoreVersion =
    templateHook.template?.inherits_from_core_version ?? null
  React.useEffect(() => {
    if (!inheritsFromCoreId) {
      setInheritedCore(null)
      return
    }
    let cancelled = false
    focusCoresService
      .get(inheritsFromCoreId)
      .then((core) => {
        if (!cancelled) setInheritedCore(core)
      })
      .catch(() => {
        if (!cancelled) setInheritedCore(null)
      })
    return () => {
      cancelled = true
    }
  }, [inheritsFromCoreId, inheritsFromCoreVersion])

  // ── Resolver-driven inheritance provenance (template only) ────────
  const [sources, setSources] = React.useState<ResolveSources | null>(null)
  const templateSlug = templateHook.template?.template_slug
  const templateVertical = templateHook.template?.vertical ?? null
  const templateVersion = templateHook.template?.version
  React.useEffect(() => {
    if (!templateSlug) {
      setSources(null)
      return
    }
    if (typeof focusTemplatesService.resolve !== "function") {
      setSources(null)
      return
    }
    let cancelled = false
    focusTemplatesService
      .resolve({
        template_slug: templateSlug,
        vertical: templateVertical,
      })
      .then((resp) => {
        if (!cancelled) setSources(resp.sources)
      })
      .catch(() => {
        if (!cancelled) setSources(null)
      })
    return () => {
      cancelled = true
    }
  }, [templateSlug, templateVertical, templateVersion])

  // ── Active hook (whichever is bound) drives dirty + last-saved ────
  const mode: "core" | "template" | "empty" =
    subject?.kind === "core"
      ? "core"
      : subject?.kind === "template"
        ? "template"
        : "empty"
  const isDirty =
    mode === "core" ? coreHook.isDirty : mode === "template" ? templateHook.isDirty : false
  const isSaving =
    mode === "core"
      ? coreHook.isSaving
      : mode === "template"
        ? templateHook.isSaving
        : false
  const saveError =
    mode === "core"
      ? coreHook.error
      : mode === "template"
        ? templateHook.error
        : null
  const lastSavedAt =
    mode === "core"
      ? coreHook.lastSavedAt
      : mode === "template"
        ? templateHook.lastSavedAt
        : null
  const handleRetrySave = React.useCallback(() => {
    if (mode === "core") void coreHook.save()
    else if (mode === "template") void templateHook.save()
  }, [mode, coreHook, templateHook])

  // ── F-5 verticals fetch for breadcrumb display_name lookup ────────
  // Tree fetches verticals separately for its own data needs; the
  // breadcrumb needs the same map to translate vertical slug → label.
  // Fetched once at mount; verticals are stable.
  const [verticals, setVerticals] = React.useState<Vertical[]>([])
  React.useEffect(() => {
    let cancelled = false
    verticalsService
      .list()
      .then((rows) => {
        if (!cancelled) setVerticals(rows)
      })
      .catch(() => {
        // Best-effort — missing verticals just degrade the breadcrumb
        // to slug-only segments; not load-bearing.
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Browser confirm-before-leave when dirty.
  React.useEffect(() => {
    if (!isDirty) return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ""
    }
    window.addEventListener("beforeunload", handler)
    return () => window.removeEventListener("beforeunload", handler)
  }, [isDirty])

  // ── InheritedCoreInspectorPanel state ─────────────────────────────
  const [inheritedCorePanelOpen, setInheritedCorePanelOpen] =
    React.useState(false)
  // Close panel when subject changes.
  React.useEffect(() => {
    setInheritedCorePanelOpen(false)
  }, [currentSubjectKey])

  const navigateToTier1Core = React.useCallback(
    (coreId: string) => {
      const params = new URLSearchParams(searchParams)
      params.set("subject", `core:${coreId}`)
      setSearchParams(params, { replace: false })
    },
    [searchParams, setSearchParams],
  )

  // Suppress unused-warning for navigate (reserved for F-5 back-link).
  void navigate

  // Theme tokens — F-2 keeps light-mode defaults; Theme picker is F-4.
  const themeTokens = React.useMemo(() => ({ ...BASE_TOKENS.light }), [])

  // ── F-5 breadcrumb segments derivation ────────────────────────────
  // Hierarchy mirrors the left tree's source-of-truth:
  //   vertical → focus-type → core → template
  // CORE subject → 3 segments; TEMPLATE subject → 4. Verticals slug →
  // display_name mapping comes from the verticals-list fetch above.
  // Falls back to slug when display_name can't be resolved.
  const breadcrumbSegments = React.useMemo<string[]>(() => {
    if (mode === "empty") return []
    const verticalDisplayFor = (slug: string | null | undefined): string | null => {
      if (!slug) return null
      const found = verticals.find((v) => v.slug === slug)
      return found?.display_name ?? slug
    }
    if (mode === "core") {
      const core = coreHook.core
      if (!core) return []
      const verticalLabel = verticalDisplayFor(studioActiveVertical)
      const ftLabel = focusTypeLabel(focusTypeForCore(core))
      const segs: string[] = []
      if (verticalLabel) segs.push(verticalLabel)
      segs.push(ftLabel)
      segs.push(core.display_name)
      return segs
    }
    // template
    const tpl = templateHook.template
    if (!tpl) return []
    const verticalLabel = verticalDisplayFor(tpl.vertical)
    const ftLabel = inheritedCore
      ? focusTypeLabel(focusTypeForCore(inheritedCore))
      : null
    const segs: string[] = []
    if (verticalLabel) segs.push(verticalLabel)
    if (ftLabel) segs.push(ftLabel)
    if (inheritedCore) segs.push(inheritedCore.display_name)
    segs.push(tpl.display_name)
    return segs
  }, [
    mode,
    verticals,
    studioActiveVertical,
    coreHook.core,
    templateHook.template,
    inheritedCore,
  ])

  // ── F-3 — DndContext + drag/drop handlers ─────────────────────────
  //
  // Drop handler extracts the widget slug from `active.id` (format
  // `palette-widget:<slug>`), calls `addWidget` on the template hook,
  // and auto-selects the new widget. Drops are only meaningful when
  // editing a template — the canvas drop zone is disabled in core
  // mode (FocusBuilderCanvas's `useDroppable({ disabled: mode !== 'template' })`).
  // FF-3 — sensor stack.
  //   - PointerSensor: 3px activation per Q-9 (click vs. drag
  //     disambiguation; matches @dnd-kit default). Pre-FF-3 the value
  //     was 6px (F-3 palette drop didn't need finer threshold). FF-3
  //     widget repositioning wants the canonical 3px so a brief
  //     intentional press resolves as a click → selection, and any
  //     ≥3px movement is unambiguously a drag.
  //   - KeyboardSensor: Space activates drag; arrow keys nudge; Space
  //     commits; Escape cancels. Per Q-40 (JSDOM weakness mitigation),
  //     integration tests drive @dnd-kit through the keyboard sensor.
  //     Pointer-event coverage in JSDOM is unreliable; FF-7 ships
  //     Playwright drag coverage for real pointer gestures.
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 3 },
    }),
    useSensor(KeyboardSensor),
  )
  const [activeDragLabel, setActiveDragLabel] = React.useState<string | null>(
    null,
  )

  // ── FF-5 — right-click context menu state + dispatcher ────────────
  //
  // Single menu instance rendered at page root via portal (per
  // CanvasContextMenu). Right-click on any free-form widget opens it
  // at the cursor position; left-click anywhere outside closes it
  // (via the menu's own document-level mousedown listener). The
  // dispatch routes through templateHook.setWidgetZIndex.
  const [contextMenuState, setContextMenuState] = React.useState<{
    open: boolean
    position: { x: number; y: number }
    targetPlacementId: string | null
  }>({ open: false, position: { x: 0, y: 0 }, targetPlacementId: null })

  const handleWidgetContextMenuRequest = React.useCallback(
    (placementId: string, position: { x: number; y: number }) => {
      setContextMenuState({
        open: true,
        position,
        targetPlacementId: placementId,
      })
    },
    [],
  )

  const handleContextMenuClose = React.useCallback(() => {
    setContextMenuState((prev) => ({ ...prev, open: false }))
  }, [])

  // FF-7 — handleContextMenuActionUnified (declared below) replaces
  // the FF-5 single-purpose handler. The dispatcher now distinguishes
  // z-order (single-select) vs align (multi-select) based on selection.

  // Close the menu when the subject changes (defensive — same idiom
  // as the inherited-core panel close-on-subject-change).
  React.useEffect(() => {
    setContextMenuState((prev) =>
      prev.open ? { ...prev, open: false } : prev,
    )
  }, [currentSubjectKey])

  // ── FF-7 — snap state + alt-key tracking ──────────────────────────
  // `snapLines` are live during the drag (set via `onDragMove`),
  // cleared on drag-end. Alt-key flag tracked at document level
  // because @dnd-kit's DragMoveEvent does NOT expose the activator's
  // current modifier state mid-gesture.
  const [snapLines, setSnapLines] = React.useState<SnapLine[]>([])
  const altKeyHeldRef = React.useRef(false)
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      altKeyHeldRef.current = e.altKey
    }
    const onKeyUp = (e: KeyboardEvent) => {
      altKeyHeldRef.current = e.altKey
    }
    document.addEventListener("keydown", onKey)
    document.addEventListener("keyup", onKeyUp)
    return () => {
      document.removeEventListener("keydown", onKey)
      document.removeEventListener("keyup", onKeyUp)
    }
  }, [])

  // ── FF-7 — marquee state ──────────────────────────────────────────
  // Coordinates are canvas-relative (resolved from the freeform layer
  // element's bounding rect at pointer-down). `active` flips true once
  // the 3px threshold is exceeded; below threshold, pointer-up is
  // treated as a background-click → clearSelection.
  const [marquee, setMarquee] = React.useState<{
    start: { x: number; y: number } | null
    current: { x: number; y: number } | null
    active: boolean
  }>({ start: null, current: null, active: false })

  // FF-7 — selection helpers are destructured above with `selection`
  // + `setSelection`; the FF-7 multi-select handlers (add / remove /
  // clear / setMulti / isIn) flow through the same hook call.

  // ── FF-7 — shift+click handler: add / remove this id from selection.
  const handleWidgetShiftSelect = React.useCallback(
    (id: string) => {
      if (isInSelection(id)) {
        removeFromSelection(id)
      } else {
        addToSelection(id)
      }
    },
    [isInSelection, addToSelection, removeFromSelection],
  )

  // ── FF-7 — align action dispatcher (multi-select inspector +
  // context menu).
  const handleAlignAction = React.useCallback(
    (action: AlignAction) => {
      if (mode !== "template") return
      if (selection.kind !== "widgets-multi") return
      const placements = flattenFreeFormPlacements(templateHook.rowsDraft)
      const selected = placements.filter((p) =>
        selection.ids.includes(p.id),
      )
      // Normalize positioning fields to numbers (rowsDraft may carry
      // undefined / null when round-tripped from legacy shapes).
      const alignable = selected.map((p) => ({
        id: p.id,
        x: typeof p.x === "number" ? p.x : 0,
        y: typeof p.y === "number" ? p.y : 0,
        width:
          typeof p.width === "number" && p.width > 0
            ? p.width
            : FREE_FORM_DEFAULT_DIMENSIONS.width,
        height:
          typeof p.height === "number" && p.height > 0
            ? p.height
            : FREE_FORM_DEFAULT_DIMENSIONS.height,
      }))
      const targets = computeAlignTargets(alignable, action)
      for (const t of targets) {
        const partial: Record<string, unknown> = {}
        if (typeof t.x === "number") partial.x = t.x
        if (typeof t.y === "number") partial.y = t.y
        templateHook.updateWidget(t.id, partial)
      }
    },
    [mode, selection, templateHook],
  )

  // ── FF-7 — unified context-menu action dispatcher. Distinguishes
  // z-order vs align by current selection.kind.
  const handleContextMenuActionUnified = React.useCallback(
    (action: ContextMenuAction) => {
      if (selection.kind === "widgets-multi") {
        // Align vocabulary.
        handleAlignAction(action as AlignAction)
        return
      }
      // Z-order vocabulary (FF-5 path preserved).
      if (!contextMenuState.targetPlacementId) return
      if (mode !== "template") return
      templateHook.setWidgetZIndex(
        contextMenuState.targetPlacementId,
        action as ZIndexAction,
      )
    },
    [
      selection,
      handleAlignAction,
      contextMenuState.targetPlacementId,
      mode,
      templateHook,
    ],
  )

  // ── FF-7 — marquee pointer handlers on the canvas background.
  // The freeform layer's onPointerDown receives the pointer-down
  // gesture; we only initiate marquee when the down lands on the
  // background (NOT on a widget — widgets stopPropagation in
  // PlacedWidgetCore's onClick path, but pointer events bubble
  // separately, so we discriminate by event target attribute).
  const handleLayerPointerDown = React.useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      // Only initiate marquee when the pointer-down lands directly
      // on the canvas-background element (the freeform layer). When
      // it lands on a widget or core, the widget's own pointer flow
      // governs.
      const target = e.target as HTMLElement | null
      if (!target) return
      const isBackground =
        target.getAttribute("data-canvas-background") === "true"
      if (!isBackground) return
      // Resolve canvas-relative coords.
      const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      setMarquee({ start: { x, y }, current: { x, y }, active: false })
    },
    [],
  )
  const handleLayerPointerMove = React.useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      // Capture rect + coords OUTSIDE the state updater. React pools
      // synthetic events; `e.currentTarget` is null by the time the
      // updater runs.
      const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      setMarquee((prev) => {
        if (!prev.start) return prev
        const dx = x - prev.start.x
        const dy = y - prev.start.y
        const active =
          prev.active || Math.sqrt(dx * dx + dy * dy) >= 3
        return { start: prev.start, current: { x, y }, active }
      })
    },
    [],
  )
  const handleLayerPointerUp = React.useCallback(
    () => {
      setMarquee((prev) => {
        if (!prev.start || !prev.current) {
          return { start: null, current: null, active: false }
        }
        if (!prev.active) {
          // Below threshold — treat as background click → clear selection.
          clearSelection()
          return { start: null, current: null, active: false }
        }
        // Commit marquee selection. Compute bounding-box intersection
        // for every free-form placement.
        const left = Math.min(prev.start.x, prev.current.x)
        const right = Math.max(prev.start.x, prev.current.x)
        const top = Math.min(prev.start.y, prev.current.y)
        const bottom = Math.max(prev.start.y, prev.current.y)
        const placements = flattenFreeFormPlacements(templateHook.rowsDraft)
        const enclosed: string[] = []
        for (const p of placements) {
          const px = typeof p.x === "number" ? p.x : 0
          const py = typeof p.y === "number" ? p.y : 0
          const pw =
            typeof p.width === "number" && p.width > 0
              ? p.width
              : FREE_FORM_DEFAULT_DIMENSIONS.width
          const ph =
            typeof p.height === "number" && p.height > 0
              ? p.height
              : FREE_FORM_DEFAULT_DIMENSIONS.height
          // Standard AABB intersection.
          if (
            !(
              px + pw < left ||
              px > right ||
              py + ph < top ||
              py > bottom
            )
          ) {
            enclosed.push(p.id)
          }
        }
        setMultiSelection(enclosed)
        return { start: null, current: null, active: false }
      })
    },
    [clearSelection, setMultiSelection, templateHook.rowsDraft],
  )

  // ── FF-7 — keyboard nudge + z-order shortcuts ──────────────────────
  // Arrow keys nudge the selected widget(s) by 1px (Shift+arrow = 10px).
  // `]` / `[` / `Shift+]` / `Shift+[` are z-order shortcuts in
  // single-select mode. Listeners ignore typing in inputs/textareas.
  React.useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Ignore typing in inputs / textareas / contenteditable.
      const target = e.target as HTMLElement | null
      const tag = target?.tagName
      const editable =
        tag === "INPUT" || tag === "TEXTAREA" || target?.isContentEditable
      if (editable) return
      // Ignore focused buttons — covers ScrubbableButton (`<button>`
      // with its own ArrowLeft/Right handler), the inspector's align
      // buttons, the layer-section toggle buttons, the right-rail
      // tab buttons, and any other operator-driven keyboard target.
      // The nudge listener fires on `window`, so we need to discriminate
      // by activeElement before consuming the keystroke.
      if (tag === "BUTTON") return
      // Guard: only when editing a template.
      if (mode !== "template") return
      // Guard: bail when a drag is in flight. @dnd-kit's
      // KeyboardSensor + PointerSensor own the arrow keys during a
      // gesture (Space activates, arrows nudge, Space commits). The
      // page-level nudge listener must not race the sensor.
      if (activeDragLabel !== null) return

      // Resolve currently-selected placement ids.
      let ids: string[] = []
      if (selection.kind === "widget") ids = [selection.id]
      else if (selection.kind === "widgets-multi") ids = selection.ids
      if (ids.length === 0) return

      const placements = flattenFreeFormPlacements(templateHook.rowsDraft)
      const selectedPlacements = placements.filter((p) => ids.includes(p.id))
      if (selectedPlacements.length === 0) return

      const canvasConfig = templateHook.template?.canvas_config as
        | Record<string, unknown>
        | undefined
      const canvasWidth =
        (canvasConfig?.width as number | undefined) ??
        FREE_FORM_DEFAULT_CANVAS_WIDTH
      const canvasHeight =
        (canvasConfig?.height as number | undefined) ??
        FREE_FORM_DEFAULT_CANVAS_HEIGHT

      // Arrow nudges.
      const stepDelta = e.shiftKey ? 10 : 1
      let dx = 0
      let dy = 0
      if (e.key === "ArrowLeft") dx = -stepDelta
      else if (e.key === "ArrowRight") dx = stepDelta
      else if (e.key === "ArrowUp") dy = -stepDelta
      else if (e.key === "ArrowDown") dy = stepDelta

      if (dx !== 0 || dy !== 0) {
        e.preventDefault()
        for (const p of selectedPlacements) {
          const curX = typeof p.x === "number" ? p.x : 0
          const curY = typeof p.y === "number" ? p.y : 0
          const w =
            typeof p.width === "number" && p.width > 0
              ? p.width
              : FREE_FORM_DEFAULT_DIMENSIONS.width
          const h =
            typeof p.height === "number" && p.height > 0
              ? p.height
              : FREE_FORM_DEFAULT_DIMENSIONS.height
          const nextX = Math.max(0, Math.min(curX + dx, canvasWidth - w))
          const nextY = Math.max(0, Math.min(curY + dy, canvasHeight - h))
          templateHook.updateWidget(p.id, { x: nextX, y: nextY })
        }
        return
      }

      // Z-order shortcuts: single-select only.
      if (selection.kind !== "widget") return
      const id = selection.id
      if (e.key === "]") {
        e.preventDefault()
        templateHook.setWidgetZIndex(id, e.shiftKey ? "front" : "forward")
        return
      }
      if (e.key === "[") {
        e.preventDefault()
        templateHook.setWidgetZIndex(id, e.shiftKey ? "back" : "backward")
        return
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [mode, selection, templateHook, activeDragLabel])

  const handleDragStart = React.useCallback((e: DragStartEvent) => {
    const id = String(e.active.id ?? "")
    const slug = paletteItemIdToSlug(id)
    setActiveDragLabel(slug ?? id)
  }, [])

  const handleDragEnd = React.useCallback(
    (e: DragEndEvent) => {
      setActiveDragLabel(null)
      const { active, over } = e

      // FF-4 — resize branch. The drag id matches
      // `<placementId>-handle-<position>`. Dispatch to
      // `computeResizeCommit` with the placement's current geometry,
      // the canvas bounds (Q-14), and the registry-resolved min
      // dimensions (Q-13, 80×40 platform fallback). Commit width/
      // height/x/y via the existing `updateWidget` mutator (FF-1's
      // positioning-field routing). Checked BEFORE the FF-3 move
      // branch because handle ids share the placement id prefix.
      const handleParsed = parseResizeHandleId(String(active.id))
      if (handleParsed) {
        if (mode !== "template") return
        const flat = flattenFreeFormPlacements(templateHook.rowsDraft)
        const placement = flat.find((p) => p.id === handleParsed.placementId)
        if (!placement) return
        const currentX = typeof placement.x === "number" ? placement.x : 0
        const currentY = typeof placement.y === "number" ? placement.y : 0
        const currentWidth =
          typeof placement.width === "number" && placement.width > 0
            ? placement.width
            : FREE_FORM_DEFAULT_DIMENSIONS.width
        const currentHeight =
          typeof placement.height === "number" && placement.height > 0
            ? placement.height
            : FREE_FORM_DEFAULT_DIMENSIONS.height
        const canvasConfig = templateHook.template?.canvas_config as
          | Record<string, unknown>
          | undefined
        const canvasWidth =
          (canvasConfig?.width as number | undefined) ??
          FREE_FORM_DEFAULT_CANVAS_WIDTH
        const canvasHeight =
          (canvasConfig?.height as number | undefined) ??
          FREE_FORM_DEFAULT_CANVAS_HEIGHT
        const minDimensions = getFreeFormMinDimensions(placement.widget_slug)
        const next = computeResizeCommit({
          currentPlacement: {
            x: currentX,
            y: currentY,
            width: currentWidth,
            height: currentHeight,
          },
          handle: handleParsed.position,
          delta: { x: e.delta?.x ?? 0, y: e.delta?.y ?? 0 },
          canvasDimensions: { width: canvasWidth, height: canvasHeight },
          minDimensions,
        })
        templateHook.updateWidget(handleParsed.placementId, {
          x: next.x,
          y: next.y,
          width: next.width,
          height: next.height,
        })
        return
      }

      // FF-3 — drag-to-move branch. An existing free-form placement is
      // being repositioned. The drag id is the placement's draggable
      // id (`free-form-placed-widget:<placement-id>`). No drop target
      // required — the gesture is a delta on the active widget. The
      // commit applies `delta.x` / `delta.y` to the placement's
      // current x/y and clamps to canvas bounds via
      // `computeDragMoveCommit` (Q-14).
      //
      // FF-7: snap-to-alignment fires AFTER the clamp. Multi-select
      // moves all selected widgets together if the dragged widget is
      // part of the current multi-selection (Figma precedent: a drag
      // of a widget NOT in the selection moves only that widget +
      // preserves the existing multi-selection).
      const placementId = parseFreeFormDraggableId(String(active.id))
      if (placementId !== null) {
        if (mode !== "template") return
        // Find placement by id across all rows.
        const flat = flattenFreeFormPlacements(templateHook.rowsDraft)
        const placement = flat.find((p) => p.id === placementId)
        if (!placement) return
        const currentX = typeof placement.x === "number" ? placement.x : 0
        const currentY = typeof placement.y === "number" ? placement.y : 0
        const widgetWidth =
          typeof placement.width === "number" && placement.width > 0
            ? placement.width
            : FREE_FORM_DEFAULT_DIMENSIONS.width
        const widgetHeight =
          typeof placement.height === "number" && placement.height > 0
            ? placement.height
            : FREE_FORM_DEFAULT_DIMENSIONS.height
        const canvasConfig = templateHook.template?.canvas_config as
          | Record<string, unknown>
          | undefined
        const canvasWidth =
          (canvasConfig?.width as number | undefined) ??
          FREE_FORM_DEFAULT_CANVAS_WIDTH
        const canvasHeight =
          (canvasConfig?.height as number | undefined) ??
          FREE_FORM_DEFAULT_CANVAS_HEIGHT

        // FF-7 — multi-select drag branch. When the dragged placement
        // is part of a multi-selection, apply the SAME delta to every
        // selected widget (each clamped to its own canvas bounds).
        // Otherwise fall through to the single-widget commit.
        let appliedDx = e.delta?.x ?? 0
        let appliedDy = e.delta?.y ?? 0

        // Compute snapped position for the DRAGGED widget. Snap fires
        // AFTER canvas-bounds clamp. Inherited core excluded from
        // other placements (structural-immutability canon).
        const clampedSelf = computeDragMoveCommit({
          currentX,
          currentY,
          dx: appliedDx,
          dy: appliedDy,
          canvasWidth,
          canvasHeight,
          widgetWidth,
          widgetHeight,
        })
        const others = flat
          .filter((p) => p.id !== placementId)
          .map((p) => ({
            id: p.id,
            x: typeof p.x === "number" ? p.x : 0,
            y: typeof p.y === "number" ? p.y : 0,
            width:
              typeof p.width === "number" && p.width > 0
                ? p.width
                : FREE_FORM_DEFAULT_DIMENSIONS.width,
            height:
              typeof p.height === "number" && p.height > 0
                ? p.height
                : FREE_FORM_DEFAULT_DIMENSIONS.height,
          }))
        const snapped = computeSnapAdjustment({
          draggedPlacement: {
            id: placementId,
            x: currentX,
            y: currentY,
            width: widgetWidth,
            height: widgetHeight,
          },
          otherPlacements: others,
          canvasDimensions: { width: canvasWidth, height: canvasHeight },
          dragPosition: { x: clampedSelf.x, y: clampedSelf.y },
          altKeyHeld: altKeyHeldRef.current,
        })
        // Snap may have shifted position — re-clamp to canvas bounds
        // so a snap target NEAR the edge that would push outside the
        // canvas defers to the bound (the bound wins).
        const finalX = Math.max(
          0,
          Math.min(snapped.x, canvasWidth - widgetWidth),
        )
        const finalY = Math.max(
          0,
          Math.min(snapped.y, canvasHeight - widgetHeight),
        )
        // The effective delta after clamp + snap re-clamp:
        appliedDx = finalX - currentX
        appliedDy = finalY - currentY

        // Clear snap lines on drag-end.
        setSnapLines([])

        // Apply to dragged widget.
        templateHook.updateWidget(placementId, { x: finalX, y: finalY })

        // Multi-select cohort: apply the SAME effective delta to every
        // other selected widget, each clamped to canvas bounds. Only
        // applies when the dragged widget IS in multi-selection.
        if (selection.kind === "widgets-multi" && selection.ids.includes(placementId)) {
          for (const other of flat) {
            if (other.id === placementId) continue
            if (!selection.ids.includes(other.id)) continue
            const oX = typeof other.x === "number" ? other.x : 0
            const oY = typeof other.y === "number" ? other.y : 0
            const oW =
              typeof other.width === "number" && other.width > 0
                ? other.width
                : FREE_FORM_DEFAULT_DIMENSIONS.width
            const oH =
              typeof other.height === "number" && other.height > 0
                ? other.height
                : FREE_FORM_DEFAULT_DIMENSIONS.height
            const nextX = Math.max(0, Math.min(oX + appliedDx, canvasWidth - oW))
            const nextY = Math.max(0, Math.min(oY + appliedDy, canvasHeight - oH))
            templateHook.updateWidget(other.id, { x: nextX, y: nextY })
          }
        }
        return
      }

      // F-3 / FF-2 — palette drop branch (existing).
      if (!over) return
      if (over.id !== CANVAS_DROP_ZONE_ID) return
      const slug = paletteItemIdToSlug(String(active.id))
      if (!slug) return
      if (mode !== "template") return

      // FF-2 — template-shape branch. Existing templates respect
      // their current placement shape (mixed-shape rejected at the
      // FF-1 backend validator); empty templates default to FREE-
      // FORM per Q-27 — every new Focus template authored after the
      // FF-2 ship is a free-form template.
      const currentShape = detectTemplateShape(templateHook.rowsDraft)
      const isEmpty = !templateHook.rowsDraft || templateHook.rowsDraft.length === 0
      const useFreeForm = currentShape === "freeform" || isEmpty

      if (useFreeForm) {
        // Compute cursor position relative to the canvas. dnd-kit's
        // `DragEndEvent` exposes the original pointerdown via
        // `activatorEvent` (clientX/Y) + cumulative `delta` (movement
        // since activation). cursor = activator + delta. Subtract
        // the canvas's bounding rect to get canvas-relative coords.
        // The free-form layer is centered inside the canvas drop
        // zone (margin: 0 auto), so we resolve coords against the
        // layer element when available — falls back to the drop
        // zone's rect when the layer is not yet mounted (very
        // first drop on a brand-new template).
        const dropZoneEl = document.querySelector<HTMLElement>(
          `[data-testid="focus-builder-canvas"]`,
        )
        const layerEl =
          document.querySelector<HTMLElement>(
            `[data-testid="focus-builder-freeform-layer"]`,
          ) ?? dropZoneEl
        const rect = layerEl?.getBoundingClientRect()
        const activator = e.activatorEvent as
          | PointerEvent
          | MouseEvent
          | TouchEvent
          | null
        let clientX = 0
        let clientY = 0
        if (activator && "clientX" in activator) {
          clientX = (activator as MouseEvent).clientX
          clientY = (activator as MouseEvent).clientY
        } else if (
          activator &&
          "touches" in activator &&
          (activator as TouchEvent).touches.length > 0
        ) {
          clientX = (activator as TouchEvent).touches[0].clientX
          clientY = (activator as TouchEvent).touches[0].clientY
        }
        const cursorX = clientX + (e.delta?.x ?? 0)
        const cursorY = clientY + (e.delta?.y ?? 0)
        const relX = rect ? cursorX - rect.left : cursorX
        const relY = rect ? cursorY - rect.top : cursorY

        // Resolve per-widget defaults from registry (Q-5).
        const { width, height } = getFreeFormDefaultDimensions(slug)

        // Q-4 + Q-14 via shared helper. When the layer isn't mounted
        // yet (empty template, first drop), fall back to 1200×800
        // platform defaults.
        const canvasW = rect?.width ?? 1200
        const canvasH = rect?.height ?? 800
        const { x, y } = computeFreeFormDropPosition({
          cursorX: relX,
          cursorY: relY,
          width,
          height,
          canvasWidth: canvasW,
          canvasHeight: canvasH,
        })

        const newId = templateHook.addWidget(slug, {
          x,
          y,
          width,
          height,
          z_index: 0,
        })
        setSelection({ kind: "widget", id: newId })
        return
      }

      // F-3 grid path preserved unchanged.
      const newId = templateHook.addWidget(slug)
      setSelection({ kind: "widget", id: newId })
    },
    [mode, templateHook, setSelection, selection],
  )

  // ── FF-7 — live snap lines during drag-move ────────────────────────
  // Fires on every drag-move tick from @dnd-kit; computes the live
  // snap candidates so SnapLineOverlay can render them. Cleared at
  // drag-end (above) + drag-cancel.
  const handleDragMove = React.useCallback(
    (e: DragMoveEvent) => {
      if (mode !== "template") return
      const placementId = parseFreeFormDraggableId(String(e.active.id))
      if (placementId === null) return
      const flat = flattenFreeFormPlacements(templateHook.rowsDraft)
      const placement = flat.find((p) => p.id === placementId)
      if (!placement) return
      const currentX = typeof placement.x === "number" ? placement.x : 0
      const currentY = typeof placement.y === "number" ? placement.y : 0
      const widgetWidth =
        typeof placement.width === "number" && placement.width > 0
          ? placement.width
          : FREE_FORM_DEFAULT_DIMENSIONS.width
      const widgetHeight =
        typeof placement.height === "number" && placement.height > 0
          ? placement.height
          : FREE_FORM_DEFAULT_DIMENSIONS.height
      const canvasConfig = templateHook.template?.canvas_config as
        | Record<string, unknown>
        | undefined
      const canvasWidth =
        (canvasConfig?.width as number | undefined) ??
        FREE_FORM_DEFAULT_CANVAS_WIDTH
      const canvasHeight =
        (canvasConfig?.height as number | undefined) ??
        FREE_FORM_DEFAULT_CANVAS_HEIGHT
      const clamped = computeDragMoveCommit({
        currentX,
        currentY,
        dx: e.delta?.x ?? 0,
        dy: e.delta?.y ?? 0,
        canvasWidth,
        canvasHeight,
        widgetWidth,
        widgetHeight,
      })
      const others = flat
        .filter((p) => p.id !== placementId)
        .map((p) => ({
          id: p.id,
          x: typeof p.x === "number" ? p.x : 0,
          y: typeof p.y === "number" ? p.y : 0,
          width:
            typeof p.width === "number" && p.width > 0
              ? p.width
              : FREE_FORM_DEFAULT_DIMENSIONS.width,
          height:
            typeof p.height === "number" && p.height > 0
              ? p.height
              : FREE_FORM_DEFAULT_DIMENSIONS.height,
        }))
      const snapped = computeSnapAdjustment({
        draggedPlacement: {
          id: placementId,
          x: currentX,
          y: currentY,
          width: widgetWidth,
          height: widgetHeight,
        },
        otherPlacements: others,
        canvasDimensions: { width: canvasWidth, height: canvasHeight },
        dragPosition: { x: clamped.x, y: clamped.y },
        altKeyHeld: altKeyHeldRef.current,
      })
      setSnapLines(snapped.snapLines)
    },
    [mode, templateHook],
  )

  const handleDragCancel = React.useCallback(() => {
    setActiveDragLabel(null)
    setSnapLines([])
  }, [])

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragMove={handleDragMove}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
    <div
      className="flex h-[calc(100vh-3rem)] min-h-[600px] flex-col bg-surface-base"
      data-testid="focus-builder-page"
    >
      <header
        className="flex h-10 shrink-0 items-center gap-3 border-b border-[color:var(--border-subtle)] bg-surface-sunken px-4 text-[12px] text-content-muted"
        data-testid="focus-builder-topbar"
      >
        <span className="font-plex-mono uppercase tracking-wider">
          Bridgeable Studio · Focus Builder
        </span>
        {breadcrumbSegments.length > 0 && (
          <>
            <span
              aria-hidden
              className="text-[color:var(--accent)]"
              data-testid="focus-builder-topbar-breadcrumb-anchor-separator"
            >
              ·
            </span>
            <FocusBuilderBreadcrumb segments={breadcrumbSegments} />
          </>
        )}
        <div className="flex flex-1 items-center justify-end gap-2">
          <FocusBuilderSaveIndicator
            isDirty={isDirty}
            isSaving={isSaving}
            error={saveError}
            lastSavedAt={lastSavedAt}
            onRetry={handleRetrySave}
          />
        </div>
      </header>

      <div className="relative flex min-h-0 flex-1">
        <aside
          className="flex w-[280px] shrink-0 flex-col overflow-y-auto border-r border-[color:var(--border-subtle)] bg-surface-sunken py-2"
          data-testid="focus-builder-tree-region"
        >
          <FocusBuilderTree
            selectedSubject={subject}
            onSelectSubject={handleSelectSubject}
            studioActiveVertical={studioActiveVertical}
          />
        </aside>

        <section
          className="relative min-w-0 flex-1 overflow-hidden"
          data-testid="focus-builder-canvas-region"
        >
          <FocusBuilderCanvas
            mode={mode}
            themeTokens={themeTokens}
            core={coreHook.core}
            template={templateHook.template}
            inheritedCore={inheritedCore}
            chromeOverridesDraft={
              mode === "template" ? templateHook.chromeOverridesDraft : undefined
            }
            substrateDraft={
              mode === "template" ? templateHook.substrateDraft : undefined
            }
            typographyDraft={
              mode === "template" ? templateHook.typographyDraft : undefined
            }
            coreChromeDraft={mode === "core" ? coreHook.draft : undefined}
            rowsDraft={mode === "template" ? templateHook.rowsDraft : undefined}
            onWidgetContextMenuRequest={
              mode === "template" ? handleWidgetContextMenuRequest : undefined
            }
            onWidgetShiftSelect={
              mode === "template" ? handleWidgetShiftSelect : undefined
            }
            marqueeStart={marquee.start}
            marqueeCurrent={marquee.current}
            marqueeActive={marquee.active}
            snapLines={snapLines}
            onLayerPointerDown={
              mode === "template" ? handleLayerPointerDown : undefined
            }
            onLayerPointerMove={
              mode === "template" ? handleLayerPointerMove : undefined
            }
            onLayerPointerUp={
              mode === "template" ? handleLayerPointerUp : undefined
            }
          />
        </section>

        <aside
          className="relative w-[320px] shrink-0 overflow-hidden border-l border-[color:var(--border-subtle)] bg-surface-sunken"
          data-testid="focus-builder-right-rail-region"
        >
          <FocusBuilderRightRail
            mode={mode}
            themeTokens={themeTokens}
            coreHook={mode === "core" ? coreHook : null}
            templateHook={mode === "template" ? templateHook : null}
            inheritedCore={inheritedCore}
            sources={sources}
            onOpenInheritedCorePanel={
              mode === "template" && inheritedCore
                ? () => setInheritedCorePanelOpen(true)
                : undefined
            }
          />
          {inheritedCorePanelOpen && mode === "template" && (
            <InheritedCoreInspectorPanel
              core={inheritedCore}
              isDirty={templateHook.isDirty}
              saveDraft={templateHook.save}
              discardDraft={templateHook.discard}
              onNavigateToTier1Core={(coreId) => {
                setInheritedCorePanelOpen(false)
                navigateToTier1Core(coreId)
              }}
              onClose={() => setInheritedCorePanelOpen(false)}
            />
          )}
        </aside>
      </div>
    </div>
    {/* FF-5 + FF-7 — single context menu instance, portal-rendered
       into document.body. Closes via Escape / click-outside (own
       document listeners) / option click. actionSet switches between
       z-order (single-select) and align (multi-select). */}
    <CanvasContextMenu
      isOpen={contextMenuState.open}
      position={contextMenuState.position}
      onClose={handleContextMenuClose}
      onAction={handleContextMenuActionUnified}
      actionSet={selection.kind === "widgets-multi" ? "align" : "z-order"}
    />
    <DragOverlay>
      {activeDragLabel ? (
        <div
          data-testid="focus-builder-drag-overlay"
          className="rounded-md border border-[color:var(--accent)] bg-surface-elevated px-3 py-1.5 text-[12px] shadow-lg"
          style={{
            fontFamily: "var(--font-plex-sans)",
            color: "var(--content-strong)",
          }}
        >
          {activeDragLabel}
        </div>
      ) : null}
    </DragOverlay>
    </DndContext>
  )
}

export default FocusBuilderPage
