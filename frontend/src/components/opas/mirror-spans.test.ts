/**
 * Slicing the bar's text by the server's spans. James 2026-10-16, step 2.
 *
 * ⚠️ THE STALE RULE IS THE ONE WORTH MOST OF THIS FILE. A span computed for
 * "order for hop" says nothing about "order for hopkins f". Rendering it anyway —
 * clamped, shifted, or best-effort — paints a tint over words the engine never
 * claimed, and that reads as a parser bug rather than a rendering bug, so it would
 * be debugged in the wrong half of the system.
 */
import { describe, expect, it } from "vitest"

import { fieldsAtCaret, mirrorPieces } from "./mirror-spans"

const T = "order for hopkins blargle"
//          0123456789...
const SPANS = [
  { start: 10, end: 17, state: "captured" as const, field_ids: ["funeral_home"] },
  { start: 18, end: 25, state: "unrecognized" as const, field_ids: [] },
]

describe("mirrorPieces", () => {
  it("covers the text exactly, with no characters added or lost", () => {
    // ⚠️ THE ASSERTION THAT CATCHES EVERY OFF-BY-ONE AT ONCE. If the pieces rejoin to
    // the original string, no character was duplicated, dropped or reordered — which
    // is the whole correctness question for a slicer.
    const joined = mirrorPieces(T, SPANS, T).map((p) => p.text).join("")
    expect(joined).toBe(T)
  })

  it("decorates exactly the claimed text", () => {
    const pieces = mirrorPieces(T, SPANS, T)
    const captured = pieces.filter((p) => p.state === "captured")
    const dotted = pieces.filter((p) => p.state === "unrecognized")
    expect(captured.map((p) => p.text)).toEqual(["hopkins"])
    expect(captured[0].fieldIds).toEqual(["funeral_home"])
    expect(dotted.map((p) => p.text)).toEqual(["blargle"])
  })

  it("leaves the gaps between spans plain", () => {
    const plain = mirrorPieces(T, SPANS, T).filter((p) => p.state === null)
    expect(plain.map((p) => p.text)).toEqual(["order for ", " "])
  })

  it("renders NOTHING decorated when the spans are for other text", () => {
    // James: "only when spans_for_text === current text exactly. Otherwise render none."
    const pieces = mirrorPieces(T + " more", SPANS, T)
    expect(pieces).toHaveLength(1)
    expect(pieces[0].state).toBeNull()
    expect(pieces[0].text).toBe(T + " more")
  })

  it("renders nothing decorated one keystroke ahead OR behind", () => {
    // ⚠️ BOTH DIRECTIONS. Deleting a character is as common as adding one, and a
    // rule that only checked length would pass on a same-length edit.
    for (const text of ["order for hopkins blargl", "order for hopkins blargles",
                        "order for hopkins blargle".replace("h", "H")]) {
      const pieces = mirrorPieces(text, SPANS, T)
      expect(pieces.every((p) => p.state === null), text).toBe(true)
    }
  })

  it("discards a span that does not fit the text rather than clamping it", () => {
    // ⚠️ CLAMPING WOULD PAINT SOMETHING, which is the behaviour that hides the bug
    // that produced it. An impossible span is dropped and the rest still render.
    const pieces = mirrorPieces(T, [
      { start: 10, end: 17, state: "captured", field_ids: ["funeral_home"] },
      { start: 900, end: 999, state: "captured", field_ids: ["vault"] },
    ], T)
    expect(pieces.map((p) => p.text).join("")).toBe(T)
    expect(pieces.some((p) => p.fieldIds.includes("vault"))).toBe(false)
  })

  it("handles empty text and absent spans without inventing pieces", () => {
    expect(mirrorPieces("", SPANS, "")).toEqual([])
    expect(mirrorPieces(T, undefined, T)).toHaveLength(1)
    expect(mirrorPieces(T, [], T)).toHaveLength(1)
  })
})

describe("fieldsAtCaret", () => {
  it("reports the fields the caret is inside", () => {
    expect(fieldsAtCaret(SPANS, T, T, 12)).toEqual(["funeral_home"])
  })

  it("is inclusive at the start and EXCLUSIVE at the end", () => {
    // ⚠️ A CARET RESTING JUST AFTER A SPAN IS OUTSIDE IT. Otherwise typing a space
    // after a captured word keeps its row lit while the director has moved on.
    expect(fieldsAtCaret(SPANS, T, T, 10)).toEqual(["funeral_home"])
    expect(fieldsAtCaret(SPANS, T, T, 17)).toEqual([])
  })

  it("reports nothing while the spans are stale", () => {
    expect(fieldsAtCaret(SPANS, T, T + "!", 12)).toEqual([])
  })

  it("reports nothing with no caret", () => {
    expect(fieldsAtCaret(SPANS, T, T, null)).toEqual([])
  })
})
