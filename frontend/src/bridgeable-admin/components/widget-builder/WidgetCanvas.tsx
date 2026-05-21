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
import { useMemo } from "react"

import { cn } from "@/lib/utils"
import type {
  AtomNode,
  CompositionBlob,
} from "@/lib/widget-builder/types/composition-blob"
import { ComposedWidget } from "@/lib/widget-builder/runtime/ComposedWidget"
import { isContainerAtom } from "./atom-tree-helpers"


export interface WidgetCanvasProps {
  /** The DRAFT composition_blob the operator is currently editing.
   *  Canvas reads this (WYSIWYG); changes flow back through the
   *  page-level mutators. */
  blob: CompositionBlob
  /** The currently selected atom_id (null = no selection / widget
   *  root selected). */
  selectedAtomId: string | null
  onSelect: (atom_id: string | null) => void
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


export function WidgetCanvas({
  blob,
  selectedAtomId,
  onSelect,
}: WidgetCanvasProps) {
  const root = blob.atom_tree[blob.root_atom_id]
  const rootDirection =
    (root?.config?.direction as "row" | "column" | undefined) ?? "column"
  const rootGap = root?.config?.gap_token as string | undefined

  const rootChildren = useMemo(() => root?.children ?? [], [root])

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
      {/* The composed render — WYSIWYG. */}
      <div
        data-testid="widget-builder-canvas-render"
        className="pointer-events-none"
      >
        <ComposedWidget
          widgetDefinition={{
            widget_id: "__widget_builder_preview__",
            composition_blob: blob,
          }}
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
                  <CanvasAtom
                    node={node}
                    selected={selectedAtomId === child_id}
                    onSelect={onSelect}
                  >
                    {/* The visible atom shape is rendered by
                        ComposedWidget below; this overlay block holds
                        the drop / selection affordances. */}
                    <div className="min-h-[24px] min-w-[24px]" />
                  </CanvasAtom>
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
