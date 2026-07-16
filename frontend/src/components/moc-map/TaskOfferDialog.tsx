/**
 * TaskOfferDialog — the standard updated; here's exactly what (Tenant
 * Ponder-Editor P3, the V-2 grammar at the task tier).
 *
 * Opens from the badge/gap chip on their forked row: the publisher's note
 * + THE DIFF IN THE PROSE GRAMMAR ("The last Friday of every month at
 * 9:30 AM → The first Monday of every month at 4:00 PM") — the derivation
 * grammar as the diff renderer. Per-field keep-mine toggles (take-new is
 * the default: accepting means taking; tasks carry no override ledger, a
 * deliberate lightening of V-2's keep-mine default — the toggle is the
 * honest per-field escape). Accept applies to THEIR row, triggers staying
 * unpromoted; decline is quiet-but-recallable (the gap chip reopens here).
 *
 * Admins decide; everyone else reads (the honest note replaces the
 * buttons — no dead controls).
 */
import { useEffect, useState } from "react"
import { ArrowRight, GitBranch } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from "@/components/ui/dialog"
import type { TaskOffer } from "@/bridgeable-admin/services/moc-service"
import {
  acceptTaskOffer, declineTaskOffer, getTaskOffer,
} from "@/services/moc-map-service"

const FIELD_LABELS: Record<string, string> = {
  schedule: "Schedule",
  name: "Name",
  description: "Description",
  icon: "Icon",
  frequency: "Frequency",
  task_type: "Type",
}

function _render(v: unknown): string {
  if (v == null || v === "") return "(not set)"
  if (Array.isArray(v)) return v.join("; ") || "(none)"
  return String(v)
}

export function TaskOfferDialog({
  offerId, taskName, canDecide, onClose, onDecided,
}: {
  offerId: string
  taskName: string
  canDecide: boolean
  onClose: () => void
  /** Refetch the map — badges + row content re-derive. */
  onDecided: () => Promise<void> | void
}) {
  const [offer, setOffer] = useState<TaskOffer | null>(null)
  const [keeps, setKeeps] = useState<Set<string>>(new Set())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getTaskOffer(offerId)
      .then(setOffer)
      .catch(() => setError("Couldn't load the update."))
  }, [offerId])

  async function decide(action: "accept" | "decline") {
    setBusy(true)
    setError(null)
    try {
      if (action === "accept") {
        const choices: Record<string, "keep" | "take"> = {}
        keeps.forEach((f) => { choices[f] = "keep" })
        await acceptTaskOffer(offerId, choices)
      } else {
        await declineTaskOffer(offerId)
      }
      await onDecided()
      onClose()
    } catch (e) {
      const d = (e as { response?: { data?: { detail?: { message?: string } | string } } })
        ?.response?.data?.detail
      setError(typeof d === "string" ? d : d?.message || "Couldn't apply the decision.")
    } finally {
      setBusy(false)
    }
  }

  const fields = offer ? Object.entries(offer.diff.fields) : []

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="max-w-lg" data-testid="task-offer-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <GitBranch size={16} className="flex-none text-accent" />
            The standard version updated
          </DialogTitle>
          <DialogDescription>
            <strong>{taskName}</strong> — your version can take the update, keep
            what's yours, or both. Your triggers stay in dry-run either way.
          </DialogDescription>
        </DialogHeader>

        {error ? (
          <p className="text-body-sm text-status-error" data-testid="task-offer-error">{error}</p>
        ) : !offer ? (
          <p className="text-body-sm text-content-muted">Loading…</p>
        ) : (
          <div className="space-y-3">
            {offer.patch_notes ? (
              <p className="rounded-md border border-border-base bg-surface-sunken p-2.5 text-body-sm text-content-base"
                data-testid="task-offer-notes-display">
                “{offer.patch_notes}”
              </p>
            ) : null}
            <div className="space-y-2.5">
              {fields.map(([field, delta]) => (
                <div key={field} data-testid={`task-offer-field-${field}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-caption font-medium uppercase tracking-wide text-content-subtle">
                      {FIELD_LABELS[field] ?? field}
                    </span>
                    {canDecide ? (
                      <label className="flex items-center gap-1.5 text-caption text-content-muted">
                        <input
                          type="checkbox"
                          checked={keeps.has(field)}
                          onChange={(e) => {
                            const next = new Set(keeps)
                            if (e.target.checked) next.add(field)
                            else next.delete(field)
                            setKeeps(next)
                          }}
                          data-testid={`task-offer-keep-${field}`}
                        />
                        keep mine
                      </label>
                    ) : null}
                  </div>
                  <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-body-sm">
                    <span className={keeps.has(field) ? "text-content-strong" : "text-content-muted line-through"}>
                      {_render(delta.from)}
                    </span>
                    <ArrowRight size={11} className="text-content-subtle" />
                    <span className={keeps.has(field) ? "text-content-muted line-through" : "text-content-strong"}>
                      {_render(delta.to)}
                    </span>
                  </p>
                </div>
              ))}
            </div>
            {offer.status === "declined" ? (
              <p className="text-caption text-content-subtle" data-testid="task-offer-declined-note">
                You declined this earlier — it's still here whenever you want it.
              </p>
            ) : null}
          </div>
        )}

        <DialogFooter>
          {canDecide && offer ? (
            <>
              {offer.status === "pending" ? (
                <Button variant="outline" disabled={busy}
                  onClick={() => void decide("decline")}
                  data-testid="task-offer-decline">
                  Not now
                </Button>
              ) : null}
              <Button disabled={busy || fields.length === keeps.size}
                onClick={() => void decide("accept")}
                data-testid="task-offer-accept">
                {busy ? "Applying…" : "Apply the update"}
              </Button>
            </>
          ) : (
            <p className="text-caption text-content-subtle">
              An admin can apply this update.
            </p>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
