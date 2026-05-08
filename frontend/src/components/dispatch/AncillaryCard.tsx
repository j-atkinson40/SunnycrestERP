/**
 * AncillaryCard — compact card for STANDALONE ancillary deliveries.
 *
 * Phase 4.3.3 commit 2. Renders inside Scheduling Focus driver
 * lanes alongside primary `DeliveryCard`s. PRODUCT_PRINCIPLES
 * §Domain-Specific Operational Semantics (post-4.3.3 amendment):
 * standalone ancillaries are independent stops on a driver's day —
 * not paired with a primary delivery, but assigned to a driver +
 * date. Rendering them in the lane shows dispatchers the FULL set of
 * stops a driver has, not just the kanban primaries.
 *
 * Field set is intentionally smaller than DeliveryCard:
 *   - **Headline**: product / type (`type_config.product_summary` →
 *     fallback `type_config.vault_type` → fallback delivery_type
 *     label). Per Phase 4.3.3 Flag 5: the product IS the type from
 *     dispatcher's scan-speed perspective.
 *   - **Subhead**: destination funeral home (`funeral_home_name`),
 *     optionally followed by city (`cemetery_city` is sometimes
 *     populated even on ancillaries — it's the geographic anchor
 *     for pairing decisions).
 *   - **Status row**: only the note icon (driver_note). No family,
 *     no section, no chat, no hole-dug, no equipment. Ancillaries
 *     are simpler operations — fewer scan-speed signals matter.
 *
 * Visual hierarchy vs. DeliveryCard (DL §5 + §6):
 *   - Same chrome tokens — `bg-surface-elevated`, `shadow-level-1`,
 *     `rounded-md`, NO perimeter border (DL §6 canon).
 *   - Tighter padding: `px-2.5 py-1.5` body + `px-2.5 py-1` icon-row
 *     (matches DeliveryCard's compact density).
 *   - Smaller height: 2 text lines + status row vs DeliveryCard's
 *     4 lines + status row → ~half the vertical footprint.
 *   - Text scale: headline `text-body-sm font-medium`; subhead
 *     `text-caption text-content-muted`. Same scale family as
 *     DeliveryCard's compact mode.
 *
 * Drag behavior: identical to DeliveryCard per PQB §5 Consistency
 * — same `useDraggable`, same drag-id format with `delivery:`
 * prefix so SchedulingKanbanCore's onDragEnd handler treats
 * ancillaries and primaries uniformly. PointerSensor activation
 * constraint distance:8 (configured at the DndContext level)
 * separates click (open edit) from drag (reassign).
 *
 * Click behavior: short click → onOpenEdit (opens QuickEditDialog
 * for the ancillary). The QuickEditDialog already handles
 * scheduling_type='ancillary' rows correctly — same field set, just
 * fewer fields are meaningful.
 */

import { useDraggable } from "@dnd-kit/core"
import { CSS } from "@dnd-kit/utilities"

import type { DeliveryDTO } from "@/services/dispatch-service"
import { cn } from "@/lib/utils"

// R-2.1 — sub-section wrapped components imported from the registrations
// barrel. Each emits a data-component-name boundary div for click-to-
// edit resolution.
import {
  AncillaryCardHeader,
  AncillaryCardBody,
  AncillaryCardActions,
} from "@/lib/visual-editor/registry/registrations/entity-card-sections"


export interface AncillaryCardProps {
  /** The ancillary delivery (scheduling_type='ancillary'). */
  delivery: DeliveryDTO
  /** Click on card body → open quick-edit dialog. */
  onOpenEdit?: (delivery: DeliveryDTO) => void
  /** ARIA-label override; default is product-based. */
  ariaLabel?: string
}


/** Resolve the ancillary's display label.
 *
 *  Headline priority (Phase 4.3.3 Flag 5):
 *    1. type_config.product_summary  (e.g. "Urn vault (extra)")
 *    2. type_config.vault_type        (e.g. "Cameo Rose")
 *    3. delivery_type translated      (e.g. "Drop-off" for
 *       funeral_home_dropoff, "Pickup" for funeral_home_pickup,
 *       "Supply" for supply_delivery)
 *    4. raw delivery_type             (last-resort fallback)
 */
function resolveAncillaryLabel(d: DeliveryDTO): string {
  const tc = d.type_config ?? {}
  const product = (tc.product_summary as string | undefined) ?? ""
  if (product.trim()) return product
  const vault = (tc.vault_type as string | undefined) ?? ""
  if (vault.trim()) return vault
  // Map known ancillary delivery_types to friendly labels
  const TYPE_LABELS: Record<string, string> = {
    funeral_home_dropoff: "Drop-off",
    funeral_home_pickup: "Pickup",
    supply_delivery: "Supply",
  }
  return TYPE_LABELS[d.delivery_type] ?? d.delivery_type
}


/** R-2.0 — exported as `AncillaryCardRaw`; the wrapped version
 *  (carrying `data-component-name="ancillary-card"` for runtime-editor
 *  click-to-edit) is the default export from
 *  `@/lib/visual-editor/registry/registrations/entity-cards`. The raw
 *  reference stays exported so the registration shim can wrap it; new
 *  call sites should import the wrapped `AncillaryCard` from the
 *  registrations barrel. */
export function AncillaryCardRaw({
  delivery,
  onOpenEdit,
  ariaLabel,
}: AncillaryCardProps) {
  const tc = delivery.type_config ?? {}
  const fh = (tc.funeral_home_name as string | undefined) ?? "—"
  const city = (tc.cemetery_city as string | undefined) ?? ""
  const driverNote = (tc.driver_note as string | undefined) ?? ""
  // special_instructions is a top-level field, not type_config.
  const note = driverNote || delivery.special_instructions || ""
  const label = resolveAncillaryLabel(delivery)

  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: `delivery:${delivery.id}`,
      data: { deliveryId: delivery.id },
    })

  const dragStyle = transform
    ? { transform: CSS.Translate.toString(transform) }
    : undefined

  return (
    <div
      ref={setNodeRef}
      data-slot="dispatch-ancillary-card"
      data-delivery-id={delivery.id}
      data-dragging={isDragging ? "true" : "false"}
      style={dragStyle}
      aria-label={ariaLabel ?? `Ancillary: ${label}`}
      {...attributes}
      {...listeners}
      className={cn(
        // Chrome — DL §6 canonical level-1 card. Same tokens as
        // DeliveryCard so primary + ancillary read as siblings;
        // visual hierarchy comes from CONTENT density, not chrome.
        "relative rounded-md bg-surface-elevated shadow-level-1",
        "transition-shadow duration-settle ease-settle hover:shadow-level-2",
        // Drag lift per PQB §2 (same physics as DeliveryCard).
        isDragging && "shadow-level-2 opacity-95 scale-[1.02]",
        "cursor-grab active:cursor-grabbing",
        "focus-ring-accent outline-none",
      )}
      role="button"
      tabIndex={0}
    >
      <button
        type="button"
        data-slot="dispatch-ancillary-card-body"
        onClick={(e) => {
          e.stopPropagation()
          onOpenEdit?.(delivery)
        }}
        className={cn(
          "block w-full text-left",
          // Tighter than DeliveryCard's compact — ancillary has 2 lines.
          "px-2.5 py-1.5",
          "focus-ring-accent outline-none rounded-md",
        )}
        aria-label={`Edit ${label} ancillary`}
      >
        {/* R-2.1 — header sub-section (product label headline). */}
        <AncillaryCardHeader label={label} />

        {/* R-2.1 — body sub-section (destination FH + city). */}
        <AncillaryCardBody fh={fh} city={city} />
      </button>

      {/* R-2.1 — actions sub-section (optional icon row). Self-collapses
          when no note + no buttonSlugs configured. */}
      <AncillaryCardActions note={note} />
    </div>
  )
}
