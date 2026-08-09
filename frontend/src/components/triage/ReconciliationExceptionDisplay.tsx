/**
 * ReconciliationExceptionDisplay — Books Review Arc B B-3.
 *
 * ONE display component; the card FORM is derived at display time from candidate
 * presence (the decided two-card design, since display_component is queue-level):
 *   - candidates present → RANKED card (candidates via the B-2 RankedRows primitive;
 *     near-misses fold in as low-ranked rows carrying their rejection reason).
 *   - candidates absent   → CODING card (the operator picks the GL account this
 *     belongs in; a note is optional beside it). L-3.
 *   - candidates absent AND no contra leg → CODING-BLOCKED card: no form at all,
 *     because no choice the operator makes could post. L-3.
 *
 * Accept DISPATCHES BY ITEM DATA through the one `reconciliation.accept` handler:
 *   - ranked → selecting a row commits THAT candidate (selection flows to the
 *     payload; the top row is selected by default). One key, one handler.
 *   - coding → `gl_account_id` is the payload, `note` optional beside it.
 *     Accepting BOOKS a balanced draft JE before the row clears (L-3); pre-L-3
 *     this was one free-text box that cleared the row against nothing.
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

import {
  fetchGLAccounts,
  GLAccountPicker,
  type GLAccount,
} from "@/components/accounting/GLAccountPicker"
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
 * and only lacks somewhere to book it. So the card names the class and says what
 * would change that. It never asks the operator to code the row: coding it one at
 * a time is the wrong unit of work when one settings change unblocks every row of
 * that class at once.
 *
 * L-2.1c: five of the six reasons name a fixable problem. `keyword_gl_intentional`
 * does not — it means an operator already decided this class does not post
 * automatically, which for payroll and NSF is the correct answer rather than an
 * unfinished one. Its copy must read as a settled state, never as a gap; telling
 * someone to fix what they deliberately chose is worse than saying nothing. When
 * adding a reason, decide which of those two kinds it is BEFORE writing the words.
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

/**
 * WHERE THE FIX HAPPENS, named once and identically in every variant.
 *
 * The card telling an operator to configure something is only useful if they can
 * find it. "Financial Accounts" is the nav label for `/settings/accounts`
 * (navigation-service.ts, Operations group) — the two are pinned to each other
 * by a test, because a card that says one thing while the nav says another sends
 * someone hunting, which is the failure this whole sub-arc exists to remove.
 */
export const SETTINGS_DESTINATION = "Settings → Financial Accounts"

/**
 * L-3 CODING-BLOCKED card copy.
 *
 * A coding row's DEBIT leg is the operator's to choose; its CREDIT leg is the
 * bank account's GL cash account, which is not. When that is missing the row
 * cannot post no matter what they pick — so the form is not offered at all,
 * rather than accepting into a failure at the end.
 *
 * Same discipline as the keyword CONFIG card: name the fix, not the failure,
 * and never imply the operator did something wrong. The difference is that a
 * keyword row is blocked for the whole CLASS (one settings change unblocks all
 * bank fees); a coding row is blocked for the whole ACCOUNT (one settings change
 * unblocks every uncoded row on that bank account), which is why the copy talks
 * about the account rather than this transaction.
 */
const CODING_BLOCKED_COPY: Record<string, { pill: string; headline: string; fix: string }> = {
  contra_gl_unset: {
    pill: "cannot post",
    headline:
      "This bank account has no GL cash account, so a coded entry would have only one leg.",
    fix: `An administrator needs to set the account's GL cash account in ${SETTINGS_DESTINATION}. That unblocks every uncoded item on this account at once.`,
  },
  contra_gl_dangling: {
    pill: "cannot post",
    headline:
      "This bank account points at a GL cash account that no longer resolves, so a coded entry has nowhere to balance against.",
    fix: `An administrator needs to re-map the account's GL cash account in ${SETTINGS_DESTINATION}.`,
  },
  period_locked: {
    pill: "period closed",
    headline: "This transaction's accounting period is closed, so nothing can post into it.",
    fix: "Reopening the period is an administrator decision — it is a policy gate, not a configuration gap.",
  },
}

interface BlockedCopy {
  headline: (plural: string) => string
  fix: string
  /**
   * The status word beside the classification pill. Defaults to "not posted",
   * which is the honest word for every reason EXCEPT the deliberate one — there,
   * "not posted" frames a settled decision as a failure.
   */
  pill?: string
}

const BLOCKED_COPY: Record<string, BlockedCopy> = {
  keyword_gl_unmapped: {
    headline: (plural) => `No GL account is configured for ${plural}.`,
    fix: `An administrator sets this once in ${SETTINGS_DESTINATION}. Every transaction of this kind will post automatically from then on.`,
  },
  // The ONE variant that is not a problem to solve. Payroll and NSF have no
  // correct single GL account on a real chart — a net payroll draw is gross
  // wages plus employer taxes across departments, and an NSF reverses against
  // AR — so an operator turning automatic posting off for them has finished,
  // not stalled. Every word here has to avoid implying otherwise: no "missing",
  // no "not configured", no "an administrator sets this". The phrasing also has
  // to survive all three plurals, including "payroll", which takes a singular
  // verb — hence "posting is turned off for X" rather than "X don't post".
  keyword_gl_intentional: {
    headline: (plural) => `Automatic posting is turned off for ${plural}.`,
    fix: "That is a deliberate setting, not a gap — some kinds of transaction do not map to a single GL account and are booked by a person. Flag it to whoever handles these, or skip it.",
    pill: "needs a person",
  },
  keyword_gl_dangling: {
    headline: (plural) =>
      `The GL account configured for ${plural} is no longer active.`,
    fix: `An administrator re-maps it in ${SETTINGS_DESTINATION}. The account it points at has been deactivated or removed.`,
  },
  contra_gl_unset: {
    headline: () => "This bank account has no GL cash account set.",
    fix: `An administrator sets the GL account on the bank account in ${SETTINGS_DESTINATION}. Without it there is no offsetting side for the entry.`,
  },
  contra_gl_dangling: {
    headline: () => "This bank account's GL cash account is no longer active.",
    fix: `An administrator re-maps the GL account on the bank account in ${SETTINGS_DESTINATION}. The account it points at has been deactivated or removed.`,
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
  // LIVE as of this render (the builder re-derives it), not the snapshot the
  // matcher stamped — so configuring the map and coming back shows the change.
  const blockedReason = readString(item, "blocked_reason")
  // A keyword row whose configuration now resolves: no reason left, no
  // candidates, and still in the queue because nothing has booked it yet.
  const canPostNow = itemField(item, "can_post_now") === true
  const evaluatedAt = readString(item, "evaluated_at")
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
    fix: `An administrator needs to check the reconciliation GL configuration in ${SETTINGS_DESTINATION}.`,
  }
  const blockedHeadline = blockedCopy.headline(classificationPlural)
  // L-3. Non-null means this row has no usable contra leg, so the coding FORM is
  // not offered — see CODING_BLOCKED_COPY.
  const codingBlockedReason = readString(item, "coding_blocked_reason")
  const [glAccountId, setGLAccountId] = useState<string | null>(null)
  const [note, setNote] = useState("")
  const [glAccounts, setGLAccounts] = useState<GLAccount[]>([])
  const [flagOpen, setFlagOpen] = useState(false)
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())
  const working = status === "working"

  // Is the fillable coding form what this item renders? Drives the chart fetch,
  // which must not fire for ranked / keyword / blocked items.
  const needsChart =
    !keywordClassification && !canPostNow && candidates.length === 0 && !codingBlockedReason

  // Expanded group rows must NOT survive the item changing — expanding a group
  // on this item, then the queue advancing, must not leave a group expanded on
  // the next item. Neither may a coding choice: an account picked for the
  // PREVIOUS transaction silently applying to this one is a wrong posting with
  // no error signal, which is the worst shape a bug in this arc can take.
  useEffect(() => {
    setExpandedGroups(new Set())
    setGLAccountId(null)
    setNote("")
  }, [item.entity_id])

  // The chart is caller-supplied and caller-cached per the picker's contract.
  // Fetched once per mount and reused across items — it is the tenant's chart,
  // not this row's, so re-fetching per item would be one request per keystroke
  // of triage.
  useEffect(() => {
    if (!needsChart || glAccounts.length > 0) return
    let cancelled = false
    fetchGLAccounts()
      .then((accounts) => {
        if (!cancelled) setGLAccounts(accounts)
      })
      .catch(() => {
        if (!cancelled) toast.error("Could not load the chart of accounts.")
      })
    return () => {
      cancelled = true
    }
  }, [needsChart, glAccounts.length])

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

  // ORDER MATTERS: a postable row is ALSO a keyword row, so `canPostNow` has to
  // be excluded here or the config card wins and renders a blocked message for
  // something that is no longer blocked.
  const body = keywordClassification && !canPostNow ? (
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
        <span className="text-caption text-content-subtle">
          {blockedCopy.pill ?? "not posted"}
        </span>
      </div>
      <p className="mt-2 text-body-sm text-content-base">{blockedHeadline}</p>
      <p className="mt-1 text-caption text-content-muted">{blockedCopy.fix}</p>
    </div>
  ) : canPostNow ? (
    // The row was blocked when the statement was scored and is not blocked now
    // — someone configured it in between. It has no reason left to show and no
    // candidates, so without this branch it would render a card with nothing to
    // say. It cannot silently leave the queue either: booking is the licence to
    // clear, so leaving is what the button does.
    <div
      className="rounded-lg border border-border-subtle bg-surface-elevated p-4 shadow-level-1"
      data-testid="reconciliation-postable-card"
    >
      <div className="flex items-baseline gap-2">
        <span className="rounded-full bg-accent-subtle px-2 py-0.5 text-caption font-medium text-content-strong">
          {classificationLabel}
        </span>
        <span className="text-caption text-status-success">ready to post</span>
      </div>
      <p className="mt-2 text-body-sm text-content-base">
        This can post now — the GL accounts it needs are configured.
      </p>
      <p className="mt-1 text-caption text-content-muted">
        It was waiting when this statement was matched, so it stayed here.
        Posting writes a draft journal entry and clears the row.
      </p>
      <button
        type="button"
        disabled={working}
        onClick={() => act({ action_id: "post_keyword", payload: {} })}
        data-testid="reconciliation-post-button"
        className="mt-3 inline-flex items-center rounded-md bg-accent px-3 py-1.5 text-body-sm font-medium text-content-on-accent transition-opacity duration-quick disabled:opacity-50"
      >
        Post it
      </button>
    </div>
  ) : candidates.length === 0 && codingBlockedReason ? (
      // CODING-BLOCKED card (L-3) — the row has no contra leg.
      //
      // Deliberately offers NO form, for the same reason the keyword CONFIG card
      // offers no Accept: an operator must not be able to pick an account, write
      // a note, hit Accept, and only THEN learn the bank account was never
      // mapped. The backend refuses this correctly; discovering it there is a
      // wasted decision, and the fix is not theirs to make anyway. Flag and Skip
      // remain below — "ask someone" is exactly right when an admin owns the fix.
      <div
        className="rounded-lg border border-border-subtle bg-surface-elevated p-4 shadow-level-1"
        data-testid="reconciliation-coding-blocked-card"
      >
        {(() => {
          const copy = CODING_BLOCKED_COPY[codingBlockedReason] ?? {
            pill: "cannot post",
            headline: "This item cannot be posted to the ledger yet.",
            fix: `An administrator needs to check the reconciliation GL configuration in ${SETTINGS_DESTINATION}.`,
          }
          return (
            <>
              <div className="flex items-baseline gap-2">
                <span className="rounded-full bg-accent-subtle px-2 py-0.5 text-caption font-medium text-content-strong">
                  Uncoded
                </span>
                <span className="text-caption text-content-subtle">{copy.pill}</span>
              </div>
              <p className="mt-2 text-body-sm text-content-base">{copy.headline}</p>
              <p className="mt-1 text-caption text-content-muted">{copy.fix}</p>
            </>
          )
        })()}
      </div>
    ) : candidates.length === 0 ? (
      // CODING card — the operator supplies the debit leg (L-3).
      //
      // The account IS the decision; the note is a note. Pre-L-3 this was one
      // free-text box that cleared the row against nothing, which is why Accept
      // is now gated on a chosen account rather than on any text at all.
      <div
        className="rounded-lg border border-border-subtle bg-surface-elevated p-4 shadow-level-1"
        data-testid="reconciliation-coding-card"
      >
        <p className="text-body-sm text-content-muted">
          No matching candidates. Choose the account this belongs in — accepting
          posts a draft journal entry and clears the row.
        </p>
        <div className="mt-2">
          <GLAccountPicker
            accounts={glAccounts}
            value={glAccountId}
            onChange={setGLAccountId}
            placeholder="Select account…"
            disabled={working}
            aria-label="GL account"
            data-testid="reconciliation-coding-account"
          />
        </div>
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Note (optional)"
          aria-label="Note"
          data-testid="reconciliation-coding-note"
          className="mt-2 w-full rounded-md border border-border-base bg-surface-raised px-3 py-2 text-body-sm text-content-base outline-none focus-visible:border-signature-steel focus-visible:ring-1 focus-visible:ring-signature-steel/50"
        />
        <button
          type="button"
          // Gated on the ACCOUNT, never on the note. A row that cannot post
          // cannot be accepted — the same fail-closed rule the backend enforces,
          // not quietly undone at the UI.
          disabled={working || !glAccountId}
          onClick={() =>
            accept(note.trim() ? { gl_account_id: glAccountId, note: note.trim() } : { gl_account_id: glAccountId })
          }
          data-testid="reconciliation-coding-accept"
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
      {/* AS-OF. The blocked REASON above is live, re-derived this render — but
          the candidate set beside it is still whatever the last matcher run
          computed. Without this line a freshly-correct reason implies freshly
          matched candidates, which would be the wrong thing to imply. Cheap,
          honest, and it stays true even once posting works. */}
      {evaluatedAt && (
        <p
          className="text-right text-micro text-content-subtle"
          data-testid="reconciliation-evaluated-at"
        >
          Matched against your ledger {new Date(evaluatedAt).toLocaleDateString()}
        </p>
      )}
      <FlagDestinationPicker
        open={flagOpen}
        onClose={() => setFlagOpen(false)}
        onFlag={(p) => void flag(p)}
      />
    </div>
  )
}
