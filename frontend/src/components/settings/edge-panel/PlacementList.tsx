/**
 * R-5.1 — PlacementList: per-row placement editor for the
 * `/settings/edge-panel` settings page.
 *
 * Renders the effective placements in a row (tenant placements +
 * user-added `additional_placements` filtered to this row, with
 * `hidden_placement_ids` applied + `placement_order` honored). Each
 * placement carries an ownership badge — "From admin" for tenant,
 * "Personal" for user-added. Per-placement actions:
 *   - Tenant placement → "Hide" (writes to `hidden_placement_ids`)
 *     OR "Show" if already hidden (in-place strikethrough render)
 *   - Personal placement → "Edit" + "Delete" (mutates
 *     `additional_placements`)
 *
 * Reorder via simple drag-handle (HTML5 native dragstart/dragover/
 * drop). Drop emits `onReorder(orderedIds)` with the post-drop
 * placement_id sequence.
 */
import { useMemo, useState } from "react"
import {
  Eye,
  EyeOff,
  GripVertical,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { getByName } from "@/lib/visual-editor/registry"
import type { Placement } from "@/lib/visual-editor/compositions/types"


export interface PlacementListProps {
  rowIndex: number
  /** Tenant-default placements in this row (from the resolved
   *  composition's tenant default — not yet filtered for hidden). */
  tenantPlacements: Placement[]
  /** User-added placements that target this row_index. Already
   *  filtered upstream. */
  additionalPlacements: Placement[]
  hiddenIds: string[]
  /** When provided, `[orderId1, orderId2, ...]` ordering for
   *  placements in this row. */
  placementOrder: string[] | null
  onToggleHide: (placementId: string) => void
  onDeletePersonal: (placementId: string) => void
  /** Open inline edit form for a personal placement. The page
   *  editor handles the form; this component just emits the
   *  intent. */
  onEditPersonal?: (placement: Placement) => void
  /** Trigger to open the ButtonPicker scoped to this row. */
  onAddPlacement: () => void
  /** Emit the post-drop ordering of placement_ids. */
  onReorder: (orderedIds: string[]) => void
}


function placementDisplayName(p: Placement): string {
  if (p.component_kind === "button") {
    const entry = getByName("button", p.component_name)
    if (entry) return entry.metadata.displayName
  }
  if (p.component_kind === "edge-panel-label") {
    const text = (p.prop_overrides?.text as string) ?? ""
    return text || "Group separator"
  }
  if (p.component_kind === "edge-panel-divider") return "Divider"
  return p.component_name
}


function placementLabelOverride(p: Placement): string | null {
  const override = p.prop_overrides?.label
  return typeof override === "string" && override.length > 0 ? override : null
}


export function PlacementList({
  rowIndex,
  tenantPlacements,
  additionalPlacements,
  hiddenIds,
  placementOrder,
  onToggleHide,
  onDeletePersonal,
  onEditPersonal,
  onAddPlacement,
  onReorder,
}: PlacementListProps) {
  const hiddenSet = useMemo(() => new Set(hiddenIds), [hiddenIds])

  /** Compute the effective merged placements in display order. We
   *  preserve tenant placements (with their hidden state) so the
   *  user can un-hide. Personal placements are appended after
   *  tenant placements, then placement_order reorders both classes
   *  together. */
  const mergedDisplay = useMemo(() => {
    const tenant = tenantPlacements.map((p) => ({
      placement: p,
      ownership: "tenant" as const,
      hidden: hiddenSet.has(p.placement_id),
    }))
    const personal = additionalPlacements.map((p) => ({
      placement: p,
      ownership: "personal" as const,
      hidden: false,
    }))
    const all = [...tenant, ...personal]
    if (!placementOrder || placementOrder.length === 0) return all
    const orderIndex = new Map<string, number>()
    placementOrder.forEach((pid, idx) => orderIndex.set(pid, idx))
    const inOrder: typeof all = []
    const remaining: typeof all = []
    for (const entry of all) {
      const found = orderIndex.get(entry.placement.placement_id)
      if (found !== undefined) {
        inOrder.push(entry)
      } else {
        remaining.push(entry)
      }
    }
    inOrder.sort((a, b) => {
      const ai = orderIndex.get(a.placement.placement_id)!
      const bi = orderIndex.get(b.placement.placement_id)!
      return ai - bi
    })
    return [...inOrder, ...remaining]
  }, [tenantPlacements, additionalPlacements, hiddenSet, placementOrder])

  const [draggingId, setDraggingId] = useState<string | null>(null)

  function handleDragStart(pid: string) {
    setDraggingId(pid)
  }

  function handleDragOver(e: React.DragEvent<HTMLLIElement>) {
    e.preventDefault()
  }

  function handleDrop(targetId: string) {
    if (!draggingId || draggingId === targetId) {
      setDraggingId(null)
      return
    }
    const ids = mergedDisplay.map((entry) => entry.placement.placement_id)
    const fromIdx = ids.indexOf(draggingId)
    const toIdx = ids.indexOf(targetId)
    if (fromIdx === -1 || toIdx === -1) {
      setDraggingId(null)
      return
    }
    const [moved] = ids.splice(fromIdx, 1)
    ids.splice(toIdx, 0, moved)
    onReorder(ids)
    setDraggingId(null)
  }

  return (
    <div
      className="flex flex-col gap-2"
      data-testid={`edge-panel-settings-placement-list-row-${rowIndex}`}
    >
      <ul className="flex flex-col gap-1">
        {mergedDisplay.map(({ placement, ownership, hidden }) => {
          const display = placementDisplayName(placement)
          const labelOverride = placementLabelOverride(placement)
          const visibleText = labelOverride ?? display
          return (
            <li
              key={placement.placement_id}
              draggable
              onDragStart={() => handleDragStart(placement.placement_id)}
              onDragOver={handleDragOver}
              onDrop={() => handleDrop(placement.placement_id)}
              data-testid={`edge-panel-settings-placement-${placement.placement_id}`}
              data-ownership={ownership}
              data-hidden={hidden ? "true" : "false"}
              className="flex items-center gap-2 rounded-md border border-border-subtle bg-surface-elevated p-2"
            >
              <span
                className="cursor-grab text-content-subtle"
                aria-label="Drag to reorder"
              >
                <GripVertical className="h-4 w-4" />
              </span>
              <span
                className={
                  hidden
                    ? "flex-1 text-content-muted line-through"
                    : "flex-1 text-content-strong"
                }
              >
                {visibleText}
              </span>
              {ownership === "tenant" ? (
                <Badge variant="secondary">From admin</Badge>
              ) : (
                <Badge className="bg-accent-subtle text-content-strong border-accent">
                  Personal
                </Badge>
              )}
              {ownership === "tenant" ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onToggleHide(placement.placement_id)}
                  data-testid={`edge-panel-settings-placement-toggle-hide-${placement.placement_id}`}
                  aria-label={hidden ? "Show placement" : "Hide placement"}
                >
                  {hidden ? (
                    <Eye className="h-4 w-4" />
                  ) : (
                    <EyeOff className="h-4 w-4" />
                  )}
                </Button>
              ) : (
                <>
                  {onEditPersonal && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onEditPersonal(placement)}
                      data-testid={`edge-panel-settings-placement-edit-${placement.placement_id}`}
                      aria-label="Edit personal placement"
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onDeletePersonal(placement.placement_id)}
                    data-testid={`edge-panel-settings-placement-delete-${placement.placement_id}`}
                    aria-label="Delete personal placement"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </>
              )}
            </li>
          )
        })}
      </ul>
      <Button
        variant="outline"
        size="sm"
        onClick={onAddPlacement}
        data-testid={`edge-panel-settings-placement-add-row-${rowIndex}`}
        type="button"
      >
        <Plus className="h-4 w-4" /> Add button
      </Button>
    </div>
  )
}
