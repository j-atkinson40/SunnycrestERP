/**
 * What Tab does, decided before anything moves.
 *
 * Slice 2, item 2 (James, 2026-10-28): *"Tab — accepts the ghost and flies the word in;
 * with no ghost, places the current word or holds it; Tab never moves focus out of the
 * bar."*
 *
 * ⚠️ THE GHOST HALF AND THE FOCUS HALF ALREADY SHIPPED — this module is the third
 * clause only. `OpasHost`'s bar has carried `if (e.key === "Tab" && entryMode) {
 * e.preventDefault(); … acceptGhost(…) }` since 2026-10-14, so Tab already completes a
 * term and already refuses to move focus. Measured before building rather than
 * rebuilt: what was missing is what Tab does when there is NO ghost to accept.
 *
 * ⚠️ THE RULE IS THE PROTOTYPE'S `leftover()`, AND THE TRANSLATION IS NOT LITERAL,
 * because the two engines divide the work differently.
 * `docs/prototypes/2026-10-27-guided-order-capture.html`:
 *
 *     function leftover(){
 *       const text=inp.value.trim();
 *       if(!text)return;
 *       if(S.pending){S.flash='Pick one of these first.';renderSide();shake();return}
 *       const cur=currentField(), nm=nameFrom(tokens(text));
 *       … if(f&&val){setField(f,val);inp.value='';runFlies([…]);return}
 *       hold(text,r);
 *     }
 *
 * The prototype matches the bar's text itself at Tab time. Ours does not have to: the
 * server has ALREADY re-extracted the whole text, so what is placeable is sitting in
 * `spans` as a `captured` span. Tab therefore READS the extraction rather than
 * repeating it, and the only decision left is place-this-one or hold-this-one.
 *
 * ⚠️ AND IT DELIBERATELY IGNORES GATE 1. `wordsReadyToLeave` refuses a word still under
 * the caret, because a word taken from under the caret is text destroyed with no undo.
 * Tab IS the director saying they are done with that word — the signal gate 1 exists to
 * wait for. So Tab places the word gate 1 is holding, which is the whole point of the
 * key: `"order for monticello"` + Tab lands the vault without waiting to see whether
 * `monticello 34` was coming.
 */
import type { CaptureSpan, VocabTerm } from "@/services/opas-capture-service"

/** Place a captured word into its field — the flying half of clause 1, on demand. */
export interface TabPlace {
  readonly kind: "place"
  readonly fieldId: string
  readonly text: string
  readonly start: number
  readonly end: number
}

/** Park a word Opas cannot place under the order. */
export interface TabHold {
  readonly kind: "hold"
  readonly word: string
  readonly start: number
  readonly end: number
}

export interface TabNothing {
  readonly kind: "nothing"
  /** Why, for the test to name and for a future flash line to say out loud. */
  readonly why: "empty" | "pick-open" | "not-capturing" | "no-span"
}

export type TabAction = TabPlace | TabHold | TabNothing

export interface TabInput {
  readonly text: string
  readonly spans: readonly CaptureSpan[] | undefined
  readonly spansForText: string | null | undefined
  readonly values: Readonly<Record<string, unknown>>
  readonly pendingPickCount: number
  readonly status: string
  readonly vocab: readonly VocabTerm[]
}

/**
 * What Tab should do, given everything the pane knows.
 *
 * ⚠️ PURE, AND THAT IS THE POINT RATHER THAN A STYLE PREFERENCE. The alternative is a
 * keydown handler that reads four pieces of state, measures a rect, starts an
 * animation and fires a request — one function in which every branch needs a DOM to
 * assert. Deciding first and acting second makes the DECISION testable without a
 * browser, which is where the refusals live.
 */
export function whatTabDoes(input: TabInput): TabAction {
  const { text, spans, spansForText, values, pendingPickCount, status } = input

  if (text.trim() === "") return { kind: "nothing", why: "empty" }
  // ⚠️ AN OPEN PICK OUTRANKS TAB, by ruling and by the prototype's own first branch
  // (`if(S.pending){…'Pick one of these first.'…}`). The director is mid-question;
  // placing or holding under it would answer a different one.
  if (pendingPickCount > 0) return { kind: "nothing", why: "pick-open" }
  if (status !== "capturing") return { kind: "nothing", why: "not-capturing" }

  // ⚠️ STALE SPANS CANNOT PLACE, BUT THEY CAN STILL HOLD — and the asymmetry is the
  // careful part. Placing cuts `[start,end)` out of the bar, so a span computed for
  // different text cuts the wrong characters. Holding reads the last word out of the
  // CURRENT text and needs no span at all, so Tab still does something useful while
  // the extraction is a keystroke behind, which is most of the time a person is typing.
  const fresh = spans !== undefined && spans.length > 0 && spansForText === text

  if (fresh) {
    // ⚠️ THE LAST PLACEABLE SPAN, NOT THE FIRST. Tab means "the word I just typed", and
    // earlier captured words have already flown away on their own under clause 1 — so
    // the one still sitting in the bar is the latest, which is the one gate 1 held.
    const placeable = (spans as readonly CaptureSpan[])
      .filter(
        (sp) =>
          sp.state === "captured" &&
          sp.field_ids.length === 1 &&
          sp.start >= 0 &&
          sp.end <= text.length &&
          sp.end > sp.start &&
          typeof values[sp.field_ids[0]] === "string" &&
          values[sp.field_ids[0]] !== "",
      )
      .sort((a, b) => a.start - b.start)
    const word = placeable[placeable.length - 1]
    if (word !== undefined) {
      return {
        kind: "place",
        fieldId: word.field_ids[0],
        text: text.slice(word.start, word.end),
        start: word.start,
        end: word.end,
      }
    }
  }

  // ⚠️ THE UNRECOGNIZED SPAN, WHOLE. `"order for green pastures"` holds
  // `green pastures`, not `pastures` — a held chip the director has to reassemble is
  // worse than no chip, because the cemetery's name is the thing they typed.
  if (fresh) {
    const unknown = (spans as readonly CaptureSpan[])
      .filter(
        (sp) =>
          sp.state === "unrecognized" &&
          sp.start >= 0 &&
          sp.end <= text.length &&
          sp.end > sp.start,
      )
      .sort((a, b) => a.start - b.start)
    const last = unknown[unknown.length - 1]
    if (last !== undefined) {
      return {
        kind: "hold",
        word: text.slice(last.start, last.end),
        start: last.start,
        end: last.end,
      }
    }
  }

  // ⚠️ NO SPAN, NO MOVE — AND THIS REPLACED A LAST-WORD FALLBACK THAT BROKE JAMES'S
  // WALK. The old code ended `const last = lastWordOf(text)` and held it, on the
  // reasoning that a Tab doing nothing reads as a dead key. It reads worse than that:
  // he typed `"8 chairs"`, Tab took `chairs` alone into the strip, and `8` sat in the
  // bar as a word Opas cannot place by itself.
  //
  // ⚠️ THE ENGINE HAD IT RIGHT THE WHOLE TIME, measured 2026-11-03: `"8 chairs"` is
  // ONE span, `(start=0, end=8, captured, ('chairs_total',))`. So does `"st marys"`
  // (0-8, cemetery), `"lowering device and grass"` (0-25, cemetery_equipment),
  // `"section A, lot 2"` (0-16, grave_location) and `"monticello Burial Vault"`
  // (0-23, vault). Every one is a phrase the server read as a unit, and `lastWordOf`
  // knew nothing about any of them — it counted spaces.
  //
  // James's ruling: *"Words leave the bar by the server's SPANS, never by single word
  // — a multi-word span leaves as one unit or not at all."* So the fallback is gone
  // rather than made smarter. Tab with no usable span waits, which costs one keypress
  // once the extraction lands; splitting a phrase costs the director their number.
  return { kind: "nothing", why: "no-span" }
}
