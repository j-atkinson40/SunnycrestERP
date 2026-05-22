/**
 * WidgetBuilderPage — WB-4a Studio shell for composed widget authoring.
 *
 * Mounted at `/studio/widget-builder/{slug?}` per the build prompt. No
 * slug → renders a "create new widget" landing card; on click, calls
 * the create endpoint + navigates to `/studio/widget-builder/{new-slug}`.
 *
 * Layout (Area 6 substrate enumeration):
 *   - Top chrome: editable widget name + tier indicator badge + draft
 *     state indicator + Publish button + canvas root flex config
 *     selects (direction / gap_token).
 *   - Left rail: AtomPalette (9 atoms in 2 sections).
 *   - Center: WidgetCanvas (flex-stack WYSIWYG).
 *   - Right rail: placeholder for WB-4b inspector ("Configuration
 *     coming soon").
 *
 * Auto-save: useWidgetAutoSave dispatches PUT /draft on every
 * composition_blob mutation with a 200 ms debounce. Status indicator
 * surfaces saving / saved / dirty / error.
 *
 * Publish: dispatches POST /publish. On success, calls
 * refreshComposedWidgets() so the new widget surfaces in the Focus
 * Builder palette without a page reload. On 422, renders the
 * validation errors in a banner (per Area 5 lock — Phase 1 banner-only;
 * per-atom outline ships in WB-4b).
 *
 * Per-atom inspector controls (8a) deferred to WB-4b; the right rail
 * exposes only a stub.
 */
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core"
import { Loader2, ZapIcon } from "lucide-react"
import { useCallback, useEffect, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"
import type {
  AtomType,
  CompositionBlob,
} from "@/lib/widget-builder/types/composition-blob"
import { refreshComposedWidgets } from "@/lib/widget-builder/runtime/registerComposedWidgets"
import {
  WidgetBuilderApiError,
  widgetBuilderService,
  type WidgetBuilderRecord,
} from "@/bridgeable-admin/services/widget-builder-service"
import { useWidgetAutoSave } from "@/bridgeable-admin/hooks/useWidgetAutoSave"

import { AtomPalette } from "./AtomPalette"
import { VariantSwitcher } from "./VariantSwitcher"
import { WidgetCanvas } from "./WidgetCanvas"
import {
  insertAtomAt,
  makeDefaultAtomNode,
  moveAtomTo,
  setRootDirection,
  setRootGap,
} from "./atom-tree-helpers"
import {
  AtomInspectorDispatch,
  useAtomBindingUpdater,
  useAtomConfigUpdater,
} from "./inspectors/AtomInspectorDispatch"
import { AtomVariantVisibility } from "./inspectors/AtomVariantVisibility"
import { VariantsInspectorSection } from "./inspectors/VariantsInspectorSection"
import { useVariantAuthoring } from "./useVariantAuthoring"
import { ErrorSummary } from "./ErrorSummary"
import { useWidgetValidation } from "@/bridgeable-admin/hooks/useWidgetValidation"


function isDraftDiffersFromPublished(
  draft: CompositionBlob | null,
  published: CompositionBlob | null,
): boolean {
  if (draft === null && published === null) return false
  if (draft === null || published === null) return true
  return JSON.stringify(draft) !== JSON.stringify(published)
}


export default function WidgetBuilderPage() {
  const navigate = useNavigate()
  const { slug: slugParam } = useParams<{ slug?: string }>()
  const slug = slugParam ?? null

  const [record, setRecord] = useState<WidgetBuilderRecord | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [selectedAtomId, setSelectedAtomId] = useState<string | null>(null)
  const [title, setTitle] = useState<string>("")
  const [publishing, setPublishing] = useState(false)
  const [publishError, setPublishError] = useState<{
    message: string
    errors?: string[]
  } | null>(null)
  const [createBusy, setCreateBusy] = useState(false)

  // Load on slug change.
  useEffect(() => {
    let cancelled = false
    if (slug === null) {
      setRecord(null)
      return
    }
    setLoading(true)
    setLoadError(null)
    widgetBuilderService
      .get(slug)
      .then((r) => {
        if (cancelled) return
        setRecord(r)
        setTitle(r.title)
      })
      .catch((e: unknown) => {
        if (cancelled) return
        setLoadError(e instanceof Error ? e.message : String(e))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [slug])

  // Auto-save hook.
  const { draft, setDraft, flush, status, editSessionId } = useWidgetAutoSave({
    slug,
    lastServerSnapshot: record?.composition_blob ?? null,
    title,
    onSaved: (r) => {
      setRecord(r)
    },
  })

  // WB-4b — client-side validation. Memoized off the draft. Defined
  // before handlePublish so the defense-in-depth check has access.
  // WB-8 — supported_surfaces flows into the validation hook to power
  // cross-surface compat warnings + Lock 3a.2/3a.3 enforcement.
  const supportedSurfaces = record?.supported_surfaces
  const validation = useWidgetValidation(draft, supportedSurfaces)

  // WB-8 — variant authoring substrate. State for currentVariantId +
  // CRUD ops composed atop the auto-save setDraft pipeline.
  const variantAuthoring = useVariantAuthoring(draft, setDraft)

  // @dnd-kit sensors per Q-40 (PointerSensor + KeyboardSensor).
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 3 } }),
    useSensor(KeyboardSensor),
  )

  const onDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event
      if (!over || !draft) return
      const activeData = active.data.current as
        | { source?: string; atom_type?: AtomType; atomId?: string }
        | undefined
      const overData = over.data.current as
        | {
            source?: string
            kind?: "insertion" | "container" | "empty"
            parentId?: string
            index?: number
          }
        | undefined
      if (!activeData || !overData) return

      // Case 1: from palette → new atom into canvas.
      if (activeData.source === "palette" && activeData.atom_type) {
        const newNode = makeDefaultAtomNode(activeData.atom_type)
        const parentId = overData.parentId ?? draft.root_atom_id
        const index =
          overData.kind === "container"
            ? // drop-as-last-child of a container
              (draft.atom_tree[parentId]?.children?.length ?? 0)
            : (overData.index ?? 0)
        try {
          const { next } = insertAtomAt(draft, parentId, index, newNode)
          setDraft(next)
        } catch {
          // Silent — malformed container or invalid index.
        }
        return
      }

      // Case 2: drag-to-reorder within canvas.
      if (
        activeData.source === "canvas-atom" &&
        activeData.atomId &&
        overData.parentId !== undefined
      ) {
        const parentId = overData.parentId
        const index =
          overData.kind === "container"
            ? (draft.atom_tree[parentId]?.children?.length ?? 0)
            : (overData.index ?? 0)
        const next = moveAtomTo(draft, activeData.atomId, parentId, index)
        setDraft(next)
      }
    },
    [draft, setDraft],
  )

  const handleCreate = useCallback(async () => {
    setCreateBusy(true)
    try {
      const r = await widgetBuilderService.create({
        title: "Untitled widget",
        tier_scope: "vertical",
      })
      navigate(`/studio/widget-builder/${r.widget_id}`)
    } catch (e: unknown) {
      setLoadError(e instanceof Error ? e.message : String(e))
    } finally {
      setCreateBusy(false)
    }
  }, [navigate])

  const handlePublish = useCallback(async () => {
    if (slug === null) return
    // WB-4b defense-in-depth: even with the disabled state, refuse to
    // dispatch when client-side validation has errors. The button-
    // disable is the primary gate; this is the fallback.
    if (validation.hasErrors) {
      setPublishError({
        message: "Resolve composition errors before publishing.",
        errors: validation.errorList.map(
          (e) => `${e.atom_type}: ${e.message}`,
        ),
      })
      return
    }
    setPublishing(true)
    setPublishError(null)
    try {
      // Flush any pending draft save before publishing.
      await flush()
      const r = await widgetBuilderService.publish(slug)
      setRecord(r)
      // Surface in palette w/o reload.
      void refreshComposedWidgets()
    } catch (e: unknown) {
      if (e instanceof WidgetBuilderApiError && e.status === 422) {
        const detail = e.detail as {
          code?: string
          errors?: string[]
        }
        setPublishError({
          message: "Composition is invalid",
          errors: detail?.errors,
        })
      } else {
        setPublishError({
          message: e instanceof Error ? e.message : String(e),
        })
      }
    } finally {
      setPublishing(false)
    }
  }, [flush, slug, validation])

  // WB-4b — locate handler: select the offending atom + scroll into view.
  const handleLocate = useCallback((atomId: string) => {
    setSelectedAtomId(atomId)
    if (typeof document !== "undefined") {
      const el = document.querySelector(
        `[data-testid="widget-builder-canvas-atom-${atomId}"]`,
      )
      if (el && "scrollIntoView" in el) {
        ;(el as HTMLElement).scrollIntoView({
          behavior: "smooth",
          block: "center",
        })
      }
    }
  }, [])

  // WB-4b — config mutator for the per-atom inspector.
  const updateAtomConfig = useAtomConfigUpdater(draft, setDraft)
  const updateAtomBinding = useAtomBindingUpdater(draft, setDraft)

  // Root flex config bound to the canvas-root container atom.
  const rootNode = draft ? draft.atom_tree[draft.root_atom_id] : null
  const rootDirection =
    (rootNode?.config?.direction as "row" | "column" | undefined) ?? "column"
  const rootGap =
    (rootNode?.config?.gap_token as "sm" | "md" | "lg" | undefined) ?? "sm"

  const setRootDir = useCallback(
    (dir: "row" | "column") => {
      if (!draft) return
      setDraft(setRootDirection(draft, dir))
    },
    [draft, setDraft],
  )
  const setRootGapValue = useCallback(
    (gap: "sm" | "md" | "lg") => {
      if (!draft) return
      setDraft(setRootGap(draft, gap))
    },
    [draft, setDraft],
  )

  const draftDiffers = isDraftDiffersFromPublished(
    draft,
    record?.published_composition_blob ?? null,
  )

  // Landing — no slug.
  if (slug === null) {
    return (
      <div
        data-testid="widget-builder-landing"
        className="flex h-full flex-col items-center justify-center gap-4 p-12"
      >
        <h1 className="text-h2 text-content-strong">Widget Builder</h1>
        <p className="text-body text-content-muted max-w-md text-center">
          Compose widgets from atomic pieces. Drop atoms onto the canvas,
          configure each one, and publish when ready.
        </p>
        <Button
          data-testid="widget-builder-new-widget-button"
          onClick={handleCreate}
          disabled={createBusy}
        >
          {createBusy ? (
            <Loader2 size={16} className="animate-spin mr-2" />
          ) : null}
          + New Widget
        </Button>
        {loadError && (
          <div className="text-status-error text-body-sm">{loadError}</div>
        )}
      </div>
    )
  }

  if (loading || !record || !draft) {
    return (
      <div
        data-testid="widget-builder-loading"
        className="flex h-full items-center justify-center"
      >
        <Loader2 size={20} className="animate-spin text-content-muted" />
      </div>
    )
  }

  return (
    <DndContext sensors={sensors} onDragEnd={onDragEnd}>
      <div
        data-testid="widget-builder-page"
        className="flex h-full flex-col bg-surface-base"
      >
        {/* Top chrome */}
        <div
          data-testid="widget-builder-topbar"
          className="flex items-center gap-3 border-b border-border-subtle bg-surface-raised px-4 py-2"
        >
          <Input
            data-testid="widget-builder-title-input"
            value={title}
            placeholder="Untitled widget"
            onChange={(e) => setTitle(e.target.value)}
            onBlur={() => {
              // Title rides on the next draft save automatically via
              // the hook's titleRef; nudge a save.
              if (draft) setDraft(draft)
            }}
            className="max-w-xs"
          />
          <Badge
            data-testid="widget-builder-tier-indicator"
            variant="secondary"
          >
            {record.tier_scope === "platform" ? "Platform" : "Vertical"}
          </Badge>
          <div
            data-testid="widget-builder-save-status"
            data-status={status}
            className={cn(
              "flex items-center gap-1 text-caption",
              status === "error"
                ? "text-status-error"
                : "text-content-muted",
            )}
          >
            {status === "saving" && (
              <>
                <Loader2 size={12} className="animate-spin" />
                Saving…
              </>
            )}
            {status === "saved" && (draftDiffers ? "Draft (unpublished)" : "Saved")}
            {status === "dirty" && "Editing…"}
            {status === "idle" &&
              (draftDiffers ? "Draft (unpublished)" : "Saved")}
            {status === "error" && "Save failed"}
          </div>
          <div className="flex-1" />

          {/* Canvas root flex config */}
          <div
            data-testid="widget-builder-root-flex-config"
            className="flex items-center gap-2"
          >
            <span className="text-caption text-content-muted">Direction</span>
            <Select
              value={rootDirection}
              onValueChange={(v) => setRootDir(v as "row" | "column")}
            >
              <SelectTrigger
                data-testid="widget-builder-root-direction"
                className="w-28"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="column">Column</SelectItem>
                <SelectItem value="row">Row</SelectItem>
              </SelectContent>
            </Select>
            <span className="text-caption text-content-muted">Gap</span>
            <Select
              value={rootGap}
              onValueChange={(v) => setRootGapValue(v as "sm" | "md" | "lg")}
            >
              <SelectTrigger
                data-testid="widget-builder-root-gap"
                className="w-20"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="sm">Sm</SelectItem>
                <SelectItem value="md">Md</SelectItem>
                <SelectItem value="lg">Lg</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <VariantSwitcher
            blob={draft}
            currentVariantId={variantAuthoring.currentVariantId}
            onChange={variantAuthoring.setCurrentVariantId}
          />

          <ErrorSummary validation={validation} onLocate={handleLocate} />

          <Button
            data-testid="widget-builder-publish-button"
            onClick={handlePublish}
            disabled={publishing || validation.hasErrors}
            data-validation-blocked={validation.hasErrors ? "true" : "false"}
            title={
              validation.hasErrors
                ? `Resolve ${validation.errorList.length} error(s) before publishing`
                : undefined
            }
          >
            {publishing ? (
              <Loader2 size={16} className="animate-spin mr-2" />
            ) : (
              <ZapIcon size={16} className="mr-2" />
            )}
            Publish
          </Button>
        </div>

        {/* Publish error banner */}
        {publishError && (
          <div
            data-testid="widget-builder-publish-error"
            role="alert"
            className="border-b border-status-error/30 bg-status-error-muted px-4 py-2 text-body-sm text-status-error"
          >
            <div className="font-medium">{publishError.message}</div>
            {publishError.errors && publishError.errors.length > 0 && (
              <ul className="mt-1 list-disc pl-5">
                {publishError.errors.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* Three-pane body */}
        <div className="flex flex-1 overflow-hidden">
          <AtomPalette />
          <main
            data-testid="widget-builder-canvas-region"
            className="flex-1 overflow-auto p-6"
          >
            <WidgetCanvas
              blob={draft}
              selectedAtomId={selectedAtomId}
              onSelect={setSelectedAtomId}
              errorsByAtom={validation.errorsByAtom}
              currentVariantId={variantAuthoring.currentVariantId}
            />
          </main>
          <aside
            data-testid="widget-builder-inspector"
            data-edit-session={editSessionId.slice(0, 8)}
            className="w-72 overflow-auto border-l border-border-subtle bg-surface-sunken p-4"
          >
            <div className="mb-3 text-caption font-medium uppercase tracking-wide text-content-muted">
              Inspector
            </div>
            {/* WB-8 — Variants section lives at the top of the inspector
                rail and is visible regardless of atom selection (per
                Lock 2a.6). When an atom is selected, the per-atom
                visibility chip-toggle group sits below the per-atom
                inspector. */}
            <VariantsInspectorSection
              blob={draft}
              variantAuthoring={variantAuthoring}
              variantWarnings={validation.variantWarnings}
              variantErrors={validation.variantErrors}
            />
            <AtomInspectorDispatch
              blob={draft}
              selectedAtomId={selectedAtomId}
              onUpdateConfig={updateAtomConfig}
              onUpdateBinding={updateAtomBinding}
              errors={validation.errorsByAtom}
            />
            {selectedAtomId && selectedAtomId !== draft.root_atom_id ? (
              <AtomVariantVisibility
                blob={draft}
                atomId={selectedAtomId}
                variantAuthoring={variantAuthoring}
              />
            ) : null}
          </aside>
        </div>
      </div>
    </DndContext>
  )
}
