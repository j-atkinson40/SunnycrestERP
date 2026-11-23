/**
 * The three pane bodies: the week's union dues, one member's working, and one
 * person's timecard.
 *
 * ⚠️ **EVERY FIGURE HERE IS READ-ONLY** — corrections are made only through
 * the Focus, so a pane can never be the thing that changed a number.
 *
 * ⚠️ **ONE EXCEPTION, ADDED 2026-11-21: THE STATUS ROW.** This header said
 * "all read-only" and is corrected rather than left standing, because a
 * docstring that contradicts a write in its own file is the stale-prose defect
 * this repo keeps catching. `EmployeeStatusRow` writes one thing, and the rule
 * above still holds as written: a status is not a figure and is not
 * week-scoped — it is a fact about a person that outlives every week in the
 * pane. It does move the R-115's line 1, which the row says on its face.
 * James ruled the row belongs in these two panes on 2026-11-21.
 *
 * ⚠️ EVERY ONE HAS A WRITTEN EMPTY STATE. Never a blank table: "nothing here"
 * and "this did not load" are different facts and a reader must be able to
 * tell them apart without opening a console.
 */

import { useEffect, useState } from "react"

import {
  getMemberPane,
  getTimecardPane,
  getUnionDuesPane,
  type MemberPane,
  type TimecardPane,
  type UnionDuesPane,
} from "@/lib/payroll/focus-api"

import { EmployeeStatusRow } from "./EmployeeStatusRow"


function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-6 text-body-sm text-content-muted">{children}</p>
}

function Failed({ what }: { what: string }) {
  return (
    <p className="py-6 text-body-sm text-status-error">
      {what} could not be loaded. Nothing has been changed — try again, and if
      it keeps happening the week may need re-calculating.
    </p>
  )
}

/** `null` = still loading, `false` = failed. Three states, never two: a
 *  failure rendered as "nothing here" is the absent-signal problem. */
function usePane<T>(load: () => Promise<T>, deps: unknown[]) {
  const [state, setState] = useState<T | null | false>(null)
  useEffect(() => {
    let live = true
    setState(null)
    load()
      .then((d) => live && setState(d))
      .catch(() => live && setState(false))
    return () => {
      live = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return state
}

function Row({
  label,
  value,
  note,
}: {
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

const money = (v: string | null) => (v == null ? "—" : `$${v}`)

/** ⚠️ Hours and rates arrive at 4 decimals because the columns are
 *  `Numeric(10,4)`. Rendered raw they read "40.0000 reg · 0.0000 personal",
 *  which is noise on a screen whose whole job is being read quickly. Display
 *  only — nothing posted back is trimmed. */
const num = (v: string | null) => {
  if (v == null) return "—"
  return /^-?\d+(\.\d+)?$/.test(v) ? String(Number(v)) : v
}
const hours = num

/** The binding component in words. `binds` is "a", "b" or "c"; "a binds" reads
 *  as a sentence fragment to anyone who has not read the engine. */
const BINDS: Record<string, string> = {
  a: "the percentage binds",
  b: "the cap binds",
  c: "the per-hour amount binds",
}


export function UnionDuesPaneBody({ weekId }: { weekId: string }) {
  const d = usePane<UnionDuesPane>(() => getUnionDuesPane(weekId), [weekId])
  if (d === null) return <Empty>Loading the week&rsquo;s dues…</Empty>
  if (d === false) return <Failed what="The week's dues" />
  if (d.members.length === 0) {
    return (
      <Empty>
        No members on week {d.week_number} yet. Dues appear once the week has
        been calculated from its hours.
      </Empty>
    )
  }
  return (
    <div>
      <p className="pb-2 text-caption text-content-muted">
        {d.members_paying} of {d.members_total} paying · from what Payentry will
        pay
      </p>
      <table className="w-full text-body-sm">
        <thead>
          <tr className="text-micro uppercase tracking-wider text-content-muted">
            <th className="py-1 text-left font-normal">Member</th>
            <th className="py-1 text-right font-normal">Hours</th>
            <th className="py-1 text-right font-normal">Dues</th>
          </tr>
        </thead>
        <tbody>
          {d.members.map((m) => (
            <tr key={m.employee_id} className="border-t border-border-subtle">
              <td className="py-1 text-content-strong">{m.display_name ?? m.file_number}</td>
              <td className="py-1 text-right">{hours(m.dues_hours)}</td>
              <td className="py-1 text-right">{money(m.dues)}</td>
            </tr>
          ))}
          <tr className="border-t border-border-subtle font-medium">
            <td className="py-1.5 text-content-strong">Total</td>
            <td className="py-1.5 text-right">{hours(d.total_dues_hours)}</td>
            <td className="py-1.5 text-right">{money(d.total_dues)}</td>
          </tr>
        </tbody>
      </table>
      <p className="pt-3 text-caption text-content-muted">
        {d.basis.sentence} Today: the lower of {d.basis.percent} of dues wage
        and {d.basis.cap_multiplier} × the cap hours, plus ${d.basis.per_hour} an
        hour. Rules in force from {d.basis.rule_set_effective}.
      </p>
    </div>
  )
}


export function UnionMemberPaneBody({
  weekId,
  employeeId,
  readOnly,
  onOpenTimecard,
  onOpenVacation,
}: {
  weekId: string
  employeeId: string
  /** From the Focus dispatcher, passed down rather than re-derived — the
   *  status row is the one write in this file and obeys the same answer the
   *  surface around it obeys. */
  readOnly: boolean
  onOpenTimecard: () => void
  /** ⚠️ The vacation pane's UNION entrance. The timecard pane carries the
   *  non-union one; James, 2026-11-23, named both. */
  onOpenVacation?: () => void
}) {
  const d = usePane<MemberPane>(
    () => getMemberPane(weekId, employeeId),
    [weekId, employeeId],
  )
  if (d === null) return <Empty>Loading the member…</Empty>
  if (d === false) {
    return (
      <Empty>
        No dues result for this person on week this week. Somebody with no hours
        has no dues row, which is a real answer rather than a problem.
      </Empty>
    )
  }
  return (
    <div>
      <Row
        label="Hours"
        value={hours(d.hours.dues_hours)}
        note={`${num(d.hours.reg)} reg · ${num(d.hours.personal)} personal · ${num(d.hours.ot)} OT`}
      />
      <Row
        label="Dues wage"
        value={money(d.dues_wage)}
        note={
          d.ot_rate_used
            ? // ⚠️ WHICH OT RATE, AND WHETHER IT WAS DERIVED. The week-44
              // investigation turned on this: the workbook's typed OT rates
              // were stale, and the difference was invisible until the rate
              // used was shown next to the figure it produced.
              `OT at $${num(d.ot_rate_used)}${d.ot_rate_derived ? " (1.5× today's rate)" : " (rate on file)"}`
            : undefined
        }
      />
      <Row
        label="Dues this week"
        value={money(d.dues)}
        note={
          d.working.component_a
            ? `lower of ${money(d.working.component_a)} and ${money(d.working.component_b)} (cap), plus ${money(d.working.component_c)}${d.working.binds && BINDS[d.working.binds] ? ` · ${BINDS[d.working.binds]}` : ""}`
            : "no hours, no dues"
        }
      />
      {d.working.initiation_fee && d.working.initiation_fee !== "0.00" ? (
        <Row label="Initiation fee" value={money(d.working.initiation_fee)} />
      ) : null}
      <Row label="Union member" value={d.union_member ? "Yes" : "No"} />
      <EmployeeStatusRow employeeId={employeeId} readOnly={readOnly} />
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          data-testid="pane-open-timecard"
          className="rounded-lg border border-border-subtle bg-surface-elevated px-3 py-1.5 text-body-sm text-content-strong hover:border-border-strong"
          onClick={onOpenTimecard}
        >
          Timecard
        </button>
        {onOpenVacation ? (
          <button
            type="button"
            data-testid="pane-open-vacation"
            className="rounded-lg border border-border-subtle bg-surface-elevated px-3 py-1.5 text-body-sm text-content-strong hover:border-border-strong"
            onClick={onOpenVacation}
          >
            Vacation
          </button>
        ) : null}
      </div>
    </div>
  )
}


export function TimecardPaneBody({
  weekId,
  empId,
  readOnly,
  onOpenVacation,
  corrections,
}: {
  weekId: string
  empId: string
  /** From the Focus dispatcher, passed down rather than re-derived. */
  readOnly: boolean
  /** ⚠️ The vacation pane's NON-UNION entrance. A non-union person is reached
   *  through the timecard, never through the union member pane. */
  onOpenVacation?: () => void
  /** From the Focus, so a correction is labelled with who, when and why
   *  without this pane needing a second endpoint for it. */
  corrections: { work_date: string; hours: string; reason: string; entered_at: string | null }[]
}) {
  const d = usePane<TimecardPane>(
    () => getTimecardPane(weekId, empId),
    [weekId, empId],
  )
  if (d === null) return <Empty>Loading the timecard…</Empty>
  if (d === false) return <Failed what="The timecard" />

  /* ⚠️ THE STATUS ROW RENDERS EVEN WHEN THERE ARE NO HOURS, and that is the
     case it matters in. Somebody with no hours is exactly the person whose
     status wants recording — they left, or they are on comp — so a row that
     appeared only alongside a populated timecard would be missing from every
     instance of the situation it exists for. This pane is the non-union
     entrance; the union one is `UnionMemberPaneBody`. */
  const statusRow = (
    <>
      <EmployeeStatusRow employeeId={empId} readOnly={readOnly} />
      {onOpenVacation ? (
        <button
          type="button"
          data-testid="pane-open-vacation-timecard"
          className="my-2 rounded-lg border border-border-subtle bg-surface-elevated px-3 py-1 text-caption text-content-strong hover:border-border-strong"
          onClick={onOpenVacation}
        >
          Vacation
        </button>
      ) : null}
    </>
  )

  if (d.days.length === 0) {
    return (
      <div>
        {statusRow}
        <Empty>
          No hours and no corrections for this person on week {d.week_number}.
          {d.punch_data_present
            ? " There are punches, so the hours may not have reached Payentry's export."
            : " No punch file was loaded for this week either, so there is nothing to compare against."}
        </Empty>
      </div>
    )
  }
  const byDate = new Map<string, typeof corrections>()
  for (const c of corrections) {
    byDate.set(c.work_date, [...(byDate.get(c.work_date) ?? []), c])
  }
  return (
    <div>
      {statusRow}
      {d.days.map((day) => (
        <div
          key={`${day.work_date}:${day.pay_type}`}
          className="border-b border-border-subtle py-2 last:border-0"
        >
          <div className="flex items-baseline justify-between gap-4">
            <span className="text-body-sm text-content-muted">
              {day.work_date} · {day.pay_type}
            </span>
            <span className="text-body-sm text-content-strong">
              {day.total_hours}
            </span>
          </div>
          {/* ⚠️ PARSED AND CORRECTED SHOWN APART. "Payentry said 8 and Susan
              added 2.25" is the fact a reviewer needs; a merged 10.25 hides
              who decided it. */}
          {day.corrected_hours !== "0.0000" && day.corrected_hours !== "0" ? (
            <span className="text-caption text-content-muted">
              Payentry {day.parsed_hours} · corrected {day.corrected_hours}
              {(byDate.get(day.work_date) ?? []).map((c, i) => (
                <span key={i} className="block">
                  {c.reason}
                  {c.entered_at ? ` · ${c.entered_at.slice(0, 10)}` : ""}
                </span>
              ))}
            </span>
          ) : null}
        </div>
      ))}
      <div className="flex items-baseline justify-between gap-4 border-t border-border-subtle py-2 font-medium">
        <span className="text-body-sm text-content-strong">Total</span>
        <span className="text-body-sm text-content-strong">
          {d.total_parsed}
          {d.total_corrected !== "0.0000" && d.total_corrected !== "0"
            ? ` + ${d.total_corrected} corrected`
            : ""}
        </span>
      </div>
      <p className="pt-2 text-caption text-content-muted">
        {d.source}.{" "}
        {d.punch_data_present
          ? "Punches were loaded for this week."
          : "No punch file was loaded for this week."}{" "}
        Read-only — corrections are made in the Focus.
      </p>
    </div>
  )
}
