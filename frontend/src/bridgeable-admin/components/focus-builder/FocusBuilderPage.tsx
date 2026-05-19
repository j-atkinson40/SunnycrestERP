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
import { Circle } from "lucide-react"
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
import { BASE_TOKENS } from "@/lib/visual-editor/themes/base-tokens"
import { InheritedCoreInspectorPanel } from "@/bridgeable-admin/components/visual-editor/InheritedCoreInspectorPanel"

import FocusBuilderTree, {
  type FocusBuilderSubject,
} from "./FocusBuilderTree"
import { FocusBuilderCanvas, CANVAS_DROP_ZONE_ID } from "./FocusBuilderCanvas"
import { FocusBuilderRightRail } from "./FocusBuilderRightRail"
import {
  FocusBuilderSelectionProvider,
  useFocusBuilderSelection,
} from "./FocusBuilderSelectionContext"
import { paletteItemIdToSlug } from "./FocusBuilderPalette"


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


function relativeTime(when: Date | null): string {
  if (!when) return ""
  const secs = Math.max(0, Math.round((Date.now() - when.getTime()) / 1000))
  if (secs < 5) return "just now"
  if (secs < 60) return `${secs}s ago`
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  return `${hrs}h ago`
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
  const templateHook = useFocusTemplateDraft(templateSubjectId)

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
  const lastSavedAt =
    mode === "core"
      ? coreHook.lastSavedAt
      : mode === "template"
        ? templateHook.lastSavedAt
        : null

  // Force-refresh "Auto-saved Xs ago" every 5 seconds.
  const [, force] = React.useReducer((n: number) => n + 1, 0)
  React.useEffect(() => {
    if (!lastSavedAt) return
    const id = setInterval(force, 5000)
    return () => clearInterval(id)
  }, [lastSavedAt])

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
        <div className="flex flex-1 items-center justify-end gap-2">
          {isDirty && (
            <span
              data-testid="dirty-indicator"
              className="flex items-center gap-1.5 text-[11px] text-[color:var(--accent)]"
              aria-label="Unsaved changes"
            >
              <Circle className="h-2 w-2 fill-[color:var(--accent)] text-[color:var(--accent)]" />
              Unsaved
            </span>
          )}
          {!isDirty && lastSavedAt && (
            <span
              data-testid="last-saved-indicator"
              className="text-[11px] text-[color:var(--content-muted)]"
            >
              Auto-saved {relativeTime(lastSavedAt)}
            </span>
          )}
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
