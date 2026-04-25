/**
 * AncillaryPoolPin — Phase B Session 4.3b.3 Canvas widget.
 *
 * Renders pool ancillaries (date-less, unassigned, floating) as a
 * scrollable list of compact draggable rows. Each row is a drag
 * source with `useDraggable({ id: "ancillary:<id>" })` so the
 * elevated DndContext (FocusDndProvider) can route drops:
 *
 *   onto driver lane     → assign_ancillary_standalone
 *   onto Unassigned lane → return_ancillary_to_pool (no-op for pool)
 *   onto parent card     → attach_ancillary
 *
 * Routing logic lives in SchedulingKanbanCore's useDndMonitor
 * listener (commit 4); this component is purely the drag SOURCE.
 *
 * Mount point
 * ───────────
 * Registered with the canvas widget registry under
 * `"funeral-scheduling.ancillary-pool"` via
 * `dispatch/scheduling-focus/register.ts`. The funeral-scheduling
 * Focus's tenantDefault layout (commit 4) seeds the widget at the
 * right-rail anchor, ~260px wide, ~70vh tall. User can drag-
 * reposition via WidgetChrome (existing canvas widget UX).
 *
 * Tier degradation
 * ────────────────
 * Canvas tier  → renders inline as a free-form widget (this surface)
 * Stack tier   → renders as a Smart Stack tile (StackRail's
 *                getWidgetRenderer dispatch)
 * Icon tier    → renders inside BottomSheet's tile grid + tap-to-
 *                expand
 * All three tiers handled by the canonical canvas widget framework
 * (Phase A Sessions 3.7-3.8 + the Phase 4.3b.3 typed-widget
 * registry).
 *
 * Empty state
 * ───────────
 * When pool is empty, render a quiet "No pool items" message — the
 * dispatcher's normal target state (every ancillary either paired
 * or standalone). Loading state during refresh: subdued opacity on
 * the existing list rather than a spinner (per PLATFORM_QUALITY_BAR
 * §1 — no perceptible lag, no spinner where in-flight data isn't
 * blocking).
 *
 * Why not reuse AncillaryCard for the row chrome
 * ──────────────────────────────────────────────
 * AncillaryCard targets driver-lane rendering with `bg-surface-
 * elevated` + `shadow-level-1` + same chrome as DeliveryCard. Pool
 * pin items are denser — visually subordinate to the lane cards
 * since pool is the "waiting" state. Compact list rows (single line
 * with truncation) maximize how many items fit at once. Same
 * type_config.product_summary fallback chain as AncillaryCard for
 * label resolution; sharing that helper would be a future
 * cleanup. For 4.3b.3 the helper inlines.
 */

import { useDraggable, useDroppable } from "@dnd-kit/core"
import { CSS } from "@dnd-kit/utilities"
import { InboxIcon } from "lucide-react"

import { useFocusDndActiveId } from "@/components/focus/FocusDndProvider"
import { useSchedulingFocus } from "@/contexts/scheduling-focus-context"
import { cn } from "@/lib/utils"
import type { DeliveryDTO } from "@/services/dispatch-service"


/** Drop target id for the AncillaryPoolPin. SchedulingKanbanCore's
 *  drag handler routes ancillary drops on this id to
 *  `returnAncillaryToPool`. Exported so tests + handler can share
 *  the canonical string without drift. */
export const ANCILLARY_POOL_DROPPABLE_ID = "ancillary-pool"


// Same fallback chain AncillaryCard uses (Flag 5 from 4.3.3 spec).
// Inlined here for now; a shared helper is a future cleanup.
function resolvePoolItemLabel(d: DeliveryDTO): string {
  const tc = d.type_config ?? {}
  const product = (tc.product_summary as string | undefined) ?? ""
  if (product.trim()) return product
  const vault = (tc.vault_type as string | undefined) ?? ""
  if (vault.trim()) return vault
  const TYPE_LABELS: Record<string, string> = {
    funeral_home_dropoff: "Drop-off",
    funeral_home_pickup: "Pickup",
    supply_delivery: "Supply",
  }
  return TYPE_LABELS[d.delivery_type] ?? d.delivery_type
}


function resolvePoolItemSubhead(d: DeliveryDTO): string {
  const tc = d.type_config ?? {}
  const fh = (tc.funeral_home_name as string | undefined) ?? ""
  const family = (tc.family_name as string | undefined) ?? ""
  // Family OR funeral home — whichever is set. Family is the more
  // specific identifier when present (e.g. "Lombardi" pin item).
  if (family.trim()) return family
  return fh.trim()
}


interface PoolItemProps {
  delivery: DeliveryDTO
}


function PoolItem({ delivery }: PoolItemProps) {
  // Drag source. Same `distance: 8` activation constraint cascades
  // through the elevated DndContext provided by FocusDndProvider —
  // PointerSensor lives at the provider level. Drag id carries the
  // `ancillary:` prefix so SchedulingKanbanCore's drag handler
  // routes correctly (vs `delivery:` for kanban + standalone
  // cards, `widget:` for canvas widgets).
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: `ancillary:${delivery.id}`,
      data: { ancillaryId: delivery.id, source: "pool" },
    })

  const dragStyle = transform
    ? { transform: CSS.Translate.toString(transform) }
    : undefined

  const label = resolvePoolItemLabel(delivery)
  const subhead = resolvePoolItemSubhead(delivery)

  return (
    <div
      ref={setNodeRef}
      style={dragStyle}
      data-slot="ancillary-pool-item"
      data-ancillary-id={delivery.id}
      data-dragging={isDragging ? "true" : "false"}
      {...attributes}
      {...listeners}
      className={cn(
        // Compact row chrome — visually subordinate to lane cards.
        // Single border-bottom separates rows; bg-transparent at rest;
        // hover gets a subtle brass-subtle wash matching the platform's
        // hover convention.
        //
        // Phase 4.3b.3.2 — whole-item drag (no grip handle). Per the
        // platform standard, every draggable surface uses the
        // PointerSensor activation constraint (distance: 8) to
        // separate click from drag. Explicit drag handles clutter UI
        // and confuse the interaction model. This row is a peer of
        // DeliveryCard's drag-from-anywhere pattern (Phase A
        // Session 3.5 for canvas widgets, Phase 4.2.4 for delivery
        // cards). See PRODUCT_PRINCIPLES.md "Drag interactions" for
        // the canonical statement.
        "relative px-3 py-2",
        "border-b border-border-subtle/60 last:border-b-0",
        "transition-colors duration-quick ease-settle",
        "hover:bg-brass-subtle/40 cursor-grab active:cursor-grabbing",
        "focus-ring-brass outline-none",
        // Drag lift per PQB §2 (subtle scale + opacity dim per the
        // canonical drag-source contract).
        isDragging && "opacity-95 scale-[1.02] bg-brass-subtle/60",
      )}
      role="button"
      tabIndex={0}
      aria-label={`${label} — drag to assign or attach`}
    >
      <p
        className={cn(
          "truncate text-body-sm font-medium leading-tight",
          "text-content-strong font-plex-sans",
        )}
        title={label}
      >
        {label}
      </p>
      {subhead && (
        <p
          className={cn(
            "mt-0.5 truncate text-caption leading-tight",
            "text-content-muted font-plex-sans",
          )}
          title={subhead}
        >
          {subhead}
        </p>
      )}
    </div>
  )
}


export interface AncillaryPoolPinProps {
  /** Stable widget id from WidgetState (provided by the canvas
   *  framework's getWidgetRenderer dispatch). Currently unused —
   *  there's only one pool pin per Focus today — but matches the
   *  WidgetRendererProps contract for future per-widget telemetry /
   *  state-keying. */
  widgetId?: string
}


export function AncillaryPoolPin(_props: AncillaryPoolPinProps) {
  // Read pool data from the Focus-level provider. useSchedulingFocus
  // throws if mounted outside the provider — that's the contract:
  // this widget is only valid inside the funeral-scheduling Focus.
  const { poolAncillaries, poolLoading } = useSchedulingFocus()

  // Phase 4.3b.4 — pin becomes a drop target for return-to-pool.
  // Drag flows that drop here:
  //   - Standalone ancillary in a driver lane → returnAncillaryToPool
  //   - Attached ancillary from drawer expansion → returnAncillaryToPool
  //   - Pool item from this same pin → no-op (already in pool)
  // SchedulingKanbanCore's onDragEnd handler routes by `over.id ===
  // ANCILLARY_POOL_DROPPABLE_ID`. Visual feedback below mirrors the
  // delivery-as-parent droppable pattern: brass dashed outline +
  // brass-subtle wash, gated on active drag being an ancillary
  // (delivery: + widget: drags don't trigger pin feedback).
  const { setNodeRef: setDropRef, isOver } = useDroppable({
    id: ANCILLARY_POOL_DROPPABLE_ID,
  })
  const activeDragId = useFocusDndActiveId()
  const isAncillaryDragActive = activeDragId?.startsWith("ancillary:") ?? false
  // The pin is its own source of items, so a pool→pool drop should
  // NOT light up — feedback only when the dragged ancillary is NOT
  // currently in the pool list (standalone or attached).
  const draggedIsFromPool =
    activeDragId !== null &&
    poolAncillaries.some(
      (d) => d.id === activeDragId.replace(/^ancillary:/, ""),
    )
  const showPoolDropFeedback =
    isOver && isAncillaryDragActive && !draggedIsFromPool

  return (
    <div
      ref={setDropRef}
      data-slot="ancillary-pool-pin"
      data-pool-drop-target={showPoolDropFeedback ? "true" : "false"}
      className={cn(
        "flex h-full flex-col bg-surface-elevated",
        // Subtle dim during refresh — keeps the existing list visible
        // but signals data is in flight.
        poolLoading && "opacity-80",
        // Phase 4.3b.4 — drop-target visual feedback. Brass dashed
        // outline + brass-subtle wash matching DeliveryCard's parent-
        // drop pattern (Phase 4.3b.3) for consistency across all
        // ancillary drop surfaces (lane = solid brass ring;
        // parent card = dashed brass ring; pin = dashed brass
        // ring). Same DESIGN_LANGUAGE §6 brass family across the
        // platform's ancillary-drag affordances.
        showPoolDropFeedback && [
          "ring-2 ring-brass ring-dashed ring-offset-2 ring-offset-surface-base",
          "bg-brass-subtle/40",
        ],
        "transition-shadow duration-quick ease-settle",
      )}
    >
      {/* Header — eyebrow + count badge. Matches DESIGN_LANGUAGE §4
          eyebrow treatment: text-micro uppercase tracking-wider
          text-content-muted. Count chip styling parallels the chat
          unread chip from _shared.tsx IconTooltip badge. */}
      <div
        data-slot="ancillary-pool-pin-header"
        className={cn(
          "flex items-baseline justify-between gap-2",
          "border-b border-border-subtle px-3 py-2",
        )}
      >
        <div>
          <p
            className={cn(
              "text-micro uppercase tracking-wider",
              "text-content-muted font-plex-sans",
            )}
          >
            Ancillary pool
          </p>
          <h3
            className={cn(
              "mt-0.5 text-body-sm font-medium leading-tight",
              "text-content-strong font-plex-sans",
            )}
          >
            Waiting for pairing
          </h3>
        </div>
        {poolAncillaries.length > 0 && (
          <span
            data-slot="ancillary-pool-pin-count"
            className={cn(
              "inline-flex items-center justify-center",
              "min-w-[20px] h-5 px-1.5 rounded-full",
              "bg-brass text-content-on-brass text-caption font-medium",
              "font-plex-mono tabular-nums",
            )}
            aria-label={`${poolAncillaries.length} pool ${
              poolAncillaries.length === 1 ? "item" : "items"
            }`}
          >
            {poolAncillaries.length}
          </span>
        )}
      </div>

      {/* List body — scrollable when overflow. Empty state when no
          pool items. */}
      <div
        data-slot="ancillary-pool-pin-list"
        className="flex-1 overflow-y-auto"
      >
        {poolAncillaries.length === 0 && !poolLoading && (
          <div
            data-slot="ancillary-pool-pin-empty"
            className={cn(
              "flex h-full flex-col items-center justify-center gap-2",
              "px-4 py-6 text-center",
            )}
          >
            <InboxIcon
              className="h-6 w-6 text-content-subtle"
              aria-hidden
            />
            <p
              className={cn(
                "text-caption text-content-muted font-plex-sans",
                "leading-tight",
              )}
            >
              {showPoolDropFeedback ? "Drop to return to pool" : "No pool items"}
            </p>
            <p
              className={cn(
                "text-micro text-content-subtle font-plex-sans",
                "leading-tight",
              )}
            >
              {showPoolDropFeedback
                ? "Releases driver + date assignment."
                : "Pair complete — every ancillary is assigned."}
            </p>
          </div>
        )}
        {poolAncillaries.map((d) => (
          <PoolItem key={d.id} delivery={d} />
        ))}
      </div>
    </div>
  )
}
