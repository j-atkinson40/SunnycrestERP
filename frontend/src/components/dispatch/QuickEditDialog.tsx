/**
 * QuickEditDialog — opens from DeliveryCard click on the Dispatch
 * Monitor. Lets the dispatcher change time / driver / hole-dug /
 * note without leaving the Monitor.
 *
 * Revert-awareness (Phase B Session 1 state machine): if the
 * delivery's schedule is currently `finalized`, saving shows a
 * confirmation dialog first — "this will revert the schedule back
 * to draft." Dispatcher can proceed or cancel. Cancel preserves
 * both the delivery state and schedule state.
 *
 * Uses the shared Dialog primitive from `ui/dialog.tsx` (the
 * platform overlay family from Aesthetic Arc Session 2). Stays
 * inside the overlay composition discipline: backdrop blur + level-2
 * shadow + brass focus rings.
 *
 * Fields:
 *   - service_time — free-text time field (e.g. "10:00", "11:30"),
 *     stored in `type_config.service_time` so the display updates
 *     immediately
 *   - assigned_driver_id — dropdown, null option = unassigned
 *   - hole_dug_status — three-state radio (unknown/yes/no) + "not
 *     set" option
 *   - special_instructions — note field, append or replace
 *
 * Quick-edit is NOT a full edit — complex changes (reschedule to a
 * different day, change customer/FH) require the full delivery edit
 * page. Quick-edit is for the 90% case the dispatcher adjusts
 * mid-planning.
 */

import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import type {
  DeliveryDTO,
  DriverDTO,
  HoleDugStatus,
} from "@/services/dispatch-service"
import { cn } from "@/lib/utils"


export interface QuickEditSavePayload {
  deliveryId: string
  serviceTime: string | null
  assignedDriverId: string | null
  holeDugStatus: HoleDugStatus
  note: string | null
  /** True iff the parent schedule is currently finalized; parent
   *  uses this to decide whether to show the revert confirmation
   *  AFTER the dialog save resolves. Passed through for observability. */
  scheduleWasFinalized: boolean
}


export interface QuickEditDialogProps {
  /** Delivery being edited. `null` means the dialog is closed. */
  delivery: DeliveryDTO | null
  /** Full driver roster for the picker. */
  drivers: DriverDTO[]
  /** True iff the delivery's schedule is finalized — drives the
   *  revert-confirmation UX. */
  scheduleFinalized: boolean
  /** Called when the user dismisses without saving. */
  onClose: () => void
  /** Called when the user confirms a save. Parent handles the API
   *  call + optimistic UI + any revert confirmation. */
  onSave: (payload: QuickEditSavePayload) => Promise<void> | void
}


export function QuickEditDialog({
  delivery,
  drivers,
  scheduleFinalized,
  onClose,
  onSave,
}: QuickEditDialogProps) {
  const open = delivery !== null
  const [serviceTime, setServiceTime] = useState("")
  const [assignedDriverId, setAssignedDriverId] = useState<string | null>(null)
  const [holeDug, setHoleDug] = useState<HoleDugStatus>("unknown")
  const [note, setNote] = useState("")
  const [saving, setSaving] = useState(false)
  const [confirmRevertOpen, setConfirmRevertOpen] = useState(false)
  const [pendingPayload, setPendingPayload] =
    useState<QuickEditSavePayload | null>(null)

  // Reset form state every time a new delivery is passed in.
  useEffect(() => {
    if (delivery === null) return
    const tc = delivery.type_config ?? {}
    setServiceTime((tc.service_time as string | undefined) ?? "")
    setAssignedDriverId(delivery.assigned_driver_id ?? null)
    // Phase 3.1: hole_dug is three-state non-nullable. If a legacy
    // DTO still surfaces null (pre-r50 migration), coerce to
    // 'unknown' — matches the backfill semantic.
    setHoleDug(delivery.hole_dug_status ?? "unknown")
    setNote(delivery.special_instructions ?? "")
    setSaving(false)
    setConfirmRevertOpen(false)
    setPendingPayload(null)
  }, [delivery])

  if (delivery === null) {
    return null
  }

  const family = (delivery.type_config?.family_name as string | undefined) ?? "—"

  const buildPayload = (): QuickEditSavePayload => ({
    deliveryId: delivery.id,
    serviceTime: serviceTime.trim() || null,
    assignedDriverId: assignedDriverId,
    holeDugStatus: holeDug,
    note: note.trim() || null,
    scheduleWasFinalized: scheduleFinalized,
  })

  async function handleSaveClick() {
    const payload = buildPayload()
    if (scheduleFinalized) {
      // Stage for confirmation.
      setPendingPayload(payload)
      setConfirmRevertOpen(true)
      return
    }
    await commitSave(payload)
  }

  async function commitSave(payload: QuickEditSavePayload) {
    setSaving(true)
    try {
      await onSave(payload)
    } finally {
      setSaving(false)
    }
  }

  async function handleConfirmRevert() {
    if (!pendingPayload) return
    setConfirmRevertOpen(false)
    await commitSave(pendingPayload)
    setPendingPayload(null)
  }

  const driverOptions = drivers.map((d) => ({
    id: d.id,
    label: d.display_name || `Driver ${d.license_number ?? "(no CDL#)"}`,
  }))

  return (
    <>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          if (!next && !saving) onClose()
        }}
      >
        <DialogContent
          className="max-w-md"
          data-slot="dispatch-quick-edit-dialog"
        >
          <DialogHeader>
            <DialogTitle>{family}</DialogTitle>
            <DialogDescription>
              Quick-edit delivery details. For larger changes open the
              full delivery page.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Time */}
            <div className="space-y-1.5">
              <Label htmlFor="quick-edit-time">Service time</Label>
              <Input
                id="quick-edit-time"
                type="time"
                value={serviceTime}
                onChange={(e) => setServiceTime(e.target.value)}
                disabled={saving}
                placeholder="10:00"
              />
            </div>

            {/* Driver */}
            <div className="space-y-1.5">
              <Label htmlFor="quick-edit-driver">Assigned driver</Label>
              <select
                id="quick-edit-driver"
                value={assignedDriverId ?? ""}
                onChange={(e) =>
                  setAssignedDriverId(e.target.value || null)
                }
                disabled={saving}
                className={cn(
                  "w-full rounded border border-border-base",
                  "bg-surface-raised px-4 py-2.5",
                  "text-body text-content-base font-plex-sans",
                  "focus:border-brass focus:ring-2 focus:ring-brass/30",
                  "outline-none",
                )}
              >
                <option value="">Unassigned</option>
                {driverOptions.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Hole dug — three-state non-nullable (Phase 3.1). */}
            <div className="space-y-1.5">
              <Label>Hole dug</Label>
              <div
                role="radiogroup"
                aria-label="Hole-dug status"
                className="flex items-center gap-1 rounded border border-border-base bg-surface-raised p-1"
              >
                {(["unknown", "yes", "no"] as const).map((v) => {
                  const stored: HoleDugStatus = v
                  const selected = holeDug === stored
                  const label =
                    v === "unknown" ? "Unknown"
                    : v === "yes" ? "Yes"
                    : "No"
                  return (
                    <button
                      key={v}
                      type="button"
                      role="radio"
                      aria-checked={selected}
                      disabled={saving}
                      onClick={() => setHoleDug(stored)}
                      className={cn(
                        "flex-1 rounded px-2 py-1.5 text-body-sm transition-colors duration-quick",
                        selected
                          ? "bg-brass text-content-on-brass font-medium"
                          : "text-content-muted hover:text-content-strong hover:bg-surface-sunken",
                        "focus-ring-brass outline-none",
                      )}
                    >
                      {label}
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Note */}
            <div className="space-y-1.5">
              <Label htmlFor="quick-edit-note">Note</Label>
              <Textarea
                id="quick-edit-note"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                disabled={saving}
                placeholder="Dispatcher notes — visible to drivers."
                rows={3}
              />
            </div>

            {/* Revert warning when schedule is finalized */}
            {scheduleFinalized && (
              <div
                className={cn(
                  "rounded border px-3 py-2 text-caption",
                  "bg-status-warning-muted/50 border-status-warning/30",
                  "text-status-warning",
                )}
                data-slot="dispatch-quick-edit-revert-warning"
              >
                <strong>Heads up:</strong> this schedule is finalized.
                Saving will revert it to draft.
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={handleSaveClick}
              disabled={saving}
            >
              {saving ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Revert confirmation dialog — separate Dialog so dismissing it
          leaves the primary edit dialog open (user cancels the revert
          but keeps editing). */}
      <Dialog
        open={confirmRevertOpen}
        onOpenChange={(next) => {
          if (!next) setConfirmRevertOpen(false)
        }}
      >
        <DialogContent
          className="max-w-sm"
          data-slot="dispatch-revert-confirm-dialog"
        >
          <DialogHeader>
            <DialogTitle>Revert schedule to draft?</DialogTitle>
            <DialogDescription>
              This schedule is currently finalized. Saving your change
              will revert it to draft state so edits can propagate.
              Re-finalize when you're done.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setConfirmRevertOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={handleConfirmRevert}
            >
              Save &amp; revert to draft
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
