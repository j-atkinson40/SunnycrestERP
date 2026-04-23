/**
 * DeliveryCard — single kanban card for the Dispatch Monitor.
 *
 * Phase 3.1 + 3.2 rebuild (2026-04-23, per James' operational
 * feedback on Phase 3). What changed from Phase 3:
 *   - Service-type color tints REMOVED. Dispatchers prioritize
 *     equipment context over service type as a visual cue.
 *   - Hole-dug is three-state non-nullable (unknown | yes | no).
 *     Cycles unknown → yes → no → unknown. Migration r50 backfilled
 *     all NULLs to 'unknown' + made the column NOT NULL.
 *   - Hole-dug + ancillary collapsed into a single status-indicator
 *     row. Same visual weight; both are the "what state is this in?"
 *     signal bank at the bottom of the card.
 *   - Primary text hierarchy (James' dispatcher mental model):
 *       1. Funeral home name (headline — identifies the job)
 *       2. Cemetery · City
 *       3. Service time · location · ETA  (e.g. "11:00 Church · ETA 12:00")
 *       4. Vault type · equipment hint
 *   - Secondary info compacted into an icon+tooltip row at the
 *     bottom: family name (User), driver note (StickyNote), chat
 *     activity (MessageCircle), cemetery section (MapPin) — each
 *     hidden when its data is empty. Hover / focus / tap-and-hold
 *     reveals the tooltip with the actual text.
 *   - Card target ~100-120px tall (down from ~180px in Phase 3).
 *   - Service-time + ETA ordering FIX (per user correction):
 *     service time first (anchor — that's when the service starts),
 *     ETA second (when driver arrives at cemetery after service
 *     ends). Matches "church at 11, graveside by 12" mental model.
 *
 * Card is a drag source via @dnd-kit useDraggable. Parent DndContext
 * (MonitorPage) handles drop. Clicking the card body (non-drag)
 * opens the QuickEditDialog via parent prop.
 *
 * Data throughout — shape matches `DeliveryDTO` from
 * `services/dispatch-service.ts`; type_config fields rendered
 * null-safe.
 */

import { useDraggable } from "@dnd-kit/core"
import { CSS } from "@dnd-kit/utilities"
import {
  CheckIcon,
  HelpCircleIcon,
  MessageCircleIcon,
  MinusIcon,
  StickyNoteIcon,
  MapPinIcon,
  UserIcon,
} from "lucide-react"

import type {
  DeliveryDTO,
  HoleDugStatus,
} from "@/services/dispatch-service"
import { cn } from "@/lib/utils"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"


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
  /** Click on hole-dug badge cycles unknown → yes → no → unknown. */
  onCycleHoleDug?: (delivery: DeliveryDTO, nextStatus: HoleDugStatus) => void
  /** Whether ancillary expanded (inline reveal below the card). */
  ancillaryExpanded?: boolean
  /** ARIA label override for the draggable wrapper. */
  ariaLabel?: string
}


/** Next value in the hole-dug three-state cycle: unknown → yes → no →
 *  unknown. Phase 3.1 dropped the null state per operational feedback
 *  (nobody asked for a fourth option). Exported for tests. */
export function nextHoleDugStatus(curr: HoleDugStatus): HoleDugStatus {
  if (curr === "unknown") return "yes"
  if (curr === "yes") return "no"
  // curr === "no"
  return "unknown"
}


/** Short inline label for the service-time line — the SERVICE
 *  LOCATION (where the service takes place, derived from
 *  `type_config.service_type`). Not to be confused with equipment
 *  (that's `type_config.equipment_type`, a separate field).
 *
 *  - Graveside: service happens at the cemetery — no meeting point
 *    to label differently.
 *  - Church / Funeral Home: service starts at a different location;
 *    driver needs to know where.
 *  - Ancillary / direct_ship: not kanban deliveries; no service-time
 *    line rendered (handled by the `timeLine` being empty in the
 *    card render). */
function serviceTimeLocationLabel(t: string | null | undefined): string | null {
  switch (t) {
    case "graveside":     return "Graveside"
    case "church":        return "Church"
    case "funeral_home":  return "Funeral Home"
    default: return null  // ancillary / direct_ship use no time line
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
  const family = (tc.family_name as string | undefined) ?? ""
  const cemetery = (tc.cemetery_name as string | undefined) ?? ""
  const city = (tc.cemetery_city as string | undefined) ?? ""
  const section = (tc.cemetery_section as string | undefined) ?? ""
  const fh = (tc.funeral_home_name as string | undefined) ?? "—"
  const time = (tc.service_time as string | undefined) ?? null
  const eta = (tc.eta as string | undefined) ?? null
  const vaultType = (tc.vault_type as string | undefined) ?? null
  const equipmentType = (tc.equipment_type as string | undefined) ?? null
  const serviceType = (tc.service_type as string | undefined) ?? null
  const driverNote = (tc.driver_note as string | undefined) ?? ""
  const chatCount =
    typeof tc.chat_activity_count === "number" ? tc.chat_activity_count : 0

  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: `delivery:${delivery.id}`,
      data: { deliveryId: delivery.id },
    })

  const dragStyle = transform
    ? { transform: CSS.Translate.toString(transform) }
    : undefined

  // Compose the compact service-time line. Examples (user spec):
  //   "11:00 Graveside"
  //   "11:00 Church · ETA 12:00"
  //   "11:00 Funeral Home · ETA 12:00"
  // Service time FIRST (anchor — when service starts). ETA SECOND
  // (when driver arrives at cemetery AFTER service ends).
  const timeLocLabel = serviceTimeLocationLabel(serviceType)
  const timeLineParts: string[] = []
  if (time) timeLineParts.push(time)
  if (timeLocLabel) timeLineParts.push(timeLocLabel)
  const timeLine = timeLineParts.join(" ")
  const showEta = Boolean(eta) && serviceType !== "graveside"

  return (
    <div
      ref={setNodeRef}
      data-slot="dispatch-delivery-card"
      data-delivery-id={delivery.id}
      data-service-type={serviceType ?? ""}
      data-hole-dug={delivery.hole_dug_status}
      data-schedule-state={scheduleFinalized ? "finalized" : "draft"}
      data-dragging={isDragging ? "true" : "false"}
      style={dragStyle}
      aria-label={ariaLabel ?? `Delivery for the ${family || "unknown"} family`}
      {...attributes}
      {...listeners}
      className={cn(
        // Card chrome — DESIGN_LANGUAGE §6 shadow-level-1 baseline,
        // lifts on hover + drag. Neutral surface; no service-type tint
        // (removed in Phase 3.1).
        "relative rounded-md border bg-surface-elevated shadow-level-1",
        "transition-shadow duration-quick ease-settle hover:shadow-level-2",
        isDragging && "shadow-level-2 opacity-90",
        // Border treatment — dashed for draft, solid for finalized.
        scheduleFinalized
          ? "border-border-subtle"
          : "border-border-base border-dashed",
        "cursor-grab active:cursor-grabbing",
        "focus-ring-brass outline-none",
      )}
      role="button"
      tabIndex={0}
    >
      {/* Body — clickable for edit. Drag listeners sit on the wrapper.
          Inner button's stopPropagation prevents body click from also
          firing a drag-start on the wrapper's pointerdown. */}
      <button
        type="button"
        data-slot="dispatch-card-body"
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => {
          e.stopPropagation()
          onOpenEdit?.(delivery)
        }}
        className={cn(
          "block w-full px-3 py-2 text-left",
          "focus-ring-brass outline-none rounded-md",
        )}
        aria-label={`Edit ${family || "unnamed"} family delivery`}
      >
        {/* Line 1 — funeral home (the headline; identifies the job). */}
        <div
          className={cn(
            "truncate text-body-sm font-medium leading-tight text-content-strong",
            "font-plex-sans",
          )}
          data-slot="dispatch-card-fh"
          title={fh}
        >
          {fh}
        </div>

        {/* Line 2 — cemetery · city */}
        {cemetery && (
          <div
            className="mt-0.5 truncate text-body-sm text-content-base"
            data-slot="dispatch-card-cemetery"
          >
            {cemetery}
            {city && (
              <span className="text-content-muted">
                {" · "}
                {city}
              </span>
            )}
          </div>
        )}

        {/* Line 3 — service time · location · ETA (compact, mono for
            numeric anchor). Omitted for ancillary / direct_ship. */}
        {timeLine && (
          <div
            className="mt-0.5 truncate text-body-sm text-content-base"
            data-slot="dispatch-card-timeline"
          >
            <span className="font-plex-mono tabular-nums">{timeLine}</span>
            {showEta && (
              <span className="text-content-muted">
                {" · ETA "}
                <span className="font-plex-mono tabular-nums">{eta}</span>
              </span>
            )}
          </div>
        )}

        {/* Line 4 — Product · Equipment bundle (caption, muted).
            Product = vault_type (Monticello / Graveliner / Salute /
            etc). Equipment = equipment_type bundle name (Full
            Equipment / Full w/ Placer / Device / etc). Distinct
            fields; the "Church procession" / "Graveside setup"
            descriptors were service_type hints mismapped as
            equipment in Phase 3.1 — service_type is the service
            LOCATION and lives in line 3 only. */}
        {(vaultType || equipmentType) && (
          <div
            className="mt-0.5 truncate text-caption text-content-muted"
            data-slot="dispatch-card-product"
          >
            {vaultType && <span>{vaultType}</span>}
            {vaultType && equipmentType && <span>{" · "}</span>}
            {equipmentType && <span>{equipmentType}</span>}
          </div>
        )}
      </button>

      {/* Status + icons row — same visual weight. Ancillary +
          hole-dug are status indicators; family / note / chat /
          section are icon+tooltip affordances. Single horizontal
          rail at the card's bottom edge. */}
      <div
        data-slot="dispatch-card-icon-row"
        className="flex items-center justify-between gap-1.5 border-t border-border-subtle/60 px-3 py-1.5"
      >
        {/* Left — secondary-info icons with tooltips. Each renders
            only when its data is present, keeping the row clean. */}
        <div className="flex items-center gap-0.5">
          {family && (
            <IconTooltip
              icon={UserIcon}
              label={`Family: ${family}`}
              dataSlot="dispatch-icon-family"
            />
          )}
          {section && (
            <IconTooltip
              icon={MapPinIcon}
              label={`Cemetery section: ${section}`}
              dataSlot="dispatch-icon-section"
            />
          )}
          {driverNote && (
            <IconTooltip
              icon={StickyNoteIcon}
              label={driverNote}
              dataSlot="dispatch-icon-note"
              highlight
            />
          )}
          {chatCount > 0 && (
            <IconTooltip
              icon={MessageCircleIcon}
              label={`${chatCount} unread ${chatCount === 1 ? "message" : "messages"} with funeral home`}
              dataSlot="dispatch-icon-chat"
              highlight
              badge={chatCount}
            />
          )}
        </div>

        {/* Right — status indicators (ancillary + hole-dug). */}
        <div className="flex items-center gap-1">
          {ancillaryCount > 0 && (
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
      </div>
    </div>
  )
}


// ── Icon + tooltip helper ──────────────────────────────────────────────
//
// Tiny wrapper — a Lucide icon inside a TooltipTrigger that opens the
// canonical Tooltip primitive. Used for family / section / note /
// chat affordances. `highlight` bumps the icon to text-brass to signal
// "this has non-empty content worth noticing" (distinct from the
// always-present family + section which render in content-muted).


function IconTooltip({
  icon: Icon,
  label,
  dataSlot,
  highlight = false,
  badge,
}: {
  icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>
  label: string
  dataSlot: string
  highlight?: boolean
  badge?: number
}) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span
            data-slot={dataSlot}
            onPointerDown={(e) => e.stopPropagation()}
            className={cn(
              "relative inline-flex h-6 w-6 items-center justify-center rounded-sm",
              "focus-ring-brass outline-none cursor-default",
              highlight ? "text-brass" : "text-content-muted",
              "hover:bg-surface-sunken transition-colors duration-quick",
            )}
            role="img"
            aria-label={label}
            tabIndex={0}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden />
            {typeof badge === "number" && badge > 0 && (
              <span
                data-slot={`${dataSlot}-badge`}
                className={cn(
                  "absolute -top-0.5 -right-0.5 min-w-[14px] h-[14px] px-1",
                  "inline-flex items-center justify-center rounded-full",
                  "bg-brass text-content-on-brass text-[10px] font-medium",
                  "font-plex-mono tabular-nums",
                )}
                aria-hidden
              >
                {badge}
              </span>
            )}
          </span>
        }
      />
      <TooltipContent side="top" size="default" className="max-w-[240px]">
        {label}
      </TooltipContent>
    </Tooltip>
  )
}


// ── Hole-dug three-state badge ─────────────────────────────────────────
//
// Three states (Phase 3.1): unknown | yes | no. No null state — every
// delivery has a hole-dug state; the question is whether the dispatcher
// has confirmed it. Default 'unknown' renders visible (question-mark
// on warning-muted) so the affordance stays discoverable.


function HoleDugBadge({
  status,
  onCycle,
}: {
  status: HoleDugStatus
  onCycle?: () => void
}) {
  const config = {
    yes: {
      icon: CheckIcon,
      cls: "bg-status-success-muted text-status-success",
      label: "Hole dug: yes",
    },
    no: {
      icon: MinusIcon,
      cls: "bg-surface-sunken text-content-muted border border-border-base",
      label: "Hole dug: no",
    },
    unknown: {
      icon: HelpCircleIcon,
      cls: "bg-status-warning-muted text-status-warning",
      label: "Hole dug: unknown (not yet confirmed)",
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
    <Tooltip>
      <TooltipTrigger
        render={
          <button
            type="button"
            data-slot="dispatch-hole-dug-badge"
            data-status={status}
            disabled={!onCycle}
            className={cn(
              "inline-flex h-5 w-5 items-center justify-center rounded-full",
              config.cls,
              onCycle &&
                "hover:ring-1 hover:ring-brass/40 transition-all duration-quick cursor-pointer",
              !onCycle && "cursor-default",
              "focus-ring-brass outline-none",
            )}
            aria-label={config.label}
            {...clickProps}
          >
            <Icon className="h-3 w-3" aria-hidden />
          </button>
        }
      />
      <TooltipContent side="top" size="default">
        {config.label}
        {onCycle && (
          <span className="ml-1 text-content-muted">— click to cycle</span>
        )}
      </TooltipContent>
    </Tooltip>
  )
}
