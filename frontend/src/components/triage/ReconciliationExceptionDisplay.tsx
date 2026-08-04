/**
 * ReconciliationExceptionDisplay — Books Review Arc B B-3.
 *
 * ONE display component; the card FORM is derived at display time from candidate
 * presence (the decided two-card design, since display_component is queue-level):
 *   - candidates present → RANKED card (candidates via the B-2 RankedRows primitive;
 *     near-misses fold in as low-ranked rows carrying their rejection reason).
 *   - candidates absent   → CODING card (a coding note the operator enters to accept).
 *
 * Accept DISPATCHES BY ITEM DATA through the one `reconciliation.accept` handler:
 *   - ranked → selecting a row commits THAT candidate (selection flows to the
 *     payload; the top row is selected by default). One key, one handler.
 *   - coding → the coding note is the payload.
 * `act` throws on an errored result (period locked, non-viable candidate, claim
 * race lost) and does NOT advance — we surface the message as a toast.
 *
 * DESIGN_LANGUAGE reference: this is the fully-conforming triage display —
 * surface/content/border tokens + shadow-level, NO shadcn Card shell or
 * text-muted-foreground. Follow THIS for new triage displays (it supersedes
 * EmailUnclassifiedItemDisplay, which still carries the residual Card shell).
 */
import { useState } from "react"
import { toast } from "sonner"

import { RankedRows } from "@/components/triage/RankedRows"
import { useTriageSession } from "@/contexts/triage-session-context"
import type { TriageItem } from "@/types/triage"

interface ReconciliationCandidate {
  id: string
  candidate_record_type: string
  candidate_record_id: string
  score: string
  rank: number
  rejection_reason: string | null
  rejection_detail: Record<string, unknown> | null
}

interface Props {
  item: TriageItem
  display?: unknown
  onAdvance?: () => void | Promise<void>
}

const REASON_LABEL: Record<string, string> = {
  OUTSIDE_DATE_WINDOW: "outside the date window",
  DIRECTION_MISMATCH: "wrong direction",
  ALREADY_CLAIMED: "already reconciled",
  AMOUNT_MISMATCH: "amount differs",
  PERIOD_LOCKED: "period locked",
}

function itemField(item: TriageItem, key: string): unknown {
  const extras = item.extras as Record<string, unknown> | undefined
  if (extras && key in extras) return extras[key]
  return (item as unknown as Record<string, unknown>)[key]
}

function readCandidates(item: TriageItem): ReconciliationCandidate[] {
  const raw = itemField(item, "candidates")
  return Array.isArray(raw) ? (raw as ReconciliationCandidate[]) : []
}

export function ReconciliationExceptionDisplay({ item }: Props) {
  const { act, status } = useTriageSession()
  const candidates = readCandidates(item)
  const amount = itemField(item, "amount")
  const [coding, setCoding] = useState("")
  const working = status === "working"

  const accept = async (payload: Record<string, unknown>) => {
    try {
      await act({ action_id: "accept", payload })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Accept failed")
    }
  }

  const header = (
    <div className="rounded-lg border border-border-subtle bg-surface-elevated p-4 shadow-level-1">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-body font-medium text-content-strong">{item.title}</h3>
        {typeof amount === "string" && (
          <span className="font-plex-mono text-body tabular-nums text-content-base">{amount}</span>
        )}
      </div>
      {item.subtitle && <p className="mt-1 text-caption text-content-muted">{item.subtitle}</p>}
    </div>
  )

  if (candidates.length === 0) {
    // CODING card
    return (
      <div className="flex flex-col gap-3" data-testid="reconciliation-coding-card">
        {header}
        <div className="rounded-lg border border-border-subtle bg-surface-elevated p-4 shadow-level-1">
          <p className="text-body-sm text-content-muted">
            No matching candidates. Code this item to accept it.
          </p>
          <textarea
            value={coding}
            onChange={(e) => setCoding(e.target.value)}
            placeholder="Account / category / note"
            rows={3}
            aria-label="Coding"
            className="mt-2 w-full rounded-md border border-border-base bg-surface-raised px-3 py-2 text-body-sm text-content-base outline-none focus-visible:border-signature-steel focus-visible:ring-1 focus-visible:ring-signature-steel/50"
          />
          <button
            type="button"
            disabled={working || !coding.trim()}
            onClick={() => accept({ coding: coding.trim() })}
            className="mt-2 inline-flex items-center rounded-md bg-accent px-3 py-1.5 text-body-sm font-medium text-content-on-accent transition-opacity duration-quick disabled:opacity-50"
          >
            Accept coding
          </button>
        </div>
      </div>
    )
  }

  // RANKED card
  return (
    <div className="flex flex-col gap-3" data-testid="reconciliation-ranked-card">
      {header}
      <RankedRows
        items={candidates}
        getKey={(c) => c.id}
        ariaLabel="Match candidates"
        enabled={!working}
        onSelect={(c) => accept({ candidate_id: c.id })}
        renderItem={(c) => (
          <div className="flex min-w-0 items-baseline justify-between gap-3">
            <span className="min-w-0 truncate text-body-sm text-content-base">
              {c.candidate_record_type.replace(/_/g, " ")}
              <span className="ml-2 font-plex-mono text-caption text-content-subtle">
                {c.candidate_record_id.slice(0, 8)}
              </span>
            </span>
            {c.rejection_reason ? (
              <span className="shrink-0 text-caption text-content-muted">
                {REASON_LABEL[c.rejection_reason] ?? c.rejection_reason.toLowerCase()}
              </span>
            ) : (
              <span className="shrink-0 font-plex-mono text-caption tabular-nums text-content-muted">
                score {c.score}
              </span>
            )}
          </div>
        )}
      />
    </div>
  )
}
