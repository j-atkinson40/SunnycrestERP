/**
 * The weekly payroll Focus — Payroll 5a.
 *
 * One week, in the order Susan works it:
 *   1. no hours yet        → upload Employee Hours (Punch Location optional)
 *   2. what Opas flagged   → one at a time, numbered answers on keys 1/2/3
 *   3. the week            → everyone's hours and dues, then the checks
 *   4. approve             → the list to enter in Payentry
 *   5. after Thursday      → the register, then the items that do not match
 *
 * ⚠️ **READ-ONLY IS THE LAYER'S ANSWER, NOT THIS COMPONENT'S.** `readOnly`
 * arrives from the dispatcher via `useFocusReadOnly(config)`, keyed on
 * `editPermission: "payroll.approve"`. A core that re-derived it would look
 * identical to one whose user happens to hold the permission.
 *
 * ⚠️ Every stage has a written empty state. Never a blank table: "nothing to
 * do" and "this did not load" are different facts.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"

import {
  didWriteLand,
  failureText,
  gotNoReply,
} from "@/lib/payroll/failure"
import { listRegisterImports } from "@/lib/payroll/setup-api"
import {
  approveWeek,
  getCurrentWeek,
  listWeeks,
  getUnionDuesPane,
  postHourCorrection,
  postWeekDecision,
  uploadRegister,
  uploadWeekHours,
  type UnionDuesPane,
  type CurrentWeek,
  type WeekFinding,
  type WeekFocus,
  getWeekFocus,
} from "@/lib/payroll/focus-api"
import {
  TimecardPaneBody,
  UnionDuesPaneBody,
  UnionMemberPaneBody,
} from "./panes/panes"
import { VacationPaneBody } from "./panes/VacationPaneBody"
import {
  PayrollPaneStack,
  type PayrollPaneSpec,
} from "./panes/PayrollPaneStack"


/** The answers offered per finding code, in the order they are numbered.
 *
 * ⚠️ `outcome` values come from the server's declared set (served as
 * `decision_outcomes`); `correct` opens the by-day form instead of posting an
 * outcome directly. A code with no entry here falls back to the generic three,
 * so a new backend flag is answerable on the day it appears rather than
 * rendering as an unanswerable sentence.
 */
interface Answer {
  label: string
  outcome?: string
  opensCorrection?: boolean
}

const ANSWERS: Record<string, Answer[]> = {
  // ⚠️ **KEYED ON THE SERVER'S REAL FLAG CODES.** A first draft used
  // `no_hours`, `missing_lunch` and `probation` — the words from the brief —
  // and NONE of them exists. Every real finding would have fallen through to
  // the generic three, and "Enter hours" would never have appeared. The
  // component test did not catch it because it fed a fabricated code, so the
  // test was green against a fiction. The codes below are read from
  // `app/services/payroll/validation.py`.
  //
  // A union member who is configured and active but absent from the hours
  // export: Stevenson's case, and the one that must not wait.
  configured_member_missing_from_export: [
    { label: "Enter hours", opensCorrection: true },
    { label: "He didn't work", outcome: "not_an_issue" },
    { label: "Leave for now", outcome: "asked" },
  ],
  // Paid something with no hours behind it.
  zero_hours_with_pay: [
    { label: "Enter the hours", opensCorrection: true },
    { label: "The pay is right as it stands", outcome: "settled" },
    { label: "Ask HR One", outcome: "asked" },
  ],
  // In the export but not on the roster — nobody can be paid dues until
  // somebody says who this is.
  in_export_not_configured: [
    { label: "Ask HR One who this is", outcome: "asked" },
    { label: "Not a union job", outcome: "not_an_issue" },
  ],
  missing_rate: [
    { label: "Ask HR One for the rate", outcome: "asked" },
    { label: "Not a union job", outcome: "not_an_issue" },
  ],
  ot_rate_not_one_and_a_half: [
    { label: "The rate on file is right", outcome: "settled" },
    { label: "Ask HR One", outcome: "asked" },
  ],
}

/** Exported for the test that checks every key is a code the server sends. */
export const __ANSWER_CODES__ = Object.keys(ANSWERS)

const GENERIC: Answer[] = [
  { label: "Looked at, correct as it stands", outcome: "settled" },
  { label: "Not a problem", outcome: "not_an_issue" },
  { label: "Asked someone", outcome: "asked" },
]

/** Why the finding is being asked, in one short line. Keyed on code so the
 *  wording is not buried in the server's message. */
const WHY: Record<string, string> = {
  configured_member_missing_from_export:
    "A union member with no hours is usually a missed punch, not a week off — and an unpaid week is the one mistake that cannot wait.",
  zero_hours_with_pay:
    "Pay with no hours behind it means the hours did not land, so the dues calculated from them are wrong too.",
  in_export_not_configured:
    "Somebody is on the hours file who is not on the roster, so nothing can be worked out for them until you say who they are.",
  missing_rate:
    "Without a rate there is no dues wage, so this person's dues cannot be calculated at all.",
  ot_rate_not_one_and_a_half:
    "The overtime rate on file is not 1.5x the regular one. That is allowed, but it changes the dues wage, so it is worth a look.",
  findings_unavailable:
    "The stored dues below are unaffected — only the re-run failed.",
}

/** `40.0000` -> `40`, `7.5000` -> `7.5`. Display only; the stored value and
 *  everything posted back keep every decimal the column carries. */
function trimHours(v: string): string {
  if (!/^-?\d+(\.\d+)?$/.test(v)) return v
  return String(Number(v))
}

const PAY_TYPES = ["REG", "OT1", "PTO", "Sick"] as const


export function WeeklyPayrollCore({
  readOnly,
  scope,
}: {
  focusId: string
  config: unknown
  readOnly: boolean
  scope: Record<string, unknown>
}) {
  // ⚠️ **SCOPE FIRST, THEN THE URL, AND THE FALLBACK IS LOAD-BEARING.**
  //
  // A Focus normally carries its scope in a focus SESSION. A payroll-limited
  // user cannot create one: `/focus` is an unbuilt composed surface, so the
  // area guard refuses `openFocusSession` with a 403 and the context falls
  // back to the registry default — which has no params. The console says
  // "continuing with registry default" and the Focus opens scoped to nothing.
  //
  // So the week is read from the URL when the session could not supply it.
  // Without this the one user the Focus exists for always sees "No week
  // chosen". Found by walking the page as her.
  /**
   * ⚠️ **A WEEK DESCRIPTOR, NOT ONLY AN ID.** The Focus used to open on a
   * `week_id` alone — and that row is created BY the upload whose card lives
   * in this Focus. So a tenant with nothing uploaded could not reach the one
   * screen that would let them upload.
   *
   * `week_end` is the alternative key: a date the calendar can produce before
   * any row exists. When it is supplied and no row is found, the Focus opens
   * on the DESCRIPTOR with the upload card as step 1, and the upload creates
   * the row.
   */
  /** The descriptor for a week with no row yet. `false` = could not be read. */
  const [pending, setPending] = useState<CurrentWeek | null | false>(null)
  /** Set once the upload creates the row, so the Focus switches to the real
   *  week without a reload. */
  const [resolvedId, setResolvedId] = useState<string | null>(null)
  /** ⚠️ **A URL, NOT A SECOND PANE.** The vacation pay Focus is a Focus — it
   *  has its own two entrances (this one and the note line) and its own
   *  read-only answer from the dispatcher. Rendering it inside a pane would
   *  give it neither. */
  const navigate = useNavigate()
  /** ⚠️ **WHETHER THE LAST MESSAGE IS GOOD NEWS, CARRIED WITH IT.** The upload
   *  reports through the same slot as every failure, and that slot is styled
   *  `text-status-error` — so the first successful Employee Hours upload
   *  rendered "Week 44 loaded: 25 people, 708.61 hours." IN RED. A success in
   *  error colour is a sentence that contradicts itself, and the reader
   *  believes the colour.
   *
   *  Defaults to false, so every existing `setError` path keeps reporting as
   *  a failure; only a caller that KNOWS it succeeded says so. */
  const [noticeOk, setNoticeOk] = useState(false)

  const weekEnd = useMemo(() => {
    if (typeof scope.week_end === "string" && scope.week_end) return scope.week_end
    return new URLSearchParams(window.location.search).get("week_end")
  }, [scope.week_end])

  const weekId = useMemo(() => {
    if (resolvedId) return resolvedId
    if (typeof scope.week_id === "string" && scope.week_id) return scope.week_id
    if (typeof window === "undefined") return null
    return new URLSearchParams(window.location.search).get("week_id")
  }, [scope.week_id, resolvedId])

  const [focus, setFocus] = useState<WeekFocus | null | false>(null)
  const [dues, setDues] = useState<UnionDuesPane | null | false>(null)
  const [panes, setPanes] = useState<PayrollPaneSpec[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    // ⚠️ NO ID BUT A WEEK END: ask the server which week that is and whether
    // it has a row yet. `exists === false` is the pre-upload state and is not
    // an error — it is the state the upload card exists for.
    if (!weekId) {
      if (!weekEnd) return
      try {
        // ⚠️ THE WEEK THE CALLER ASKED FOR, not the week it is today.
                const cur = await getCurrentWeek(weekEnd)
        setPending(cur)
        if (cur.week_id) setResolvedId(cur.week_id)
      } catch {
        setPending(false)
      }
      return
    }
    try {
      const [f, d] = await Promise.all([
        getWeekFocus(weekId),
        getUnionDuesPane(weekId).catch(() => null),
      ])
      setFocus(f)
      setDues(d ?? false)
    } catch {
      setFocus(false)
    }
  }, [weekId, weekEnd])

  useEffect(() => {
    void reload()
  }, [reload])

  const closePane = useCallback((key: string) => {
    setPanes((p) => p.filter((q) => q.key !== key))
  }, [])

  const openPane = useCallback((spec: PayrollPaneSpec) => {
    setPanes((p) => (p.some((q) => q.key === spec.key) ? p : [...p, spec]))
  }, [])

  // ⚠️ **A WEEK WITH NO ROW YET — STEP 1 IS THE UPLOAD, AND IT CREATES THE
  // ROW.** This branch is the path that did not exist on 2026-11-17: with the
  // switch on, a register loaded and a roster reconciled, Susan still could
  // not upload hours, because the card was inside a Focus that needed the row
  // the upload makes.
  if (!weekId && weekEnd) {
    if (pending === null) {
      return <Shell><p className="text-body-sm text-content-muted">Working out which week this is…</p></Shell>
    }
    if (pending === false) {
      return (
        <Shell>
          <p className="text-body-sm text-status-error" data-testid="week-unresolved">
            This week could not be read from the server, so nothing is shown
            rather than a week that might be the wrong one. Nothing has been
            changed by opening this.
          </p>
        </Shell>
      )
    }
    return (
      <Shell>
        <div data-testid="pending-week" className="space-y-4">
          <div>
            <h2 className="text-h4 text-content-strong">
              Week {pending.week_number}
            </h2>
            <p className="mt-1 text-caption text-content-muted">
              {pending.week_start_date} to {pending.week_end_date} · checks
              dated {pending.check_date} · Payentry needs it by{" "}
              {new Date(pending.cutoff_at).toLocaleString(undefined, {
                weekday: "long", hour: "numeric", minute: "2-digit",
              })}
            </p>
            {/* The deadline is an ASSUMED rule. A screen that states one
                should be able to say who said so. */}
            <p className="mt-1 text-caption text-content-subtle">
              Cutoff is {pending.cutoff_provenance.status}, not confirmed.
            </p>
          </div>
          <p className="text-body text-content-base">
            No hours for week {pending.week_number} yet. Upload the Employee
            Hours export and the week is created from it.
          </p>
          <UploadCard
            weekNumber={pending.week_number}
            weekEndDate={pending.week_end_date}
            readOnly={readOnly}
            busy={busy}
            setBusy={setBusy}
            onDone={async (msg, ok) => {
              setError(msg)
              setNoticeOk(Boolean(ok))
              // The upload created the row; pick it up without a reload.
              try {
                // ⚠️ THE WEEK THE CALLER ASKED FOR, not the week it is today.
                const cur = await getCurrentWeek(weekEnd)
                if (cur.week_id) setResolvedId(cur.week_id)
                else setPending(cur)
              } catch {
                /* the message above already says what happened */
              }
            }}
          />
          {/* ⚠️ The upload's own words render HERE too. `setError` is read at
              the bottom of the main branch, which this state never reaches —
              so without this the upload would report into a message nobody
              could see, including a refusal. */}
          {error ? (
            <p
              data-testid="focus-error"
              data-ok={noticeOk ? "yes" : "no"}
              className={`text-body-sm ${noticeOk ? "text-content-base" : "text-status-error"}`}
            >
              {error}
            </p>
          ) : null}
        </div>
      </Shell>
    )
  }

  if (!weekId) {
    return (
      <Shell>
        <p className="text-body-sm text-content-muted">
          No week chosen. Open this from the week&rsquo;s line on your home
          note, which carries the week with it.
        </p>
      </Shell>
    )
  }
  if (focus === null) {
    return (
      <Shell>
        <p className="text-body-sm text-content-muted">Loading the week…</p>
      </Shell>
    )
  }
  if (focus === false) {
    return (
      <Shell>
        <p className="text-body-sm text-status-error">
          This week could not be loaded. Nothing has been changed. If payroll
          data is switched off for this company, that is what this looks like.
        </p>
      </Shell>
    )
  }

  const hasHours = dues !== false && dues !== null && dues.members.length > 0
  const decided = new Set(focus.decisions.map((d) => d.finding_key))
  const open = focus.findings.filter((f) => !decided.has(f.key))
  const current = open[0] ?? null

  return (
    <Shell>
      <div className="relative flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto pr-1">
        <header className="flex flex-wrap items-baseline justify-between gap-3">
          <div>
            <p className="text-micro uppercase tracking-wider text-content-muted">
              Weekly payroll
            </p>
            <h2 className="text-h2 text-content-strong">
              Week {focus.week_number}
            </h2>
            <p className="text-caption text-content-muted">
              week ending {focus.week_end_date} · checks dated{" "}
              {focus.check_date} · {focus.status}
            </p>
          </div>
          <button
            type="button"
            data-testid="open-dues-pane"
            className="rounded-lg border border-border-subtle bg-surface-elevated px-3 py-1.5 text-body-sm text-content-strong hover:border-border-strong"
            onClick={() =>
              openPane({
                key: "union-dues",
                title: `Week ${focus.week_number} dues`,
                subtitle: `${focus.dues.members_paying} of ${focus.dues.members_total} paying`,
                body: <UnionDuesPaneBody weekId={weekId} />,
              })
            }
          >
            Union dues{focus.dues.total ? ` · $${focus.dues.total}` : ""}
          </button>
        </header>

        {error ? (
          <p
            data-testid="focus-error"
            data-ok={noticeOk ? "yes" : "no"}
            className={`text-body-sm ${noticeOk ? "text-content-base" : "text-status-error"}`}
          >
            {error}
          </p>
        ) : null}

        {/* ── 1. no hours yet ─────────────────────────────────────────── */}
        {!hasHours ? (
          <UploadCard
            weekNumber={focus.week_number}
            weekEndDate={focus.week_end_date}
            readOnly={readOnly}
            busy={busy}
            onDone={async (msg, ok) => {
              setError(msg)
              setNoticeOk(Boolean(ok))
              await reload()
            }}
            setBusy={setBusy}
          />
        ) : null}

        {/* ── 2. what Opas flagged, one at a time ─────────────────────── */}
        <section aria-label="What Opas flagged" data-testid="findings">
          <SectionHead
            title="What Opas flagged"
            right={
              open.length > 0
                ? `${open.length} to answer`
                : focus.findings.length > 0
                  ? "all answered"
                  : undefined
            }
          />
          {current ? (
            <FindingCard
              finding={current}
              outcomes={focus.decision_outcomes}
              readOnly={readOnly}
              weekId={weekId}
              onAnswered={reload}
              onError={setError}
              openTimecard={(empId) =>
                openPane({
                  key: `timecard-${empId}`,
                  title: `Timecard · ${empId}`,
                  subtitle: `week ${focus.week_number}`,
                  body: (
                    <TimecardPaneBody
                      weekId={weekId}
                      empId={empId}
                      readOnly={readOnly}
                      corrections={focus.corrections.filter(
                        (c) => c.emp_id === empId,
                      )}
                    />
                  ),
                })
              }
            />
          ) : focus.findings.length === 0 ? (
            <Empty>
              Nothing flagged on week {focus.week_number}. Opas checked the
              hours against the register and the roster and found nothing to
              ask about.
            </Empty>
          ) : (
            <Empty>
              Every finding has an answer. They stay listed below so the week
              can be read back later.
            </Empty>
          )}
          {focus.decisions.length > 0 ? (
            <ul className="mt-3 space-y-1" data-testid="answered-findings">
              {focus.decisions.map((d) => (
                <li
                  key={d.finding_key}
                  className="flex items-baseline justify-between gap-3 text-caption text-content-muted"
                >
                  <span className="truncate">{d.finding_key}</span>
                  <span className="text-content-strong">
                    {focus.decision_outcomes[d.outcome] ?? d.outcome}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </section>

        {/* ── 3. the week ─────────────────────────────────────────────── */}
        <section aria-label="The week" data-testid="the-week">
          <SectionHead title="The week" right={focus.status} />
          {dues === false || dues === null ? (
            <Empty>
              The week&rsquo;s figures are not available yet. They appear once
              the hours have been loaded and the week calculated.
            </Empty>
          ) : dues.members.length === 0 ? (
            <Empty>
              No people on week {focus.week_number} yet. Upload the Employee
              Hours file above to start the week.
            </Empty>
          ) : (
            <WeekTable
              dues={dues}
              onOpenMember={(empId, name) =>
                openPane({
                  key: `member-${empId}`,
                  title: name ?? empId,
                  subtitle: `week ${focus.week_number} · union member`,
                  body: (
                    <UnionMemberPaneBody
                      weekId={weekId}
                      employeeId={empId}
                      readOnly={readOnly}
                      onOpenVacation={() =>
                        openPane({
                          key: `vacation-${empId}`,
                          title: `Vacation · ${name ?? empId}`,
                          subtitle: "allowance, picks and pay",
                          body: (
                            <VacationPaneBody
                              employeeId={empId}
                              readOnly={readOnly}
                              onOpenPay={(vid) =>
                                navigate(
                                  `/home?focus=vacation-pay&vacation_id=${vid}`,
                                )
                              }
                            />
                          ),
                        })
                      }
                      onOpenTimecard={() =>
                        openPane({
                          key: `timecard-${empId}`,
                          title: `Timecard · ${name ?? empId}`,
                          subtitle: `week ${focus.week_number}`,
                          body: (
                            <TimecardPaneBody
                              weekId={weekId}
                              empId={empId}
                              readOnly={readOnly}
                              corrections={focus.corrections.filter(
                                (c) => c.emp_id === empId,
                              )}
                            />
                          ),
                        })
                      }
                    />
                  ),
                })
              }
            />
          )}
        </section>

        {/* ── 4. approve, then what to enter in Payentry ──────────────── */}
        <ApproveSection
          focus={focus}
          dues={dues === false ? null : dues}
          readOnly={readOnly}
          openFindings={open.length}
          busy={busy}
          setBusy={setBusy}
          onError={setError}
          onApproved={reload}
        />

        {/* ── 5. after Thursday ──────────────────────────────────────── */}
        <RegisterSection readOnly={readOnly} busy={busy} setBusy={setBusy}
                         onError={setError} />

      </div>

      {/* ⚠️ OUTSIDE THE SCROLLING COLUMN. Inside it, a pane was positioned
          against the scroller and scrolled away with the content — opened from
          a name near the bottom of the week table it was already half off the
          top. The Focus frame does not scroll, so the panes stay where they
          were put. */}
      <PayrollPaneStack panes={panes} onClose={closePane} />
    </Shell>
  )
}


/** The core's own surface.
 *
 * ⚠️ **IT PAINTS ONE, AND THAT IS THE 4.4.2 RULE RATHER THAN A DEPARTURE
 * FROM IT.** The Focus shell is transparent on purpose — "a Focus is a mode,
 * not a modal" — and the same ruling says *each child element provides its
 * own visual weight*. This core never did: it rendered bare text onto
 * `Dialog.Backdrop`'s dimming layer.
 *
 * Measured from a real screenshot, 2026-11-21, before this surface existed:
 *
 *     1.94   "Cutoff is assumed, not confirmed."
 *     3.20   "No hours for week 47 yet. Upload the Employee Hours export…"
 *     3.55   "Week 47"
 *
 * against AA's 4.5:1. The three elements that passed in the same shot —
 * 5.18, 18.05, 19.18 — are all INSIDE `UploadCard`, which paints
 * `bg-surface-elevated`. The card was carrying the rule and the page around
 * it was not, which is as clean a demonstration of the cause as the data
 * offers.
 *
 * ⚠️ **THIS ALONE DOES NOT REACH AA.** "Cutoff is assumed, not confirmed."
 * uses `--content-subtle`, which renders 2.94:1 on the lightest surface the
 * platform has — it improves from 1.94 to 2.94 here and still fails. That
 * token is a separate, approved change to DESIGN_LANGUAGE; the two together
 * are what clear the floor. See DECISIONS 2026-11-21.
 */
function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div
      data-slot="weekly-payroll-core"
      className="relative flex h-full flex-col rounded-xl bg-surface-base px-6 py-5 text-content-base [font-variant-numeric:tabular-nums]"
    >
      {children}
    </div>
  )
}

function SectionHead({ title, right }: { title: string; right?: string }) {
  return (
    <div className="mb-2 flex items-baseline justify-between gap-3 border-b border-border-subtle pb-1">
      <h3 className="text-body font-medium text-content-strong">{title}</h3>
      {right ? (
        <span className="text-micro uppercase tracking-wider text-content-muted">
          {right}
        </span>
      ) : null}
    </div>
  )
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-3 text-body-sm text-content-muted">{children}</p>
}


// ── 1. the upload card ──────────────────────────────────────────────────────

function UploadCard({
  weekNumber,
  weekEndDate,
  readOnly,
  busy,
  setBusy,
  onDone,
}: {
  weekNumber: number
  weekEndDate: string
  readOnly: boolean
  busy: boolean
  setBusy: (b: boolean) => void
  onDone: (message: string | null, ok?: boolean) => void
}) {
  const hours = useRef<HTMLInputElement>(null)
  const punch = useRef<HTMLInputElement>(null)

  return (
    <section
      aria-label="Upload hours"
      data-testid="upload-card"
      className="rounded-xl border border-border-subtle bg-surface-elevated px-4 py-4"
    >
      <h3 className="text-body font-medium text-content-strong">
        No hours for week {weekNumber} yet. Upload Employee Hours
      </h3>
      <p className="mt-1 text-caption text-content-muted">
        Punch Location is optional — the week can be worked without it, and the
        timecards will say so instead of looking empty.
      </p>
      {readOnly ? (
        <p className="mt-3 text-body-sm text-content-muted">
          You can see this week but not load it. Loading hours needs{" "}
          <span className="font-mono text-caption">payroll.upload</span>.
        </p>
      ) : (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <label className="text-body-sm text-content-muted">
            Employee Hours
            <input
              ref={hours}
              type="file"
              accept="application/pdf"
              data-testid="hours-file"
              className="ml-2 text-body-sm"
            />
          </label>
          <label className="text-body-sm text-content-muted">
            Punch Location
            <input
              ref={punch}
              type="file"
              data-testid="punch-file"
              className="ml-2 text-body-sm"
            />
          </label>
          <button
            type="button"
            disabled={busy}
            data-testid="upload-hours"
            className="rounded-lg border border-border-subtle bg-surface-raised px-3 py-1.5 text-body-sm text-content-strong hover:border-border-strong disabled:opacity-50"
            onClick={async () => {
              const f = hours.current?.files?.[0]
              if (!f) {
                onDone("Choose the Employee Hours file first.")
                return
              }
              setBusy(true)
              try {
                const r = await uploadWeekHours({
                  weekNumber,
                  weekEndDate,
                  hoursFile: f,
                  punchFile: punch.current?.files?.[0] ?? null,
                })
                // ⚠️ ONE PLAIN SENTENCE, and the BLOCKING flag wins over the
                // counts. "347 rows loaded" beside an error is a success
                // message covering a failure.
                const blocking = (r.flags ?? []).find(
                  (x) => x.severity === "error",
                )
                // ⚠️ **AND IT SAYS WHAT HAPPENED TO THE PUNCH FILE.** She can
                // attach one; nothing stores it yet. A success sentence that
                // does not mention a file she attached is how somebody comes
                // to believe punches were loaded.
                const punchNote =
                  r.punch_file && !r.punch_file.stored
                    ? ` ${r.punch_file.reason}`
                    : ""
                onDone(
                  blocking
                    ? blocking.message
                    : `Week ${weekNumber} loaded: ${
                        r.summary?.people ?? r.summary?.rows_stored ?? "—"
                      } people, ${r.summary?.hours ?? "—"} hours.${punchNote}`,
                  // ⚠️ A BLOCKING FLAG IS STILL BAD NEWS even though the
                  // request succeeded — the severity follows the OUTCOME, not
                  // the status code.
                  !blocking,
                )
              } catch (err) {
                // ⚠️ **A FOURTH INSTANCE OF THE SAME DEFECT, FOUND BY ASKING
                // THE FILE RATHER THAN THE BUG REPORT.** The ruling named
                // three writes; "The week is unchanged" is the same unknowable
                // claim, on the upload Susan runs every Monday.
                if (!gotNoReply(err)) {
                  onDone(failureText(err))
                } else {
                  const verdict = await didWriteLand(
                    () => listWeeks(),
                    (w) => w.weeks.some((x) => x.week_number === weekNumber),
                  )
                  if (verdict === "landed") {
                    onDone(`No reply reached this page, but week ${weekNumber} IS on the server. Reload to see it; do not upload again.`)
                  } else if (verdict === "did-not-land") {
                    onDone(`No reply reached this page, and week ${weekNumber} is not on the server — it is safe to upload again.`)
                  } else {
                    onDone("No reply from the server, and the follow-up check could not reach it either. Whether the week loaded is unknown; do not upload again until it responds.")
                  }
                }
              } finally {
                setBusy(false)
              }
            }}
          >
            Upload
          </button>
        </div>
      )}
    </section>
  )
}


// ── 2. one finding at a time ────────────────────────────────────────────────

function FindingCard({
  finding,
  outcomes,
  readOnly,
  weekId,
  onAnswered,
  onError,
  openTimecard,
}: {
  finding: WeekFinding
  outcomes: Record<string, string>
  readOnly: boolean
  weekId: string
  onAnswered: () => Promise<void> | void
  onError: (m: string | null) => void
  openTimecard: (empId: string) => void
}) {
  const answers = ANSWERS[finding.code] ?? GENERIC
  const [correcting, setCorrecting] = useState(false)

  const answer = useCallback(
    async (a: Answer) => {
      if (readOnly) return
      if (a.opensCorrection) {
        setCorrecting(true)
        return
      }
      if (!a.outcome) return
      try {
        await postWeekDecision(weekId, finding.key, a.outcome, a.label)
        onError(null)
        await onAnswered()
      } catch (err) {
        if (!gotNoReply(err)) {
          // The server answered. Its words beat any sentence written here.
          onError(failureText(err))
          return
        }
        // ⚠️ NO REPLY, SO WHETHER THE ANSWER WAS RECORDED IS UNKNOWN AND WE
        // ASK THE SERVER. This used to say "Nothing has been changed", which
        // it could not know — and a re-answer on a false "nothing happened"
        // supersedes a decision that was already stored.
        const verdict = await didWriteLand(
          () => getWeekFocus(weekId),
          (f) => f.decisions.some((d) => d.finding_key === finding.key),
        )
        if (verdict === "landed") {
          onError("No reply reached this page, but the answer WAS recorded. Nothing to redo.")
          await onAnswered()
        } else if (verdict === "did-not-land") {
          onError("No reply reached this page, and the answer is not on the server — answer it again.")
        } else {
          onError("No reply from the server, and the follow-up check could not reach it either. Whether the answer was recorded is unknown; do not answer again until it responds.")
        }
      }
    },
    [readOnly, weekId, finding.key, onAnswered, onError],
  )

  // ⚠️ KEYS 1/2/3, bound while this finding is the open one. Scoped to the
  // card rather than the window so the digits stay typable in the correction
  // form below — a global handler would answer the finding while somebody was
  // entering hours into it.
  useEffect(() => {
    if (readOnly || correcting) return
    function onKey(e: KeyboardEvent) {
      const i = Number(e.key) - 1
      if (!Number.isInteger(i) || i < 0 || i >= answers.length) return
      // ⚠️ TWO GUARDS PROTECT THIS, AND NEITHER IS REDUNDANT THE WAY IT
      // FIRST LOOKS. The effect is unbound while `correcting`, and this skips
      // form fields. Break-tested both ways: removing EITHER one alone reddens
      // nothing, because the other still catches it; removing BOTH reddens
      // `the number keys stop answering while the correction form is open`.
      //
      // Kept as a pair deliberately. `correcting` covers the form; this covers
      // any other field that lands on this screen later — stage 5's match
      // notes will — and a digit answering a finding while someone types is
      // the kind of thing nobody reports, they just stop trusting the keys.
      const t = e.target as HTMLElement | null
      if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return
      e.preventDefault()
      void answer(answers[i])
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [answers, answer, readOnly, correcting])

  const empId = finding.file_number ?? finding.employee_id ?? null

  return (
    <div
      data-testid={`finding-${finding.code}`}
      className="rounded-xl border border-border-subtle bg-surface-elevated px-4 py-3"
    >
      <p className="text-body text-content-strong">{finding.message}</p>
      {WHY[finding.code] ? (
        <p className="mt-1 text-caption text-content-muted">
          {WHY[finding.code]}
        </p>
      ) : null}
      {empId ? (
        <button
          type="button"
          data-testid="finding-open-timecard"
          className="mt-2 text-caption text-steel underline-offset-2 hover:underline"
          onClick={() => openTimecard(empId)}
        >
          Open {empId}&rsquo;s timecard
        </button>
      ) : null}

      {readOnly ? (
        <p className="mt-3 text-body-sm text-content-muted">
          Answering a finding needs{" "}
          <span className="font-mono text-caption">payroll.approve</span>.
        </p>
      ) : correcting && empId ? (
        <CorrectionForm
          weekId={weekId}
          empId={empId}
          onCancel={() => setCorrecting(false)}
          onDone={async (ok, failure) => {
            setCorrecting(false)
            if (!ok) {
              // ⚠️ The form now says WHICH of the three happened. The fallback
              // is only reached if a future caller forgets to pass one, and it
              // still does not claim nothing changed.
              onError(failure ?? "The correction did not complete. Check the week before entering it again.")
              return
            }
            // ⚠️ The correction and the ANSWER are two writes, and the answer
            // is what takes the finding off the list. Recorded as `corrected`
            // so the week reads back as "hours were corrected", not "settled".
            try {
              await postWeekDecision(
                weekId,
                finding.key,
                outcomes.corrected ? "corrected" : "settled",
                "hours entered by hand",
              )
            } catch {
              onError(
                "The hours were saved but the finding was not marked answered.",
              )
            }
            onError(null)
            await onAnswered()
          }}
        />
      ) : (
        <ol className="mt-3 space-y-1">
          {answers.map((a, i) => (
            <li key={a.label}>
              <button
                type="button"
                data-testid={`answer-${i + 1}`}
                className="flex w-full items-center gap-2 rounded-lg border border-transparent px-2 py-1 text-left text-body-sm text-content-strong hover:border-border-subtle hover:bg-surface-raised"
                onClick={() => void answer(a)}
              >
                <kbd className="rounded border border-border-subtle bg-surface-raised px-1.5 font-mono text-micro">
                  {i + 1}
                </kbd>
                {a.label}
              </button>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}


function CorrectionForm({
  weekId,
  empId,
  onCancel,
  onDone,
}: {
  weekId: string
  empId: string
  onCancel: () => void
  /**
   * `ok` is "the correction is ON THE SERVER", not "the request returned".
   *
   * ⚠️ **`failure` EXISTS BECAUSE A BOOLEAN CANNOT CARRY THE DIFFERENCE THAT
   * MATTERS.** This form used to catch its own error and report `false`, so a
   * server refusal and a lost reply arrived at the parent identically — and the
   * parent then said "Nothing has been changed", which is true of the first and
   * unknowable for the second. The form keeps the check because the form is
   * where the correction's identity (day, pay type) lives.
   */
  onDone: (ok: boolean, failure?: string) => void
}) {
  const [day, setDay] = useState("")
  const [payType, setPayType] = useState<string>("REG")
  const [hours, setHours] = useState("")
  const [reason, setReason] = useState("")
  const [saving, setSaving] = useState(false)

  const ready = day !== "" && hours !== "" && reason.trim() !== ""

  return (
    <div data-testid="correction-form" className="mt-3 space-y-2">
      <p className="text-caption text-content-muted">
        Hours for {empId}. This is added to what Payentry printed, so the
        arithmetic stays visible — and a reason is required because nobody can
        review an unexplained correction six weeks later.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="date"
          aria-label="Day"
          data-testid="correction-date"
          value={day}
          onChange={(e) => setDay(e.target.value)}
          className="rounded-lg border border-border-subtle bg-surface-raised px-2 py-1 text-body-sm"
        />
        <select
          aria-label="Pay type"
          data-testid="correction-paytype"
          value={payType}
          onChange={(e) => setPayType(e.target.value)}
          className="rounded-lg border border-border-subtle bg-surface-raised px-2 py-1 text-body-sm"
        >
          {PAY_TYPES.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <input
          type="text"
          inputMode="decimal"
          aria-label="Hours"
          placeholder="hours"
          data-testid="correction-hours"
          value={hours}
          onChange={(e) => setHours(e.target.value)}
          className="w-24 rounded-lg border border-border-subtle bg-surface-raised px-2 py-1 text-body-sm"
        />
      </div>
      <input
        type="text"
        aria-label="Reason"
        placeholder="why — e.g. clocked in, never out"
        data-testid="correction-reason"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        className="w-full rounded-lg border border-border-subtle bg-surface-raised px-2 py-1 text-body-sm"
      />
      <div className="flex gap-2">
        <button
          type="button"
          disabled={!ready || saving}
          data-testid="correction-save"
          className="rounded-lg border border-border-subtle bg-surface-raised px-3 py-1.5 text-body-sm text-content-strong hover:border-border-strong disabled:opacity-50"
          onClick={async () => {
            setSaving(true)
            try {
              await postHourCorrection(weekId, {
                empId,
                workDate: day,
                payType,
                hours,
                reason,
              })
              onDone(true)
            } catch (err) {
              if (!gotNoReply(err)) {
                // The server answered. Pass its words up verbatim.
                onDone(false, failureText(err))
              } else {
                // ⚠️ No reply: ask the server whether this correction is there.
                // Matched on (employee, date, pay type) — the natural key of
                // what was just sent.
                const verdict = await didWriteLand(
                  () => getWeekFocus(weekId),
                  (f) =>
                    f.corrections.some(
                      (c) =>
                        c.emp_id === empId &&
                        c.work_date === day &&
                        c.pay_type === payType,
                    ),
                )
                if (verdict === "landed") {
                  // It IS saved, so the week may proceed to the answer.
                  onDone(true)
                } else if (verdict === "did-not-land") {
                  onDone(
                    false,
                    "No reply reached this page, and the correction is not on the server — enter it again.",
                  )
                } else {
                  onDone(
                    false,
                    "No reply from the server, and the follow-up check could not reach it either. Whether the correction saved is unknown; do not enter it again until it responds.",
                  )
                }
              }
            } finally {
              setSaving(false)
            }
          }}
        >
          Save hours
        </button>
        <button
          type="button"
          data-testid="correction-cancel"
          className="rounded-lg px-3 py-1.5 text-body-sm text-content-muted hover:text-content-strong"
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>
    </div>
  )
}


// ── 3. the week ─────────────────────────────────────────────────────────────

function WeekTable({
  dues,
  onOpenMember,
}: {
  dues: UnionDuesPane
  onOpenMember: (empId: string, name: string | null) => void
}) {
  return (
    <div>
      <table className="w-full text-body-sm" data-testid="week-table">
        <thead>
          <tr className="text-micro uppercase tracking-wider text-content-muted">
            <th className="py-1 text-left font-normal">Person</th>
            <th className="py-1 text-right font-normal">Dues hours</th>
            <th className="py-1 text-right font-normal">Dues wage</th>
            <th className="py-1 text-right font-normal">Dues</th>
          </tr>
        </thead>
        <tbody>
          {dues.members.map((m) => (
            <tr key={m.employee_id} className="border-t border-border-subtle">
              <td className="py-1">
                <button
                  type="button"
                  data-testid={`week-row-${m.file_number ?? m.employee_id}`}
                  className="text-steel underline-offset-2 hover:underline"
                  onClick={() => onOpenMember(m.employee_id, m.display_name)}
                >
                  {m.display_name ?? m.file_number ?? m.employee_id}
                </button>
              </td>
              <td className="py-1 text-right">{m.dues_hours ?? "—"}</td>
              <td className="py-1 text-right">
                {m.dues_wage ? `$${m.dues_wage}` : "—"}
              </td>
              {/* The working is on hover rather than in a column: it is four
                  more numbers per row, and it is read when a figure is being
                  questioned, not while scanning the week. */}
              <td
                className="py-1 text-right"
                title={
                  m.component_a
                    ? `a ${m.component_a} (pct) · b ${m.component_b} (cap) · c ${m.component_c} (per hr)${m.binds ? ` · ${m.binds} binds` : ""}`
                    : undefined
                }
              >
                {m.dues ? `$${m.dues}` : "—"}
              </td>
            </tr>
          ))}
          <tr className="border-t border-border-subtle font-medium">
            <td className="py-1.5 text-content-strong">
              Total · {dues.members_paying} of {dues.members_total} paying
            </td>
            <td className="py-1.5 text-right">{dues.total_dues_hours ?? "—"}</td>
            <td />
            <td className="py-1.5 text-right">
              {dues.total_dues ? `$${dues.total_dues}` : "—"}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}


// ── 4. approve, and what to enter in Payentry ───────────────────────────────

function ApproveSection({
  focus,
  dues,
  readOnly,
  openFindings,
  busy,
  setBusy,
  onError,
  onApproved,
}: {
  focus: WeekFocus
  dues: UnionDuesPane | null
  readOnly: boolean
  openFindings: number
  busy: boolean
  setBusy: (b: boolean) => void
  onError: (m: string | null) => void
  onApproved: () => Promise<void> | void
}) {
  const approved = focus.status === "approved"
  const paidWithNoHours = useMemo(
    () =>
      (dues?.members ?? []).filter(
        (m) => (m.dues_hours == null || Number(m.dues_hours) === 0) && m.dues
          && Number(m.dues) > 0,
      ),
    [dues],
  )

  const deductionList = useMemo(
    () =>
      (dues?.members ?? [])
        .filter((m) => m.dues && Number(m.dues) > 0)
        .map((m) => `${m.display_name ?? m.file_number}\t${m.dues}`),
    [dues],
  )

  return (
    <section aria-label="Approve" data-testid="approve-section">
      <SectionHead
        title={approved ? "Enter in Payentry" : "Checks before approving"}
        right={approved ? "approved" : undefined}
      />
      {!approved ? (
        <>
          <ul className="space-y-1 text-body-sm">
            <li className="flex items-baseline justify-between gap-3">
              <span className="text-content-muted">Findings still open</span>
              <span className="text-content-strong">{openFindings}</span>
            </li>
            <li className="flex items-baseline justify-between gap-3">
              <span className="text-content-muted">
                Anyone paid with no hours
              </span>
              <span
                className={
                  paidWithNoHours.length
                    ? "text-status-warning"
                    : "text-content-strong"
                }
              >
                {paidWithNoHours.length === 0
                  ? "none"
                  : paidWithNoHours
                      .map((m) => m.display_name ?? m.file_number)
                      .join(", ")}
              </span>
            </li>
            <li className="flex items-baseline justify-between gap-3">
              <span className="text-content-muted">Dues this week</span>
              <span className="text-content-strong">
                {focus.dues.total ? `$${focus.dues.total}` : "—"}
              </span>
            </li>
          </ul>
          {/* ⚠️ Totals against last week are NOT shown. The Focus is scoped to
              one week and no endpoint serves the previous one's total, so the
              comparison would have to be invented here. Stated rather than
              rendered as a blank. */}
          <p className="mt-2 text-caption text-content-muted">
            The comparison against last week is not shown yet — it needs the
            previous week&rsquo;s total, which this screen is not given.
          </p>
          {readOnly ? (
            <p className="mt-3 text-body-sm text-content-muted">
              Approving needs{" "}
              <span className="font-mono text-caption">payroll.approve</span>.
            </p>
          ) : (
            <button
              type="button"
              disabled={busy}
              data-testid="approve-week"
              className="mt-3 rounded-lg border border-border-subtle bg-surface-raised px-3 py-1.5 text-body-sm text-content-strong hover:border-border-strong disabled:opacity-50"
              onClick={async () => {
                setBusy(true)
                try {
                  await approveWeek(focus.week_id)
                  onError(null)
                  await onApproved()
                } catch {
                  onError(
                    "The week was not approved. If it is not calculated yet, that is why.",
                  )
                } finally {
                  setBusy(false)
                }
              }}
            >
              Approve week {focus.week_number}
            </button>
          )}
        </>
      ) : (
        <>
          {deductionList.length === 0 ? (
            <Empty>
              Nobody has dues on this week, so there is nothing to enter in
              Payentry.
            </Empty>
          ) : (
            <>
              <ul
                data-testid="deduction-list"
                className="space-y-1 text-body-sm"
              >
                {deductionList.map((row) => {
                  const [name, amount] = row.split("\t")
                  return (
                    <li
                      key={row}
                      className="flex items-baseline justify-between gap-3"
                    >
                      <span className="text-content-strong">{name}</span>
                      <span>${amount}</span>
                    </li>
                  )
                })}
              </ul>
              <button
                type="button"
                data-testid="copy-deductions"
                className="mt-2 rounded-lg border border-border-subtle bg-surface-elevated px-3 py-1.5 text-body-sm text-content-strong hover:border-border-strong"
                onClick={() => {
                  void navigator.clipboard?.writeText(deductionList.join("\n"))
                }}
              >
                Copy all {deductionList.length}
              </button>
            </>
          )}
          {focus.corrections.length > 0 ? (
            <div className="mt-4">
              <SectionHead title="Hour corrections to enter" />
              <ul className="space-y-1 text-body-sm" data-testid="corrections-to-enter">
                {focus.corrections.map((c, i) => (
                  <li
                    key={i}
                    className="flex items-baseline justify-between gap-3"
                  >
                    <span className="text-content-strong">
                      {c.emp_id} · {c.work_date} · {c.pay_type}
                    </span>
                    <span className="text-right">
                      {/* ⚠️ Trimmed. The server sends HOURS at 4 decimals
                          because the column is Numeric(10,4); rendering it raw
                          put "40.0000" on the one list Susan retypes into
                          Payentry. */}
                      {trimHours(c.hours)}{" "}
                      <span className="text-content-muted">({c.reason})</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      )}
    </section>
  )
}


// ── 5. after Thursday ───────────────────────────────────────────────────────

function RegisterSection({
  readOnly,
  busy,
  setBusy,
  onError,
}: {
  readOnly: boolean
  busy: boolean
  setBusy: (b: boolean) => void
  onError: (m: string | null) => void
}) {
  const file = useRef<HTMLInputElement>(null)
  return (
    <section aria-label="The register" data-testid="register-section">
      <SectionHead title="After the checks are dated" />
      <p className="text-body-sm text-content-muted">
        Load the payroll register and Opas compares every line with what you
        approved.
      </p>
      {readOnly ? (
        <p className="mt-2 text-body-sm text-content-muted">
          Loading the register needs{" "}
          <span className="font-mono text-caption">payroll.upload</span>.
        </p>
      ) : (
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <input
            ref={file}
            type="file"
            data-testid="register-file"
            className="text-body-sm"
          />
          <button
            type="button"
            disabled={busy}
            data-testid="upload-register"
            className="rounded-lg border border-border-subtle bg-surface-elevated px-3 py-1.5 text-body-sm text-content-strong hover:border-border-strong disabled:opacity-50"
            onClick={async () => {
              const f = file.current?.files?.[0]
              if (!f) {
                onError("Choose the register file first.")
                return
              }
              setBusy(true)
              try {
                await uploadRegister(f)
                onError("Register loaded. Opas is comparing it line by line.")
              } catch (err) {
                if (!gotNoReply(err)) {
                  onError(failureText(err))
                } else {
                  // ⚠️ Same reasoning as the answer above, and here a blind
                  // retry is only harmless because the import is idempotent on
                  // (check number, check date, employee id).
                  const verdict = await didWriteLand(
                    () => listRegisterImports(3),
                    (log) => log.imports.some((i) => i.filename === f.name),
                  )
                  if (verdict === "landed") {
                    onError("No reply reached this page, but the server DID load the register. Nothing to re-upload.")
                  } else if (verdict === "did-not-land") {
                    onError("No reply reached this page, and the register is not in the server's import log — it is safe to try again.")
                  } else {
                    onError("No reply from the server, and the follow-up check could not reach it either. Whether the register loaded is unknown; do not re-upload until it responds.")
                  }
                }
              } finally {
                setBusy(false)
              }
            }}
          >
            Upload register
          </button>
        </div>
      )}
      {/* ⚠️ The match items are NOT rendered, because nothing serves them.
          `explain_dues_difference` and the comparison live in
          `week_findings.py` and are not exposed by any endpoint — so the
          "doesn't match → 1 catch up / 2 Payentry is right / 3 ask HR One"
          answers have no data to attach to yet. Said here rather than shown
          as an empty list that looks like "everything matched". */}
      <p className="mt-2 text-caption text-content-muted">
        The line-by-line comparison is not shown on this screen yet: no
        endpoint serves it. An empty list here would read as
        &ldquo;everything matched&rdquo;, which is not something this screen
        can currently claim.
      </p>
    </section>
  )
}
