/**
 * TriggerChips — a task's DESCRIPTIVE triggers as kind-distinct chips (T-1b).
 *
 * Read-only summary (the table cell) or removable (the panel list, when onRemove
 * is passed). Kind-distinct icon + color: schedule (clock/info), event (bolt/
 * accent), manual (play/neutral). The chip label is the backend `summary` (reuses
 * the shipped humanize helper — no frontend drift). Nothing fires.
 */
import { Clock, Play, X, Zap, type LucideIcon } from "lucide-react"

import type { MoCTrigger, MoCTriggerKind } from "@/bridgeable-admin/services/moc-service"

const KIND_STYLE: Record<MoCTriggerKind, { icon: LucideIcon; chip: string }> = {
  schedule: { icon: Clock, chip: "bg-status-info-muted text-status-info" },
  event: { icon: Zap, chip: "bg-accent-subtle text-accent" },
  manual: { icon: Play, chip: "bg-surface-sunken text-content-muted" },
}

export function TriggerChips({
  triggers, onRemove,
}: {
  triggers: MoCTrigger[]
  onRemove?: (triggerId: string) => void
}) {
  if (triggers.length === 0) {
    return <span className="text-content-subtle">—</span>
  }
  return (
    <span className="flex flex-wrap gap-1">
      {triggers.map((t) => {
        const { icon: Icon, chip } = KIND_STYLE[t.kind] ?? KIND_STYLE.manual
        return (
          <span
            key={t.id}
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
        )
      })}
    </span>
  )
}
