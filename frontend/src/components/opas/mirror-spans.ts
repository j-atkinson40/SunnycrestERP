/**
 * Turning the server's spans into contiguous pieces of the bar's text.
 *
 * ⚠️ A PURE FUNCTION, SEPARATE FROM THE COMPONENT, BECAUSE THIS IS WHERE THE
 * OFF-BY-ONE LIVES. Rendering is easy to eyeball and hard to test; slicing a string
 * by server offsets is the opposite. Keeping it here means the stale-text rule and
 * the gap-filling can be asserted without a DOM.
 */
import type { CaptureSpan } from "@/services/opas-capture-service"

export interface MirrorPiece {
  readonly text: string
  /** null for the stretches between spans — rendered plain. */
  readonly state: CaptureSpan["state"] | null
  readonly fieldIds: readonly string[]
  /** This piece's offsets in the text it was sliced from.
   *
   *  ⚠️ CARRIED SO A WORD'S RECT CAN BE MEASURED BEFORE IT LEAVES THE BAR. Slice 2's
   *  flight starts from where the word IS on screen, and the design review established
   *  that the start rect cannot come from the server: `spans_for_text` describes the
   *  text the server was handed, and clause 1 removes the word from that text in the
   *  same gesture. The mirror is the only thing that knows where a character is, and a
   *  piece has to say which characters it is for that lookup to be exact.
   *
   *  ⚠️ OFFSETS RATHER THAN A FIELD ID, because two pieces can carry the same field —
   *  a director who names the funeral home twice — and the flight is about one of
   *  them. */
  readonly start: number
  readonly end: number
}

/**
 * Slice `text` into pieces, decorated where a span covers it.
 *
 * ⚠️ IT RETURNS ONE PLAIN PIECE WHEN THE SPANS ARE NOT FOR THIS EXACT TEXT. James:
 * "Render spans from the server response in the mirror, only when spans_for_text ===
 * current text exactly. Otherwise render none." Comparing the TEXT rather than a
 * counter is what makes this safe: a counter needs both sides to agree about
 * sequencing, and the failure mode of getting that wrong is a tint drawn over the
 * wrong words — which looks like a parser bug and is a rendering bug.
 *
 * ⚠️ STALE SPANS ARE DROPPED, NEVER SHIFTED. There is no "best effort" here. A span
 * computed for "order for hop" says nothing about "order for hopkins f", and
 * stretching it would be inventing a claim the engine never made.
 */
export function mirrorPieces(
  text: string,
  spans: readonly CaptureSpan[] | undefined,
  spansForText: string | null | undefined,
): readonly MirrorPiece[] {
  const plain: MirrorPiece[] = [
    { text, state: null, fieldIds: [], start: 0, end: text.length },
  ]
  if (!text) return []
  if (!spans || spans.length === 0) return plain
  if (spansForText !== text) return plain

  const ordered = [...spans].sort((a, b) => a.start - b.start || a.end - b.end)
  const out: MirrorPiece[] = []
  let cursor = 0
  for (const sp of ordered) {
    // ⚠️ A SPAN OUTSIDE THE TEXT IS DISCARDED RATHER THAN CLAMPED. Clamping would
    // paint SOMETHING, which is the behaviour that hides the bug that produced it.
    if (sp.start < cursor || sp.start < 0 || sp.end > text.length || sp.end <= sp.start) {
      continue
    }
    if (sp.start > cursor) {
      out.push({
        text: text.slice(cursor, sp.start),
        state: null,
        fieldIds: [],
        start: cursor,
        end: sp.start,
      })
    }
    out.push({
      text: text.slice(sp.start, sp.end),
      state: sp.state,
      fieldIds: sp.field_ids,
      start: sp.start,
      end: sp.end,
    })
    cursor = sp.end
  }
  if (cursor < text.length) {
    out.push({
      text: text.slice(cursor),
      state: null,
      fieldIds: [],
      start: cursor,
      end: text.length,
    })
  }
  return out
}

/**
 * Which fields the caret is sitting inside.
 *
 * ⚠️ THE LINK RUNS CARET -> ROW, NOT HOVER -> ROW, BY RULING (James, 2026-10-16):
 * "the textarea owns the pointer". A textarea swallows pointer events over its own
 * text, so a span in a layer behind it can never be hovered — the obvious design
 * from the previous dispatch was unbuildable and he changed it rather than have it
 * faked with a transparent overlay that would have stolen the caret.
 *
 * ⚠️ HALF-OPEN AT THE END, INCLUSIVE AT THE START. A caret resting immediately after
 * a span is "outside" it — otherwise typing a space after a captured word would keep
 * its row lit while the director has moved on.
 */
export function fieldsAtCaret(
  spans: readonly CaptureSpan[] | undefined,
  spansForText: string | null | undefined,
  text: string,
  caret: number | null,
): readonly string[] {
  if (caret === null || !spans || spansForText !== text) return []
  const hit = spans.find((s) => caret >= s.start && caret < s.end)
  return hit ? hit.field_ids : []
}
