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
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
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
} from "./FocusBuilderCanvas"
import { getFreeFormDefaultDimensions } from "@/lib/visual-editor/registry"
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
  const { selection, setSelection } = useFocusBuilderSelection()
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
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    }),
  )
  const [activeDragLabel, setActiveDragLabel] = React.useState<string | null>(
    null,
  )

  const handleDragStart = React.useCallback((e: DragStartEvent) => {
    const id = String(e.active.id ?? "")
    const slug = paletteItemIdToSlug(id)
    setActiveDragLabel(slug ?? id)
  }, [])

  const handleDragEnd = React.useCallback(
    (e: DragEndEvent) => {
      setActiveDragLabel(null)
      const { active, over } = e
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
    [mode, templateHook, setSelection],
  )

  const handleDragCancel = React.useCallback(() => {
    setActiveDragLabel(null)
  }, [])

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
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
