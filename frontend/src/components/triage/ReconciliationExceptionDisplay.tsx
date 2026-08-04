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
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { FlagDestinationPicker, type FlagPayload } from "@/components/triage/FlagDestinationPicker"
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

interface GroupMember {
  type: string
  id: string
  amount: string
}

/**
 * A one-to-many (payment_group) candidate: a summary the operator can expand to
 * see the members before accepting — never "accept N payments you can't see".
 *
 * The disclosure is CLICK-ONLY, with stopPropagation so expanding never also
 * accepts the row. It is intentionally not a nested <button> (invalid inside
 * RankedRows' <button> row) and not keyboard-toggled: RankedRows' global
 * capture-phase Enter listener would fire "accept" before any in-row keydown,
 * so a keyboard toggle can't win here without changing the primitive. Keyboard
 * users see the summary (count + total); the member breakdown is mouse-expand.
 */
function GroupRow({
  candidate,
  expanded,
  onToggle,
}: {
  candidate: ReconciliationCandidate
  expanded: boolean
  onToggle: () => void
}) {
  const detail = (candidate.rejection_detail ?? {}) as Record<string, unknown>
  const members = Array.isArray(detail.members) ? (detail.members as GroupMember[]) : []
  const total = typeof detail.member_total === "string" ? detail.member_total : ""
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <div className="flex items-baseline justify-between gap-3">
        <span className="min-w-0 text-body-sm text-content-base">
          {members.length} payments totalling{" "}
          <span className="font-plex-mono tabular-nums">{total}</span>
        </span>
        <span
          role="button"
          onClick={(e) => {
            e.stopPropagation()
            onToggle()
          }}
          className="shrink-0 cursor-pointer text-caption text-content-muted underline-offset-2 hover:text-content-base hover:underline"
        >
          {expanded ? "Hide" : "Show"}
        </span>
      </div>
      {expanded && (
        <ul className="mt-1 flex flex-col gap-0.5 border-l border-border-subtle pl-2">
          {members.map((m) => (
            <li
              key={m.id}
              className="flex items-baseline justify-between gap-3 text-caption text-content-muted"
            >
              <span className="min-w-0 truncate">
                {m.type.replace(/_/g, " ")}
                <span className="ml-2 font-plex-mono text-content-subtle">{m.id.slice(0, 8)}</span>
              </span>
              <span className="shrink-0 font-plex-mono tabular-nums">{m.amount}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function ReconciliationExceptionDisplay({ item }: Props) {
  const { act, status } = useTriageSession()
  const candidates = readCandidates(item)
  const amount = itemField(item, "amount")
  const [coding, setCoding] = useState("")
  const [flagOpen, setFlagOpen] = useState(false)
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())
  const working = status === "working"

  // Expanded group rows must NOT survive the item changing — expanding a group
  // on this item, then the queue advancing, must not leave a group expanded on
  // the next item.
  useEffect(() => {
    setExpandedGroups(new Set())
  }, [item.entity_id])

  const toggleGroup = (id: string) =>
    setExpandedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const accept = async (payload: Record<string, unknown>) => {
    try {
      await act({ action_id: "accept", payload })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Accept failed")
    }
  }

  const flag = async (payload: FlagPayload) => {
    try {
      await act({ action_id: "flag", payload: payload as unknown as Record<string, unknown> })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Flag failed")
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

  const body =
    candidates.length === 0 ? (
      // CODING card
      <div
        className="rounded-lg border border-border-subtle bg-surface-elevated p-4 shadow-level-1"
        data-testid="reconciliation-coding-card"
      >
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
    ) : (
      // RANKED card
      <div data-testid="reconciliation-ranked-card">
        <RankedRows
          items={candidates}
          getKey={(c) => c.id}
          ariaLabel="Match candidates"
          // Disabled while the Flag picker is open so the two RankedRows
          // capture-phase listeners never both fire on the same keystroke.
          enabled={!working && !flagOpen}
          onSelect={(c) => accept({ candidate_id: c.id })}
          renderItem={(c) =>
            c.candidate_record_type === "payment_group" ? (
              <GroupRow
                candidate={c}
                expanded={expandedGroups.has(c.id)}
                onToggle={() => toggleGroup(c.id)}
              />
            ) : (
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
            )
          }
        />
      </div>
    )

  return (
    <div className="flex flex-col gap-3">
      {header}
      {body}
      {/* Flag is display-owned (interactive: opens a picker before dispatch).
          Neutral outline — Accept stays the one chrome-filled primary. */}
      <div className="flex justify-end">
        <button
          type="button"
          disabled={working}
          onClick={() => setFlagOpen(true)}
          className="rounded-md border border-border-base bg-surface-elevated px-3 py-1.5 text-body-sm text-content-base transition-colors duration-quick hover:bg-surface-raised disabled:opacity-50"
        >
          Flag…
        </button>
      </div>
      <FlagDestinationPicker
        open={flagOpen}
        onClose={() => setFlagOpen(false)}
        onFlag={(p) => void flag(p)}
      />
    </div>
  )
}
