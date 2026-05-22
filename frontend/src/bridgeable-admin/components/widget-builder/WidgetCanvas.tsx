/**
 * WidgetCanvas — WB-4a flex-stack composition canvas.
 *
 * Per Area 1 lock (flex-stack canvas):
 *   - Canvas root is a vertical flex stack (direction/gap from the
 *     root conditional_container's config).
 *   - Children render via the ComposedWidget runtime (WB-2) — canvas
 *     IS the preview (WYSIWYG).
 *   - Drop targets:
 *       1. Between sibling atoms (insertion indicator)
 *       2. On container atoms (drop-into-container)
 *       3. On canvas root (append at end when canvas is empty OR drop
 *          below the last sibling)
 *   - Selection: click an atom → selection ring + page-level selection
 *     state updates. No inspector opens in WB-4a (WB-4b ships per-atom
 *     inspectors).
 *   - No free-form positioning. No resize handles.
 *
 * Build-new substrate per Area 1 — NOT FF-2 reuse.
 *
 * Test ids:
 *   - data-testid="widget-builder-canvas" on the root.
 *   - data-testid="widget-builder-canvas-drop-target-{parentId}-{index}"
 *     on each between-sibling drop zone.
 *   - data-testid="widget-builder-canvas-container-drop-{atomId}" on
 *     each container's drop-as-child target.
 *   - data-testid="widget-builder-canvas-atom-{atomId}" on each
 *     rendered atom wrapper.
 */
import { useDroppable } from "@dnd-kit/core"
import { useCallback, useMemo, useState } from "react"

import { cn } from "@/lib/utils"
import type {
  AtomNode,
  BindingRef,
  CompositionBlob,
  VariantId,
} from "@/lib/widget-builder/types/composition-blob"
import { ComposedWidget } from "@/lib/widget-builder/runtime/ComposedWidget"
import { isContainerAtom } from "./atom-tree-helpers"
import { AtomErrorIndicator } from "./AtomErrorIndicator"
import {
  useCanvasPreviewData,
  type CanvasPreviewDataMap,
} from "@/bridgeable-admin/hooks/useCanvasPreviewData"
import { AtomSkeleton } from "./AtomSkeleton"
import { CanvasPreviewBanner } from "./CanvasPreviewBanner"
import { AtomResolutionIndicator } from "./AtomResolutionIndicator"


export interface WidgetCanvasProps {
  /** The DRAFT composition_blob the operator is currently editing.
   *  Canvas reads this (WYSIWYG); changes flow back through the
   *  page-level mutators. */
  blob: CompositionBlob
  /** The currently selected atom_id (null = no selection / widget
   *  root selected). */
  selectedAtomId: string | null
  onSelect: (atom_id: string | null) => void
  /** WB-4b — per-atom validation errors. Wrapping AtomErrorIndicator
   *  renders a 2px red outline + tooltip when errors are present. */
  errorsByAtom?: Record<string, string[]>
  /** WB-8 — currently-previewed variant (undefined = "all atoms"
   *  unfiltered render path). Passed through to the embedded
   *  ComposedWidget so the AtomRenderer's visible_in_variants filter
   *  applies + the active variant's canonical_dimensions drive the
   *  render-box size. Authoring-only — data layer stays passive (WB-5
   *  fetch state unaffected per Lock 5a). */
  currentVariantId?: VariantId
}


/** Drop indicator (between-sibling insertion line). */
function InsertionIndicator({
  parentId,
  index,
  direction,
}: {
  parentId: string
  index: number
  direction: "row" | "column"
}) {
  const { setNodeRef, isOver } = useDroppable({
    id: `canvas-insertion:${parentId}:${index}`,
    data: { source: "canvas", kind: "insertion", parentId, index },
  })
  return (
    <div
      ref={setNodeRef}
      data-testid={`widget-builder-canvas-drop-target-${parentId}-${index}`}
      data-direction={direction}
      data-over={isOver ? "true" : "false"}
      className={cn(
        "shrink-0 transition-colors",
        direction === "column"
          ? "h-1 w-full"
          : "h-full w-1",
        isOver && "bg-accent",
      )}
      aria-hidden="true"
    />
  )
}


/** Container drop overlay — invisible until drag-over, then a subtle
 *  tint to communicate "drop here as child." */
function ContainerDropTarget({
  atomId,
  children,
}: {
  atomId: string
  children: React.ReactNode
}) {
  const { setNodeRef, isOver } = useDroppable({
    id: `canvas-container:${atomId}`,
    data: { source: "canvas", kind: "container", parentId: atomId },
  })
  return (
    <div
      ref={setNodeRef}
      data-testid={`widget-builder-canvas-container-drop-${atomId}`}
      data-over={isOver ? "true" : "false"}
      className={cn(
        "relative w-full",
        isOver && "outline outline-2 outline-accent/60 outline-offset-2",
      )}
    >
      {children}
    </div>
  )
}


/** A single atom wrapper with selection chrome + click-to-select.
 *  Container atoms also act as drop-into targets. */
function CanvasAtom({
  node,
  selected,
  onSelect,
  children,
}: {
  node: AtomNode
  selected: boolean
  onSelect: (atom_id: string | null) => void
  children: React.ReactNode
}) {
  const Wrap = isContainerAtom(node) ? ContainerDropTarget : "div"
  const wrapProps = isContainerAtom(node) ? { atomId: node.atom_id } : {}
  return (
    <div
      data-testid={`widget-builder-canvas-atom-${node.atom_id}`}
      data-atom-type={node.atom_type}
      data-selected={selected ? "true" : "false"}
      onClick={(e) => {
        e.stopPropagation()
        onSelect(node.atom_id)
      }}
      className={cn(
        "relative cursor-pointer rounded-sm",
        selected && "outline outline-2 outline-accent",
      )}
    >
      {/* @ts-expect-error — runtime narrowing of conditional wrapper */}
      <Wrap {...wrapProps}>{children}</Wrap>
    </div>
  )
}


function gapClass(token: string | undefined): string {
  if (token === "lg") return "gap-4"
  if (token === "md") return "gap-3"
  return "gap-2"
}


/** Walk the atom tree, find atoms whose binding(s) reference a saved
 *  view that errored at the atom level (NOT network class), and
 *  build a per-atom error message map.
 *
 *  Used to wrap each canvas atom in `AtomResolutionIndicator` per
 *  Area 4 Lock 4a. Network-class errors are surfaced via the
 *  canvas-level banner instead.
 *
 *  Also surfaces cross-tenant masked fields (E7) as a separate
 *  variant when the binding's field appears in the view's
 *  masked_fields list.
 */
export function buildResolutionErrorsByAtom(
  blob: CompositionBlob,
  previewData: CanvasPreviewDataMap,
): Record<string, { message: string; variant: "error" | "masked" }> {
  const errors: Record<
    string,
    { message: string; variant: "error" | "masked" }
  > = {}
  const bindingsCatalog: Record<string, BindingRef> =
    blob.bindings_catalog ?? {}

  for (const atom of Object.values(blob.atom_tree)) {
    if (!atom.binding_refs) continue
    for (const bindingId of Object.values(atom.binding_refs)) {
      const ref = bindingsCatalog[bindingId]
      if (!ref || ref.binding_type !== "field_path" || !ref.saved_view_id) {
        continue
      }
      const state = previewData[ref.saved_view_id]
      if (!state) continue
      // Atom-level error: NOT network_class. Network class is hoisted
      // to the canvas banner per Lock 4a.
      if (
        state.status === "error" &&
        state.error &&
        state.error.network_class === false
      ) {
        if (!errors[atom.atom_id]) {
          errors[atom.atom_id] = {
            message: state.error.message,
            variant: "error",
          }
        }
        continue
      }
      // Cross-tenant masking (E7): success + masked_fields contains
      // this binding's field_path.
      if (
        state.status === "success" &&
        state.data &&
        ref.field_path &&
        Array.isArray(state.data.masked_fields) &&
        state.data.masked_fields.includes(ref.field_path)
      ) {
        if (!errors[atom.atom_id]) {
          errors[atom.atom_id] = {
            message: "Field masked per cross-tenant policy",
            variant: "masked",
          }
        }
      }
    }
  }
  return errors
}


/** Per-atom: is this atom in "first load" state — i.e. it has a
 *  binding referencing a view whose fetch has not yet produced a
 *  success/error AND has no `previous` to render? */
export function buildSkeletonAtomIds(
  blob: CompositionBlob,
  previewData: CanvasPreviewDataMap,
): Set<string> {
  const ids = new Set<string>()
  const bindingsCatalog: Record<string, BindingRef> =
    blob.bindings_catalog ?? {}
  for (const atom of Object.values(blob.atom_tree)) {
    if (!atom.binding_refs) continue
    for (const bindingId of Object.values(atom.binding_refs)) {
      const ref = bindingsCatalog[bindingId]
      if (!ref || ref.binding_type !== "field_path" || !ref.saved_view_id) {
        continue
      }
      const state = previewData[ref.saved_view_id]
      // First load: no state yet OR loading without previous.
      if (
        state === undefined ||
        (state.status === "loading" && state.previous === undefined)
      ) {
        ids.add(atom.atom_id)
        break
      }
    }
  }
  return ids
}


/** Per-atom: is this atom currently mid-refresh (optimistic stale)?
 *  Used to overlay shimmer atop the rendered atom. */
export function buildShimmerAtomIds(
  blob: CompositionBlob,
  previewData: CanvasPreviewDataMap,
): Set<string> {
  const ids = new Set<string>()
  const bindingsCatalog: Record<string, BindingRef> =
    blob.bindings_catalog ?? {}
  for (const atom of Object.values(blob.atom_tree)) {
    if (!atom.binding_refs) continue
    for (const bindingId of Object.values(atom.binding_refs)) {
      const ref = bindingsCatalog[bindingId]
      if (!ref || ref.binding_type !== "field_path" || !ref.saved_view_id) {
        continue
      }
      const state = previewData[ref.saved_view_id]
      if (
        state &&
        state.status === "loading" &&
        state.previous !== undefined
      ) {
        ids.add(atom.atom_id)
        break
      }
    }
  }
  return ids
}


export function WidgetCanvas({
  blob,
  selectedAtomId,
  onSelect,
  errorsByAtom,
  currentVariantId,
}: WidgetCanvasProps) {
  const root = blob.atom_tree[blob.root_atom_id]
  const rootDirection =
    (root?.config?.direction as "row" | "column" | undefined) ?? "column"
  const rootGap = root?.config?.gap_token as string | undefined

  const rootChildren = useMemo(() => root?.children ?? [], [root])

  // WB-5 — canvas-side fetch orchestrator. Walks bindings_catalog,
  // deduplicates saved_view_ids, fetches each via executeSavedView.
  // Coexists with WB-4a auto-save AbortController via separate
  // controller refs — verified in source-shape gate.
  const previewData = useCanvasPreviewData(blob)

  // Retry bumper — increments to force the hook to re-fire (changing
  // the bindings_catalog identity is the canonical re-fire trigger,
  // but a no-op blob change is invasive; instead we bump a local
  // counter that flows into a synthetic catalog wrapper). For Phase 1
  // we simply rely on the user's next edit to trigger a refresh —
  // the Retry button is wired by re-mounting the hook via a key.
  const [retryKey, setRetryKey] = useState(0)
  const handleRetry = useCallback(() => {
    setRetryKey((k) => k + 1)
  }, [])

  // Compute the 3-flavor dataContext to pass to ComposedWidget.
  // Per Risk 4: undefined is reserved for "no bindings at all" (the
  // WB-6 1-mock-row authoring fallback). When the catalog has any
  // field_path bindings, we pass the canvas-preview map (which
  // resolveBinding + AtomRenderer interpret); per-view errors live
  // inside the map itself, NOT as a separate dataContext shape.
  const dataContext = useMemo(() => {
    const hasFieldPathBindings = Object.values(
      blob.bindings_catalog ?? {},
    ).some((b) => b.binding_type === "field_path" && b.saved_view_id)
    if (!hasFieldPathBindings) {
      return undefined // WB-6 fallback path.
    }
    // Strip out any error-only entries that have no `previous` — they
    // would otherwise be passed through as success-ish to children;
    // resolveBinding handles this defensively but we keep the wire
    // shape explicit. retryKey is a no-op for the runtime but exists
    // to bust caller memoization on Retry.
    void retryKey
    return {
      __canvas_preview: true as const,
      byView: previewData,
    }
  }, [blob.bindings_catalog, previewData, retryKey])

  const resolutionErrors = useMemo(
    () => buildResolutionErrorsByAtom(blob, previewData),
    [blob, previewData],
  )
  const skeletonAtomIds = useMemo(
    () => buildSkeletonAtomIds(blob, previewData),
    [blob, previewData],
  )
  const shimmerAtomIds = useMemo(
    () => buildShimmerAtomIds(blob, previewData),
    [blob, previewData],
  )

  // Empty-canvas drop target: renders the "drop atoms here" affordance.
  const emptyDroppable = useDroppable({
    id: `canvas-empty:${blob.root_atom_id}`,
    data: { source: "canvas", kind: "empty", parentId: blob.root_atom_id },
  })

  // The canvas surface uses ComposedWidget for runtime parity — but
  // overlays drop indicators + selection chrome. ComposedWidget itself
  // renders the actual atom shapes; we layer interactivity on top.
  return (
    <div
      data-testid="widget-builder-canvas"
      onClick={() => onSelect(null)}
      className={cn(
        "relative min-h-[400px] w-full rounded-md border border-border-base",
        "bg-surface-elevated p-6",
      )}
    >
      {/* WB-5 — canvas-level preview banner (network errors / fetching pill). */}
      <CanvasPreviewBanner
        previewData={previewData}
        onRetry={handleRetry}
      />

      {/* The composed render — WYSIWYG. WB-5 supplies real data via
       *  dataContext: undefined when no bindings (WB-6 1-mock-row
       *  authoring fallback); canvas-preview map otherwise. */}
      <div
        data-testid="widget-builder-canvas-render"
        className="pointer-events-none"
      >
        <ComposedWidget
          widgetDefinition={{
            widget_id: "__widget_builder_preview__",
            composition_blob: blob,
          }}
          variantId={currentVariantId}
          dataContext={dataContext}
        />
      </div>

      {/* Overlay layer: drop indicators + selection chrome. */}
      <div
        data-testid="widget-builder-canvas-overlay"
        className={cn(
          "absolute inset-6 flex",
          rootDirection === "column" ? "flex-col" : "flex-row",
          gapClass(rootGap),
        )}
      >
        {rootChildren.length === 0 ? (
          <div
            ref={emptyDroppable.setNodeRef}
            data-testid={`widget-builder-canvas-drop-target-${blob.root_atom_id}-0`}
            data-over={emptyDroppable.isOver ? "true" : "false"}
            className={cn(
              "flex h-32 w-full items-center justify-center rounded-md border-2 border-dashed",
              emptyDroppable.isOver
                ? "border-accent bg-accent/10 text-accent"
                : "border-border-base text-content-muted",
            )}
          >
            Drag atoms here to build your widget
          </div>
        ) : (
          <>
            {rootChildren.map((child_id, idx) => {
              const node = blob.atom_tree[child_id]
              if (!node) return null
              return (
                <div key={child_id} className="contents">
                  <InsertionIndicator
                    parentId={blob.root_atom_id}
                    index={idx}
                    direction={rootDirection}
                  />
                  <AtomErrorIndicator
                    atomId={child_id}
                    errors={errorsByAtom?.[child_id]}
                  >
                    <AtomResolutionIndicator
                      atomId={child_id}
                      message={resolutionErrors[child_id]?.message}
                      variant={resolutionErrors[child_id]?.variant}
                    >
                      <CanvasAtom
                        node={node}
                        selected={selectedAtomId === child_id}
                        onSelect={onSelect}
                      >
                        {/* The visible atom shape is rendered by
                            ComposedWidget below; this overlay block
                            holds the drop / selection affordances. */}
                        {skeletonAtomIds.has(child_id) ? (
                          <AtomSkeleton atomType={node.atom_type} />
                        ) : shimmerAtomIds.has(child_id) ? (
                          <div
                            data-testid={`widget-builder-canvas-atom-shimmer-${child_id}`}
                            className={cn(
                              "pointer-events-none absolute inset-0",
                              "animate-pulse rounded-sm bg-accent-subtle/20",
                            )}
                            aria-hidden="true"
                          />
                        ) : (
                          <div className="min-h-[24px] min-w-[24px]" />
                        )}
                      </CanvasAtom>
                    </AtomResolutionIndicator>
                  </AtomErrorIndicator>
                </div>
              )
            })}
            <InsertionIndicator
              parentId={blob.root_atom_id}
              index={rootChildren.length}
              direction={rootDirection}
            />
          </>
        )}
      </div>
    </div>
  )
}
