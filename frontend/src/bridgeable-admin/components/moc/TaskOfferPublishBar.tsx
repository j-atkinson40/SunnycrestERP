/**
 * TaskOfferPublishBar — THE DELIBERATE BOUNDARY (Tenant Ponder-Editor P3).
 *
 * The V-2 publish pattern at the task tier, lighter: editing a vertical
 * default is PRIVATE; this bar is the explicit "offer this change to
 * tenant versions" moment — with a note, never on every save. Renders only
 * in the ADMIN ponder's edit mode (the tenant service carries no publish
 * fns) on vertical-default tasks that actually have forks.
 *
 * The copy states the scope line a tenant must find legible: the offer
 * covers the TASK'S OWN settings; the workflow is shared and improves for
 * everyone automatically.
 */
import { useEffect, useState } from "react"
import { GitBranch, Send } from "lucide-react"

import type { TaskOfferPreview } from "@/bridgeable-admin/services/moc-service"
import { usePonderService } from "./ponder-service-context"

const MUTED = "#A79B8E"
const FAINT = "#6E6459"
const CARD = "rgba(255,251,245,0.055)"
const EDGE = "rgba(234,227,218,0.16)"

export function TaskOfferPublishBar({ taskId }: { taskId: string }) {
  const svc = usePonderService()
  const [preview, setPreview] = useState<TaskOfferPreview | null>(null)
  const [open, setOpen] = useState(false)
  const [notes, setNotes] = useState("")
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setPreview(null)
    setDone(null)
    svc.taskOfferPreview?.(taskId).then(setPreview).catch(() => setPreview(null))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId])

  if (!svc.publishTaskOffer || !preview || preview.fork_count === 0) return null

  async function publish() {
    setBusy(true)
    setError(null)
    try {
      const out = await svc.publishTaskOffer!(taskId, notes.trim() || null)
      setDone(
        out.offers_created > 0
          ? `Offered to ${out.offers_created} tenant version${out.offers_created === 1 ? "" : "s"}.`
          : "Every tenant version already matches the standard — nothing to offer.",
      )
      setOpen(false)
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || "Couldn't publish the offer.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="mx-auto mb-2 w-full max-w-2xl rounded-md px-4 py-2.5"
      style={{ background: CARD, border: `1px solid ${EDGE}` }}
      data-testid="task-offer-publish-bar"
    >
      <div className="flex flex-wrap items-center gap-2">
        <GitBranch size={13} style={{ color: FAINT }} />
        <span className="text-body-sm" style={{ color: MUTED }}>
          {preview.fork_count} tenant version{preview.fork_count === 1 ? "" : "s"} run
          {preview.fork_count === 1 ? "s" : ""} their own copy of this task.
        </span>
        {done ? (
          <span className="text-caption" style={{ color: "var(--accent)" }}
            data-testid="task-offer-published">
            {done}
          </span>
        ) : (
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className="focus-ring-accent ml-auto inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-body-sm"
            style={{ color: "var(--accent)" }}
            data-testid="task-offer-open"
          >
            <Send size={12} /> Offer current standard…
          </button>
        )}
      </div>
      {open ? (
        <div className="mt-2 space-y-2 border-t pt-2" style={{ borderColor: EDGE }}>
          <p className="text-caption" style={{ color: FAINT }}>
            Offers this task's own settings (schedule, wording) to the{" "}
            {preview.offerable_count} version{preview.offerable_count === 1 ? "" : "s"} that
            differ{preview.offerable_count === 1 ? "s" : ""}. The workflow itself is shared —
            its improvements reach every tenant automatically, no offer needed.
          </p>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            placeholder="A note for the tenants (what changed, why)…"
            className="w-full rounded-md border bg-transparent px-2 py-1 text-body-sm focus-visible:outline-none"
            style={{ borderColor: EDGE, color: "#EAE3DA" }}
            data-testid="task-offer-notes"
          />
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setOpen(false)} disabled={busy}
              className="rounded-md px-2 py-1 text-body-sm" style={{ color: MUTED }}>
              Cancel
            </button>
            <button
              type="button" disabled={busy}
              onClick={() => void publish()}
              className="rounded-md px-2.5 py-1 text-body-sm font-medium"
              style={{ background: "var(--accent)", color: "#1a1512" }}
              data-testid="task-offer-publish"
            >
              {busy ? "Offering…" : "Offer to tenant versions"}
            </button>
          </div>
          {error ? (
            <p className="text-caption" style={{ color: "#E08A6D" }}>{error}</p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
