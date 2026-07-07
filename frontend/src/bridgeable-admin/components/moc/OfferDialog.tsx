/**
 * Offer dialog (Focus Variations V-2) — the owner's review of an offered
 * update: the authored patch notes, the derived diff (per-field, from
 * THIS variation's pin), the keep-mine / take-new chooser on customized
 * fields, and Accept / Decline / Later.
 *
 * The diff IS the evidence-backed confirm (the Live-toggle philosophy):
 * the consequence is fully visible before the click commits. Accept is
 * the pin-move apply — atomic server-side; keep-mine never writes.
 * Decline is quiet-but-recallable (this dialog reopens from the gap chip
 * and accept still works on a declined offer).
 */

import * as React from "react"
import { toast } from "sonner"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { UpdateDiffList } from "@/bridgeable-admin/components/moc/UpdateDiffList"
import {
  acceptUpdateOffer,
  declineUpdateOffer,
  getUpdateOffer,
  type UpdateOffer,
} from "@/bridgeable-admin/services/moc-service"

export function OfferDialog({
  offerId,
  targetLabel,
  onClose,
  onDecided,
}: {
  offerId: string
  targetLabel: string
  onClose: () => void
  /** Fired after accept OR decline — the caller refreshes states/pills. */
  onDecided: () => void
}) {
  const [offer, setOffer] = React.useState<UpdateOffer | null>(null)
  const [failed, setFailed] = React.useState(false)
  const [choices, setChoices] = React.useState<Record<string, "keep" | "take">>({})
  const [busy, setBusy] = React.useState(false)

  React.useEffect(() => {
    getUpdateOffer(offerId).then(setOffer).catch(() => setFailed(true))
  }, [offerId])

  async function accept() {
    setBusy(true)
    try {
      const r = await acceptUpdateOffer(offerId, choices)
      toast.success(`Updated to v${r.pinned_version}`)
      onDecided()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Apply failed")
      setBusy(false)
    }
  }

  async function decline() {
    setBusy(true)
    try {
      await declineUpdateOffer(offerId)
      onDecided()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Decline failed")
      setBusy(false)
    }
  }

  const declined = offer?.status === "declined"

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="max-w-lg" data-testid="offer-dialog">
        <DialogHeader>
          <DialogTitle>Update available — {targetLabel}</DialogTitle>
          <DialogDescription>
            {offer
              ? `${offer.source_slug} v${offer.source_version_from} → v${offer.source_version_to}` +
                (declined ? " · previously declined — still applicable." : "")
              : failed
                ? "Couldn't load the offer."
                : "Loading…"}
          </DialogDescription>
        </DialogHeader>

        {offer ? (
          <div className="space-y-4">
            {offer.patch_notes ? (
              <p
                className="rounded-md border border-border-subtle bg-surface-sunken px-3 py-2 text-body-sm text-content-base"
                data-testid="offer-patch-notes"
              >
                {offer.patch_notes}
              </p>
            ) : null}
            <div className="max-h-52 overflow-y-auto">
              <UpdateDiffList
                fields={offer.derived_diff.fields}
                choices={choices}
                onChoice={(field, choice) =>
                  setChoices((c) => ({ ...c, [field]: choice }))
                }
              />
            </div>
          </div>
        ) : null}

        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Later
          </Button>
          {!declined ? (
            <Button
              variant="ghost"
              onClick={() => void decline()}
              disabled={!offer || busy}
              data-testid="offer-decline-button"
            >
              Decline
            </Button>
          ) : null}
          <Button
            onClick={() => void accept()}
            disabled={!offer || busy}
            data-testid="offer-accept-button"
          >
            {busy ? "Applying…" : "Accept update"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
