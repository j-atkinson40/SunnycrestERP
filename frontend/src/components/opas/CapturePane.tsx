/**
 * The typed order-capture pane.
 *
 * ⚠️ EVERY STRUCTURAL CHOICE IS QUOTED FROM `docs/prototypes/2026-10-01-opas-overlay.html`
 * (md5 `a52a1e95153bd5c686b88d0acffc31e6`) rather than designed here:
 *
 *   `:413`  header = title + `<b>N</b> captured` + `<b>N</b> needed`, the needed pill
 *           taking its emphasis class only once the director has signalled done
 *   `:414`  a column header row: the capture label on the left, `AI ASSIST` on the right
 *   `:410`  one row per field: a mark, a label, a value
 *   `:409`  value text per state — the value, "Still needed", "Not mentioned yet"
 *   `:416`  footer = a `Review` button, disabled while anything is needed, + Cancel
 *   `:389`  the review stage replaces the rows with a summary grid
 *   `:431`  a capture pane is `wide`
 *
 * ⚠️ THE FOURTH ROW STATE COMES FROM THE OTHER PROTOTYPE, and the Opas overlay is SILENT
 * on it — measured: zero occurrences of `unconfig` there. `not_configured` is
 * `docs/prototypes/2026-09-22-capture-schema-prototype.html` (md5
 * `5d286c79a855f7397a8d62f3ad983228`), `.cap.unconfig`: amber at lower intensity with a
 * DASHED mark border. Two sources, each cited, neither inferred from the other.
 *
 * ⚠️ THE SERVER OWNS THE STATE. This component holds a `CaptureState` and renders it. It
 * does not compute which fields are missing, does not resolve anything, and does not
 * choose between candidates — those are the engine's and the resolvers' jobs, and a
 * second implementation here would be the duplication the capture engine removed.
 */
import { useCallback, useEffect, useRef, useState } from "react"

import { writeStoredCaptureSession } from "@/contexts/opas-context"
import {
  addLine,
  choosePick,
  readCapture,
  startCapture,
  type CapturePick,
  type CaptureState,
} from "@/services/opas-capture-service"

/** ⚠️ Per-state classes, named after the prototype's own selectors so a reader can find
 *  them in the source file. */
const ROW_CLASS: Record<string, string> = {
  done: "border-[rgba(74,160,110,0.35)] bg-[rgba(74,160,110,0.05)]",
  needed: "border-[rgba(224,168,74,0.55)] bg-[rgba(224,168,74,0.08)]",
  not_mentioned: "border-border-subtle bg-transparent",
  // `.cap.unconfig` — amber at LOWER intensity than `needed`, and the mark is dashed.
  not_configured: "border-[rgba(224,168,74,0.35)] bg-[rgba(224,168,74,0.04)]",
}

const MARK_CLASS: Record<string, string> = {
  done: "border-[rgb(74,160,110)] text-[rgb(74,160,110)]",
  needed: "border-[rgb(224,168,74)] text-[rgb(224,168,74)]",
  not_mentioned: "border-border-base text-content-subtle",
  not_configured: "border-[rgb(224,168,74)] border-dashed text-[rgb(224,168,74)]",
}

/** The value text per state.
 *
 * ⚠️ A VALUE WINS OVER THE STATE WORDING, AND THIS DEVIATES FROM THE PROTOTYPE ON PURPOSE.
 * The prototype shows the value only when `done` (`:409`) — correct there, because its
 * rows are ONE FIELD each, so a row is either answered or it is not.
 *
 * Our rows COMPOSE several fields (`surfaces.py`): the Service row joins location, date
 * and time. Measured on dev: after typing a service date and time but no location, the
 * server returned that row with `state: "not_mentioned"` AND
 * `value: "2027-03-02 · 10:00"`. Following the prototype literally would print "Not
 * mentioned yet" over a value the director had just given, and they would retype it.
 *
 * So the wording is the FALLBACK, used when there is nothing to show. The state still
 * drives the colour and the mark, which is what says the row is not finished.
 */
function valueText(state: string, value: string | null): string {
  if (value) return value
  if (state === "needed") return "Still needed"
  if (state === "not_configured") return "Not configured for this licensee"
  return "Not mentioned yet"
}

export function CapturePane({
  openingLine,
  sessionId: existingSessionId,
  onSessionStarted,
}: {
  /** Fed through extraction on start, per the prototype (`:568` calls `feed` at once). */
  readonly openingLine?: string
  /** ⚠️ WHEN PRESENT THE PANE RE-READS RATHER THAN STARTING. This is how a tuck survives:
   *  the pane is re-mounted and reconstructed from the server, not from client memory. */
  readonly sessionId?: string
  readonly onSessionStarted?: (id: string) => void
}) {
  const [state, setState] = useState<CaptureState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [draft, setDraft] = useState("")
  const inputRef = useRef<HTMLInputElement | null>(null)
  // ⚠️ A REF, NOT STATE. Two StrictMode mounts would otherwise start two sessions, and
  // the second would orphan the first — a half-typed order nobody can reach.
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true
    let alive = true
    const run = async () => {
      try {
        const s = existingSessionId
          ? await readCapture(existingSessionId)
          : await startCapture(openingLine)
        if (!alive) return
        setState(s)
        if (!existingSessionId) onSessionStarted?.(s.session_id)
      } catch {
        if (!alive) return
        // ⚠️ A STALE RESTORED ID CLEARS ITSELF. If this mount was a restore and the server
        // no longer has that session, carrying the id forward would resurrect a ghost pane
        // on every reload. The wording distinguishes the two causes, because "could not
        // start" on a restore would send someone looking for the wrong fault.
        if (existingSessionId) {
          writeStoredCaptureSession(null)
          setError("That order is no longer on the server")
        } else {
          setError("Could not start the capture")
        }
      }
    }
    void run()
    return () => {
      alive = false
    }
  }, [existingSessionId, openingLine, onSessionStarted])

  const send = useCallback(
    async (line: string) => {
      if (!state || !line.trim()) return
      setBusy(true)
      try {
        setState(await addLine(state.session_id, line))
        setDraft("")
      } catch {
        setError("That line did not reach the server")
      } finally {
        setBusy(false)
        inputRef.current?.focus()
      }
    },
    [state],
  )

  const pick = useCallback(
    async (p: CapturePick, oneBased: number) => {
      if (!state) return
      setBusy(true)
      try {
        setState(await choosePick(state.session_id, p.field_id, oneBased))
      } catch {
        setError("That choice did not reach the server")
      } finally {
        setBusy(false)
      }
    },
    [state],
  )

  if (error) {
    return (
      <div className="p-4 text-body-sm text-status-error" data-testid="capture-error">
        {error}
      </div>
    )
  }
  if (!state) {
    return (
      <div className="p-4 text-body-sm text-content-muted" data-testid="capture-loading">
        Starting…
      </div>
    )
  }

  const rows = state.surface.rows
  const captured = rows.filter((r) => r.state === "done").length
  const needed = rows.filter((r) => r.state === "needed").length
  const reviewing = state.status === "review"

  return (
    <div className="flex flex-col gap-3 p-3" data-testid="capture-pane">
      {/* header — prototype `:413` */}
      <div className="flex items-center gap-2" data-testid="capture-head">
        <span className="text-body-sm font-medium text-content-strong">
          {reviewing ? "Review" : "Order capture"}
        </span>
        <span
          className="rounded-full border border-border-subtle px-2 py-0.5 text-micro text-content-muted"
          data-testid="capture-captured-pill"
        >
          <b className="text-content-strong">{captured}</b> captured
        </span>
        <span
          className={`rounded-full border px-2 py-0.5 text-micro ${
            needed
              ? "border-[rgba(224,168,74,0.55)] text-[rgb(224,168,74)]"
              : "border-border-subtle text-content-muted"
          }`}
          data-testid="capture-needed-pill"
        >
          <b>{needed}</b> needed
        </span>
      </div>

      {!reviewing && (
        <>
          {/* column header — prototype `:414`. ⚠️ `AI ASSIST` is a LABEL in the
              prototype and nothing more; this slice makes no model call, so the label
              would be a claim. It reads RULES, which is what the pane does. */}
          <div className="flex items-center justify-between border-b border-border-subtle pb-1 text-micro uppercase tracking-wide text-content-subtle">
            <span>Order capture</span>
            <span data-testid="capture-assist-label">RULES</span>
          </div>

          <div className="flex flex-col gap-1" data-testid="capture-rows">
            {rows.map((r) => (
              <div
                key={r.row_id}
                data-testid={`capture-row-${r.row_id}`}
                data-state={r.state}
                className={`flex items-start gap-2 rounded-base border px-2 py-1.5 ${
                  ROW_CLASS[r.state] ?? ROW_CLASS.not_mentioned
                }`}
              >
                <span
                  aria-hidden
                  className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border text-[10px] ${
                    MARK_CLASS[r.state] ?? MARK_CLASS.not_mentioned
                  }`}
                >
                  {r.state === "done" ? "✓" : ""}
                </span>
                <div className="min-w-0">
                  <div className="text-micro uppercase tracking-wide text-content-subtle">
                    {r.label}
                  </div>
                  <div
                    className={`text-body-sm ${
                      r.state === "done"
                        ? "text-content-strong"
                        : "italic text-content-muted"
                    }`}
                  >
                    {valueText(r.state, r.value)}
                  </div>
                  {r.secondary_value ? (
                    <div className="text-micro text-content-muted">
                      {r.secondary_value}
                    </div>
                  ) : null}
                </div>
              </div>
            ))}
          </div>

          {/* numbered picks — the prototype's `pending` mechanism (`:583`, `:606`, `:622`).
              ⚠️ ONE-BASED LABELS because the prototype's digit keys are 1..9. */}
          {state.pending_picks.map((p) => (
            <div
              key={p.field_id}
              data-testid={`capture-pick-${p.field_id}`}
              className="rounded-base border border-border-accent bg-accent-subtle p-2"
            >
              <div className="text-body-sm text-content-strong">
                {p.options.length} matches for “{p.phrase}”. Which one?
                {p.discriminator ? (
                  <span className="ml-1 text-micro text-content-muted">
                    ({p.discriminator})
                  </span>
                ) : null}
              </div>
              <ol className="mt-1 flex flex-col gap-1">
                {p.options.map(([value, label], i) => (
                  <li key={value}>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void pick(p, i + 1)}
                      data-testid={`capture-pick-option-${p.field_id}-${i + 1}`}
                      className="w-full rounded-base px-2 py-1 text-left text-body-sm hover:bg-surface-sunken focus-ring-accent"
                    >
                      <span className="mr-2 text-content-subtle">{i + 1}</span>
                      {label}
                    </button>
                  </li>
                ))}
              </ol>
            </div>
          ))}

          {/* ⚠️ UNRECOGNIZED TEXT IS VISIBLE AND ATTRIBUTED. E1's never-dropped rule is
              only worth anything if the director can see what was not understood. */}
          {state.unrecognized.length > 0 && (
            <div
              className="rounded-base border border-dashed border-border-base p-2"
              data-testid="capture-unrecognized"
            >
              <div className="text-micro uppercase tracking-wide text-content-subtle">
                Not understood
              </div>
              <ul className="mt-1 flex flex-col gap-0.5">
                {state.unrecognized.map((u, i) => (
                  <li
                    key={`${u}-${i}`}
                    className="text-body-sm text-content-muted"
                    data-testid="capture-unrecognized-item"
                  >
                    {u}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* the typed transcript, so a line can be attributed */}
          {state.typed_lines.length > 0 && (
            <ul
              className="flex flex-col gap-0.5 border-t border-border-subtle pt-2"
              data-testid="capture-lines"
            >
              {state.typed_lines.map((l, i) => (
                <li key={`${l}-${i}`} className="text-micro text-content-subtle">
                  {l}
                </li>
              ))}
            </ul>
          )}

          <form
            onSubmit={(e) => {
              e.preventDefault()
              void send(draft)
            }}
          >
            <input
              ref={inputRef}
              value={draft}
              disabled={busy}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Type what the director said…"
              aria-label="Type what the director said"
              data-testid="capture-input"
              className="w-full rounded-base border border-border-base bg-surface-raised px-2 py-1.5 text-body-sm focus-ring-accent"
            />
          </form>
        </>
      )}

      {/* review stage — prototype `:389-404`. ⚠️ READ-ONLY: no Approve control, by
          ruling (E5). A disabled button would read as a feature that exists. */}
      {reviewing && (
        <div data-testid="capture-summary" className="flex flex-col gap-2">
          <div className="grid grid-cols-2 gap-2">
            {rows.map((r) => (
              <div
                key={r.row_id}
                data-testid={`summary-row-${r.row_id}`}
                className="rounded-base border border-border-subtle p-2"
              >
                <div className="text-micro uppercase tracking-wide text-content-subtle">
                  {r.label}
                </div>
                <div className="text-body-sm text-content-strong">
                  {r.value ?? "None"}
                </div>
                {r.secondary_value ? (
                  <div className="text-micro text-content-muted">
                    {r.secondary_value}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
          <p className="text-micro text-content-subtle" data-testid="capture-no-approve">
            Read-only. Creating the sales order is a separate build.
          </p>
        </div>
      )}
    </div>
  )
}
