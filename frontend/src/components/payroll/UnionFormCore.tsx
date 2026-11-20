/**
 * The union remittance form (R-115) for one month — Payroll 5b.
 *
 * ⚠️ **ONE READ, BECAUSE THE STAGE AND THE FIGURES MUST NOT DISAGREE.**
 * `GET /r115` returns the form, its stage, the due date, the numbered lines,
 * the header and the copies together. Fetching the stage separately would let
 * this render "Sent" above a table from a later rebuild.
 *
 * ⚠️ **COPIES SIT NEAR THE TOP, AND THEIR WORDING IS THE POINT.** "Printed by
 * Susan, Dec 3" is not a delivery: a browser cannot confirm paper came out, so
 * the line says where it went after isn't known. "Marked sent" carries the HOW
 * the person typed, because "sent" with no method is a claim nobody can follow
 * up. And when today's figures have moved away from a copy, the copy says so —
 * that notice is the reason the record exists at all.
 */
import { useCallback, useEffect, useMemo, useState } from "react"

import apiClient from "@/lib/api-client"

const BASE = "/payroll-reports"

/** One numbered line of the form, as the server composes it. */
interface FormLine {
  number: number | null
  key: string
  label: string
  kind: "count" | "hours" | "money"
  rate: string | null
  value: string | null
  blank: boolean
}

interface Copy {
  id: string
  left_as: "printed" | "downloaded" | "emailed" | "marked_sent"
  sent_how: string | null
  made_at: string | null
  made_by_name: string | null
  differs_from_today: boolean | null
}

interface FormPayload {
  year: number
  month: number
  form: { id: string; status: string; total_remittance: string } | null
  preview: unknown | null
  schedule: {
    stage: string
    stage_label: string
    last_check_date: string
    due_date: string | null
    overdue: boolean
  }
  lines: FormLine[] | null
  lines_unavailable: string | null
  warnings: string[]
  percentage_dues_computed: string | null
  percentage_dues_variance: string | null
  header: Record<string, string | null>
  copies: Copy[]
}

/** `2026-10` → `{year, month}`. Returns null for anything else.
 *
 *  ⚠️ VALIDATED, NOT PARSED OPTIMISTICALLY. An unscoped open is the defect the
 *  PR C walk-through caught on the week entry — a URL claiming a surface that
 *  rendered nothing. Here a missing or malformed period says so. */
export function parsePeriod(raw: string | null): { year: number; month: number } | null {
  if (!raw) return null
  const m = /^(\d{4})-(\d{2})$/.exec(raw.trim())
  if (!m) return null
  const year = Number(m[1])
  const month = Number(m[2])
  if (month < 1 || month > 12) return null
  return { year, month }
}

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
]

export function monthName(year: number, month: number): string {
  return `${MONTHS[month - 1]} ${year}`
}

/** A date the way this surface writes dates: "Dec 3".
 *
 * ⚠️ **A BARE `YYYY-MM-DD` IS PARSED AS LOCAL, NOT UTC, AND THAT IS A BUG FIX
 * RATHER THAN A PREFERENCE.** `new Date("2026-10-29")` is defined to parse as
 * UTC midnight; `getDate()` then answers in the LOCAL zone, which west of
 * Greenwich is the 28th. Every bare date this surface shows — the last check
 * date, the due date, the pay period — comes from the server as `YYYY-MM-DD`,
 * so all of them displayed a day early. "Due Nov 15" read "Nov 14" on a form
 * filed against a deadline.
 *
 * A full timestamp (`made_at`) is a real instant and is parsed normally: it
 * SHOULD be shown in the reader's zone, which is the opposite requirement and
 * the reason these two cases are told apart rather than handled alike.
 */
export function shortDate(iso: string | null): string {
  if (!iso) return ""
  const bare = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso.trim())
  const d = bare
    ? new Date(Number(bare[1]), Number(bare[2]) - 1, Number(bare[3]))
    : new Date(iso)
  if (Number.isNaN(d.getTime())) return ""
  return `${MONTHS[d.getMonth()].slice(0, 3)} ${d.getDate()}`
}

/**
 * How a copy reads on screen.
 *
 * ⚠️ **EXPORTED AND PURE, BECAUSE THE HONESTY IS IN THE WORDS.** These
 * sentences are the whole reason the record is worth keeping, and a sentence
 * built inline in JSX can only be tested by rendering the component and
 * reading pixels. Each mode says exactly what is known and no more.
 */
export function copyWording(copy: Copy): string {
  const who = copy.made_by_name ?? "Someone"
  const when = shortDate(copy.made_at)
  const stamp = when ? `${who}, ${when}` : who
  switch (copy.left_as) {
    case "printed":
      // ⚠️ NOT "SENT". The print view was opened; paper is outside what a
      // browser can see.
      return `Printed by ${stamp}: where it went after isn't known`
    case "downloaded":
      return `Downloaded by ${stamp}: where it went after isn't known`
    case "marked_sent":
      return copy.sent_how
        ? `Marked sent by ${stamp}: ${copy.sent_how}`
        : `Marked sent by ${stamp}`
    case "emailed":
      return `Emailed by ${stamp}`
    default:
      return `Left by ${stamp}`
  }
}

export function UnionFormCore({
  readOnly,
  scope,
}: {
  focusId: string
  config: unknown
  readOnly: boolean
  scope: Record<string, unknown>
}) {
  /* ⚠️ SCOPE FIRST, THEN THE URL — the same fallback `WeeklyPayrollCore`
     carries, and for the same reason: a payroll-limited user cannot create a
     focus session, so the context falls back to a registry default with no
     params and the Focus would open scoped to nothing. */
  const period = useMemo(() => {
    const fromScope =
      typeof scope.period === "string" && scope.period ? scope.period : null
    return parsePeriod(
      fromScope ?? new URLSearchParams(window.location.search).get("period"),
    )
  }, [scope.period])

  const [data, setData] = useState<FormPayload | null>(null)
  const [failed, setFailed] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [sendingHow, setSendingHow] = useState("")
  const [askingHow, setAskingHow] = useState(false)
  /** What went wrong with the last act, if anything. Separate from `failed`,
   *  which is the page not loading at all — a reader needs to tell "the form
   *  is not here" from "the form is here and your click did nothing". */
  const [actionFailed, setActionFailed] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!period) return
    try {
      const r = await apiClient.get<FormPayload>(`${BASE}/r115`, {
        params: { year: period.year, month: period.month },
      })
      setData(r.data)
      setFailed(null)
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })
        ?.response?.data?.detail
      setFailed(
        typeof detail === "string"
          ? detail
          : (detail as { message?: string })?.message ??
              "The union form could not be loaded.",
      )
    }
  }, [period])

  useEffect(() => {
    void load()
  }, [load])

  /** Run an action, reload, and SAY SO IF IT FAILED.
   *
   * ⚠️ **THE FIRST VERSION HAD NO `catch`, AND A FAILED ACTION WAS SILENT.**
   * The button stopped being busy, nothing changed, and the rejection left
   * the handler as an unhandled promise — which vitest surfaced and a person
   * would not have. On this surface that is worse than elsewhere: the acts
   * are "record that this left the building" and "tell the union it was
   * sent", and a failure nobody sees reads exactly like a success.
   */
  async function act(fn: () => Promise<unknown>) {
    setBusy(true)
    setActionFailed(null)
    try {
      await fn()
      await load()
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })
        ?.response?.data?.detail
      setActionFailed(
        typeof detail === "string"
          ? detail
          : (detail as { message?: string })?.message ??
              "That did not go through. Nothing was recorded.",
      )
    } finally {
      setBusy(false)
    }
  }

  /** ⚠️ RECORD THE COPY, THEN PRINT. If the record fails the print does not
   *  happen — a page that left with no copy of it is the gap this whole
   *  feature exists to close, and printing first would make that the common
   *  case whenever the request failed. */
  async function printForm() {
    if (!period) return
    await act(async () => {
      const body = new FormData()
      body.append("year", String(period.year))
      body.append("month", String(period.month))
      body.append("left_as", "printed")
      await apiClient.post(`${BASE}/r115/copies`, body)
      window.print()
    })
  }

  async function markSent() {
    if (!period || !sendingHow.trim()) return
    await act(async () => {
      const body = new FormData()
      body.append("year", String(period.year))
      body.append("month", String(period.month))
      body.append("left_as", "marked_sent")
      body.append("sent_how", sendingHow.trim())
      await apiClient.post(`${BASE}/r115/copies`, body)
      if (data?.form) {
        await apiClient.post(`${BASE}/r115/${data.form.id}/status`, (() => {
          const f = new FormData()
          f.append("to_status", "filed")
          return f
        })())
      }
      setSendingHow("")
      setAskingHow(false)
    })
  }

  if (!period) {
    return (
      <div data-testid="union-form-no-period" className="p-6">
        <p className="text-body text-content-base">
          This form needs a month. Open it from the note or from Opas, which
          both carry one.
        </p>
      </div>
    )
  }

  if (failed) {
    return (
      <div data-testid="union-form-failed" className="p-6">
        <p className="text-body text-content-base">{failed}</p>
      </div>
    )
  }

  if (!data) {
    return (
      <div data-testid="union-form-loading" className="p-6">
        <p className="text-body-sm text-content-muted">Reading the month…</p>
      </div>
    )
  }

  const { schedule, header } = data
  const stale = data.copies.some((c) => c.differs_from_today === true)

  return (
    /* ⚠️ **IT PAINTS ITS OWN SURFACE, AND THAT IS A BUG FIX.** The Focus
       renders inside a dialog over a dimmed, blurred note. A core with no
       background of its own sits directly on that dimming layer: measured off
       this walk's own screenshot, the page behind the form was (106,106,107)
       and even the darkest text reached 3.20:1 — below AA, on a form somebody
       checks figures against a cheque with.

       ⚠️ The same measurement on PR C's capture put the weekly payroll
       Focus's header at 1.30:1, so this is not local to the union form. The
       shared Focus shell is the right place to fix it for every core; doing
       that here would change four other surfaces in a payroll PR, so it is
       reported rather than done. */
    <div
      data-testid="union-form-core"
      className="space-y-6 rounded-xl bg-surface-base p-6 text-content-base"
    >
      <header className="space-y-1">
        <p className="text-caption uppercase tracking-wide text-content-subtle">
          Union remittance · R-115
        </p>
        <h2 className="text-h2 text-content-strong">
          {monthName(period.year, period.month)}
        </h2>
        <p data-testid="union-form-stage" className="text-body-sm text-content-muted">
          {schedule.stage_label}
          {schedule.stage === "filling" &&
            ` — checks can still land until ${shortDate(schedule.last_check_date)}`}
          {" · "}
          {/* ⚠️ "No due date set" IS THE CLIENT'S WORDING for a null the
              server sends. A server that sent the sentence would be deciding
              copy, and a second surface would have to match it by hand. */}
          {schedule.due_date
            ? `${schedule.overdue ? "Was due" : "Due"} ${shortDate(schedule.due_date)}`
            : "No due date set"}
        </p>
      </header>

      {/* ── copies, near the top ──────────────────────────────────────── */}
      {data.copies.length > 0 && (
        <section data-testid="union-form-copies" className="space-y-1">
          <h3 className="text-caption uppercase tracking-wide text-content-subtle">
            Copies that have left
          </h3>
          <ul className="space-y-1">
            {data.copies.map((c) => (
              <li
                key={c.id}
                data-testid={`copy-${c.id}`}
                data-left-as={c.left_as}
                className="text-body-sm text-content-base"
              >
                <span>{copyWording(c)}</span>{" "}
                <a
                  href={`?focus=union-form&period=${period.year}-${String(
                    period.month,
                  ).padStart(2, "0")}&copy=${c.id}`}
                  className="text-caption text-steel underline-offset-2 hover:underline"
                >
                  open this copy
                </a>
                {c.differs_from_today === true && (
                  <span
                    data-testid={`copy-stale-${c.id}`}
                    className="ml-2 text-caption text-content-muted"
                  >
                    · Today's figures differ from this copy
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.warnings.map((w) => (
        <p key={w} data-testid="union-form-warning"
           className="text-body-sm text-content-muted">
          {w}
        </p>
      ))}

      {/* ── the form, in the order the paper form carries ─────────────── */}
      {data.lines_unavailable ? (
        <p data-testid="union-form-lines-unavailable"
           className="text-body-sm text-content-muted">
          {data.lines_unavailable}
        </p>
      ) : (
        <section data-testid="union-form-lines">
          <dl className="space-y-1">
            {(data.lines ?? []).map((line) => (
              <div
                key={line.key}
                data-testid={`line-${line.key}`}
                data-line-number={line.number ?? ""}
                className="flex items-baseline gap-3 text-body"
              >
                <span className="w-6 shrink-0 text-right text-caption text-content-subtle">
                  {line.number ?? ""}
                </span>
                <dt className="flex-1 text-content-base">
                  {line.label}
                  {line.rate && (
                    <span className="ml-2 text-caption text-content-subtle">
                      rate {line.rate}
                    </span>
                  )}
                </dt>
                <dd
                  data-testid={`value-${line.key}`}
                  className={
                    line.number === null
                      ? "font-medium tabular-nums text-content-strong"
                      : "tabular-nums text-content-base"
                  }
                >
                  {/* ⚠️ A BLANK LINE PRINTS BLANK, NOT "0.00". A zero asserts
                      "none this month"; a blank says the line does not apply,
                      and nothing here measured either. */}
                  {line.blank ? "" : line.value}
                </dd>
              </div>
            ))}
          </dl>
          {data.percentage_dues_variance &&
            data.percentage_dues_variance !== "0.00" && (
              <p data-testid="union-form-variance"
                 className="mt-3 text-body-sm text-content-muted">
                {/* ⚠️ "a difference of -0.05" reads as a typo. The sign is
                    real — the plug can sit either side of the rules' figure —
                    so it is said in words and the magnitude printed without
                    one. */}
                Line 5 is the remainder, so the form adds up to what was
                deducted. Worked out from the rules it would be{" "}
                {data.percentage_dues_computed} —{" "}
                {data.percentage_dues_variance.startsWith("-")
                  ? `${data.percentage_dues_variance.slice(1)} lower here`
                  : `${data.percentage_dues_variance} higher here`}
                .
              </p>
            )}
        </section>
      )}

      <section className="space-y-1 text-body-sm text-content-muted">
        <p>
          {header.company}
          {header.plant ? ` · ${header.plant}` : " · Plant not set"}
          {header.local ? ` · Local ${header.local}` : " · Local not set"}
        </p>
        <p>
          Completed by {header.completed_by ?? "— not set"}
          {header.pay_period_begin &&
            ` · ${header.pay_period_begin} to ${header.pay_period_end}`}
        </p>
      </section>

      {/* ── what can be done ──────────────────────────────────────────── */}
      <section className="flex flex-wrap items-center gap-3">
        {!data.form && data.lines && (
          <button
            type="button"
            disabled={readOnly || busy}
            data-testid="union-form-build"
            onClick={() =>
              act(() => {
                const f = new FormData()
                f.append("year", String(period.year))
                f.append("month", String(period.month))
                return apiClient.post(`${BASE}/r115`, f)
              })
            }
            className="text-body-sm underline underline-offset-2 disabled:opacity-50"
          >
            Start this month's form
          </button>
        )}

        {data.form?.status === "draft" && (
          <button
            type="button"
            disabled={readOnly || busy}
            data-testid="union-form-approve"
            onClick={() =>
              act(() => {
                const f = new FormData()
                f.append("to_status", "submitted")
                return apiClient.post(`${BASE}/r115/${data.form!.id}/status`, f)
              })
            }
            className="text-body-sm underline underline-offset-2 disabled:opacity-50"
          >
            Approve
          </button>
        )}

        <button
          type="button"
          disabled={busy || !data.lines}
          data-testid="union-form-print"
          onClick={printForm}
          className="text-body-sm underline underline-offset-2 disabled:opacity-50"
        >
          Print
        </button>

        {data.form?.status === "submitted" &&
          (askingHow ? (
            <span className="flex items-center gap-2">
              <label className="text-body-sm text-content-muted">
                How was it sent?
                <input
                  autoFocus
                  value={sendingHow}
                  disabled={busy}
                  data-testid="union-form-how"
                  placeholder="mailed with check 4521"
                  onChange={(e) => setSendingHow(e.target.value)}
                  className="ml-2 border-b border-border-strong bg-transparent text-body-sm"
                />
              </label>
              <button
                type="button"
                disabled={busy || !sendingHow.trim()}
                data-testid="union-form-mark-sent-confirm"
                onClick={markSent}
                className="text-body-sm underline underline-offset-2 disabled:opacity-50"
              >
                Mark sent
              </button>
            </span>
          ) : (
            <button
              type="button"
              disabled={readOnly || busy}
              data-testid="union-form-mark-sent"
              onClick={() => setAskingHow(true)}
              className="text-body-sm underline underline-offset-2 disabled:opacity-50"
            >
              Mark sent
            </button>
          ))}
      </section>

      {actionFailed && (
        <p data-testid="union-form-action-failed"
           className="text-body-sm text-status-error">
          {actionFailed}
        </p>
      )}

      {stale && (
        <p data-testid="union-form-stale-banner"
           className="text-body-sm text-content-muted">
          At least one copy that has left no longer matches today's figures.
        </p>
      )}
    </div>
  )
}
