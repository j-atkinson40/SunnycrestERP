/**
 * TriggerChips — a task's triggers as kind-distinct chips (T-1b), now carrying
 * the LIVE STATE (T-2.1c).
 *
 * Read-only summary (the table cell) or interactive (the panel list, when
 * onRemove / onToggleLive are passed). Kind-distinct icon + color: schedule
 * (clock/info), event (bolt/accent), manual (play/neutral).
 *
 * SCHEDULE chips carry a Live/Dry-run badge — the T-2.1b is_live promotion
 * state, shown honestly:
 * - "Live" is CONSEQUENTIAL: solid accent fill + pulse dot — a promoted trigger
 *   fires REAL effects on schedule; it must be unmistakable at a glance.
 * - "Dry-run" is calm: muted, bordered — the safe default state.
 * - The badge reflects the EFFECTIVE state: a MIRROR task's trigger shows
 *   Dry-run even if is_live is set (the sweep's §6 guard forces dry-run), and
 *   its toggle is DISABLED with the reason — never a control that appears to
 *   work but silently stays dry.
 * - Toggling TO live goes through the parent's confirm (evidence-backed);
 *   toggling BACK to dry-run is immediate (the safe direction is friction-free).
 */
import { Clock, Lock, Play, X, Zap, type LucideIcon } from "lucide-react"

import type { MoCTrigger, MoCTriggerKind } from "@/bridgeable-admin/services/moc-service"

const KIND_STYLE: Record<MoCTriggerKind, { icon: LucideIcon; chip: string }> = {
  schedule: { icon: Clock, chip: "bg-status-info-muted text-status-info" },
  event: { icon: Zap, chip: "bg-accent-subtle text-accent" },
  manual: { icon: Play, chip: "bg-surface-sunken text-content-muted" },
}

export const MIRROR_LIVE_REASON =
  "This automation’s schedule is managed by the standard scheduler — going live waits for the schedule transfer (§6 double-fire guard, narrowed T-1: adopt the schedule to transfer authority)."

/** The Live/Dry-run badge for a schedule trigger. Shows the EFFECTIVE state:
 * live requires is_live AND a live-capable (compiled) task. Interactive when
 * onToggle is passed and the task is capable; a mirror task renders the badge
 * disabled with the §6 reason. */
function LiveBadge({
  trigger, liveCapable, onToggle,
}: {
  trigger: MoCTrigger
  liveCapable: boolean
  onToggle?: (trigger: MoCTrigger, next: boolean) => void
}) {
  const effectiveLive = Boolean(trigger.is_live) && liveCapable
  const interactive = Boolean(onToggle)

  const badge = effectiveLive ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-accent px-2 py-0.5 text-caption font-semibold uppercase tracking-wide text-content-on-accent shadow-level-1">
      <span className="h-1.5 w-1.5 flex-none animate-pulse rounded-full bg-content-on-accent" />
      Live
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full border border-border-base bg-surface-sunken px-2 py-0.5 text-caption text-content-muted">
      {!liveCapable ? <Lock size={9} className="flex-none" /> : null}
      Dry-run
    </span>
  )

  if (!interactive) {
    return (
      <span
        data-testid={`trigger-live-badge-${trigger.id}`}
        data-live={effectiveLive ? "true" : "false"}
        title={!liveCapable ? MIRROR_LIVE_REASON : undefined}
      >
        {badge}
      </span>
    )
  }

  if (!liveCapable) {
    // The §6 guard: a mirror task's toggle is DISABLED with the reason — not a
    // control that appears to work but silently stays dry-run.
    return (
      <button
        type="button"
        disabled
        aria-disabled="true"
        title={MIRROR_LIVE_REASON}
        data-testid={`trigger-live-toggle-${trigger.id}`}
        data-live="false"
        className="cursor-not-allowed opacity-70"
      >
        {badge}
      </button>
    )
  }

  return (
    <button
      type="button"
      onClick={() => onToggle!(trigger, !trigger.is_live)}
      title={
        effectiveLive
          ? "Live — click to return to dry-run (takes effect next sweep)"
          : "Dry-run — click to go live (opens confirmation)"
      }
      data-testid={`trigger-live-toggle-${trigger.id}`}
      data-live={effectiveLive ? "true" : "false"}
      className="rounded-full transition-opacity duration-quick hover:opacity-85 focus-visible:outline-none focus-ring-accent"
    >
      {badge}
    </button>
  )
}

export function TriggerChips({
  triggers, onRemove, liveCapable = true, onToggleLive,
}: {
  triggers: MoCTrigger[]
  onRemove?: (triggerId: string) => void
  /** Whether this task's workflow can actually fire live (compiled = true;
   * mirror = false → the toggle disables with the §6 reason). */
  liveCapable?: boolean
  /** Present = schedule chips get a live TOGGLE (the panel). Absent = the
   * badge is display-only (the table cell). Toggling TO live must open the
   * parent's confirm; BACK to dry-run applies immediately. */
  onToggleLive?: (trigger: MoCTrigger, next: boolean) => void
}) {
  if (triggers.length === 0) {
    return <span className="text-content-subtle">—</span>
  }
  return (
    <span className="flex flex-wrap items-center gap-1">
      {triggers.map((t) => {
        const { icon: Icon, chip } = KIND_STYLE[t.kind] ?? KIND_STYLE.manual
        return (
          <span key={t.id} className="inline-flex items-center gap-1">
            <span
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-caption ${chip}`}
              data-testid={`trigger-chip-${t.kind}`}
            >
              <Icon size={11} className="flex-none" />
              <span className="whitespace-nowrap">{t.summary ?? t.label ?? t.kind}</span>
              {onRemove ? (
                <button
                  type="button"
                  onClick={() => onRemove(t.id)}
                  title="Remove trigger"
                  data-testid={`trigger-remove-${t.id}`}
                  className="ml-0.5 rounded-full p-0.5 hover:bg-black/10"
                >
                  <X size={10} />
                </button>
              ) : null}
            </span>
            {t.kind === "schedule" || t.kind === "event" ? (
              // T-2.2c: EVENT chips carry the live state too — event-fires
              // respect the same is_live + §6 guard as schedule fires.
              <LiveBadge trigger={t} liveCapable={liveCapable} onToggle={onToggleLive} />
            ) : null}
          </span>
        )
      })}
    </span>
  )
}
