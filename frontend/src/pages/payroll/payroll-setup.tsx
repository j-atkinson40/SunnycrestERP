/**
 * Payroll setup — the three turn-on controls, in the browser.
 *
 * ⚠️ **THIS PAGE REPLACES A TERMINAL SNIPPET, AND THAT IS ITS WHOLE REASON.**
 * The switch, the register upload and the roster reconcile have been reachable
 * only by `curl` carrying an admin bearer token, which means the turn-on
 * procedure asked a person to put a credential into a shell and read a token
 * out of a response. CLAUDE.md §7's standing rule is that a procedure
 * requiring a credential to transit something gets RESTRUCTURED rather than
 * performed carefully — and the browser session already holds an admin
 * credential, legitimately, for exactly this.
 *
 * Nothing here is a new capability. All three endpoints shipped with Payroll 3
 * and 4; this is an entrance.
 *
 * ⚠️ **ADMIN ONLY, AND THE SERVER SAYS SO TOO.** `adminOnly` on the route is
 * the UI half. The switch (GET and PUT) and the reconcile are
 * `require_admin` on the server; the whole router is tagged `area:payroll`, so
 * a user limited to another area is refused before any permission is
 * consulted. A UI-only restriction is not a restriction.
 *
 * ⚠️ **THE UPLOAD IS `payroll.upload`, NOT ADMIN — DELIBERATELY ASYMMETRIC.**
 * Susan pulls the Check Register from Payentry today and importing it here is
 * the same act, so she can also do it from inside the weekly Focus. It sits on
 * this page because the FIRST register load is part of turning payroll on, and
 * because the step after it — the reconcile — is admin-only and needs it done.
 *
 * ⚠️ **EVERY ACTION CONFIRMS FIRST AND THEN REPORTS WHAT CHANGED.** Not a
 * courtesy. Turning the switch on is the moment a tenant accepts that pay
 * rates and hours may be stored, and the reconcile writes to the roster; a
 * control whose effect is only knowable afterwards is the wrong shape for
 * either. The reconcile's confirmation step IS its dry run, so the preview a
 * person approves is the server's own account of what it would write.
 */

import { useEffect, useRef, useState } from "react"

import { uploadRegister } from "@/lib/payroll/focus-api"
import type { RegisterImportResult } from "@/lib/payroll/focus-api"
import {
  CHECKING_SUFFIX,
  didWriteLand,
  failureText,
  gotNoReply,
} from "@/lib/payroll/failure"
import {
  getDataEnabled,
  getRosterStatus,
  listRegisterImports,
  reconcileRegisterPeople,
  setDataEnabled,
  type DataSwitchState,
  type ReconcileResult,
  type RegisterImportRow,
  type RosterStatus,
} from "@/lib/payroll/setup-api"

/** `null` = loading, `false` = could not load. Three states, never two — a
 *  failure rendered as "nothing here" would read as "the switch is off", which
 *  is the one answer this page must never guess. */
type Loaded<T> = T | null | false

const CARD =
  "max-w-content rounded-base border border-border-subtle bg-surface-elevated p-6 shadow-level-1"
const BUTTON =
  "rounded-lg border border-border-subtle bg-surface-raised px-3 py-1.5 text-body-sm text-content-strong hover:border-border-strong disabled:opacity-50"
const QUIET =
  "rounded-lg px-3 py-1.5 text-body-sm text-content-muted hover:text-content-strong"


/**
 * Confirm-before-commit. Renders the trigger until it is pressed, then the
 * consequence in words with Confirm and Cancel beside it.
 *
 * ⚠️ The consequence is passed in as prose rather than derived from the label.
 * "Are you sure?" is not a confirmation — it asks a person to re-read the
 * button they just pressed.
 */
function Confirm({
  testId,
  trigger,
  consequence,
  confirmLabel,
  busy,
  disabled,
  onConfirm,
}: {
  testId: string
  trigger: string
  consequence: React.ReactNode
  confirmLabel: string
  busy?: boolean
  disabled?: boolean
  onConfirm: () => void
}) {
  const [asking, setAsking] = useState(false)

  if (!asking) {
    return (
      <button
        type="button"
        data-testid={testId}
        className={BUTTON}
        disabled={disabled || busy}
        onClick={() => setAsking(true)}
      >
        {busy ? "Working…" : trigger}
      </button>
    )
  }

  return (
    <div
      data-testid={`${testId}-confirm`}
      className="rounded-lg border border-border-strong bg-surface-raised p-4"
    >
      <p className="text-body-sm text-content-base">{consequence}</p>
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          data-testid={`${testId}-yes`}
          className={BUTTON}
          disabled={busy}
          onClick={() => {
            setAsking(false)
            onConfirm()
          }}
        >
          {confirmLabel}
        </button>
        <button
          type="button"
          data-testid={`${testId}-no`}
          className={QUIET}
          onClick={() => setAsking(false)}
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

/** A reported outcome. `ok: false` is a refusal or a failure; both say what
 *  did NOT happen rather than going quiet. */
function Outcome({
  testId,
  ok,
  children,
}: {
  testId: string
  ok: boolean
  children: React.ReactNode
}) {
  return (
    <p
      data-testid={testId}
      className={`mt-3 text-body-sm ${
        ok ? "text-content-base" : "text-status-error"
      }`}
    >
      {children}
    </p>
  )
}

// ─── (1) the data switch ─────────────────────────────────────────────────────

function DataSwitchCard({
  state,
  onChanged,
}: {
  state: Loaded<DataSwitchState>
  onChanged: (next: DataSwitchState) => void
}) {
  const [busy, setBusy] = useState(false)
  const [said, setSaid] = useState<{ ok: boolean; text: string } | null>(null)

  // Truthy already excludes `null` and `false`; a further `!== false` is
  // redundant and TypeScript says so (same note as payroll-home).
  const enabled = state ? state.enabled : null

  async function flip(to: boolean) {
    setBusy(true)
    setSaid(null)
    try {
      const r = await setDataEnabled(to)
      onChanged({ setting: r.setting, enabled: r.enabled })
      setSaid({
        ok: true,
        text: r.changed
          ? to
            ? "Payroll data loading is now ON for this company. The register upload below will work."
            : "Payroll data loading is now OFF. Existing rows are untouched; no new export can be imported."
          : `No change — it was already ${to ? "on" : "off"}. Nothing was recorded.`,
      })
    } catch (err) {
      setSaid({ ok: false, text: failureText(err) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-label="Payroll data switch" data-testid="setup-switch" className={CARD}>
      <h2 className="text-h4 text-content-strong">1 · Payroll data for this company</h2>

      {state === null ? (
        <p className="mt-2 text-body text-content-muted">Reading the switch…</p>
      ) : state === false ? (
        // ⚠️ NOT rendered as "off". The switch's state is the one fact this
        // page exists to show, and an unreadable switch is not a switch that
        // is off — offering a "turn on" button here would be guessing.
        <p className="mt-2 text-body text-status-error" data-testid="switch-unreadable">
          The switch could not be read, so this page cannot say whether payroll
          data loading is on. Nothing has been changed. Reload the page; if it
          keeps happening you are probably not signed in as an administrator of
          this company.
        </p>
      ) : (
        <>
          <p className="mt-2 text-body text-content-base" data-testid="switch-state">
            Currently{" "}
            <span className="text-content-strong">{enabled ? "ON" : "OFF"}</span>
            {enabled
              ? " — Payentry exports can be imported for this company."
              : " — no payroll export can be imported, by anyone, including an administrator."}
          </p>
          <p className="mt-1 text-caption text-content-muted">
            Off by default, per company, and audited when it changes. This is
            the deliberate “may Payentry data be loaded” decision, not a
            preference.
          </p>

          <div className="mt-4">
            {enabled ? (
              <Confirm
                testId="switch-off"
                trigger="Turn payroll data OFF"
                confirmLabel="Turn it off"
                busy={busy}
                consequence={
                  <>
                    Turning it off stops any further payroll export from being
                    imported for this company. <strong>Hours, checks and dues
                    already loaded stay exactly as they are</strong> — this does
                    not delete anything. Susan's screens keep showing the weeks
                    she already has.
                  </>
                }
                onConfirm={() => flip(false)}
              />
            ) : (
              <Confirm
                testId="switch-on"
                trigger="Turn payroll data ON"
                confirmLabel="Turn it on"
                busy={busy}
                consequence={
                  <>
                    This is the moment this company accepts that{" "}
                    <strong>pay rates, hours, union dues, child support and
                    garnishment amounts may be stored here</strong>. Your name
                    and the time are recorded against the change. It can be
                    turned off again, which stops further imports without
                    deleting what has already been loaded.
                  </>
                }
                onConfirm={() => flip(true)}
              />
            )}
          </div>
        </>
      )}

      {said ? (
        <Outcome testId="switch-said" ok={said.ok}>
          {said.text}
        </Outcome>
      ) : null}
    </section>
  )
}

// ─── (2) the register upload ─────────────────────────────────────────────────

function RegisterCard({ enabled }: { enabled: boolean | null }) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [chosen, setChosen] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<RegisterImportResult | null>(null)
  const [failed, setFailed] = useState<string | null>(null)

  async function run() {
    if (!chosen) return
    setBusy(true)
    setFailed(null)
    setResult(null)
    try {
      setResult(await uploadRegister(chosen))
    } catch (err) {
      const said = failureText(err)
      if (!gotNoReply(err)) {
        // The server answered. Its words are the answer.
        setFailed(said)
        return
      }
      // ⚠️ **NO REPLY REACHED US, SO WHETHER ANYTHING WAS SAVED IS UNKNOWN AND
      // WE GO AND LOOK.** A CORS rejection, a timeout or a reset on the RETURN
      // leg all produce this, and in every one of them the server may have
      // finished the work. Asserting "nothing has been changed" here was the
      // original defect; a retry on a false "nothing happened" is a second
      // write (safe here only because the import is idempotent).
      setFailed(said + CHECKING_SUFFIX)
      let landed: RegisterImportRow | undefined
      const verdict = await didWriteLand(
        () => listRegisterImports(3),
        (log) => {
          landed = log.imports.find((i) => i.filename === chosen.name)
          return landed !== undefined
        },
      )
      if (verdict === "landed") {
        setFailed(
          `No reply reached this page, but the server DID save the import: ` +
            `${landed?.checks_inserted ?? 0} checks from ${landed?.filename}. ` +
            `Nothing needs re-uploading.`,
        )
      } else if (verdict === "did-not-land") {
        setFailed(
          `No reply reached this page. Checked the server's import log and ` +
            `${chosen.name} is NOT there, so nothing was saved — it is safe ` +
            `to try again.`,
        )
      } else {
        // ⚠️ The check itself failed. "Still unknown" rather than falling back
        // to the sentence that started all this.
        setFailed(
          `${said} The follow-up check could not reach the server either, so ` +
            `what was saved is still unknown. Do not re-upload until it answers.`,
        )
      }
    } finally {
      setBusy(false)
    }
  }

  const report = result?.report ?? {}
  const people = report.employees
  const ambiguous = Object.keys(report.ambiguous_names ?? {})
  const unknownCodes = Object.keys(report.unknown_codes ?? {})
  const anomalies = report.union_salary_anomalies ?? []

  return (
    <section aria-label="Register upload" data-testid="setup-register" className={CARD}>
      <h2 className="text-h4 text-content-strong">2 · Load the payroll register</h2>
      <p className="mt-2 text-body text-content-muted">
        The Payroll Register PDF, downloaded from Payentry. It is read here and
        nothing is sent back — there is no Payentry login in this process.
        Re-uploading an overlapping range is safe: duplicates are counted and
        change nothing.
      </p>

      {enabled === false ? (
        // ⚠️ A WRITTEN EMPTY STATE THAT SAYS WHAT TO DO NEXT, rather than a
        // disabled button with no explanation. The refusal here is the switch
        // above, and saying so is the only useful thing this card can do.
        <p className="mt-3 text-body text-content-base" data-testid="register-blocked">
          Payroll data loading is off for this company, so an upload would be
          refused. Turn it on in step 1 first.
        </p>
      ) : (
        <div className="mt-4 space-y-3">
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf,.pdf"
            data-testid="register-file"
            className="block text-body-sm text-content-base"
            onChange={(e) => {
              setChosen(e.target.files?.[0] ?? null)
              setResult(null)
              setFailed(null)
            }}
          />
          {chosen ? (
            <Confirm
              testId="register-upload"
              trigger={`Import ${chosen.name}`}
              confirmLabel="Import it"
              busy={busy}
              disabled={enabled === null}
              consequence={
                <>
                  This reads <strong>{chosen.name}</strong> and stores every
                  check it can account for — names, pay rates, deductions.
                  Checks already loaded are left alone. Anything that does not
                  add up is reported below rather than stored silently.
                </>
              }
              onConfirm={run}
            />
          ) : (
            <p className="text-body-sm text-content-muted" data-testid="register-no-file">
              Choose a register PDF to import. Nothing happens until you do.
            </p>
          )}
        </div>
      )}

      {failed ? (
        <Outcome testId="register-said" ok={false}>
          {failed}
        </Outcome>
      ) : null}

      {result ? (
        <div className="mt-4" data-testid="register-result">
          <p className="text-body text-content-base">
            Loaded{" "}
            <span className="text-content-strong">
              {result.checks_inserted} {result.checks_inserted === 1 ? "check" : "checks"}
            </span>
            {typeof people === "number" ? (
              <>
                {" "}
                for <span className="text-content-strong">{people}</span>{" "}
                {people === 1 ? "person" : "people"}
              </>
            ) : null}{" "}
            from {result.pages} {result.pages === 1 ? "page" : "pages"}.
          </p>
          <ul className="mt-2 space-y-1 text-body-sm text-content-muted">
            <li data-testid="register-duplicates">
              {result.checks_duplicate === 0
                ? "No duplicates — none of these checks had been loaded before."
                : `${result.checks_duplicate} already loaded and skipped. That is the re-upload guard working, not a fault.`}
            </li>
            <li
              data-testid="register-failures"
              className={result.checks_failed > 0 ? "text-status-error" : undefined}
            >
              {result.checks_failed === 0
                ? "Nothing failed — every check on the file added up."
                : `${result.checks_failed} ${
                    result.checks_failed === 1 ? "check" : "checks"
                  } did not add up and were NOT stored. They need looking at in Payentry.`}
            </li>
            {ambiguous.length > 0 ? (
              <li data-testid="register-ambiguous">
                {ambiguous.length} employee{ambiguous.length === 1 ? "" : "s"} printed
                under more than one name ({ambiguous.join(", ")}). Reported, never
                merged — only a person can tell a parse fault from a name change.
              </li>
            ) : null}
            {unknownCodes.length > 0 ? (
              <li data-testid="register-unknown-codes">
                {unknownCodes.length} pay or deduction code{unknownCodes.length === 1 ? "" : "s"}{" "}
                not in the rulebook: {unknownCodes.join(", ")}.
              </li>
            ) : null}
            {anomalies.length > 0 ? (
              <li data-testid="register-anomalies">
                {anomalies.length} check{anomalies.length === 1 ? "" : "s"} carrying both
                salary and union dues — a contradiction to resolve in Payentry.
              </li>
            ) : null}
          </ul>
          {result.checks_failed === 0 &&
          ambiguous.length === 0 &&
          unknownCodes.length === 0 &&
          anomalies.length === 0 ? (
            <p className="mt-2 text-body-sm text-content-muted" data-testid="register-clean">
              Nothing needs your attention on this import. Step 3 is next.
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}

// ─── (3) the roster reconcile ────────────────────────────────────────────────

function peopleWord(n: number) {
  return n === 1 ? "person" : "people"
}

function RosterCard({ enabled }: { enabled: boolean | null }) {
  const [busy, setBusy] = useState(false)
  const [preview, setPreview] = useState<ReconcileResult | null>(null)
  const [applied, setApplied] = useState<ReconcileResult | null>(null)
  const [failed, setFailed] = useState<string | null>(null)
  /** The roster as it stood BEFORE apply was pressed, so a lost reply can be
   *  settled by comparison rather than by guessing. Captured when the preview
   *  runs, which is always before an apply. */
  const [before, setBefore] = useState<RosterStatus | null>(null)

  async function run(apply: boolean) {
    setBusy(true)
    setFailed(null)
    try {
      const r = await reconcileRegisterPeople(apply)
      if (apply) setApplied(r)
      else {
        setPreview(r)
        setApplied(null)
        // Cheap, and the only chance to read "before" while nothing is wrong.
        getRosterStatus()
          .then(setBefore)
          .catch(() => setBefore(null))
      }
    } catch (err) {
      const said = failureText(err)
      if (!gotNoReply(err) || !apply) {
        // A refusal shows the server's words. A failed PREVIEW writes nothing,
        // so there is nothing to go and check — saying otherwise would be the
        // unkept promise again, in the other direction.
        setFailed(said)
        return
      }
      // ⚠️ **AN APPLY WHOSE REPLY NEVER ARRIVED, WHICH IS WHAT HAPPENED ON
      // 2026-11-17: 499 after 125 s, and the server committed 19 s later.**
      // The page showed "this page will check what was saved" and then did
      // nothing, because this branch did not exist.
      setFailed(said + CHECKING_SUFFIX)
      let after: RosterStatus | undefined
      const verdict = await didWriteLand(
        () => getRosterStatus(),
        (now) => {
          after = now
          // The audit row is written only on apply, so a timestamp that moved
          // is proof this apply committed. Falling back to the row count
          // covers the case where no "before" was captured.
          if (before?.last_reconciled_at && now.last_reconciled_at) {
            return now.last_reconciled_at !== before.last_reconciled_at
          }
          if (now.last_reconciled_at) return true
          return before !== null && now.employees > before.employees
        },
      )
      if (verdict === "landed") {
        setFailed(
          `No reply reached this page, but the server DID create the list: ` +
            `${after?.employees ?? 0} people, ${after?.union_members ?? 0} union ` +
            `members. Nothing to redo.`,
        )
      } else if (verdict === "did-not-land") {
        setFailed(
          `No reply reached this page, and the roster shows no new reconcile — ` +
            `nothing was written, so it is safe to press it again. It only ever ` +
            `fills blanks.`,
        )
      } else {
        setFailed(
          `${said} The follow-up check could not reach the server either, so ` +
            `whether the list was created is unknown. Do not press it again ` +
            `until it responds.`,
        )
      }
    } finally {
      setBusy(false)
    }
  }

  const fills = preview ? preview.proposals.filter((p) => p.verdict === "fill") : []
  const fillFields = new Set(fills.map((p) => p.field))

  return (
    <section aria-label="Employee list" data-testid="setup-roster" className={CARD}>
      <h2 className="text-h4 text-content-strong">3 · Create the employee list from the register</h2>
      <p className="mt-2 text-body text-content-muted">
        Reads the people out of the loaded register and fills in what the
        payroll roster does not yet know. It never overwrites a fact somebody
        set by hand: where the roster already says something different, the
        disagreement is reported and left for you.
      </p>

      {enabled === false ? (
        <p className="mt-3 text-body text-content-base" data-testid="roster-blocked">
          Payroll data loading is off for this company, so there is nothing to
          read. Turn it on in step 1 and load a register in step 2 first.
        </p>
      ) : (
        <div className="mt-4 space-y-3">
          <button
            type="button"
            data-testid="roster-preview"
            className={BUTTON}
            disabled={busy || enabled === null}
            onClick={() => run(false)}
          >
            {busy && !preview ? "Reading the register…" : "See what it would create"}
          </button>
          {!preview && !failed ? (
            <p className="text-body-sm text-content-muted" data-testid="roster-not-run">
              Nothing has been read yet. This shows you the changes before any
              of them are written.
            </p>
          ) : null}
        </div>
      )}

      {failed ? (
        <Outcome testId="roster-said" ok={false}>
          {failed}
        </Outcome>
      ) : null}

      {preview && !applied ? (
        <div className="mt-4 space-y-2" data-testid="roster-preview-result">
          <p className="text-body text-content-base">
            The register accounts for{" "}
            <span className="text-content-strong">{preview.employees_seen}</span>{" "}
            {peopleWord(preview.employees_seen)}, and{" "}
            <span className="text-content-strong">{preview.union_members_proved}</span>{" "}
            of them had union dues deducted — which proves membership.
          </p>

          {fills.length === 0 ? (
            // ⚠️ Written, and it distinguishes the two reasons for nothing to
            // do. "No changes" with no explanation would read identically to a
            // reconcile that found no register at all.
            <p className="text-body-sm text-content-muted" data-testid="roster-nothing-to-fill">
              {preview.employees_seen === 0
                ? "No people found. Load a register in step 2 first — there is nothing to read from yet."
                : "The roster already knows everything this register could tell it. Nothing to create."}
            </p>
          ) : (
            <>
              <p className="text-body-sm text-content-base" data-testid="roster-fills">
                It would fill in <span className="text-content-strong">{fills.length}</span>{" "}
                blank {fills.length === 1 ? "field" : "fields"}
                {fillFields.size > 0 ? ` (${[...fillFields].sort().join(", ")})` : ""} for{" "}
                {new Set(fills.map((p) => p.emp_id)).size}{" "}
                {peopleWord(new Set(fills.map((p) => p.emp_id)).size)}.
              </p>
              <Confirm
                testId="roster-apply"
                trigger="Create the employee list"
                confirmLabel="Create it"
                busy={busy}
                consequence={
                  <>
                    This writes the <strong>{fills.length}</strong> blank{" "}
                    {fills.length === 1 ? "field" : "fields"} above onto the
                    payroll roster. Nothing that already has a value is touched,
                    and the {preview.conflicts.length} disagreement
                    {preview.conflicts.length === 1 ? "" : "s"} below{" "}
                    {preview.conflicts.length === 1 ? "is" : "are"} left for you
                    to settle.
                  </>
                }
                onConfirm={() => run(true)}
              />
            </>
          )}

          {preview.conflicts.length > 0 ? (
            <div className="mt-2" data-testid="roster-conflicts">
              <p className="text-body-sm text-status-error">
                {preview.conflicts.length} disagreement
                {preview.conflicts.length === 1 ? "" : "s"} — not written, for you to settle:
              </p>
              <ul className="mt-1 space-y-1 text-body-sm text-content-muted">
                {preview.conflicts.map((c) => (
                  <li key={`${c.emp_id}:${c.field}`}>
                    {c.emp_id} · {c.field}: register says “{c.register_says}”, the
                    roster says “{c.roster_says ?? "nothing"}”
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {Object.keys(preview.ambiguous_names).length > 0 ? (
            <p className="text-body-sm text-content-muted" data-testid="roster-ambiguous">
              {Object.keys(preview.ambiguous_names).length} employee
              {Object.keys(preview.ambiguous_names).length === 1 ? "" : "s"} printed
              under more than one name. Reported, never merged.
            </p>
          ) : null}
        </div>
      ) : null}

      {applied ? (
        <div className="mt-4" data-testid="roster-applied">
          <p className="text-body text-content-base">
            {applied.applied.length === 0 ? (
              "Nothing was written — there was nothing left to fill in."
            ) : (
              <>
                Created{" "}
                <span className="text-content-strong">{applied.applied.length}</span>{" "}
                {applied.applied.length === 1 ? "entry" : "entries"} on the payroll
                roster for{" "}
                {new Set(applied.applied.map((p) => p.emp_id)).size}{" "}
                {peopleWord(new Set(applied.applied.map((p) => p.emp_id)).size)}.
              </>
            )}
          </p>
          <p className="mt-1 text-body-sm text-content-muted">
            {applied.conflicts.length === 0
              ? "No disagreements were found, so nothing is waiting on you."
              : `${applied.conflicts.length} disagreement${
                  applied.conflicts.length === 1 ? "" : "s"
                } were left untouched and still need settling.`}
          </p>
        </div>
      ) : null}
    </section>
  )
}

// ─── the page ────────────────────────────────────────────────────────────────

export default function PayrollSetup() {
  const [sw, setSw] = useState<Loaded<DataSwitchState>>(null)

  useEffect(() => {
    let live = true
    getDataEnabled()
      .then((s) => live && setSw(s))
      .catch(() => live && setSw(false))
    return () => {
      live = false
    }
  }, [])

  // ⚠️ `null` while loading AND when unreadable, and the two are NOT collapsed
  // to `false`. The cards below use it to decide whether to say "the switch is
  // off, turn it on first" — a claim that would be a guess in either state.
  const enabled = sw ? sw.enabled : null

  return (
    <div className="space-y-6 p-6" data-testid="payroll-setup">
      <header className="space-y-1">
        <h1 className="text-h1 text-content-strong">Payroll setup</h1>
        <p className="text-body text-content-muted">
          Three steps, in order, done once per company. After them Susan's
          payroll screens show real figures instead of “no hours yet”.
        </p>
      </header>

      <DataSwitchCard state={sw} onChanged={setSw} />
      <RegisterCard enabled={enabled} />
      <RosterCard enabled={enabled} />
    </div>
  )
}
