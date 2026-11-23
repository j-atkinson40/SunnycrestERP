/**
 * One person's payroll status — the entrance `r234` shipped without.
 *
 * ⚠️ **THE COLUMNS EXISTED FOR ELEVEN DAYS WITH NO WAY TO SET THEM.** `r234`
 * added `payroll_status` and `payroll_status_since`; measured on production
 * 2026-11-21, **0 of 30** employees carried a value, while two readers
 * depended on them — the R-115's line 1, which fell back to counting checks,
 * and `roster_coverage`, whose excused branch had therefore **never once been
 * taken**, so the one member it was built to stop flagging was flagged every
 * week. CLAUDE.md §11: complete machinery behind an unprovisioned entrance.
 *
 * ⚠️ **A CHANGE IS A RECORD, NOT AN EDIT.** Every change appends, carrying
 * what it replaced and why, and the history is shown here rather than kept
 * for an audit screen nobody opens. A status decides whether somebody is
 * counted on a form filed with a union; "who said they left, and when did
 * they say it" is the question this row exists to answer a year later.
 *
 * ⚠️ **`readOnly` ARRIVES AS A PROP AND IS NEVER RE-DERIVED HERE.** It comes
 * from the Focus dispatcher's `useFocusReadOnly(config)`, keyed on
 * `editPermission: "payroll.approve"` — the same answer the rest of the Focus
 * obeys. A pane that called `usePermission` itself would look identical and
 * could disagree with the surface around it.
 *
 * ⚠️ **AND THIS IS THE ONE WRITE IN A FILE WHOSE HEADER SAYS READ-ONLY.** The
 * panes are week-scoped views of figures, and the rule that a pane cannot be
 * the thing that changed a number still holds: a status is not a figure and
 * not week-scoped. It does move the R-115's line 1, which is stated on the
 * row so nobody records one believing it is only a note. James ruled the row
 * belongs in the pane on 2026-11-21; the week's numbers stay read-only.
 */

import { useCallback, useEffect, useState } from "react"

import {
  CHECKING_SUFFIX,
  didWriteLand,
  failureText,
  gotNoReply,
} from "@/lib/payroll/failure"
import {
  getEmployeeStatus,
  setEmployeeStatus,
  type EmployeeStatus,
  type PayrollEmployeeStatus,
  type StatusChange,
} from "@/lib/payroll/focus-api"


/** The four statuses, in the order somebody picks them, with the words a
 *  person uses. `active` is a CHOICE somebody made — distinct from no status
 *  at all, which is what every employee carries today. */
const LABELS: Record<PayrollEmployeeStatus, string> = {
  active: "Working",
  left: "Left",
  workers_comp: "On workers' comp",
  leave: "On leave",
}

const ORDER: PayrollEmployeeStatus[] = ["active", "left", "workers_comp", "leave"]

/**
 * A date with its YEAR, which is why this is not `UnionFormCore.shortDate`.
 *
 * That one renders "Oct 29" because a remittance form is always about the
 * month in its own header. A leaving date is routinely in a prior year — the
 * five leavers being entered on 2026-11-21 left between February and June —
 * and "Jun 25" with no year is the wrong answer for this row.
 *
 * ⚠️ **A BARE DATE IS READ LOCALLY, A TIMESTAMP AS AN INSTANT.**
 * `new Date("2026-06-25")` is UTC midnight, which west of Greenwich reads
 * back as the 24th. That shipped once: "Due Nov 15" rendered "Nov 14".
 */
export function statusDate(iso: string | null): string {
  if (!iso) return "—"
  const bare = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso.trim())
  const d = bare
    ? new Date(Number(bare[1]), Number(bare[2]) - 1, Number(bare[3]))
    : new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

/** Today, as the `yyyy-mm-dd` a date input wants, in the LOCAL calendar —
 *  `toISOString()` would hand back tomorrow after 7pm Eastern. */
function todayLocal(): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

/** One history line, in the order a reader asks: what it is now, what it was,
 *  who said so and why. */
function HistoryLine({ c }: { c: StatusChange }) {
  const was =
    c.previous_status === null
      ? "first recorded"
      : `was ${LABELS[c.previous_status] ?? c.previous_status}${
          c.previous_since ? ` since ${statusDate(c.previous_since)}` : ""
        }`
  return (
    <li className="text-caption text-content-muted">
      <span className="text-content-strong">
        {LABELS[c.status] ?? c.status} since {statusDate(c.since)}
      </span>{" "}
      · {was}
      <span className="block">
        {/* ⚠️ `changed_at` AND `since` ARE DIFFERENT DATES and are routinely
            months apart — one is the day somebody stopped working, the other
            the day a person typed it in. Shown together on purpose. */}
        {[c.changed_by_name, c.changed_at ? `recorded ${statusDate(c.changed_at)}` : null]
          .filter(Boolean)
          .join(" · ")}
        {c.reason ? ` — ${c.reason}` : ""}
      </span>
    </li>
  )
}


export function EmployeeStatusRow({
  employeeId,
  readOnly,
}: {
  employeeId: string
  /** From the Focus dispatcher. Never re-derived here — see the header. */
  readOnly: boolean
}) {
  const [data, setData] = useState<EmployeeStatus | null | false>(null)
  const [editing, setEditing] = useState(false)
  const [status, setStatus] = useState<PayrollEmployeeStatus>("left")
  const [since, setSince] = useState("")
  const [reason, setReason] = useState("")
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [showHistory, setShowHistory] = useState(false)

  const load = useCallback(async () => {
    try {
      setData(await getEmployeeStatus(employeeId))
    } catch {
      setData(false)
    }
  }, [employeeId])

  useEffect(() => {
    let live = true
    setData(null)
    setEditing(false)
    setMessage(null)
    getEmployeeStatus(employeeId)
      .then((d) => live && setData(d))
      .catch(() => live && setData(false))
    return () => {
      live = false
    }
  }, [employeeId])

  async function save() {
    setBusy(true)
    setMessage(null)
    const attempted = { status, since, reason }
    try {
      await setEmployeeStatus(employeeId, attempted)
      setEditing(false)
      setReason("")
      await load()
      setMessage(null)
    } catch (err) {
      // ⚠️ A WRITE WHOSE REPLY NEVER ARRIVED MAY HAVE LANDED. CORS, a timeout
      // and a reset on the RETURN leg all look like a client error for work
      // the server committed, so the only account worth having comes from the
      // server's own record.
      if (gotNoReply(err)) {
        setMessage(failureText(err) + CHECKING_SUFFIX)
        const verdict = await didWriteLand(
          () => getEmployeeStatus(employeeId),
          (d) =>
            d.history.some(
              (c) => c.status === attempted.status && c.since === attempted.since,
            ),
        )
        if (verdict === "landed") {
          setEditing(false)
          setReason("")
          setMessage("It did save — the reply was the only thing lost.")
        } else if (verdict === "did-not-land") {
          setMessage("It did not save. Nothing was recorded; try again.")
        } else {
          setMessage(
            "Still unknown — the check could not reach the server either. " +
              "Re-open this pane before recording it again, so it is not " +
              "recorded twice.",
          )
        }
        await load()
      } else {
        setMessage(failureText(err))
      }
    } finally {
      setBusy(false)
    }
  }

  /** ⚠️ **THE MESSAGE OUTLIVES EVERY OTHER STATE, AND THAT IS NOT COSMETIC.**
   *  It shipped the other way first: after a write whose reply never arrived,
   *  the follow-up check also failed, so the re-read set this row to "could
   *  not be loaded" and the only sentence that mattered — *still unknown, do
   *  not record it twice* — was replaced by a generic load error. The state
   *  the reader must act on was wiped by the state that caused it. Caught by
   *  the `STILL UNKNOWN` test, not by reading. */
  const footer = message ? (
    <p
      className="mt-1 text-caption text-status-error"
      data-testid="employee-status-message"
    >
      {message}
    </p>
  ) : null

  // ⚠️ `data-testid` ON EVERY STATE'S CONTAINER, not only the loaded one. The
  // first version put it on the success branch alone, so a test asserting the
  // load-failure wording could not find the row to read it — which looks
  // exactly like the failure state not rendering at all.
  if (data === null) {
    return (
      <div
        className="border-b border-border-subtle py-2 last:border-0"
        data-testid="employee-status-row"
      >
        <span className="text-body-sm text-content-muted">Status</span>
        <span className="ml-2 text-body-sm text-content-muted">loading…</span>
        {footer}
      </div>
    )
  }
  if (data === false) {
    return (
      <div
        className="border-b border-border-subtle py-2 last:border-0"
        data-testid="employee-status-row"
      >
        <span className="text-body-sm text-content-muted">Status</span>
        <span className="ml-2 text-body-sm text-status-error">
          could not be loaded. Nothing has been changed.
        </span>
        {footer}
      </div>
    )
  }

  const recorded = data.status !== null

  return (
    <div
      className="border-b border-border-subtle py-2 last:border-0"
      data-testid="employee-status-row"
    >
      {/* ⚠️ **THE ACTION SITS ON THE VALUE LINE, AND THAT IS NOT A STYLE
          CHOICE.** The row shipped with the button on its own line below a
          three-line explanation, and the walk-through's screenshot showed the
          result: the member pane, which had always fit, now overflowed its
          clip and BOTH this button and the long-standing Timecard button were
          below the fold with no scrollbar visible — the pane stack is
          `absolute inset-0 overflow-hidden`, so the body's own scrollbar is
          clipped away too. Every test passed, because Playwright and
          testing-library both scroll to an element before clicking it. Caught
          by reading the picture, which is the only thing that could have. */}
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-body-sm text-content-muted">Status</span>
        <span className="flex items-baseline gap-2">
          <span
            className="text-body-sm text-content-strong"
            data-testid="employee-status-value"
          >
            {recorded
              ? `${LABELS[data.status!] ?? data.status} · since ${statusDate(data.since)}`
              : "Not recorded"}
          </span>
          {!readOnly && !editing ? (
            <button
              type="button"
              data-testid="employee-status-change"
              className="rounded border border-border-subtle bg-surface-elevated px-2 py-0.5 text-caption text-content-strong hover:border-border-strong"
              onClick={() => {
                setStatus(data.status ?? "left")
                setSince(data.since ?? "")
                setReason("")
                setMessage(null)
                setEditing(true)
              }}
            >
              {recorded ? "Change" : "Record"}
            </button>
          ) : null}
        </span>
      </div>

      {/* ⚠️ "NOT RECORDED" IS NOT "WORKING", and the difference is load-bearing
          rather than pedantic: with no status recorded anywhere the R-115
          counts line 1 by checks and says so. The row says what recording one
          changes, so nobody enters a leaving date believing it is a note. */}
      {!recorded ? (
        <span className="block text-caption text-content-muted">
          Nobody has said. The union form counts line 1 from who had a check
          that month, and says so on the form.
        </span>
      ) : null}

      {data.history.length > 0 ? (
        <>
          <button
            type="button"
            data-testid="employee-status-history-toggle"
            className="mt-1 text-caption text-content-muted underline hover:text-content-strong"
            onClick={() => setShowHistory((v) => !v)}
          >
            {showHistory
              ? "Hide history"
              : `${data.history.length} change${data.history.length === 1 ? "" : "s"} recorded`}
          </button>
          {showHistory ? (
            <ul className="mt-1 space-y-1" data-testid="employee-status-history">
              {data.history.map((c) => (
                <HistoryLine key={c.id} c={c} />
              ))}
            </ul>
          ) : null}
        </>
      ) : null}

      {readOnly ? (
        <span className="block text-caption text-content-muted">
          Changing a status needs{" "}
          <span className="font-mono text-caption">payroll.approve</span>.
        </span>
      ) : editing ? (
        <div className="mt-2 space-y-2" data-testid="employee-status-editor">
          <label className="block text-caption text-content-muted">
            Status
            <select
              data-testid="employee-status-select"
              className="mt-0.5 block w-full rounded-lg border border-border-subtle bg-surface-elevated px-2 py-1 text-body-sm text-content-strong"
              value={status}
              onChange={(e) => setStatus(e.target.value as PayrollEmployeeStatus)}
            >
              {ORDER.map((s) => (
                <option key={s} value={s}>
                  {LABELS[s]}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-caption text-content-muted">
            {/* ⚠️ THE DAY IT BEGAN, NOT TODAY. The R-115's line-1 rule compares
                this against the month, so a date typed as "when I noticed"
                puts a leaver back into months they had already left. */}
            Since — the day it began, not today
            <input
              type="date"
              data-testid="employee-status-since"
              max={todayLocal()}
              className="mt-0.5 block w-full rounded-lg border border-border-subtle bg-surface-elevated px-2 py-1 text-body-sm text-content-strong"
              value={since}
              onChange={(e) => setSince(e.target.value)}
            />
          </label>
          <label className="block text-caption text-content-muted">
            Reason
            <input
              type="text"
              data-testid="employee-status-reason"
              maxLength={300}
              placeholder="e.g. termination date from Payentry"
              className="mt-0.5 block w-full rounded-lg border border-border-subtle bg-surface-elevated px-2 py-1 text-body-sm text-content-strong"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          <div className="flex gap-2">
            <button
              type="button"
              data-testid="employee-status-save"
              // ⚠️ DISABLED ONLY ON WHAT IS ABSENT FROM THE FORM. Every other
              // refusal — a future date, an unknown status, a no-op — is the
              // SERVER's, printed verbatim. A second copy of those rules here
              // would be a second producer, free to drift.
              disabled={busy || !since || !reason.trim()}
              className="rounded-lg bg-accent px-3 py-1.5 text-body-sm text-content-on-accent disabled:opacity-50"
              onClick={save}
            >
              {busy ? "Recording…" : "Record change"}
            </button>
            <button
              type="button"
              data-testid="employee-status-cancel"
              disabled={busy}
              className="rounded-lg border border-border-subtle bg-surface-elevated px-3 py-1.5 text-body-sm text-content-strong"
              onClick={() => {
                setEditing(false)
                setMessage(null)
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      {footer}
    </div>
  )
}
