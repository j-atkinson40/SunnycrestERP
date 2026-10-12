/**
 * Dropping stale extraction responses.
 *
 * ⚠️ THIS IS A SEPARATE MODULE SO IT CAN BE TESTED WITHOUT TIMERS OR A DOM. The rule
 * it encodes is one line of arithmetic and three lines of state, and testing it
 * through the component would mean testing it through a 350 ms debounce — which is
 * how an off-by-one in a race gets "covered" by a test that never raced.
 *
 * THE PROBLEM. The pane re-extracts on every pause. Requests can overtake each other
 * on the wire, so the LAST response to arrive is not necessarily the one describing
 * what is currently in the bar. Applying it anyway makes the pane show an older
 * reading of the text — and because the text keeps changing, it can look like the
 * extractor randomly failing to see words that are plainly on screen.
 *
 * ⚠️ THE CLIENT DECIDES, NOT THE SERVER, and this is the half of the ruling that is
 * easy to get backwards. The server echoes `seq` back uninterpreted; it does not
 * reject a low one. It cannot: the server does not know what is in the bar, so a
 * server that dropped the "stale" request would be deciding which of the director's
 * keystrokes counted. The client issued the numbers and is the only party that knows
 * which one is current.
 *
 * THE RULE, stated so a reader can check it against the code:
 *
 *     issue()        hands out strictly increasing numbers
 *     accept(seq)    true only if seq is HIGHER than the highest already applied
 *
 * So a response that arrives late is dropped, and a response that arrives out of
 * order behind a newer one is dropped. Equal is dropped too — a duplicate delivery
 * carries nothing new, and re-applying it would re-render for no reason.
 */

export interface Sequencer {
  /** The next number to send. Strictly increasing, starting at 1. */
  readonly issue: () => number
  /** Should this response be applied? Records it when the answer is yes. */
  readonly accept: (seq: number) => boolean
  /** The highest number applied so far. 0 before anything has been. */
  readonly applied: () => number
}

export function createSequencer(): Sequencer {
  let issued = 0
  let applied = 0
  return {
    issue: () => {
      issued += 1
      return issued
    },
    accept: (seq: number) => {
      // ⚠️ STRICTLY GREATER. `>=` would re-apply a duplicate delivery, and `>` with
      // the comparison against `issued` instead of `applied` would accept every
      // response in flight — which is exactly the bug this module exists to stop.
      if (seq <= applied) return false
      applied = seq
      return true
    },
    applied: () => applied,
  }
}

/**
 * The debounce, in one named place with its measurement.
 *
 * ⚠️ 350 ms, AND HERE IS WHY RATHER THAN A ROUND NUMBER. Two quantities bound it:
 *
 *   a fast typist's inter-keystroke gap is roughly 150–250 ms, so a window shorter
 *   than that fires mid-word and the pane flickers through readings of half-typed
 *   words — which the "partial words never resolve" rule already says must not
 *   produce answers, but which still costs a round trip each.
 *
 *   one re-extraction measured p50 15.2 ms and 24.2 ms on the longest text
 *   (`backend/tests/test_typed_capture_latency.py`), so the wait, not the work, is
 *   what the director perceives. Spending 350 ms of it on being sure they stopped
 *   is cheap; the response lands about 375 ms after the last keystroke.
 *
 * It is exported rather than inlined so the number has one home and the reasoning
 * travels with it.
 */
export const EXTRACT_DEBOUNCE_MS = 350
