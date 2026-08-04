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

function readString(item: TriageItem, key: string): string | null {
  const raw = itemField(item, key)
  return typeof raw === "string" && raw.length > 0 ? raw : null
}

/**
 * L-2 CONFIG card copy.
 *
 * This is the third situation, and it is NOT an absent-candidate coding case.
 * The system knows exactly what the row is — the keyword ladder classified it —
 * and only lacks somewhere to book it. So the card names the class, names the
 * missing configuration, and says who fixes it. It never asks the operator to
 * code the row: coding it one at a time is the wrong unit of work when one
 * settings change unblocks every row of that class at once.
 */
const CLASSIFICATION_LABEL: Record<string, string> = {
  bank_fee: "Bank fee",
  payroll: "Payroll",
  nsf: "Returned item (NSF)",
}

/** Lowercase form for mid-sentence use ("no GL account for bank fees"). */
const CLASSIFICATION_PLURAL: Record<string, string> = {
  bank_fee: "bank fees",
  payroll: "payroll",
  nsf: "returned items",
}

interface BlockedCopy {
  headline: (plural: string) => string
  fix: string
}

const BLOCKED_COPY: Record<string, BlockedCopy> = {
  keyword_gl_unmapped: {
    headline: (plural) => `No GL account is configured for ${plural}.`,
    fix: "An administrator sets this once in the reconciliation GL settings. Every transaction of this kind will post automatically from then on.",
  },
  keyword_gl_dangling: {
    headline: (plural) =>
      `The GL account configured for ${plural} is no longer active.`,
    fix: "An administrator re-maps it in the reconciliation GL settings. The account it points at has been deactivated or removed.",
  },
  contra_gl_unset: {
    headline: () => "This bank account has no GL cash account set.",
    fix: "An administrator sets the GL account on the bank account itself. Without it there is no offsetting side for the entry.",
  },
  contra_gl_dangling: {
    headline: () => "This bank account's GL cash account is no longer active.",
    fix: "An administrator re-maps the GL account on the bank account. The account it points at has been deactivated or removed.",
  },
  period_locked: {
    headline: () => "The accounting period for this date is closed.",
    fix: "This is not a configuration gap — nothing will post into a closed period. Reopen the period or leave the item until it is reconciled elsewhere.",
  },
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
  // L-2: presence of a classification is what selects the CONFIG form. It is
  // checked BEFORE candidate count, because a blocked keyword row also has zero
  // candidates and would otherwise fall through to the coding card — asking the
  // operator to code a row the system has already identified.
  const keywordClassification = readString(item, "keyword_classification")
  const blockedReason = readString(item, "blocked_reason")
  const classificationLabel =
    (keywordClassification && CLASSIFICATION_LABEL[keywordClassification]) ??
    keywordClassification ??
    ""
  const classificationPlural =
    (keywordClassification && CLASSIFICATION_PLURAL[keywordClassification]) ??
    "transactions of this kind"
  // An unrecognised reason still renders a truthful card rather than an empty
  // one: we know it did not post and we know what it is, so say that much.
  const blockedCopy: BlockedCopy = (blockedReason ? BLOCKED_COPY[blockedReason] : undefined) ?? {
    headline: () => "This item could not be posted to the ledger.",
    fix: "An administrator needs to check the reconciliation GL configuration for this account.",
  }
  const blockedHeadline = blockedCopy.headline(classificationPlural)
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

  const body = keywordClassification ? (
    // CONFIG card — the row is classified; it has nowhere to book.
    //
    // Deliberately offers NO Accept. A row that cannot post cannot honestly be
    // accepted, and the fail-closed discipline that governs the backend should
    // not be quietly undone at the UI. Flag and Skip remain available below:
    // "ask someone" is exactly the right move when the fix belongs to an admin.
    <div
      className="rounded-lg border border-border-subtle bg-surface-elevated p-4 shadow-level-1"
      data-testid="reconciliation-config-card"
    >
      <div className="flex items-baseline gap-2">
        <span className="rounded-full bg-accent-subtle px-2 py-0.5 text-caption font-medium text-content-strong">
          {classificationLabel}
        </span>
        <span className="text-caption text-content-subtle">not posted</span>
      </div>
      <p className="mt-2 text-body-sm text-content-base">{blockedHeadline}</p>
      <p className="mt-1 text-caption text-content-muted">{blockedCopy.fix}</p>
    </div>
  ) : candidates.length === 0 ? (
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
