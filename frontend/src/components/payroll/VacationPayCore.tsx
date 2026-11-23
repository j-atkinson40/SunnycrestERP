/**
 * The vacation pay Focus — Payroll 5c.
 *
 * Three steps, in the order James gave them:
 *   1. how to pay it — 1, 2 or 3 checks
 *   2. the working
 *   3. approve
 *
 * ⚠️ **THE WORKING IS THE POINT, NOT THE TOTAL.** A vacation payment is
 * reconciled against the register line by line: `Vac` and `VacBonus` are two
 * separately-rounded lines (spec §3.1), and the rate they come from is
 * TRUNCATED to four decimals — which is the whole of the 975.47 → 975.46
 * correction. A screen showing only "$975.46" would be unreconcilable, which
 * is exactly what the superseded combined form was.
 *
 * ⚠️ **AND IT SHOWS WHERE THE RATE CAME FROM.** Prior-year gross over hours,
 * plus the increment, truncated — with the truncation's own rulebook key named
 * beside it, because it became effective-dated in this release and a figure
 * should be able to say which rule made it.
 *
 * ⚠️ **READ-ONLY IS THE LAYER'S ANSWER.** `readOnly` arrives from the
 * dispatcher keyed on `editPermission: "payroll.approve"`. A core that
 * re-derived it would look identical to one whose user happens to hold it.
 */

import { useCallback, useEffect, useState } from "react"

import {
  CHECKING_SUFFIX,
  didWriteLand,
  failureText,
  gotNoReply,
} from "@/lib/payroll/failure"
import {
  approveVacationPay,
  getVacationPay,
  type VacationPayView,
} from "@/lib/payroll/focus-api"

import { statusDate } from "./panes/EmployeeStatusRow"

/** The week a vacation's pay lands on: the Saturday ending its last week. */
export function weekEndFor(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso.trim())
  if (!m) return iso
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
  // ⚠️ LOCAL CONSTRUCTION, never `new Date(iso)` — a bare date parsed as UTC
  // midnight reads back a day early west of Greenwich, which shipped once as
  // "Due Nov 15" rendering "Nov 14".
  const toSaturday = (6 - d.getDay() + 7) % 7
  d.setDate(d.getDate() + toSaturday)
  const p = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

export function VacationPayCore({
  readOnly,
  scope,
}: {
  focusId: string
  config: unknown
  readOnly: boolean
  scope: Record<string, unknown>
}) {
  const vacationId =
    (typeof scope.vacation_id === "string" && scope.vacation_id) ||
    new URLSearchParams(window.location.search).get("vacation_id") ||
    ""

  const [checks, setChecks] = useState(1)
  const [view, setView] = useState<VacationPayView | null | false>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [approved, setApproved] = useState(false)

  const load = useCallback(async (n: number) => {
    try {
      setView(await getVacationPay(vacationId, n))
    } catch {
      setView(false)
    }
  }, [vacationId])

  useEffect(() => {
    if (!vacationId) return
    let live = true
    setView(null)
    getVacationPay(vacationId, checks)
      .then((d) => live && setView(d))
      .catch(() => live && setView(false))
    return () => {
      live = false
    }
  }, [vacationId, checks])

  const Shell = ({ children }: { children: React.ReactNode }) => (
    <div
      data-testid="vacation-pay-core"
      className="space-y-6 rounded-xl bg-surface-base p-6 text-content-base"
    >
      {children}
    </div>
  )

  if (!vacationId) {
    return (
      <Shell>
        <p className="text-body-sm text-status-error" data-testid="vacation-pay-unscoped">
          No vacation was passed, so nothing is shown rather than a vacation
          that might be the wrong one.
        </p>
      </Shell>
    )
  }
  if (view === null) {
    return <Shell><p className="text-body-sm text-content-muted">Working out the pay…</p></Shell>
  }
  if (view === false) {
    return (
      <Shell>
        <p className="text-body-sm text-status-error">
          This vacation could not be read from the server. Nothing has been
          changed by opening it.
        </p>
      </Shell>
    )
  }

  const v = view.vacation
  const w = view.working
  const weekEnd = weekEndFor(v.end_date)

  async function approve() {
    setBusy(true)
    setMessage(null)
    try {
      await approveVacationPay(vacationId, { checks, weekEndDate: weekEnd })
      setApproved(true)
      setMessage(null)
      await load(checks)
    } catch (err) {
      if (gotNoReply(err)) {
        setMessage(failureText(err) + CHECKING_SUFFIX)
        const verdict = await didWriteLand(
          () => getVacationPay(vacationId, checks),
          (d) => d.vacation.status === "paid",
        )
        setMessage(
          verdict === "landed"
            ? "It did approve — the reply was the only thing lost."
            : verdict === "did-not-land"
              ? "It did not approve. Nothing was written; try again."
              : "Still unknown — the check could not reach the server either. "
                + "Re-open this before approving again, so the week is not "
                + "paid twice.",
        )
        await load(checks)
      } else {
        setMessage(failureText(err))
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <Shell>
      <header>
        <p className="text-caption uppercase tracking-wide text-content-muted">
          Vacation pay
        </p>
        <h2 className="text-h3 text-content-strong" data-testid="vacation-pay-dates">
          {statusDate(v.start_date)} – {statusDate(v.end_date)}
        </h2>
        <p className="text-body-sm text-content-muted">
          {Number(v.hours)} hours · {v.source} · {v.status}
        </p>
      </header>

      {/* ── 1. how to pay it ──────────────────────────────────────────── */}
      <section aria-label="How to pay it">
        <p className="text-body-sm font-medium text-content-strong">
          How to pay it
        </p>
        <div className="mt-2 flex gap-2" data-testid="vacation-pay-checks">
          {[1, 2, 3].map((n) => (
            <button
              key={n}
              type="button"
              data-testid={`vacation-pay-checks-${n}`}
              aria-pressed={checks === n}
              disabled={readOnly || approved || v.status === "paid"}
              className={`rounded-lg border px-3 py-1.5 text-body-sm ${
                checks === n
                  ? "border-border-strong bg-surface-elevated text-content-strong"
                  : "border-border-subtle bg-surface-base text-content-muted"
              } disabled:opacity-50`}
              onClick={() => setChecks(n)}
            >
              {n} {n === 1 ? "check" : "checks"}
            </button>
          ))}
        </div>
      </section>

      {/* ── 2. the working ────────────────────────────────────────────── */}
      <section aria-label="The working">
        <p className="text-body-sm font-medium text-content-strong">The working</p>
        {w === null ? (
          <p className="mt-1 text-body-sm text-status-error"
             data-testid="vacation-pay-unavailable">
            {view.unavailable}
          </p>
        ) : (
          <div className="mt-1" data-testid="vacation-pay-working">
            {w.union ? (
              <>
                {/* ⚠️ THE RATE'S DERIVATION, SHOWN. Not "rate 22.5116" alone:
                    where it came from and that it was truncated, because the
                    truncation is the cent. */}
                <p className="text-body-sm text-content-base">
                  ${w.prior_year_gross} over {Number(w.prior_year_hours)} hours
                  gives the average, plus the increment, truncated to{" "}
                  {w.rate_truncate_dp} decimals —{" "}
                  <span className="font-medium text-content-strong"
                        data-testid="vacation-pay-rate">
                    ${w.rate}
                  </span>{" "}
                  an hour.
                </p>
                <p className="mt-1 text-body-sm text-content-base">
                  The year&rsquo;s bonus on {Number(w.entitlement_hours)} hours
                  of allowance is ${w.bonus_year_total}, paid in equal parts —
                  one with each vacation payment.
                </p>
              </>
            ) : (
              <p className="text-body-sm text-content-base">
                Regular rate ${w.rate} an hour.{" "}
                {/* ⚠️ Stated rather than silently absent: a reader should not
                    have to notice the missing line. */}
                <span className="text-content-muted">
                  No bonus — the vacation bonus comes from the union agreement.
                </span>
              </p>
            )}
            <table className="mt-3 w-full text-body-sm" data-testid="vacation-pay-parts">
              <thead>
                <tr className="text-caption uppercase tracking-wide text-content-muted">
                  <th className="py-1 text-left font-normal">Check</th>
                  <th className="py-1 text-right font-normal">Hours</th>
                  <th className="py-1 text-right font-normal">Vac</th>
                  <th className="py-1 text-right font-normal">VacBonus</th>
                </tr>
              </thead>
              <tbody>
                {w.parts.map((p) => (
                  <tr key={p.index} className="border-t border-border-subtle">
                    <td className="py-1 text-content-muted">
                      {w.union && p.count > 1
                        ? `part ${p.index} of ${p.count}`
                        : `${p.index}`}
                    </td>
                    <td className="py-1 text-right text-content-strong">
                      {Number(p.hours)}
                    </td>
                    <td className="py-1 text-right text-content-strong">
                      ${p.vac_pay}
                    </td>
                    <td className="py-1 text-right text-content-strong">
                      {p.vac_bonus === "0.00" ? "—" : `$${p.vac_bonus}`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-caption text-content-muted">
              Joins the week ending {statusDate(weekEnd)} as{" "}
              {w.union ? "Vac and VacBonus lines" : "a Vac line"} on
              Payentry&rsquo;s list.
            </p>
          </div>
        )}
      </section>

      {/* ── 3. approve ────────────────────────────────────────────────── */}
      <section aria-label="Approve">
        {v.status === "paid" || approved ? (
          <p className="text-body-sm text-content-strong"
             data-testid="vacation-pay-approved">
            Approved. It is on the week ending {statusDate(weekEnd)}.
          </p>
        ) : readOnly ? (
          <p className="text-body-sm text-content-muted">
            Approving vacation pay needs{" "}
            <span className="font-mono text-caption">payroll.approve</span>.
          </p>
        ) : (
          <button
            type="button"
            data-testid="vacation-pay-approve"
            disabled={busy || w === null}
            className="rounded-lg bg-accent px-4 py-2 text-body-sm text-content-on-accent disabled:opacity-50"
            onClick={approve}
          >
            {busy ? "Approving…" : "Approve"}
          </button>
        )}
      </section>

      {message ? (
        <p className="text-body-sm text-status-error" data-testid="vacation-pay-message">
          {message}
        </p>
      ) : null}
    </Shell>
  )
}
