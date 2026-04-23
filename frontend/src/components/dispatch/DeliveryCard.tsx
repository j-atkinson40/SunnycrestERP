/**
 * DeliveryCard — single kanban card for the Dispatch Monitor.
 *
 * Renders the fields James reads from his Airtable today: family
 * name, cemetery, service time, vault type, funeral home. Plus the
 * Phase B additions — hole-dug indicator + service-type tint +
 * draft/finalized border treatment.
 *
 * Visual spec (per Phase 3b brief):
 *   - Service-type tint via DESIGN_LANGUAGE status-muted tokens:
 *       graveside     → status-success-muted (subtle green)
 *       drop-off      → status-info-muted (subtle blue)
 *       funeral_home  → status-warning-muted (subtle amber)
 *       ancillary/others → no tint (neutral surface-elevated)
 *   - Draft schedule: dashed border (border-dashed)
 *   - Finalized schedule: solid border (default)
 *   - Hole-dug badge top-right:
 *       yes     → check icon on status-success-muted
 *       no      → em-dash on surface-sunken
 *       unknown → question-mark on status-warning-muted
 *       null    → hidden (nobody touched this yet)
 *   - Ancillary badge top-left (when >0 attached): "+N ancillary"
 *     brass-muted pill
 *
 * Card is a drag source via @dnd-kit useDraggable. Parent DndContext
 * handles drop mechanics (lifts to MonitorPage). Clicking the card
 * body (non-drag) opens the QuickEditDialog via parent prop.
 *
 * Real data throughout — shape matches `DeliveryDTO` from
 * `services/dispatch-service.ts`; type_config fields rendered
 * null-safe.
 */

import { useDraggable } from "@dnd-kit/core"
import { CSS } from "@dnd-kit/utilities"
import {
  CheckIcon,
  HelpCircleIcon,
  MinusIcon,
  MapPinIcon,
  BuildingIcon,
  ClockIcon,
} from "lucide-react"

import type {
  DeliveryDTO,
  HoleDugStatus,
} from "@/services/dispatch-service"
import { cn } from "@/lib/utils"


export interface DeliveryCardProps {
  delivery: DeliveryDTO
  /** True when the card's schedule is finalized. Drives border style. */
  scheduleFinalized: boolean
  /** Count of ancillary deliveries attached to this parent delivery.
   *  0 hides the badge. */
  ancillaryCount?: number
  /** Click on card body → open quick-edit. */
  onOpenEdit?: (delivery: DeliveryDTO) => void
  /** Click on ancillary badge → toggle expansion. */
  onToggleAncillary?: (deliveryId: string) => void
  /** Click on hole-dug badge cycles unknown → yes → no → null. */
  onCycleHoleDug?: (delivery: DeliveryDTO, nextStatus: HoleDugStatus) => void
  /** Whether ancillary expanded (inline reveal below the card). */
  ancillaryExpanded?: boolean
  /** ARIA label override for the draggable wrapper. */
  ariaLabel?: string
}


/** Next value in the hole-dug cycle: null → unknown → yes → no → null.
 *  Matches the "three-state + cleared" convention from the brief.
 *  Exported for tests. */
export function nextHoleDugStatus(curr: HoleDugStatus): HoleDugStatus {
  if (curr === null) return "unknown"
  if (curr === "unknown") return "yes"
  if (curr === "yes") return "no"
  return null
}


/** Compose tint classes keyed on service_type. Uses DESIGN_LANGUAGE
 *  status-muted tokens so both modes stay coherent. */
function tintClassesForServiceType(serviceType: string | null | undefined): string {
  switch (serviceType) {
    case "graveside":
      return "bg-status-success-muted/60"
    case "drop-off":
    case "drop_off":
      return "bg-status-info-muted/60"
    case "funeral_home":
    case "church":
      return "bg-status-warning-muted/60"
    default:
      return "bg-surface-elevated"
  }
}


/** Service-type display label (capitalized, human). Graveside =
 *  "Graveside"; church/funeral_home → "FH procession"; ancillary_*
 *  → the descriptive verb. */
function serviceTypeLabel(t: string | null | undefined): string {
  switch (t) {
    case "graveside": return "Graveside"
    case "church": return "Church → cemetery"
    case "funeral_home": return "FH → cemetery"
    case "drop-off":
    case "drop_off": return "Drop-off"
    case "ancillary_pickup": return "Ancillary pickup"
    case "ancillary_drop": return "Ancillary drop"
    case "direct_ship": return "Direct ship"
    default: return t ? t.replace(/_/g, " ") : "—"
  }
}


export function DeliveryCard({
  delivery,
  scheduleFinalized,
  ancillaryCount = 0,
  onOpenEdit,
  onToggleAncillary,
  onCycleHoleDug,
  ancillaryExpanded = false,
  ariaLabel,
}: DeliveryCardProps) {
  const tc = delivery.type_config ?? {}
  const family = (tc.family_name as string | undefined) ?? "—"
  const cemetery = (tc.cemetery_name as string | undefined) ?? "—"
  const city = (tc.cemetery_city as string | undefined) ?? ""
  const fh = (tc.funeral_home_name as string | undefined) ?? "—"
  const time = (tc.service_time as string | undefined) ?? null
  const vaultType = (tc.vault_type as string | undefined) ?? null
  const serviceType = (tc.service_type as string | undefined) ?? null

  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: `delivery:${delivery.id}`,
      data: { deliveryId: delivery.id },
    })

  const dragStyle = transform
    ? { transform: CSS.Translate.toString(transform) }
    : undefined

  const tint = tintClassesForServiceType(serviceType)

  return (
    <div
      ref={setNodeRef}
      data-slot="dispatch-delivery-card"
      data-delivery-id={delivery.id}
      data-service-type={serviceType ?? ""}
      data-hole-dug={delivery.hole_dug_status ?? ""}
      data-schedule-state={scheduleFinalized ? "finalized" : "draft"}
      data-dragging={isDragging ? "true" : "false"}
      style={dragStyle}
      aria-label={ariaLabel ?? `Delivery for the ${family} family`}
      {...attributes}
      {...listeners}
      className={cn(
        // Card chrome — DESIGN_LANGUAGE §6 shadow-level-1 baseline,
        // lifts on hover + drag
        "relative rounded-md border shadow-level-1 transition-shadow duration-quick ease-settle",
        "hover:shadow-level-2",
        isDragging && "shadow-level-2 opacity-90",
        // Border treatment — dashed for draft, solid for finalized
        scheduleFinalized
          ? "border-border-subtle"
          : "border-border-base border-dashed",
        // Service-type tint
        tint,
        // Cursor
        "cursor-grab active:cursor-grabbing",
        // Focus ring
        "focus-ring-brass outline-none",
      )}
      role="button"
      tabIndex={0}
    >
      {/* Top row — ancillary badge (left) + hole-dug badge (right) */}
      <div className="flex items-start justify-between gap-2 px-3 pt-2">
        {ancillaryCount > 0 ? (
          <button
            type="button"
            data-slot="dispatch-ancillary-badge"
            onPointerDown={(e) => e.stopPropagation()}
            onClick={(e) => {
              e.stopPropagation()
              onToggleAncillary?.(delivery.id)
            }}
            className={cn(
              "inline-flex items-center gap-1 rounded-full px-2 py-0.5",
              "text-caption font-medium bg-brass-muted text-content-strong",
              "hover:bg-brass/20 transition-colors duration-quick",
              "focus-ring-brass outline-none cursor-pointer",
            )}
            aria-label={`${ancillaryCount} ancillary ${
              ancillaryCount === 1 ? "item" : "items"
            } attached — click to ${ancillaryExpanded ? "collapse" : "expand"}`}
            aria-expanded={ancillaryExpanded}
          >
            +{ancillaryCount} ancillary
          </button>
        ) : (
          <span aria-hidden />
        )}
        <HoleDugBadge
          status={delivery.hole_dug_status}
          onCycle={
            onCycleHoleDug
              ? () =>
                  onCycleHoleDug(
                    delivery,
                    nextHoleDugStatus(delivery.hole_dug_status),
                  )
              : undefined
          }
        />
      </div>

      {/* Body — clicking opens edit. Separate from wrapper so the
          drag listeners on the wrapper don't conflict with the click
          intent. Children stopPropagation on pointerdown for
          affordances that have their own gesture. */}
      <button
        type="button"
        data-slot="dispatch-card-body"
        onPointerDown={(e) => {
          // Allow the click to fire but suppress drag on a body click.
          // @dnd-kit PointerSensor's default activation distance is
          // set by the parent — without this, a quick click starts
          // drag instead of firing the click handler.
          e.stopPropagation()
        }}
        onClick={(e) => {
          e.stopPropagation()
          onOpenEdit?.(delivery)
        }}
        className={cn(
          "w-full px-3 pb-3 pt-1 text-left",
          "focus-ring-brass outline-none rounded-b-md",
        )}
        aria-label={`Edit ${family} family delivery`}
      >
        {/* Family name — the headline. Plex Serif for gravitas per
            DESIGN_LANGUAGE §4 "decedent names carry weight." */}
        <div
          className={cn(
            "text-body font-medium leading-tight text-content-strong",
            "font-plex-serif",
          )}
        >
          {family}
        </div>

        {/* Service-type label */}
        <div className="mt-0.5 text-caption text-content-muted">
          {serviceTypeLabel(serviceType)}
        </div>

        {/* Time + cemetery + FH — compact rows */}
        <div className="mt-2 space-y-1 text-body-sm text-content-base">
          {time && (
            <div className="flex items-center gap-1.5">
              <ClockIcon
                className="h-3.5 w-3.5 text-content-muted flex-none"
                aria-hidden
              />
              <span>{time}</span>
            </div>
          )}
          <div className="flex items-start gap-1.5">
            <MapPinIcon
              className="h-3.5 w-3.5 text-content-muted flex-none mt-0.5"
              aria-hidden
            />
            <div className="flex-1 min-w-0">
              <div className="truncate">{cemetery}</div>
              {city && (
                <div className="text-caption text-content-muted truncate">
                  {city}
                </div>
              )}
            </div>
          </div>
          <div className="flex items-start gap-1.5">
            <BuildingIcon
              className="h-3.5 w-3.5 text-content-muted flex-none mt-0.5"
              aria-hidden
            />
            <div className="truncate">{fh}</div>
          </div>
        </div>

        {/* Vault type — eyebrow at bottom */}
        {vaultType && (
          <div className="mt-2 text-micro uppercase tracking-wider text-content-muted">
            {vaultType}
          </div>
        )}
      </button>
    </div>
  )
}


function HoleDugBadge({
  status,
  onCycle,
}: {
  status: HoleDugStatus
  onCycle?: () => void
}) {
  if (status === null) {
    // Null state — show a muted placeholder to make the affordance
    // discoverable. Clicking cycles to "unknown" first. If onCycle
    // isn't supplied (read-only contexts), hide entirely.
    if (!onCycle) return <span aria-hidden />
    return (
      <button
        type="button"
        data-slot="dispatch-hole-dug-badge"
        data-status="null"
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => {
          e.stopPropagation()
          onCycle()
        }}
        className={cn(
          "inline-flex h-5 w-5 items-center justify-center rounded-full",
          "text-caption text-content-subtle",
          "border border-dashed border-border-subtle",
          "hover:bg-surface-sunken transition-colors duration-quick",
          "focus-ring-brass outline-none cursor-pointer",
        )}
        aria-label="Hole-dug status not set — click to set"
        title="Hole-dug status not set"
      >
        ?
      </button>
    )
  }

  const config = {
    yes: {
      icon: CheckIcon,
      cls: "bg-status-success-muted text-status-success",
      label: "Hole dug: yes",
    },
    no: {
      icon: MinusIcon,
      cls: "bg-surface-sunken text-content-muted",
      label: "Hole dug: no",
    },
    unknown: {
      icon: HelpCircleIcon,
      cls: "bg-status-warning-muted text-status-warning",
      label: "Hole dug: unknown",
    },
  }[status]

  const Icon = config.icon

  const clickProps = onCycle
    ? {
        onPointerDown: (e: React.PointerEvent) => e.stopPropagation(),
        onClick: (e: React.MouseEvent) => {
          e.stopPropagation()
          onCycle()
        },
      }
    : {}

  return (
    <button
      type="button"
      data-slot="dispatch-hole-dug-badge"
      data-status={status}
      disabled={!onCycle}
      className={cn(
        "inline-flex h-5 w-5 items-center justify-center rounded-full",
        "border border-transparent",
        config.cls,
        onCycle &&
          "hover:ring-1 hover:ring-brass/40 transition-all duration-quick cursor-pointer",
        !onCycle && "cursor-default",
        "focus-ring-brass outline-none",
      )}
      aria-label={`${config.label}${onCycle ? " — click to cycle" : ""}`}
      title={config.label}
      {...clickProps}
    >
      <Icon className="h-3 w-3" aria-hidden />
    </button>
  )
}
