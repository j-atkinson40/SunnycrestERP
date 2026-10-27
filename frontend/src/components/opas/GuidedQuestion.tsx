/**
 * What Opas is asking, and the three or four answers — the guided-capture surface.
 *
 * James's dispatch of 2026-10-27, clause 1:
 *
 *   "the bar stays bottom right; the capture pane grows up out of it. The Opas pane
 *    (question + one-line hint) sits to the LEFT of the bar, bottom-aligned. Answer
 *    pills sit in a row directly ABOVE the bar. When narrow: pane, Opas pane, pills,
 *    bar, stacked."
 *
 * THE PROTOTYPE'S GEOMETRY, QUOTED (`docs/prototypes/2026-10-27-guided-order-capture.html`,
 * sha256 `34b3938d…`, line 44 of its own source):
 *
 *   .dock{…display:grid;
 *     grid-template-columns:300px minmax(0,600px);
 *     grid-template-areas:"side pane" "side chips" "side bar";
 *     gap:12px 16px;justify-content:end;align-items:end;…}
 *   @media (max-width:960px){.dock{grid-template-columns:minmax(0,600px);
 *     grid-template-areas:"pane" "side" "chips" "bar"}}
 *
 * ⚠️ THE NARROW ORDER IS THE DISPATCH'S, AND THE PROTOTYPE AGREES WITH IT EXACTLY —
 * `"pane" "side" "chips" "bar"` is pane, Opas pane, pills, bar. Stated because the two
 * could have disagreed and a reader should know they do not.
 *
 * ⚠️ FIXED POSITIONING RATHER THAN THE PROTOTYPE'S GRID, because the bar is already
 * `position: fixed` at `right: 24, bottom: 24` and has been since the overlay shipped.
 * Re-parenting it into a grid to inherit the prototype's layout would move the one
 * element every other measurement in `OpasHost` is taken from — `barH` feeds the entry
 * pane's height and the reply line's offset. So the AREAS are computed from the bar's
 * known box instead, which is the same arrangement `opas-reply` already uses.
 *
 * ⚠️ ⌥ AND NOT ⌘, BY RULING, AND THE PROTOTYPE SAYS ⌘. James, 2026-10-27: "Chrome keeps
 * ⌘1–8 for switching tabs, so ⌘ would only ever work in a desktop app. ⌥ works in every
 * browser." The prototype renders `const MOD=MAC?'⌘':'Ctrl+'` into each pill's `<kbd>`.
 *
 * ⚠️ AND ITS HANDLER ALREADY ACCEPTED OPTION, SO ONLY THE LABEL WAS EVER WRONG —
 * `const mod=e.metaKey||e.ctrlKey||e.altKey` (line 705). The ruling corrects what the
 * prototype ADVERTISES, not what it does. Worth knowing before someone "fixes" the
 * divergence by reading the prototype's display and changing this back.
 */
import { useCallback, useEffect, useMemo, useRef } from "react"

/** The prototype's `.side` column: `grid-template-columns:300px minmax(0,600px)`. */
const SIDE_WIDTH = 300
/** The prototype's column gap: `gap:12px 16px`. */
const SIDE_GAP = 16
/** The prototype's row gap, between the pills and the bar. */
const ROW_GAP = 12
/** The prototype's own breakpoint: `@media (max-width:960px)`. */
export const STACK_BELOW_PX = 960

/** The bar's own inset from the bottom and right. */
export const BAR_INSET = 24

/**
 * Where the capture pane's bottom edge goes: clear of the bar AND of the guided row.
 *
 * ⚠️ IT IS A FUNCTION SO THE TEST CAN READ THE REAL ONE. My first overlap test
 * REPLICATED this arithmetic in its own helper, which is CLAUDE.md §11 shape 9 — a
 * check written from the implementation, asserting the value the implementation
 * produces. Changing the anchor in `OpasHost` would have left it green. Both the host
 * and the test call this now, so the test watches the thing that ships.
 *
 * ⚠️ `guidedAbove` IS 0 WHEN THERE ARE NO PILLS, which keeps the pane TOUCHING the bar
 * in that case — asked for on 2026-10-26, when `bottom: 96` was a guess against a
 * ~46px bar and left it floating.
 */
export function paneBottomPx(barHeight: number, guidedAbove: number): number {
  return BAR_INSET + barHeight + guidedAbove
}

/** `.opt{…background:linear-gradient(160deg,var(--glass-a),var(--glass-b));…}` */
const PILL_GLASS: React.CSSProperties = {
  background: "linear-gradient(160deg, rgba(48,48,52,.66), rgba(16,16,18,.7))",
  backdropFilter: "blur(18px)",
  WebkitBackdropFilter: "blur(18px)",
  border: "1px solid rgba(255,255,255,.16)",
  boxShadow: "0 6px 18px rgba(0,0,0,.4)",
}

const PANE_GLASS: React.CSSProperties = {
  background: "linear-gradient(160deg, rgba(48,48,52,.66), rgba(16,16,18,.7))",
  backdropFilter: "blur(24px) saturate(1.4)",
  WebkitBackdropFilter: "blur(24px) saturate(1.4)",
  boxShadow:
    "inset 0 1px 0 rgba(255,255,255,.14), inset 0 0 0 1px rgba(255,255,255,.06), 0 24px 60px rgba(0,0,0,.55)",
}

export interface GuidedPill {
  readonly value: string
  readonly label: string
  readonly sub?: string
  /** An ACTION rather than an answer — today only `"review"`.
   *
   *  ⚠️ IT IS WHY `onAnswer` CANNOT BE THE ONLY ROUTE. Every other pill stores a value
   *  into a field; this one asks the pane to do what Enter does, and sending it through
   *  `/answer` would try to store "review" into whatever field was being asked. The
   *  prototype marks the same distinction — `{act:'review',label:'Review',sub:'Enter'}`. */
  readonly act?: string
}

/** The one action a pill can carry today. */
export const PILL_ACT_REVIEW = "review"

export interface GuidedQuestionProps {
  /** The sentence. Absent means there is nothing to ask and nothing renders. */
  readonly question: string | null
  readonly hint?: string | null
  /** Which field the answers belong to. Null when nothing is missing. */
  readonly fieldId: string | null
  readonly pills: readonly GuidedPill[]
  /** The "Cremation" chip's text, once the vault has settled the kind. */
  readonly cremation?: string | null
  /** The bar's measured height, so the pills sit directly above it. */
  readonly barHeight: number
  /** The bar's width, so the pills row and the bar share an edge. */
  readonly barWidth: string
  /** True below the prototype's 960px breakpoint: the Opas pane stacks above the pills. */
  readonly stacked: boolean
  /** Whether the bar currently holds text — a bare digit only answers when it is empty. */
  readonly barIsEmpty: boolean
  /** ⚠️ TRUE WHILE THE QUESTION TAKES NUMBERS. A bare "1" during "What time?" is the
   *  start of an answer, not a pick. The prototype's own list:
   *  `['time','dates','day'].includes(currentField())`. */
  readonly questionTakesNumbers: boolean
  readonly onAnswer: (fieldId: string, value: string) => void
  /** Perform a pill's ACTION — review, today. Absent means action pills are inert,
   *  which is a real state before the session exists. */
  readonly onAct?: (act: string) => void
  /**
   * How much room this surface takes ABOVE the bar, so the capture pane can sit clear
   * of it.
   *
   * ⚠️ IT IS REPORTED RATHER THAN ASSUMED BECAUSE IT WRAPS. Four pills at 1920px are
   * one row; the same four at 1280px can be two, and a hard-coded 44px would put the
   * pane back on top of the second row. The bar's height is already measured for
   * exactly this reason (`barH`) and this is the same mechanism.
   *
   * ⚠️ AND IT INCLUDES THE OPAS PANE WHEN STACKED. Below 960px the pane is above the
   * pills rather than left of the bar, so the room needed above the bar is both.
   */
  readonly onHeightAbove?: (px: number) => void
}

/**
 * ⚠️ THE FIELDS WHOSE ANSWERS ARE NUMBERS, so a bare digit must not be eaten.
 * The prototype's list is `['time','dates','day']`; these are this schema's ids for
 * the same four things. `extra_chairs_count` is ours and not the prototype's — it is
 * literally "how many", so it belongs by the same reasoning.
 */
export const NUMERIC_QUESTION_FIELDS: readonly string[] = [
  "service_time",
  "service_date",
  "date_of_birth",
  "date_of_death",
  "extra_chairs_count",
  "eta",
]

export function questionTakesNumbers(fieldId: string | null): boolean {
  return fieldId !== null && NUMERIC_QUESTION_FIELDS.includes(fieldId)
}

export function GuidedQuestion({
  question,
  hint,
  fieldId,
  pills,
  cremation,
  barHeight,
  barWidth,
  stacked,
  barIsEmpty,
  questionTakesNumbers: takesNumbers,
  onAnswer,
  onAct,
  onHeightAbove,
}: GuidedQuestionProps) {
  const pillsRef = useRef<HTMLDivElement | null>(null)
  const paneRef = useRef<HTMLDivElement | null>(null)

  /**
   * ⚠️ MEASURED, NOT COMPUTED, AND A RESIZE OBSERVER RATHER THAN A LAYOUT EFFECT. The
   * pills row wraps on width AND on content — a long cemetery name can push the fourth
   * pill to a second line without the window changing — so an effect keyed on props
   * would miss it. The bar's own height is observed the same way.
   */
  const report = useCallback(() => {
    if (onHeightAbove === undefined) return
    const pills = pillsRef.current
    const pane = paneRef.current
    let above = 0
    if (pills !== null && pills.offsetHeight > 0) {
      // ⚠️ TWO GAPS, NOT ONE, AND ONE GAP IS NOT ENOUGH. `guidedH` is measured from
      // the BAR'S TOP EDGE, so the room the pills need is the gap BELOW them (bar to
      // pills) plus their height plus the gap ABOVE them (pills to pane). With a
      // single gap the pane's bottom landed exactly on the pills' top — touching
      // rather than clear, which is not "nothing overlapping" with a shadow and a
      // border in play. The prototype's `.dock{gap:12px}` puts a gap between EVERY
      // row: bar, 12, chips, 12, pane.
      above += ROW_GAP + pills.offsetHeight + ROW_GAP
    }
    // ⚠️ ONLY WHEN STACKED. Wide, the Opas pane is in the column LEFT of the bar and
    // takes no room above it; adding its height there would push the capture pane up
    // by 100px of nothing.
    if (stacked && pane !== null && pane.offsetHeight > 0) {
      // ⚠️ ONE GAP HERE, because the gap BELOW the Opas pane is the one already added
      // above the pills. Rows stack bar, 12, chips, 12, side, 12, pane.
      above += pane.offsetHeight + ROW_GAP
    }
    onHeightAbove(above)
  }, [onHeightAbove, stacked])

  useEffect(() => {
    report()
    if (typeof ResizeObserver === "undefined") return
    const ro = new ResizeObserver(report)
    if (pillsRef.current !== null) ro.observe(pillsRef.current)
    if (paneRef.current !== null) ro.observe(paneRef.current)
    return () => ro.disconnect()
  }, [report, question, pills, stacked])

  // ⚠️ AND IT REPORTS ZERO ON THE WAY OUT. Without this the capture pane keeps the
  // room reserved for a pills row that is no longer rendered, leaving a gap above the
  // bar for the rest of the session.
  useEffect(() => () => onHeightAbove?.(0), [onHeightAbove])
  // ⚠️ CAPPED AT NINE BECAUSE THERE ARE NINE DIGITS. The server caps at four; this is
  // independence from that number rather than a second opinion about it — a tenth pill
  // would be unreachable by keyboard and labelled with a key that does not exist.
  const shown = useMemo(() => pills.slice(0, 9), [pills])

  /**
   * ⌥1-⌥9 ANYWHERE, A BARE DIGIT WHEN THE BAR IS EMPTY, OR A CLICK.
   *
   * ⚠️ CAPTURE PHASE, because the bar is a textarea that would otherwise consume the
   * keystroke first — the same reason the existing reply-line handler uses it.
   *
   * ⚠️ AND A BARE DIGIT IS REFUSED MID-PHRASE, which is the prototype's own rule:
   * `bareOK = document.activeElement!==inp || (!inp.value.trim() && !typingNumber)`.
   * "monticello 28" names a size, and consuming that 8 would both answer the wrong
   * question and eat a character.
   */
  useEffect(() => {
    // ⚠️ NO FIELD IS NOT NO PILLS. In the ready state `fieldId` is null and the only
    // pill is Review — so guarding on the field would make ⌥1 dead at exactly the
    // moment the office wants it. The branch below uses the field only for answers.
    if (shown.length === 0) return
    const options = shown
    const field = fieldId
    function onKeyDown(e: KeyboardEvent) {
      // ⚠️ `e.code` RATHER THAN `e.key` FOR THE OPTION PATH. On macOS ⌥1 produces the
      // character "¡" in `e.key`, so a `/^[1-9]$/` test on `key` never matches and the
      // whole ruling would be silently dead. `code` is `Digit1` whatever the modifier
      // does to the character. The prototype uses `e.code` for exactly this.
      const digit = /^Digit([1-9])$/.exec(e.code)
      if (digit === null) return
      if (e.metaKey || e.ctrlKey || e.shiftKey) return
      const index = Number(digit[1]) - 1
      if (index >= options.length) return
      // ⚠️ ⌥ WORKS WHEREVER THE FOCUS IS; a bare digit only when the bar is empty and
      // the question is not asking for a number.
      const bare = !e.altKey
      if (bare && !(barIsEmpty && !takesNumbers)) return
      e.preventDefault()
      e.stopImmediatePropagation()
      // ⚠️ ONE BRANCH, IN ONE PLACE, SHARED WITH THE CLICK. An action pill reached by
      // ⌥N and the same pill reached by a click must do the same thing; two call sites
      // deciding separately is how one of them ends up storing "review" into a field.
      const pill = options[index]
      if (pill.act !== undefined) onAct?.(pill.act)
      else if (field !== null) onAnswer(field, pill.value)
    }
    document.addEventListener("keydown", onKeyDown, true)
    return () => document.removeEventListener("keydown", onKeyDown, true)
  }, [fieldId, shown, barIsEmpty, takesNumbers, onAnswer, onAct])

  if (question === null) return null

  const barBottom = 24
  const barTop = barBottom + (barHeight || 46)

  // ── the Opas pane ───────────────────────────────────────────────────────────────
  // ⚠️ BOTTOM-ALIGNED WITH THE BAR WHEN WIDE (`align-items:end` plus the `"side bar"`
  // row), and ABOVE THE PILLS when stacked. Those are the two arrangements the
  // prototype declares; there is no third.
  const panePosition: React.CSSProperties = stacked
    ? {
        right: barBottom,
        bottom: barTop + ROW_GAP + (shown.length > 0 ? 44 : 0),
        width: barWidth,
      }
    : {
        right: `calc(${barBottom}px + ${barWidth} + ${SIDE_GAP}px)`,
        bottom: barBottom,
        width: SIDE_WIDTH,
      }

  return (
    <>
      <div
        data-testid="opas-guided-pane"
        ref={paneRef}
        data-stacked={stacked ? "true" : "false"}
        style={{
          position: "fixed",
          zIndex: 44,
          ...panePosition,
          ...PANE_GLASS,
          borderRadius: 18,
          padding: 14,
          display: "flex",
          flexDirection: "column",
          gap: 8,
          minWidth: 0,
          pointerEvents: "none",
        }}
      >
        {/* `.op` — the eyebrow, with the prototype's sphere as a 9px dot. */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 7,
            fontSize: 10.5,
            letterSpacing: ".16em",
            textTransform: "uppercase",
            color: "#64645f",
          }}
        >
          <span
            style={{
              width: 9,
              height: 9,
              borderRadius: "50%",
              background:
                "radial-gradient(circle at 35% 30%,#d8d8d8,#4a4a4a 55%,#111)",
              boxShadow: "0 0 8px rgba(255,255,255,.25)",
            }}
          />
          Opas
          {/* ⚠️ THE CHIP LIVES BESIDE THE EYEBROW, NOT IN THE ORDER PANE'S HEADER. The
              prototype puts it in the pane header because its pane is always open; ours
              is a separate surface that may be closed while the question is up, and a
              chip only visible when the pane happens to be open is a chip that is
              sometimes a lie about what the order is. */}
          {cremation ? (
            <span
              data-testid="opas-cremation-chip"
              style={{
                marginLeft: "auto",
                fontSize: 11,
                letterSpacing: 0,
                textTransform: "none",
                padding: "2px 9px",
                borderRadius: 999,
                color: "#8fb0cf",
                border: "1px solid rgba(143,176,207,.5)",
              }}
            >
              {cremation}
            </span>
          ) : null}
        </div>

        <div
          data-testid="opas-guided-question"
          role="status"
          aria-live="polite"
          style={{ fontSize: 17, lineHeight: 1.35, textWrap: "balance", color: "#f1f1ee" }}
        >
          {question}
        </div>

        {hint ? (
          <div
            data-testid="opas-guided-hint"
            style={{ fontSize: 12.5, color: "#a3a39f", lineHeight: 1.45 }}
          >
            {hint}
          </div>
        ) : null}

      </div>

      {/* ── the pills row, directly above the bar ───────────────────────────────────
          ⚠️ NOT RENDERED AT ALL WHEN EMPTY, which is the prototype's
          `.chips:empty{display:none}`. An empty glass strip above the bar on every
          free-text question would read as a row that failed to load. */}
      {shown.length > 0 ? (
        <div
          data-testid="opas-guided-pills"
          ref={pillsRef}
          style={{
            position: "fixed",
            zIndex: 44,
            right: barBottom,
            bottom: barTop + ROW_GAP,
            width: barWidth,
            display: "flex",
            flexWrap: "wrap",
            gap: 6,
            justifyContent: "flex-end",
            minWidth: 0,
          }}
        >
          {shown.map((pill, i) => (
            <button
              key={`${pill.value}-${i}`}
              type="button"
              data-testid={`opas-guided-pill-${i + 1}`}
              onClick={() => {
                if (pill.act !== undefined) onAct?.(pill.act)
                else if (fieldId !== null) onAnswer(fieldId, pill.value)
              }}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                maxWidth: "100%",
                textAlign: "left",
                ...PILL_GLASS,
                borderRadius: 999,
                padding: "5px 13px 5px 6px",
                cursor: "pointer",
                color: "#f1f1ee",
                font: "inherit",
              }}
            >
              {/* ⚠️ ⌥ AND THE NUMBER, which is the affordance for all three ways in —
                  the ⌥ chord, the bare digit, and the click. */}
              <kbd
                data-testid={`opas-guided-pill-key-${i + 1}`}
                style={{
                  fontFamily: "'IBM Plex Mono', ui-monospace, monospace",
                  fontSize: 11,
                  color: "#a3a39f",
                  border: "1px solid rgba(255,255,255,.16)",
                  borderRadius: 999,
                  padding: "1px 7px",
                  whiteSpace: "nowrap",
                }}
              >
                ⌥{i + 1}
              </kbd>
              <span
                style={{
                  fontSize: 13.5,
                  minWidth: 0,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {pill.label}
              </span>
              {pill.sub ? (
                <span
                  data-testid={`opas-guided-pill-sub-${i + 1}`}
                  style={{ fontSize: 12, color: "#a3a39f", whiteSpace: "nowrap" }}
                >
                  {pill.sub}
                </span>
              ) : null}
            </button>
          ))}
        </div>
      ) : null}
    </>
  )
}
