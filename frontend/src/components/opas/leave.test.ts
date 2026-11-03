/**
 * Which words leave the bar, and — more importantly — which do not.
 *
 * ⚠️ THE REFUSALS ARE THE TESTS THAT MATTER. A word that leaves too early is text
 * destroyed out from under the director's caret, and there is no undo for it; a word
 * that leaves too late merely sits in the bar a moment longer. Every gate below is
 * asserted in the refusing direction first.
 */
import { describe, expect, it } from "vitest"

import {
  aLongerTermStartsWith,
  textWithout,
  wordsReadyToLeave,
  type Leaving,
} from "./leave"
import type { CaptureSpan, VocabTerm } from "@/services/opas-capture-service"

const t = (text: string, kind = "cemetery"): VocabTerm =>
  ({ text, kind }) as VocabTerm

/** Sunnycrest's real shape for the lookahead case: the term is longer than the words
 *  the office types, and its punctuation does not match theirs. */
const VOCAB: VocabTerm[] = [
  t("St. Mary's Cemetery"),
  t("Hopkins Funeral Home", "funeral_home"),
  t("Monticello Burial Vault", "vault"),
]

const span = (
  start: number,
  end: number,
  fields: string[],
  state: CaptureSpan["state"] = "captured",
): CaptureSpan => ({ start, end, state, field_ids: fields }) as CaptureSpan

function leaving(text: string, spans: CaptureSpan[]): readonly Leaving[] {
  return wordsReadyToLeave(text, spans, text, VOCAB)
}

describe("gate 1 — nothing leaves while the caret is still on it", () => {
  it("a word at the very end of the text STAYS", () => {
    /** ⚠️ THE WHOLE OF "TYPED PAST": the caret is still on the word, so it must keep it.
     *
     *  ⚠️ AND THE TERM HERE IS DELIBERATELY ONE NOTHING EXTENDS, BECAUSE MY FIRST
     *  VERSION USED `monticello` AND A BREAK TEST PROVED IT NON-DISCRIMINATING.
     *  Deleting gate 1 outright left this green — `Monticello Burial Vault` starts with
     *  `monticello`, so GATE 2 was holding the word and gate 1 was never consulted. The
     *  comment on the next test warns about exactly that trap and this test fell into
     *  it anyway, which is why the break matrix is run rather than reasoned about. */
    const text = "order for hopkins funeral home"
    expect(leaving(text, [span(10, 30, ["funeral_home"])])).toEqual([])
  })

  it("the same word leaves once ANYTHING follows it", () => {
    /** ⚠️ `hopkins`, NOT `monticello`, AND MY FIRST VERSION OF THIS TEST USED THE
     *  WRONG WORD. `Monticello Burial Vault` is in the vocabulary, so `"monticello "`
     *  is held by GATE 2 — a longer term may still be coming — and this test would
     *  have been asserting gate 1 while gate 2 answered it. `Hopkins Funeral Home` is
     *  longer than `hopkins` too, so the word chosen here is the full term: nothing in
     *  the vocabulary extends it. */
    const text = "order for hopkins funeral home "
    expect(leaving(text, [span(10, 30, ["funeral_home"])])).toEqual([
      { fieldId: "funeral_home", text: "hopkins funeral home", start: 10, end: 30 },
    ])
  })

  it("a word whose term COULD be extended waits even with a space after it", () => {
    /** The case the test above used to confuse itself with, asserted for what it is. */
    const text = "order for monticello "
    expect(leaving(text, [span(10, 20, ["vault"])])).toEqual([])
  })

  it("a word mid-sentence leaves", () => {
    const text = "order for hopkins monticello"
    const got = leaving(text, [span(10, 17, ["funeral_home"]), span(18, 28, ["vault"])])
    // ⚠️ ONE, NOT TWO. `hopkins` has been typed past; `monticello` is at the caret.
    expect(got.map((g) => g.fieldId)).toEqual(["funeral_home"])
  })
})

describe("gate 2 — a longer term may still be coming", () => {
  it("'st marys ' WAITS, because St. Mary's Cemetery starts with it", () => {
    /** ⚠️ THE DESIGN REVIEW'S OWN CASE, and the punctuation is the trap:
     *  `"st. mary's cemetery".startsWith("st marys")` is FALSE in plain JS. A
     *  character-wise lookahead would not fire here at all. */
    const text = "order for st marys "
    expect(leaving(text, [span(10, 18, ["cemetery"])])).toEqual([])
  })

  it("but it LEAVES once a word that cannot continue it follows", () => {
    const text = "order for st marys thursday"
    const got = leaving(text, [span(10, 18, ["cemetery"])])
    expect(got.map((g) => g.text)).toEqual(["st marys"])
  })

  it("and WAITS while the next word could still continue it", () => {
    /** The prototype's second branch: the next token is the last and unfinished, so
     *  `"st marys ce"` is checked as a prefix — and it is one. */
    const text = "order for st marys ce"
    expect(leaving(text, [span(10, 18, ["cemetery"])])).toEqual([])
  })

  it("a complete term nothing extends leaves immediately", () => {
    /** ⚠️ THE CONTROL ON GATE 2. If the lookahead matched too eagerly, nothing would
     *  ever leave — which is the failure mode that looks like the feature being off. */
    const text = "order for monticello burial vault "
    const got = leaving(text, [span(10, 33, ["vault"])])
    expect(got.map((g) => g.text)).toEqual(["monticello burial vault"])
  })

  it("the lookahead needs a LONGER term, not an equal one", () => {
    expect(aLongerTermStartsWith("st marys cemetery", VOCAB)).toBe(false)
    expect(aLongerTermStartsWith("st marys", VOCAB)).toBe(true)
  })
})

describe("what never leaves at all", () => {
  it("an UNRECOGNIZED word stays in the bar", () => {
    /** ⚠️ THE PROTOTYPE'S OWN DIVISION OF LABOUR: *"Words Opas understands fly into the
     *  order … anything Opas can't place waits under the order."* Flying away words
     *  nobody placed would empty the bar of exactly the text still needing a fix.
     *
     *  ⚠️ WHICH GUARD CARRIES THIS, MEASURED RATHER THAN ASSUMED: the FIELD-COUNT one,
     *  not the state one. An unrecognized span carries no field, so deleting
     *  `state !== "captured"` leaves this green — a word with no field is refused for
     *  having nowhere to fly to. The state check is pinned by the CONFLICT test below,
     *  whose span does carry a field. Two refusals, two guards, and the break matrix
     *  is what told them apart. */
    const text = "order for blargle thursday"
    expect(leaving(text, [span(10, 17, [], "unrecognized")])).toEqual([])
  })

  it("a span with NO field stays, even when captured", () => {
    /** ⚠️ THE FIELD-COUNT GUARD'S OWN ZERO CASE, and without it `field_ids[0]` is
     *  `undefined` — the pane would record a value against a field id of `undefined`,
     *  which is a write to the order with no row to show it in. */
    const text = "order for blargle thursday"
    expect(leaving(text, [span(10, 17, [], "captured")])).toEqual([])
  })

  it("a CONFLICTED span stays", () => {
    const text = "order for nameplate only thursday"
    expect(leaving(text, [span(10, 24, ["personalization"], "conflict")])).toEqual([])
  })

  it("a span carrying TWO fields stays", () => {
    /** ⚠️ `"1948 to 2026"` IS ONE SPAN FOR TWO FIELDS. One word cannot fly to two rows,
     *  and choosing one would record half a claim — so it stays in the bar, where it is
     *  already captured and already visible. A deliberate omission, not an oversight. */
    const text = "order for 1948 to 2026 thursday"
    expect(
      leaving(text, [span(10, 22, ["date_of_birth", "date_of_death"])]),
    ).toEqual([])
  })

  it("STALE spans leave nothing", () => {
    /** ⚠️ STRONGER THAN THE MIRROR'S SAME RULE. A mis-painted tint shows the wrong
     *  word; acting on a stale span CUTS THE WRONG CHARACTERS out of the bar, and there
     *  is no undo. */
    const text = "order for hopkins monticello"
    expect(
      wordsReadyToLeave(text, [span(10, 17, ["funeral_home"])], "order for hop", VOCAB),
    ).toEqual([])
  })

  it("a span outside the text leaves nothing", () => {
    /** ⚠️ CARRIED BY GATE 1, NOT BY THE RANGE GUARD, measured by deleting the range
     *  guard and watching this stay green. `sp.end > text.length` implies
     *  `sp.end >= text.length`, so the caret gate answers every over-long span first.
     *  The range guard is not redundant — the two cases below are its alone. */
    const text = "order"
    expect(leaving(text, [span(10, 17, ["funeral_home"])])).toEqual([])
  })

  it("a span starting BEFORE the text leaves nothing", () => {
    /** ⚠️ THE RANGE GUARD'S OWN CASE, and a negative start is not merely out of range —
     *  `String.slice` reads a negative index FROM THE END, so the pane would cut a
     *  perfectly plausible word out of the wrong part of the bar and record it. A
     *  silently wrong cut, which is the one failure mode here with no undo. */
    const text = "order for hopkins x"
    expect(leaving(text, [span(-5, 17, ["funeral_home"])])).toEqual([])
  })

  it("an INVERTED span leaves nothing", () => {
    /** The range guard's other case: `end <= start` slices to the empty string, so the
     *  pane would record `""` against a real field and cut nothing out of the bar. */
    const text = "order for hopkins x"
    expect(leaving(text, [span(15, 10, ["funeral_home"])])).toEqual([])
  })

  it("no spans, no text, no vocabulary — all empty", () => {
    expect(wordsReadyToLeave("", [], "", VOCAB)).toEqual([])
    expect(wordsReadyToLeave("abc", undefined, "abc", VOCAB)).toEqual([])
    // ⚠️ AND AN EMPTY VOCABULARY DOES NOT STOP WORDS LEAVING. It is the lookahead's
    // input, not the rule's premise — a tenant whose vocabulary has not loaded yet
    // would otherwise freeze the whole gesture.
    const got = wordsReadyToLeave(
      "order for hopkins x", [span(10, 17, ["funeral_home"])], "order for hopkins x", [],
    )
    expect(got.map((g) => g.text)).toEqual(["hopkins"])
  })
})

describe("cutting the word out of the bar", () => {
  it("collapses the gap it leaves behind", () => {
    /** ⚠️ A MEASURED DEFECT, NOT A TIDINESS PREFERENCE. James's own session carried
     *  `full_text = 'riverside full equipment  chairs'` — a DOUBLE SPACE where a
     *  removed word had been — and that gap is what made the digit-swallowing bug
     *  visible at all. */
    expect(textWithout("order for hopkins monticello", 18, 28)).toBe("order for hopkins")
    expect(textWithout("a hopkins b", 2, 9)).toBe("a b")
    expect(textWithout("a hopkins b", 2, 9)).not.toContain("  ")
  })

  it("leaves no leading space when the FIRST word goes", () => {
    /** The other half of that same session: `" chairs"`. A bar that starts with a gap
     *  makes the next thing typed the second word of a sentence. */
    expect(textWithout("hopkins monticello", 0, 7)).toBe("monticello")
    expect(textWithout("hopkins monticello", 0, 7)).not.toMatch(/^\s/)
  })

  it("leaves no trailing space when the LAST word goes", () => {
    expect(textWithout("order for hopkins", 10, 17)).toBe("order for")
  })

  it("cutting the only word leaves nothing", () => {
    expect(textWithout("hopkins", 0, 7)).toBe("")
    expect(textWithout(" hopkins ", 1, 8)).toBe("")
  })
})
