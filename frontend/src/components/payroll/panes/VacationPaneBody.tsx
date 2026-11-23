/**
 * One person's vacation year — Payroll 5c.
 *
 * Allowance, used, scheduled, what's left; this year's pay lines; and "Add
 * vacation" for recording union picks and approved office requests.
 *
 * ⚠️ **FOUR NUMBERS, NOT TWO, AND COLLAPSING THEM IS THE OBVIOUS MISTAKE.**
 * "Used" and "scheduled" are different facts: a week on the calendar for
 * December has not been paid, and somebody deciding whether to approve another
 * week needs to see both. A single "taken" figure hides exactly the thing the
 * pane is opened to answer.
 *
 * ⚠️ **"NOT KNOWN" IS A STATE AND IT IS THE ONE EVERYBODY IS IN TODAY.** The
 * allowance comes from years of service, and `hire_date` is NULL for every
 * payroll employee — the column shipped with `r239` and nobody has measured a
 * hire date for anyone. So `remaining_hours` is `null`, and the pane says what
 * is missing rather than rendering "0 left", which is a different and false
 * claim.
 *
 * ⚠️ **AND THE PRIOR-YEAR COVERAGE SENTENCE IS ALWAYS SHOWN FOR A UNION
 * MEMBER.** "Registers cover 2025-11-13 – 2025-12-31 only" is the whole reason
 * an entered figure is needed, and it is measured rather than asserted — the
 * server reads it off the imported checks.
 */

import { useCallback, useEffect, useState } from "react"

import {
  CHECKING_SUFFIX,
  didWriteLand,
  failureText,
  gotNoReply,
} from "@/lib/payroll/failure"
import {
  addVacation,
  getVacationYear,
  setPriorYear,
  type VacationYear,
} from "@/lib/payroll/focus-api"

import { statusDate } from "./EmployeeStatusRow"

const hoursText = (v: string | null) => {
  if (v == null) return "—"
  return /^-?\d+(\.\d+)?$/.test(v) ? String(Number(v)) : v
}

function Row({ label, value, note }: {
  label: string
  value: React.ReactNode
  note?: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-border-subtle py-2 last:border-0">
      <div className="flex items-baseline justify-between gap-4">
        <span className="text-body-sm text-content-muted">{label}</span>
        <span className="text-body-sm text-content-strong">{value}</span>
      </div>
      {note ? <span className="text-caption text-content-muted">{note}</span> : null}
    </div>
  )
}


export function VacationPaneBody({
  employeeId,
  readOnly,
  onOpenPay,
}: {
  employeeId: string
  /** From the Focus dispatcher. Never re-derived here. */
  readOnly: boolean
  /** Opens the vacation pay Focus for one recorded vacation — the pane is one
   *  of its two entrances, the note line being the other. */
  onOpenPay?: (vacationId: string) => void
}) {
  const [data, setData] = useState<VacationYear | null | false>(null)
  const [adding, setAdding] = useState(false)
  const [start, setStart] = useState("")
  const [end, setEnd] = useState("")
  const [hours, setHours] = useState("40")
  const [source, setSource] = useState("")
  const [enteringPrior, setEnteringPrior] = useState(false)
  const [gross, setGross] = useState("")
  const [priorHours, setPriorHours] = useState("")
  const [priorSource, setPriorSource] = useState("")
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setData(await getVacationYear(employeeId))
    } catch {
      setData(false)
    }
  }, [employeeId])

  useEffect(() => {
    let live = true
    setData(null)
    setMessage(null)
    getVacationYear(employeeId)
      .then((d) => live && setData(d))
      .catch(() => live && setData(false))
    return () => {
      live = false
    }
  }, [employeeId])

  async function save(what: "vacation" | "prior") {
    setBusy(true)
    setMessage(null)
    try {
      if (what === "vacation") {
        await addVacation(employeeId, {
          startDate: start, endDate: end, hours, source,
        })
        setAdding(false)
        setSource("")
      } else {
        const d = data as VacationYear
        await setPriorYear(employeeId, d.prior_year.year, {
          gross, hours: priorHours, source: priorSource,
        })
        setEnteringPrior(false)
        setPriorSource("")
      }
      await load()
    } catch (err) {
      // ⚠️ A WRITE WHOSE REPLY NEVER ARRIVED MAY HAVE LANDED — a CORS
      // rejection, a timeout or a reset on the RETURN leg all look like this.
      if (gotNoReply(err)) {
        setMessage(failureText(err) + CHECKING_SUFFIX)
        const verdict = await didWriteLand(
          () => getVacationYear(employeeId),
          (d) =>
            what === "vacation"
              ? d.vacations.some((v) => v.start_date === start)
              : d.prior_year.basis === "entered",
        )
        setMessage(
          verdict === "landed"
            ? "It did save — the reply was the only thing lost."
            : verdict === "did-not-land"
              ? "It did not save. Nothing was recorded; try again."
              : "Still unknown — the check could not reach the server either. "
                + "Re-open this pane before recording it again, so it is not "
                + "recorded twice.",
        )
        await load()
      } else {
        setMessage(failureText(err))
      }
    } finally {
      setBusy(false)
    }
  }

  if (data === null) {
    return <p className="py-6 text-body-sm text-content-muted">Loading the vacation year…</p>
  }
  if (data === false) {
    return (
      <p className="py-6 text-body-sm text-status-error" data-testid="vacation-failed">
        The vacation year could not be loaded. Nothing has been changed.
      </p>
    )
  }

  const ent = data.entitlement
  const prior = data.prior_year
  const input =
    "mt-0.5 block w-full rounded-lg border border-border-subtle bg-surface-elevated px-2 py-1 text-body-sm text-content-strong"

  return (
    <div data-testid="vacation-pane">
      <Row
        label="Allowance"
        value={
          <span data-testid="vacation-allowance">
            {ent.hours !== null ? `${hoursText(ent.hours)} h` : "Not known"}
          </span>
        }
        note={
          ent.hours !== null
            ? ent.basis === "override"
              ? `Set by hand — ${ent.source}`
              : `${ent.years_of_service} years of service`
            : ent.why_not
        }
      />
      <Row label="Used" value={`${hoursText(data.used_hours)} h`} />
      <Row label="Scheduled" value={`${hoursText(data.scheduled_hours)} h`} />
      <Row
        label="Left"
        value={
          <span data-testid="vacation-remaining">
            {/* ⚠️ "NOT KNOWN" IS NOT "0 LEFT". Collapsing them would tell
                somebody they have no vacation when in fact nobody has entered
                a hire date. */}
            {data.remaining_hours !== null
              ? `${hoursText(data.remaining_hours)} h`
              : "Not known"}
          </span>
        }
      />

      {/* ── the vacations themselves ──────────────────────────────────── */}
      <div className="pt-3">
        <span className="text-caption text-content-muted">
          {data.year} vacations
        </span>
        {data.vacations.length === 0 ? (
          <p className="py-2 text-body-sm text-content-muted">
            None recorded for {data.year}. Union picks and approved requests are
            added here.
          </p>
        ) : (
          <ul className="mt-1 space-y-1" data-testid="vacation-list">
            {data.vacations.map((v) => (
              <li key={v.id} className="text-caption text-content-muted">
                <span className="text-content-strong">
                  {statusDate(v.start_date)} – {statusDate(v.end_date)}
                </span>{" "}
                · {hoursText(v.hours)} h · {v.status}
                {onOpenPay && v.status === "scheduled" ? (
                  <button
                    type="button"
                    data-testid={`vacation-open-pay-${v.id}`}
                    className="ml-2 rounded border border-border-subtle bg-surface-elevated px-2 py-0.5 text-caption text-content-strong hover:border-border-strong"
                    onClick={() => onOpenPay(v.id)}
                  >
                    Pay
                  </button>
                ) : null}
                <span className="block">{v.source}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* ── this year's pay lines ─────────────────────────────────────── */}
      {data.payments.length > 0 ? (
        <div className="pt-3">
          <span className="text-caption text-content-muted">
            {data.year} vacation pay
          </span>
          <ul className="mt-1 space-y-1" data-testid="vacation-payments">
            {data.payments.map((p) => (
              <li key={p.id} className="text-caption text-content-muted">
                <span className="text-content-strong">
                  {statusDate(p.week_end_date)}
                </span>{" "}
                · Vac ${p.vac_pay}
                {/* ⚠️ TWO LINES, shown as two. The register pays them
                    separately and a reader reconciles them line by line. */}
                {p.vac_bonus !== "0.00" ? ` · VacBonus $${p.vac_bonus}` : ""}
                {p.part_count > 1 ? ` · part ${p.part_index} of ${p.part_count}` : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* ── the prior year, for a union member ────────────────────────── */}
      {data.union_member ? (
        <div className="border-t border-border-subtle pt-3">
          <span className="text-caption text-content-muted">
            {prior.year} earnings, for the rate
          </span>
          <p className="text-body-sm text-content-strong" data-testid="vacation-prior">
            {prior.usable
              ? `$${prior.gross} over ${hoursText(prior.hours)} h`
              : "Not available"}
          </p>
          {/* ⚠️ THE COVERAGE SENTENCE, ALWAYS. It is measured off the imported
              checks and is what makes "not available" actionable. */}
          <span className="block text-caption text-content-muted">
            {prior.basis === "entered"
              ? `Entered — ${prior.source}`
              : prior.coverage}
          </span>
          {!readOnly && !enteringPrior && !prior.usable ? (
            <button
              type="button"
              data-testid="vacation-enter-prior"
              className="mt-1 rounded border border-border-subtle bg-surface-elevated px-2 py-0.5 text-caption text-content-strong hover:border-border-strong"
              onClick={() => {
                setGross("")
                setPriorHours("")
                setPriorSource("")
                setMessage(null)
                setEnteringPrior(true)
              }}
            >
              Enter {prior.year} figures
            </button>
          ) : null}
          {enteringPrior ? (
            <div className="mt-2 space-y-2" data-testid="vacation-prior-editor">
              <label className="block text-caption text-content-muted">
                {prior.year} gross
                <input data-testid="vacation-prior-gross" className={input}
                       value={gross} onChange={(e) => setGross(e.target.value)} />
              </label>
              <label className="block text-caption text-content-muted">
                {prior.year} hours
                <input data-testid="vacation-prior-hours" className={input}
                       value={priorHours}
                       onChange={(e) => setPriorHours(e.target.value)} />
              </label>
              <label className="block text-caption text-content-muted">
                {/* ⚠️ REQUIRED. A typed figure whose origin nobody can name is
                    one nobody can check — and this sets a year's rate. */}
                Source — where this came from
                <input data-testid="vacation-prior-source" className={input}
                       placeholder="e.g. 2025 Vac Calc tab"
                       value={priorSource}
                       onChange={(e) => setPriorSource(e.target.value)} />
              </label>
              <div className="flex gap-2">
                <button
                  type="button"
                  data-testid="vacation-prior-save"
                  disabled={busy || !gross || !priorHours || !priorSource.trim()}
                  className="rounded-lg bg-accent px-3 py-1.5 text-body-sm text-content-on-accent disabled:opacity-50"
                  onClick={() => save("prior")}
                >
                  {busy ? "Saving…" : "Save figures"}
                </button>
                <button
                  type="button"
                  data-testid="vacation-prior-cancel"
                  disabled={busy}
                  className="rounded-lg border border-border-subtle bg-surface-elevated px-3 py-1.5 text-body-sm text-content-strong"
                  onClick={() => setEnteringPrior(false)}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {/* ── add a vacation ────────────────────────────────────────────── */}
      {readOnly ? (
        <span className="mt-2 block text-caption text-content-muted">
          Recording a vacation needs{" "}
          <span className="font-mono text-caption">payroll.approve</span>.
        </span>
      ) : adding ? (
        <div className="mt-3 space-y-2 border-t border-border-subtle pt-3"
             data-testid="vacation-add-editor">
          <label className="block text-caption text-content-muted">
            First day
            <input type="date" data-testid="vacation-start" className={input}
                   value={start} onChange={(e) => setStart(e.target.value)} />
          </label>
          <label className="block text-caption text-content-muted">
            Last day
            <input type="date" data-testid="vacation-end" className={input}
                   value={end} onChange={(e) => setEnd(e.target.value)} />
          </label>
          <label className="block text-caption text-content-muted">
            Hours
            <input data-testid="vacation-hours" className={input}
                   value={hours} onChange={(e) => setHours(e.target.value)} />
          </label>
          <label className="block text-caption text-content-muted">
            Source — a union pick, or an approved request
            <input data-testid="vacation-source" className={input}
                   placeholder="e.g. union pick, posted 2026-01-15"
                   value={source} onChange={(e) => setSource(e.target.value)} />
          </label>
          <div className="flex gap-2">
            <button
              type="button"
              data-testid="vacation-add-save"
              disabled={busy || !start || !end || !hours || !source.trim()}
              className="rounded-lg bg-accent px-3 py-1.5 text-body-sm text-content-on-accent disabled:opacity-50"
              onClick={() => save("vacation")}
            >
              {busy ? "Recording…" : "Record vacation"}
            </button>
            <button
              type="button"
              data-testid="vacation-add-cancel"
              disabled={busy}
              className="rounded-lg border border-border-subtle bg-surface-elevated px-3 py-1.5 text-body-sm text-content-strong"
              onClick={() => setAdding(false)}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          data-testid="vacation-add"
          className="mt-3 rounded-lg border border-border-subtle bg-surface-elevated px-3 py-1 text-body-sm text-content-strong hover:border-border-strong"
          onClick={() => {
            setMessage(null)
            setAdding(true)
          }}
        >
          Add vacation
        </button>
      )}

      {message ? (
        <p className="mt-2 text-caption text-status-error"
           data-testid="vacation-message">
          {message}
        </p>
      ) : null}
    </div>
  )
}
