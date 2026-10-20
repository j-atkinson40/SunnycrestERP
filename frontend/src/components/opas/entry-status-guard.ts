/**
 * Is this entry-pane status the same as the last one?
 *
 * ⚠️ EXTRACTED FROM `OpasHost` SO IT CAN BE TESTED AGAINST ITS OWN TYPE. Inline in a
 * `useCallback` it was unreachable from a test, which is how it came to compare four
 * of a seven-field payload and silently drop every update that differed only in the
 * other three.
 *
 * ⚠️ IT COMPARES EVERY FIELD, AND THE TEST BESIDE IT ENFORCES THAT. The point of the
 * guard is to avoid a re-render when nothing changed; the cost of getting it wrong is
 * a feature that never renders at all, which is strictly worse than a wasted render.
 * When the two risks are that lopsided, the comparison errs toward "different".
 */
import type { EntryPaneStatus } from "./CapturePane"

function sameIds(
  a: readonly string[] | undefined,
  b: readonly string[] | undefined,
): boolean {
  if (a === b) return true
  const x = a ?? []
  const y = b ?? []
  return x.length === y.length && x.every((v, i) => v === y[i])
}

export function sameEntryStatus(
  cur: EntryPaneStatus,
  next: EntryPaneStatus,
): boolean {
  return (
    cur.question === next.question &&
    cur.capturing === next.capturing &&
    cur.ready === next.ready &&
    cur.picks.length === next.picks.length &&
    cur.picks.every(
      (p, i) =>
        p.field_id === next.picks[i].field_id &&
        p.options.length === next.picks[i].options.length,
    ) &&
    // ⚠️ THE THREE THAT WERE MISSING.
    cur.spansForText === next.spansForText &&
    (cur.spans?.length ?? 0) === (next.spans?.length ?? 0) &&
    sameIds(cur.hoveredFieldIds, next.hoveredFieldIds)
  )
}
