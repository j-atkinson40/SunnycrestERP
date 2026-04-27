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
 * shadow + accent focus rings.
 *
 * Fields:
 *   - service_time — free-text time field (e.g. "10:00", "11:30"),
 *     stored in `type_config.service_time` so the display updates
 *     immediately
 *   - primary_assignee_id — dropdown, null option = unassigned
 *     (Phase 4.3.2 r56 — renamed from assigned_driver_id; now holds
 *     users.id values. Dropdown options carry driver.user_id as the
 *     `value`, so no translation is needed.)
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
  /** Phase 4.3.2 (r56) — renamed from `assignedDriverId`. Value is
   *  a users.id (or null = unassigned). Parent caller sends it to
   *  the backend as `primary_assignee_id`. */
  assignedDriverId: string | null
  /** Phase 4.3.3 — optional second person on this delivery.
   *  users.id (or null = no helper). Parent caller sends as
   *  `helper_user_id`. */
  helperUserId: string | null
  /** Phase 4.3.3 — explicit driver start time, "HH:MM" wall clock.
   *  Null = use tenant default (DeliverySettings.default_driver_
   *  start_time, currently 07:00). Parent sends as
   *  `driver_start_time`. */
  driverStartTime: string | null
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
  /** Phase 4.3.3 — eligible helpers (any active tenant user
   *  excluding the current primary_assignee). Parent passes the
   *  full user list; the dialog filters out the primary at render.
   *  When omitted, the helper field is hidden (back-compat fallback
   *  for callers that haven't migrated yet). */
  helperCandidates?: HelperCandidate[]
  /** Phase 4.3.3 — tenant-wide weekday default start time, used
   *  for the "Use default" hint label. Defaults to "07:00" when
   *  not provided. */
  tenantDefaultStartTime?: string
  /** True iff the delivery's schedule is finalized — drives the
   *  revert-confirmation UX. */
  scheduleFinalized: boolean
  /** Called when the user dismisses without saving. */
  onClose: () => void
  /** Called when the user confirms a save. Parent handles the API
   *  call + optimistic UI + any revert confirmation. */
  onSave: (payload: QuickEditSavePayload) => Promise<void> | void
  /** Phase 4.3.3.1 — invoked when the user clicks "Detach from
   *  {family}" on an attached ancillary. Parent calls
   *  detachAncillary(deliveryId), refreshes the deliveries list, and
   *  closes the dialog. Optional — the detach button is hidden when
   *  this prop is omitted (back-compat for legacy callers). */
  onDetach?: (deliveryId: string) => Promise<void> | void
}


/**
 * Phase 4.3.3 — minimal helper candidate shape. Any active tenant
 * user. Parent caller hands these in pre-filtered (active +
 * tenant-scoped). The dialog further filters out whichever user is
 * the current primary_assignee — you can't be your own helper.
 */
export interface HelperCandidate {
  id: string  // users.id
  display_name: string
}


export function QuickEditDialog({
  delivery,
  drivers,
  helperCandidates,
  tenantDefaultStartTime = "07:00",
  scheduleFinalized,
  onClose,
  onSave,
  onDetach,
}: QuickEditDialogProps) {
  const open = delivery !== null
  const [serviceTime, setServiceTime] = useState("")
  const [assignedDriverId, setAssignedDriverId] = useState<string | null>(null)
  const [helperUserId, setHelperUserId] = useState<string | null>(null)
  const [driverStartTime, setDriverStartTime] = useState<string>("")
  // Phase 4.3.3 — useDefault tracks whether the start-time input
  // is in "use tenant default" mode (input disabled, value cleared
  // on save) vs explicit-override mode (input enabled, value
  // persisted). Toggle initializes from delivery.driver_start_time
  // — null = use default, non-null = explicit.
  const [useDefaultStart, setUseDefaultStart] = useState<boolean>(true)
  const [holeDug, setHoleDug] = useState<HoleDugStatus>("unknown")
  const [note, setNote] = useState("")
  const [saving, setSaving] = useState(false)
  // Phase 4.3.3.1 — separate "detaching" busy state so Save isn't
  // disabled while a detach is in flight (different intent, different
  // API call). Disable both interactions while either is pending.
  const [detaching, setDetaching] = useState(false)
  const [confirmRevertOpen, setConfirmRevertOpen] = useState(false)
  const [pendingPayload, setPendingPayload] =
    useState<QuickEditSavePayload | null>(null)

  // Reset form state every time a new delivery is passed in.
  useEffect(() => {
    if (delivery === null) return
    const tc = delivery.type_config ?? {}
    setServiceTime((tc.service_time as string | undefined) ?? "")
    setAssignedDriverId(delivery.primary_assignee_id ?? null)
    setHelperUserId(delivery.helper_user_id ?? null)
    // Phase 4.3.3 — start time form state. Backend gives "HH:MM:SS";
    // <input type="time"> wants "HH:MM". Trim seconds.
    const rawStart = delivery.driver_start_time ?? null
    setDriverStartTime(rawStart ? rawStart.slice(0, 5) : "")
    setUseDefaultStart(rawStart === null)
    // Phase 3.1: hole_dug is three-state non-nullable. If a legacy
    // DTO still surfaces null (pre-r50 migration), coerce to
    // 'unknown' — matches the backfill semantic.
    setHoleDug(delivery.hole_dug_status ?? "unknown")
    setNote(delivery.special_instructions ?? "")
    setSaving(false)
    setDetaching(false)
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
    helperUserId: helperUserId,
    // Phase 4.3.3 — when "Use default" is on, the value is cleared
    // back to null so the tenant default takes over server-side.
    // When off, send the explicit value (HH:MM); backend stores as
    // a TIME column.
    driverStartTime: useDefaultStart
      ? null
      : driverStartTime.trim() || null,
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

  // Phase 4.3.3.1 — detach an attached ancillary from its parent.
  // Routes through the parent-supplied onDetach callback (which
  // typically calls detachAncillary + refreshes + closes). Errors
  // surface to console; we don't try/catch around the close call
  // because the parent owns dialog lifecycle on success.
  async function handleDetachClick() {
    if (delivery === null || onDetach === undefined) return
    setDetaching(true)
    try {
      await onDetach(delivery.id)
    } finally {
      setDetaching(false)
    }
  }

  async function handleConfirmRevert() {
    if (!pendingPayload) return
    setConfirmRevertOpen(false)
    await commitSave(pendingPayload)
    setPendingPayload(null)
  }

  // Phase 4.3.2 (r56) — option value = driver.user_id (users.id),
  // so the selected value flows cleanly to the backend's
  // primary_assignee_id. Portal-only drivers (user_id null) are
  // filtered out until the post-September follow-up lifts the
  // portal-driver kanban-assignment gap.
  const driverOptions = drivers
    .filter((d) => d.user_id !== null)
    .map((d) => ({
      id: d.user_id as string,
      label: d.display_name || `Driver ${d.license_number ?? "(no CDL#)"}`,
    }))

  // Phase 4.3.3 — helper candidates. Filter out the current primary
  // assignee (you can't be your own helper). Uses helperCandidates
  // when provided; falls back to driverOptions when absent so older
  // callers still get a usable dropdown (driver-role-only).
  const helperOptions =
    helperCandidates !== undefined
      ? helperCandidates
          .filter((c) => c.id !== assignedDriverId)
          .map((c) => ({ id: c.id, label: c.display_name }))
      : driverOptions.filter((o) => o.id !== assignedDriverId)

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

          <div className="space-y-5 py-2">
            {/* Phase 4.3.3 — section: Assignment.
                Groups the WHO + WHEN-they-start fields. */}
            <section
              data-slot="dispatch-quick-edit-section-assignment"
              className="space-y-3"
            >
              <h3
                className={cn(
                  "text-micro uppercase tracking-wider",
                  "text-content-muted font-plex-sans",
                )}
              >
                Assignment
              </h3>

              {/* Driver */}
              <div className="space-y-1.5">
                <Label htmlFor="quick-edit-driver">Assigned driver</Label>
                <select
                  id="quick-edit-driver"
                  value={assignedDriverId ?? ""}
                  onChange={(e) => {
                    const next = e.target.value || null
                    setAssignedDriverId(next)
                    // If new primary == current helper, clear the
                    // helper (can't be your own helper).
                    if (next !== null && next === helperUserId) {
                      setHelperUserId(null)
                    }
                  }}
                  disabled={saving}
                  className={cn(
                    "w-full rounded border border-border-base",
                    "bg-surface-raised px-4 py-2.5",
                    "text-body text-content-base font-plex-sans",
                    "focus:border-accent focus:ring-2 focus:ring-accent/30",
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

              {/* Phase 4.3.3 — Helper (optional second person).
                  Eligibility per Flag 4: any active tenant user,
                  excluding the primary_assignee. The helper field
                  is hidden when no helperCandidates prop given
                  (back-compat for legacy callers). */}
              <div className="space-y-1.5">
                <Label htmlFor="quick-edit-helper">
                  Helper{" "}
                  <span className="text-content-muted font-normal">
                    (optional)
                  </span>
                </Label>
                <select
                  id="quick-edit-helper"
                  data-slot="dispatch-quick-edit-helper"
                  value={helperUserId ?? ""}
                  onChange={(e) => setHelperUserId(e.target.value || null)}
                  disabled={saving}
                  className={cn(
                    "w-full rounded border border-border-base",
                    "bg-surface-raised px-4 py-2.5",
                    "text-body text-content-base font-plex-sans",
                    "focus:border-accent focus:ring-2 focus:ring-accent/30",
                    "outline-none",
                  )}
                >
                  <option value="">No helper</option>
                  {helperOptions.map((h) => (
                    <option key={h.id} value={h.id}>
                      {h.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Phase 4.3.3 — Driver start time with Use-default
                  toggle. Default-on disables the input + clears the
                  value at save (null = use tenant default). Default-
                  off enables the input + persists the value as
                  HH:MM. Hint text shows the tenant default in either
                  state so the dispatcher knows what null means. */}
              <div className="space-y-1.5">
                <div className="flex items-baseline justify-between">
                  <Label htmlFor="quick-edit-start-time">
                    Driver start time
                  </Label>
                  <label
                    className={cn(
                      "flex items-center gap-1.5 text-caption",
                      "text-content-muted cursor-pointer select-none",
                    )}
                    data-slot="dispatch-quick-edit-start-time-default-toggle"
                  >
                    <input
                      type="checkbox"
                      checked={useDefaultStart}
                      onChange={(e) => setUseDefaultStart(e.target.checked)}
                      disabled={saving}
                      className="cursor-pointer"
                    />
                    Use tenant default
                  </label>
                </div>
                <Input
                  id="quick-edit-start-time"
                  data-slot="dispatch-quick-edit-start-time-input"
                  type="time"
                  value={useDefaultStart ? "" : driverStartTime}
                  onChange={(e) => setDriverStartTime(e.target.value)}
                  disabled={saving || useDefaultStart}
                  placeholder={tenantDefaultStartTime}
                />
                <p
                  className={cn(
                    "text-caption text-content-muted leading-tight",
                  )}
                >
                  {useDefaultStart
                    ? `Defaults to ${tenantDefaultStartTime} (tenant setting).`
                    : "Override the tenant default for this delivery only."}
                </p>
              </div>

              {/* Phase 4.3.3.1 — Detach button (only on attached
                  ancillaries). Sits at the bottom of the Assignment
                  section because detach IS an assignment-shape change
                  (ancillary moves from "paired with parent" to
                  standalone, claiming its own slot in the lane).
                  Distinct from Save: Save persists the assignment +
                  state edits the user typed; Detach is a one-shot
                  side-effect that rewires the row's parent FK. Hidden
                  when the delivery isn't attached OR no onDetach prop
                  was passed (back-compat). */}
              {delivery.attached_to_delivery_id && onDetach && (
                <div
                  data-slot="dispatch-quick-edit-detach-row"
                  className="pt-2 border-t border-border-subtle/60"
                >
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleDetachClick}
                    disabled={saving || detaching}
                    data-slot="dispatch-quick-edit-detach"
                  >
                    {detaching
                      ? "Detaching…"
                      : delivery.attached_to_family_name
                        ? `Detach from ${delivery.attached_to_family_name}`
                        : "Detach from parent delivery"}
                  </Button>
                  <p
                    className={cn(
                      "mt-1.5 text-caption text-content-muted leading-tight",
                    )}
                  >
                    Detaches this ancillary from its parent so it stands
                    alone in the lane. Inherited assignee + date are
                    preserved.
                  </p>
                </div>
              )}
            </section>

            {/* Phase 4.3.3 — section: Delivery state.
                Groups WHEN-the-service-happens + status indicators
                + dispatcher's note. */}
            <section
              data-slot="dispatch-quick-edit-section-state"
              className="space-y-3"
            >
              <h3
                className={cn(
                  "text-micro uppercase tracking-wider",
                  "text-content-muted font-plex-sans",
                )}
              >
                Delivery state
              </h3>

              {/* Service time */}
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
                            ? "bg-accent text-content-on-accent font-medium"
                            : "text-content-muted hover:text-content-strong hover:bg-surface-sunken",
                          "focus-ring-accent outline-none",
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
            </section>

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
