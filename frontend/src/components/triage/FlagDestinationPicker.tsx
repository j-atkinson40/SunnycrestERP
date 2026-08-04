/**
 * FlagDestinationPicker — Books Review Arc B B-4.5.
 *
 * The Flag flow: a destination picker (RankedRows consumer #2) → for "Ask
 * someone", a recipient search (RankedRows consumer #3, async). Proves the
 * primitive's seam: the CALLER owns loading / debounce / abort / empty state;
 * RankedRows just renders the rows and (on items change) resets its own
 * selection — the caller never reaches in to coordinate it.
 *
 * Each destination row STATES ITS RETURN CONDITION (owner + when it comes back)
 * — the coaching from the Figma work, not a bare list of three names. Recipients
 * show their current open-ask load ("N already waiting").
 */
import { useEffect, useRef, useState } from "react"

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { RankedRows } from "@/components/triage/RankedRows"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { searchFlagRecipients, type FlagRecipient } from "@/services/reconciliation-flag-service"

export interface FlagPayload {
  destination: "ask_someone" | "hold_for_documentation" | "accept_reconciling"
  recipient_user_id?: string
}

interface Props {
  open: boolean
  onClose: () => void
  /** Caller dispatches reconciliation.flag with this payload. */
  onFlag: (payload: FlagPayload) => void
}

interface Destination {
  id: FlagPayload["destination"]
  label: string
  /** The return condition, shown on the row — the coaching. */
  returns: string
}

const DESTINATIONS: Destination[] = [
  { id: "ask_someone", label: "Ask someone", returns: "Returns when they complete the task" },
  { id: "hold_for_documentation", label: "Hold for documentation", returns: "Returns when a document is attached" },
  { id: "accept_reconciling", label: "Accept as a reconciling item", returns: "Closes it — the amount posts as a reconciling difference" },
]

export function FlagDestinationPicker({ open, onClose, onFlag }: Props) {
  const [step, setStep] = useState<"destinations" | "recipients">("destinations")
  const [query, setQuery] = useState("")
  const debounced = useDebouncedValue(query, 200)
  const [recipients, setRecipients] = useState<FlagRecipient[]>([])
  const [loading, setLoading] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (open) {
      setStep("destinations")
      setQuery("")
      setRecipients([])
    }
  }, [open])

  // Recipient search — CALLER owns debounce + abort + loading + empty state.
  useEffect(() => {
    if (!open || step !== "recipients") return
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setLoading(true)
    searchFlagRecipients(debounced.trim(), ctrl.signal)
      .then((rows) => setRecipients(rows))
      .catch(() => {
        /* aborted or failed — leave the empty state to render "keep typing" */
      })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [open, step, debounced])

  const pickDestination = (d: Destination) => {
    if (d.id === "ask_someone") {
      setStep("recipients")
      return
    }
    onFlag({ destination: d.id })
    onClose()
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{step === "destinations" ? "Flag this item" : "Ask someone"}</DialogTitle>
        </DialogHeader>

        {step === "destinations" ? (
          <RankedRows
            items={DESTINATIONS}
            getKey={(d) => d.id}
            ariaLabel="Flag destinations"
            onSelect={pickDestination}
            escape={{ label: "Cancel", onSelect: onClose }}
            renderItem={(d) => (
              <div className="flex min-w-0 flex-col">
                <span className="text-body-sm text-content-base">{d.label}</span>
                <span className="text-caption text-content-muted">{d.returns}</span>
              </div>
            )}
          />
        ) : (
          <div className="flex flex-col gap-2">
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search people…"
              aria-label="Recipient search"
              className="w-full rounded-md border border-border-base bg-surface-raised px-3 py-2 text-body-sm text-content-base outline-none focus-visible:border-signature-steel focus-visible:ring-1 focus-visible:ring-signature-steel/50"
            />
            {recipients.length === 0 ? (
              <p className="px-1 py-2 text-caption text-content-muted" role="status">
                {loading ? "Searching…" : "No one matches — keep typing."}
              </p>
            ) : (
              <RankedRows
                items={recipients}
                getKey={(r) => r.id}
                ariaLabel="Recipients"
                onSelect={(r) => {
                  onFlag({ destination: "ask_someone", recipient_user_id: r.id })
                  onClose()
                }}
                escape={{ label: "Back", onSelect: () => setStep("destinations") }}
                renderItem={(r) => (
                  <div className="flex min-w-0 items-baseline justify-between gap-3">
                    <span className="min-w-0 truncate text-body-sm text-content-base">{r.name}</span>
                    {r.waiting_count > 0 && (
                      <span className="shrink-0 text-caption text-content-muted">
                        {r.waiting_count} already waiting
                      </span>
                    )}
                  </div>
                )}
              />
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
