/**
 * The Payroll page — where a payroll-limited user LANDS.
 *
 * ⚠️ **THIS IS SUSAN'S ENTRANCE TO THE WEEK'S WORK, THOUGH NOT WHERE SHE
 * LANDS.** She lands on `/home` — the note — like every user, per James's
 * ruling of 2026-11-16. She reaches this page from "Payroll" in her sidebar,
 * which alongside "Today" is the whole of her nav.
 *
 * It used to say "Payroll review is coming", which after Payroll 5a was false:
 * the Focus existed and she had no way to reach it from here.
 *
 * ⚠️ An earlier version of this comment said `landingRouteForAreas` sends an
 * area-limited user to their area. That function was DELETED on 2026-11-16 —
 * it never ran, and the ruling above is the behaviour.
 *
 * ⚠️ **READ FROM THE PAYROLL ENDPOINTS, NOT FROM THE NOTE'S PROSE.** The note
 * is DIFFERENTIAL — its composition gate withholds a non-prompt whose digest
 * matches what it last said, which is correct for a note and wrong for a
 * landing page. Sourced from the note, this page would be full on the first
 * visit of the day and empty on every reload after it.
 *
 * Every line opens the weekly payroll Focus, scoped to its week.
 */

import { useEffect, useState } from "react"
import { Link } from "react-router-dom"

import apiClient from "@/lib/api-client"
import {
  getCurrentWeek,
  getWeekFocus,
  type CurrentWeek,
  type WeekFocus,
} from "@/lib/payroll/focus-api"

interface WeekRow {
  id: string
  week_number: number
  week_end_date: string
  check_date: string
  status: string
}

/** `null` = loading, `false` = could not load. Three states, never two: a
 *  failure rendered as "nothing here" is the absent-signal problem, and on
 *  this page it would read as "payroll has not started". */
type Loaded<T> = T | null | false

function focusHref(weekId: string) {
  return `/home?focus=weekly-payroll&week_id=${encodeURIComponent(weekId)}`
}

/** ⚠️ **BY WEEK END, FOR A WEEK THAT MAY HAVE NO ROW.** The id form above
 *  cannot address the week Susan is about to upload, because the row is
 *  created by that upload. */
function pendingHref(weekEnd: string) {
  return `/home?focus=weekly-payroll&week_end=${encodeURIComponent(weekEnd)}`
}

export default function PayrollHome() {
  const [weeks, setWeeks] = useState<Loaded<WeekRow[]>>(null)
  const [current, setCurrent] = useState<Loaded<WeekFocus>>(null)
  /** The week being worked today, row or no row. Fetched unconditionally —
   *  it is the one read that answers before the first upload. */
  const [thisWeek, setThisWeek] = useState<Loaded<CurrentWeek>>(null)

  useEffect(() => {
    let live = true
    getCurrentWeek()
      .then((w) => live && setThisWeek(w))
      .catch(() => live && setThisWeek(false))
    apiClient
      .get<{ weeks: WeekRow[] }>("/payroll-reports/weeks")
      .then((r) => {
        if (!live) return
        const w = r.data.weeks ?? []
        setWeeks(w)
        if (w.length === 0) {
          setCurrent(false)
          return
        }
        // The dues total for the most recent week. A 403 here is the data
        // switch being off, which the empty state below says plainly rather
        // than rendering as a failure.
        getWeekFocus(w[0].id)
          .then((f) => live && setCurrent(f))
          .catch(() => live && setCurrent(false))
      })
      .catch(() => live && setWeeks(false))
    return () => {
      live = false
    }
  }, [])

  // `weeks` truthy already excludes null and false; a further `!== false`
  // is redundant and TypeScript says so.
  const lastApproved = weeks
    ? weeks.find((w) => w.status === "approved" && w.id !== weeks[0]?.id)
    : undefined

  return (
    <div className="space-y-6 p-6" data-testid="payroll-home">
      <header className="space-y-1">
        <h1 className="text-h1 text-content-strong">Payroll</h1>
        <p className="text-body text-content-muted">Weekly union dues review</p>
      </header>

      <section
        aria-label="This week"
        data-testid="payroll-this-week"
        className="max-w-reading rounded-base border border-border-subtle bg-surface-elevated p-6 shadow-level-1"
      >
        {weeks === null ? (
          <p className="text-body text-content-muted">Loading the week…</p>
        ) : weeks === false ? (
          <p className="text-body text-status-error">
            The payroll weeks could not be loaded. Nothing has been changed —
            try again, and if it keeps happening payroll data may not be
            switched on for this company yet.
          </p>
        ) : weeks.length === 0 ? (
          // ⚠️ **THIS USED TO BE A DEAD END, AND IT WAS THE WHOLE BLOCKER.**
          // The old copy said "no week, so no Focus to open and no link is
          // offered — a link that opened nothing would be worse than none."
          // That reasoning was right about an id-addressed Focus and wrong
          // about the situation: the link now carries the week END, which the
          // calendar knows before any row exists, and the Focus it opens
          // carries the upload card that creates the row.
          thisWeek === null ? (
            <p className="text-body text-content-muted">Working out this week…</p>
          ) : thisWeek === false ? (
            <>
              <h2 className="text-h4 text-content-strong">No payroll weeks yet</h2>
              <p className="mt-2 text-body text-content-muted">
                This week could not be read from the server, so no link is
                offered rather than one that might open the wrong week.
              </p>
            </>
          ) : (
            <>
              <h2 className="text-h4 text-content-strong">
                Week {thisWeek.week_number}
              </h2>
              <p className="mt-1 text-caption text-content-muted">
                {thisWeek.week_start_date} to {thisWeek.week_end_date} · checks
                dated {thisWeek.check_date}
              </p>
              <p className="mt-3 text-body text-content-base">
                No hours yet.
              </p>
              <Link
                data-testid="upload-this-week"
                to={pendingHref(thisWeek.week_end_date)}
                className="mt-3 inline-block text-body-sm text-steel underline-offset-2 hover:underline"
              >
                Upload Employee Hours
              </Link>
            </>
          )
        ) : (
          <>
            <h2 className="text-h4 text-content-strong">
              Week {weeks[0].week_number}
            </h2>
            <p className="mt-1 text-caption text-content-muted">
              week ending {weeks[0].week_end_date} · checks dated{" "}
              {weeks[0].check_date} · {weeks[0].status}
            </p>
            <p className="mt-3 text-body text-content-base">
              {current && current.dues.total ? (
                <>
                  Dues come to{" "}
                  <span className="text-content-strong">
                    ${current.dues.total}
                  </span>{" "}
                  — {current.dues.members_paying} of{" "}
                  {current.dues.members_total} paying.
                </>
              ) : current === null ? (
                "Working out this week's dues…"
              ) : (
                // Reached when the week has no figures yet (hours loaded, not
                // calculated) or the data switch is off. The Focus itself says
                // which, and offers the upload.
                `No hours for week ${weeks[0].week_number} yet.`
              )}
            </p>
            <Link
              data-testid="open-weekly-payroll"
              to={focusHref(weeks[0].id)}
              className="mt-3 inline-block text-body-sm text-steel underline-offset-2 hover:underline"
            >
              {/* ⚠️ "to upload" ONLY when we KNOW there are no figures.
                  While `current` is null the dues are still loading, and the
                  first version said "to upload" during that window — telling
                  Susan the week has no hours a moment before showing her its
                  dues. Loading is not empty. */}
              {current === false
                ? "Open weekly payroll to upload"
                : "Open weekly payroll"}
            </Link>
          </>
        )}
      </section>

      {lastApproved ? (
        <section
          aria-label="Last approved week"
          data-testid="payroll-last-approved"
          className="max-w-reading rounded-base border border-border-subtle bg-surface-elevated p-6 shadow-level-1"
        >
          <h2 className="text-h4 text-content-strong">
            Week {lastApproved.week_number} — approved
          </h2>
          <p className="mt-1 text-caption text-content-muted">
            checks dated {lastApproved.check_date}
          </p>
          <Link
            data-testid="open-last-approved"
            to={focusHref(lastApproved.id)}
            className="mt-3 inline-block text-body-sm text-steel underline-offset-2 hover:underline"
          >
            Open weekly payroll
          </Link>
        </section>
      ) : null}

      {/* ⚠️ The monthly union form belongs here and is 5b's. Deliberately NOT
          stubbed: a line that opened nothing would be worse than its absence,
          and an empty section would read as "no form this month". */}
    </div>
  )
}
