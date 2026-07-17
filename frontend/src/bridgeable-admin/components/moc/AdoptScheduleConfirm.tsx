/**
 * AdoptScheduleConfirm — the evidence-backed beat before the ATOMIC ADOPT
 * (Transfer T-1). GoLiveConfirm's sibling, adopt-flavored: the consequential
 * act here is moving schedule AUTHORITY, so the evidence is:
 *   1. the schedule being carried (the prose grammar — the adopt changes WHO
 *      fires, never WHEN),
 *   2. the authority statement (map trigger takes over; the standard
 *      scheduler entry retires — ONE-WAY),
 *   3. the off-switch note (post-adopt, flipping the trigger to dry-run is
 *      how you stop it; the standard entry does not resurrect).
 * Per-task, operator-initiated. Admin-side only (the tenant service carries
 * no adoptSchedule, so this never mounts tenant-side).
 */
import { useState } from "react"
import { ArrowRightLeft } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

export function AdoptScheduleConfirm({
  taskName, scheduleProse, onConfirm, onCancel,
}: {
  taskName: string
  /** The runtime schedule's prose (the WHEN beat's own text) — what gets
   * carried, verbatim in meaning. */
  scheduleProse: string
  onConfirm: () => Promise<void>
  onCancel: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  return (
    <Dialog open onOpenChange={(open) => { if (!open && !busy) onCancel() }}>
      <DialogContent className="max-w-md" data-testid="adopt-schedule-confirm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ArrowRightLeft size={16} className="flex-none text-accent" />
            Adopt schedule: {taskName}
          </DialogTitle>
          <DialogDescription data-testid="adopt-schedule-consequence">
            This task will now fire from the map&rsquo;s trigger; the standard
            scheduler entry retires — <strong>this is one-way</strong>.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <div className="rounded-md border border-border-base bg-surface-sunken p-2.5">
            <p className="text-caption uppercase tracking-wide text-content-subtle">
              The schedule being carried
            </p>
            <p className="mt-1 text-body-sm text-content-base" data-testid="adopt-schedule-prose">
              {scheduleProse}
            </p>
            <p className="mt-1 text-caption text-content-subtle">
              The adopt changes who fires it — never when. Fires continue at
              this exact schedule, live.
            </p>
          </div>
          <p className="text-caption text-content-muted" data-testid="adopt-schedule-offswitch">
            Afterwards, flipping the trigger to dry-run is the off switch —
            the task stops firing live and previews instead. The standard
            scheduler entry does not come back.
          </p>
          {error ? (
            <p className="text-body-sm text-status-error" data-testid="adopt-schedule-error">
              {error}
            </p>
          ) : null}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onCancel} disabled={busy}
            data-testid="adopt-schedule-cancel">
            Cancel
          </Button>
          <Button
            disabled={busy}
            onClick={async () => {
              setBusy(true)
              setError(null)
              try {
                await onConfirm()
              } catch (e) {
                setError(
                  e instanceof Error ? e.message : "The adopt failed — nothing was changed.",
                )
                setBusy(false)
              }
            }}
            data-testid="adopt-schedule-confirm-button"
          >
            Adopt schedule
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
