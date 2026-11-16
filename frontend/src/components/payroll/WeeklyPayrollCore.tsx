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

import {
  approveWeek,
  getUnionDuesPane,
  postHourCorrection,
  postWeekDecision,
  uploadRegister,
  uploadWeekHours,
  type UnionDuesPane,
  type WeekFinding,
  type WeekFocus,
  getWeekFocus,
} from "@/lib/payroll/focus-api"
import {
  TimecardPaneBody,
  UnionDuesPaneBody,
  UnionMemberPaneBody,
} from "./panes/panes"
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
  no_hours: [
    { label: "Enter hours", opensCorrection: true },
    { label: "He didn't work", outcome: "not_an_issue" },
    { label: "Leave for now", outcome: "asked" },
  ],
  missing_lunch: [
    { label: "Take 30 minutes off", opensCorrection: true },
    { label: "He worked through", outcome: "not_an_issue" },
  ],
  probation: [
    { label: "Set the end date", outcome: "asked" },
    { label: "Not a union job", outcome: "not_an_issue" },
  ],
}

const GENERIC: Answer[] = [
  { label: "Looked at, correct as it stands", outcome: "settled" },
  { label: "Not a problem", outcome: "not_an_issue" },
  { label: "Asked someone", outcome: "asked" },
]

/** Why the finding is being asked, in one short line. Keyed on code so the
 *  wording is not buried in the server's message. */
const WHY: Record<string, string> = {
  no_hours:
    "Somebody with no hours is usually a missed punch, not a week off — and an unpaid week is the one mistake that cannot wait.",
  missing_lunch:
    "Payentry deducts lunch automatically; a day without it is either a worked lunch or a punch that did not land.",
  probation:
    "Dues start when probation ends, so the date decides whether this week has dues at all.",
  findings_unavailable:
    "The stored dues below are unaffected — only the re-run failed.",
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
  // The Focus is opened scoped to a week — from the home note's dues line, or
  // from a URL. Without one there is nothing to show, and saying so beats an
  // empty shell.
  const weekId = typeof scope.week_id === "string" ? scope.week_id : null

  const [focus, setFocus] = useState<WeekFocus | null | false>(null)
  const [dues, setDues] = useState<UnionDuesPane | null | false>(null)
  const [panes, setPanes] = useState<PayrollPaneSpec[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    if (!weekId) return
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
  }, [weekId])

  useEffect(() => {
    void reload()
  }, [reload])

  const closePane = useCallback((key: string) => {
    setPanes((p) => p.filter((q) => q.key !== key))
  }, [])

  const openPane = useCallback((spec: PayrollPaneSpec) => {
    setPanes((p) => (p.some((q) => q.key === spec.key) ? p : [...p, spec]))
  }, [])

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
          <p data-testid="focus-error" className="text-body-sm text-status-error">
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
            onDone={async (msg) => {
              setError(msg)
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
                      onOpenTimecard={() =>
                        openPane({
                          key: `timecard-${empId}`,
                          title: `Timecard · ${name ?? empId}`,
                          subtitle: `week ${focus.week_number}`,
                          body: (
                            <TimecardPaneBody
                              weekId={weekId}
                              empId={empId}
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

        <PayrollPaneStack panes={panes} onClose={closePane} />
      </div>
    </Shell>
  )
}


function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div
      data-slot="weekly-payroll-core"
      className="flex h-full flex-col px-6 py-5 [font-variant-numeric:tabular-nums]"
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
  onDone: (message: string | null) => void
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
                onDone(
                  blocking
                    ? blocking.message
                    : `Week ${weekNumber} loaded: ${
                        r.summary?.people ?? r.summary?.rows_stored ?? "—"
                      } people, ${r.summary?.hours ?? "—"} hours.`,
                )
              } catch {
                onDone("The upload was refused. The week is unchanged.")
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
      } catch {
        onError("That answer was not recorded. Nothing has been changed.")
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
          onDone={async (ok) => {
            setCorrecting(false)
            if (!ok) {
              onError("The correction was refused. Nothing has been changed.")
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
  onDone: (ok: boolean) => void
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
            } catch {
              onDone(false)
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
                    <span>
                      {c.hours} <span className="text-content-muted">({c.reason})</span>
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
              } catch {
                onError("The register was refused. Nothing has been changed.")
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
