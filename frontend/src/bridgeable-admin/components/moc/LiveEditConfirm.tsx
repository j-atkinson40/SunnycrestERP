/**
 * LiveEditConfirm — the editing grammar's gravity (Tenant Ponder-Editor P1).
 *
 * ONE confirm component, all three editors (trigger / params / audience).
 * Editing a LIVE task is consequential: the next fire uses the edited
 * settings. So the confirm shows the CHANGE (the diff, in the editor's own
 * sentence) + the plain consequence — evidence, not a vibes checkbox.
 * Dry-run tasks never see this (edits are free — the GoLiveConfirm
 * precedent's safe-direction rule).
 *
 * `useLiveEditGate(isLive)` returns the `confirmGate` the editors accept:
 * resolves true/false; when the task isn't live it short-circuits true with
 * no dialog.
 */
import { useCallback, useRef, useState } from "react"
import { Radio } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from "@/components/ui/dialog"

interface Pending {
  detail: string
}

export function useLiveEditGate(isLive: boolean | undefined) {
  const [pending, setPending] = useState<Pending | null>(null)
  const resolver = useRef<((ok: boolean) => void) | null>(null)

  const confirmGate = useCallback(
    (detail: string): Promise<boolean> => {
      if (!isLive) return Promise.resolve(true) // dry-run tasks edit free
      return new Promise<boolean>((resolve) => {
        resolver.current = resolve
        setPending({ detail })
      })
    },
    [isLive],
  )

  const settle = useCallback((ok: boolean) => {
    resolver.current?.(ok)
    resolver.current = null
    setPending(null)
  }, [])

  return { confirmGate, pending, settle }
}

export function LiveEditConfirm({
  taskName, pending, onSettle,
}: {
  taskName: string
  pending: Pending | null
  onSettle: (ok: boolean) => void
}) {
  if (!pending) return null
  return (
    <Dialog open onOpenChange={(open) => { if (!open) onSettle(false) }}>
      <DialogContent className="max-w-md" data-testid="live-edit-confirm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Radio size={16} className="flex-none text-accent" />
            This task is live
          </DialogTitle>
          <DialogDescription data-testid="live-edit-consequence">
            <strong>{taskName}</strong> fires with real effects — the next
            fire uses these settings.
          </DialogDescription>
        </DialogHeader>
        <p
          className="rounded-md border border-border-base bg-surface-sunken p-2.5 text-body-sm text-content-base"
          data-testid="live-edit-diff"
        >
          {pending.detail}
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={() => onSettle(false)}
            data-testid="live-edit-cancel">
            Cancel
          </Button>
          <Button onClick={() => onSettle(true)} data-testid="live-edit-apply">
            Apply to the live task
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
