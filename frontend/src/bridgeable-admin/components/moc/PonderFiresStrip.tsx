/**
 * PonderFiresStrip — what did this machine actually DO lately (Tenant
 * Ponder-Editor P3, the monitoring leg).
 *
 * A LEDGER, not a dashboard: a quiet strip of recent fires — when, dry-run/
 * live badged honestly (read from each run's own marker), outcome, event
 * provenance where event-fired. A FAILED fire deep-links to Decision Triage
 * for roles that can follow it (can_follow_reviews — mapped server-side
 * from the queue's own config); everyone else sees the honest failed
 * status, never a dead link. A never-fired task says so plainly.
 *
 * Renders only when the script carries `fires` (the tenant read).
 */
import { Link } from "react-router-dom"
import { ArrowUpRight, Check, Radio, X as XIcon } from "lucide-react"

import type { PonderFire } from "@/bridgeable-admin/services/moc-service"

const MUTED = "#A79B8E"
const FAINT = "#6E6459"
const CARD = "rgba(255,251,245,0.055)"
const EDGE = "rgba(234,227,218,0.16)"

function _when(iso: string | null): string {
  if (!iso) return "—"
  const d = new Date(iso)
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" }) +
    " " + d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
}

export function PonderFiresStrip({
  fires, isLive, canFollowReviews,
}: {
  fires: PonderFire[]
  isLive?: boolean
  canFollowReviews?: boolean
}) {
  return (
    <div
      className="mx-auto mb-2 w-full max-w-2xl rounded-md px-4 py-2.5"
      style={{ background: CARD, border: `1px solid ${EDGE}` }}
      data-testid="ponder-fires-strip"
    >
      <p className="mb-1.5 text-caption uppercase tracking-wide" style={{ color: FAINT }}>
        Recent runs
      </p>
      {fires.length === 0 ? (
        <p className="text-body-sm" style={{ color: MUTED }} data-testid="ponder-fires-empty">
          Hasn't run yet{isLive ? " — its trigger is live" : " — it previews in dry-run"}.
        </p>
      ) : (
        <div className="flex flex-col gap-1">
          {fires.map((f) => {
            const failed = f.status === "failed"
            return (
              <div key={f.run_id} className="flex items-center gap-2.5 text-caption"
                data-testid={`ponder-fire-${f.run_id}`}>
                <span className="w-24 shrink-0" style={{ color: FAINT }}>
                  {_when(f.started_at)}
                </span>
                <span
                  className="inline-flex w-16 shrink-0 items-center gap-1 rounded-full px-1.5 py-0.5 text-micro"
                  style={f.is_dry_run
                    ? { background: CARD, color: FAINT }
                    : { background: "rgba(156,86,64,0.22)", color: "var(--accent)" }}
                >
                  {!f.is_dry_run ? <Radio size={8} /> : null}
                  {f.is_dry_run ? "dry-run" : "live"}
                </span>
                <span
                  className="inline-flex items-center gap-1"
                  style={{ color: failed ? "#E08A6D" : MUTED }}
                >
                  {failed ? <XIcon size={11} /> : <Check size={11} />}
                  {f.status.replace(/_/g, " ")}
                </span>
                {f.event_key ? (
                  <span style={{ color: FAINT }}>· {f.event_key.replace(/\./g, " ")}</span>
                ) : null}
                {failed && f.review_item_id && canFollowReviews ? (
                  <Link
                    to="/triage/workflow_review_triage"
                    className="focus-ring-accent ml-auto inline-flex items-center gap-0.5 rounded-sm hover:text-white"
                    style={{ color: "var(--accent)" }}
                    data-testid={`ponder-fire-review-${f.run_id}`}
                  >
                    review <ArrowUpRight size={10} />
                  </Link>
                ) : null}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
