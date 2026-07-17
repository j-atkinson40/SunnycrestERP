/**
 * GoLiveConfirm — the evidence-backed beat before a trigger goes live (T-2.1c).
 *
 * Flipping a trigger TO live is the one consequential act in the MoC: the sweep
 * will fire REAL effects on schedule. So the confirm SHOWS WHAT THE TASK WILL
 * ACTUALLY DO, read from its LATEST DRY-RUN PREVIEW (the engine's own "would
 * execute X" records via /schedule-runs?trigger_id=…&limit=1) — the honest
 * content, not a description.
 *
 * FALLBACK: a task that has NEVER previewed gets an explicit "hasn't previewed
 * yet" notice nudging the dry-run-first workflow — never a fabricated effect.
 * (Flipping BACK to dry-run never confirms — the safe direction is
 * friction-free; see TaskEditorPanel.)
 */
import { useEffect, useState } from "react"
import { AlertTriangle, Radio } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  getLatestScheduleRun,
  type MoCScheduleRun,
  type MoCTrigger,
} from "@/bridgeable-admin/services/moc-service"

export function GoLiveConfirm({
  trigger, taskName, onConfirm, onCancel,
}: {
  trigger: MoCTrigger
  taskName: string
  onConfirm: () => void
  onCancel: () => void
}) {
  const [loading, setLoading] = useState(true)
  const [preview, setPreview] = useState<MoCScheduleRun | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getLatestScheduleRun(trigger.id)
      .then((run) => { if (!cancelled) setPreview(run) })
      .catch(() => { if (!cancelled) setPreview(null) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [trigger.id])

  const summary = trigger.summary ?? trigger.label ?? "its trigger"
  // T-2.2c: kind-aware consequence wording — a schedule fires on the clock; an
  // event fires WHEN the domain event occurs (the event provenance is the
  // event-specific bit of the evidence).
  const consequence =
    trigger.kind === "event" ? (
      <>whenever <strong>{summary}</strong> occurs</>
    ) : (
      <>on schedule ({summary})</>
    )

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onCancel() }}>
      <DialogContent className="max-w-md" data-testid="go-live-confirm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Radio size={16} className="flex-none text-accent" />
            Go live: {taskName}
          </DialogTitle>
          <DialogDescription data-testid="go-live-consequence">
            This will fire <strong>real effects</strong> {consequence} — not a
            dry-run preview.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <p className="text-body-sm text-content-muted" data-testid="go-live-loading">
            Loading the latest dry-run preview…
          </p>
        ) : preview && preview.would_do.length > 0 ? (
          <div className="space-y-1.5" data-testid="go-live-preview">
            <p className="text-body-sm text-content-base">
              On each scheduled run, this automation will (from its latest dry-run preview):
            </p>
            <ul className="space-y-1 rounded-md border border-border-base bg-surface-sunken p-2.5">
              {preview.would_do.map((line, i) => (
                <li key={i} className="font-plex-mono text-caption text-content-base">
                  {line.replace(/^would execute /, "")}
                </li>
              ))}
            </ul>
            {preview.started_at ? (
              <p className="text-caption text-content-subtle">
                Previewed {new Date(preview.started_at).toLocaleString()}
              </p>
            ) : null}
          </div>
        ) : (
          <div
            className="flex gap-2 rounded-md border border-status-warning/30 bg-status-warning-muted p-2.5"
            data-testid="go-live-no-preview"
          >
            <AlertTriangle size={15} className="mt-0.5 flex-none text-status-warning" />
            <p className="text-body-sm text-status-warning">
              {trigger.kind === "event"
                ? "This trigger hasn’t matched-and-previewed yet — it will run its workflow live when the event occurs. Consider letting a matching event fire dry-run first to see what it does before going live."
                : "This automation hasn’t previewed yet — it will run its workflow live on schedule. Consider letting it run dry-run first (the next sweep tick) to see what it does before going live."}
            </p>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onCancel} data-testid="go-live-cancel">
            Cancel
          </Button>
          <Button onClick={onConfirm} data-testid="go-live-confirm-button">
            Go Live
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
