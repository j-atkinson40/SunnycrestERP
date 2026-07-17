/**
 * TaskCard — one task as a material object on the tenant Bridgeable Map
 * (The Sunnycrest Workshop; the flagship tenant surface).
 *
 * DESIGN_LANGUAGE discipline:
 * - Material, not paint: elevated surface + shadow lift, NO perimeter border
 *   (§6 "Card perimeter: no border" — edges emerge from lift + halo).
 * - Detail concentration: the calm body carries name/description; the
 *   jewelry is the LIVE chip (accent), the hold-P hint (the fill ring), and
 *   the "yours"/offer pills. Nothing else gets the detail budget.
 * - The card is quiet until hovered; a ponderable card lifts one level and
 *   shows the hold hint. Click opens the ponder (the mouse path); hold-P is
 *   the taught gesture. Reduced motion collapses the lift transition
 *   globally (base.css).
 * - Honest truncation: the description clamps at two lines — the full text
 *   lives in the ponder, where the teaching is.
 */
import { useCallback } from "react"
import { Clock, Radio } from "lucide-react"

import {
  HoldRing, useHoldToPonder,
} from "@/bridgeable-admin/components/moc/MoCTaskTable"
import type { MapTask } from "@/services/moc-map-service"

export function TaskCard({
  task, onPonder, onOpenOffer,
}: {
  task: MapTask
  onPonder: (task: MapTask) => void
  onOpenOffer: (task: MapTask) => void
}) {
  const ponderable = Boolean(task.workflow?.exists)
  const complete = useCallback(() => onPonder(task), [onPonder, task])
  const { hovered, holding, reduced, hoverProps } = useHoldToPonder(
    ponderable, complete,
  )

  // T-0 authority truth carries onto the card: a runtime-managed schedule
  // shows the RUNTIME prose + the quiet managed badge.
  const runtimeScheduled = task.schedule_authority === "runtime_scheduler"
  const when = runtimeScheduled
    ? task.runtime_schedule_summary || task.derived_frequency || task.frequency
    : task.derived_frequency || task.frequency
  const anyLive = (task.triggers ?? []).some((t) => t.is_live && t.is_active !== false)
  const hasTriggers = (task.triggers ?? []).some((t) => t.is_active !== false)

  return (
    <div
      {...hoverProps}
      role={ponderable ? "button" : undefined}
      tabIndex={ponderable ? 0 : undefined}
      onClick={ponderable ? () => onPonder(task) : undefined}
      onKeyDown={
        ponderable
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault()
                onPonder(task)
              }
            }
          : undefined
      }
      className={
        "group relative flex min-h-[7.5rem] flex-col rounded-md bg-surface-elevated p-4 shadow-level-1 " +
        (ponderable
          ? "cursor-pointer transition-shadow duration-quick ease-settle hover:shadow-level-2 focus-ring-accent"
          : "")
      }
      data-testid={`map-card-${task.id}`}
    >
      {/* Name row — the pills ride the name, never the chrome. */}
      <div className="flex items-start justify-between gap-2">
        <p className="text-body font-medium leading-snug text-content-strong">
          {task.name}
          {task.scope === "tenant_override" ? (
            <span
              className="ml-2 inline-flex translate-y-[-1px] rounded-full bg-accent-subtle px-2 py-0.5 align-middle text-micro font-medium text-accent"
              data-testid={`map-card-yours-${task.id}`}
            >
              yours
            </span>
          ) : null}
        </p>
        {/* Hold-to-ponder — the taught gesture, card-scoped. */}
        {ponderable && hovered ? (
          <span
            className="flex flex-none items-center gap-1.5 whitespace-nowrap text-caption text-content-muted"
            data-testid="map-hold-hint"
          >
            <HoldRing holding={holding} reduced={reduced} />
            Hold{" "}
            <kbd className="rounded-sm border border-border-base px-1 font-plex-mono text-micro">
              P
            </kbd>
          </span>
        ) : null}
      </div>

      {/* The offer pills (P3) — decision-weight, so they keep their color. */}
      {task.offer_state?.offer_status === "pending" ? (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onOpenOffer(task) }}
          className="focus-ring-accent mt-1.5 self-start rounded-full bg-accent px-2 py-0.5 text-micro font-medium text-content-on-accent"
          data-testid={`map-card-offer-${task.id}`}
        >
          standard updated
        </button>
      ) : task.offer_state?.offer_status === "declined" ? (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onOpenOffer(task) }}
          className="focus-ring-accent mt-1.5 self-start rounded-full bg-surface-sunken px-2 py-0.5 text-micro text-content-subtle"
          data-testid={`map-card-offer-gap-${task.id}`}
          title="The standard version updated — you passed earlier; still available"
        >
          yours · standard updated
        </button>
      ) : null}

      {/* The map's own description — honestly clamped; the ponder has it whole. */}
      {task.description ? (
        <p className="mt-1.5 line-clamp-2 text-body-sm leading-relaxed text-content-muted">
          {task.description}
        </p>
      ) : null}

      {/* Footer — the schedule in the prose grammar + the live truth. */}
      <div className="mt-auto flex items-center gap-2 pt-3">
        {when ? (
          <span
            className="inline-flex min-w-0 items-center gap-1.5 text-caption text-content-muted"
            data-testid={`map-card-when-${task.id}`}
          >
            <Clock size={11} className="flex-none text-content-subtle" />
            <span className="truncate">{when}</span>
          </span>
        ) : (
          <span className="text-caption text-content-subtle">No schedule yet</span>
        )}
        {runtimeScheduled ? (
          <span
            className="inline-flex flex-none rounded-full bg-surface-sunken px-1.5 py-0.5 text-micro text-content-subtle"
            data-testid={`map-card-managed-${task.id}`}
            title="This task's schedule is managed by the standard scheduler"
          >
            standard scheduler
          </span>
        ) : null}
        {/* THE JEWELRY: live gets the accent; dry-run stays quiet. */}
        {anyLive ? (
          <span
            className="ml-auto inline-flex flex-none items-center gap-1 rounded-full bg-accent-subtle px-2 py-0.5 text-micro font-medium text-accent"
            data-testid={`map-card-live-${task.id}`}
          >
            <Radio size={9} /> live
          </span>
        ) : hasTriggers ? (
          <span
            className="ml-auto flex-none rounded-full bg-surface-sunken px-2 py-0.5 text-micro text-content-subtle"
            data-testid={`map-card-dry-${task.id}`}
          >
            dry-run
          </span>
        ) : null}
      </div>
    </div>
  )
}
