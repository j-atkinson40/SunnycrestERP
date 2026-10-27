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

/**
 * Are these the same offered answers?
 *
 * ⚠️ VALUE AND LABEL, NOT JUST LENGTH, because re-ranking is the common change. A
 * home's usual vault moving to ⌥1 keeps the count identical and changes every
 * position — comparing lengths would drop exactly the update the ranking exists for.
 *
 * ⚠️ `sub` IS COMPARED TOO. It carries the town, the date and the word "cremation";
 * a pill whose sub changed while its label did not is a different answer on screen.
 */
function samePills(
  a: EntryPaneStatus["guidedPills"],
  b: EntryPaneStatus["guidedPills"],
): boolean {
  if (a === b) return true
  const x = a ?? []
  const y = b ?? []
  return (
    x.length === y.length &&
    x.every(
      (p, i) =>
        p.value === y[i].value && p.label === y[i].label && p.sub === y[i].sub,
    )
  )
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
    sameIds(cur.hoveredFieldIds, next.hoveredFieldIds) &&
    // ⚠️ THE SEVEN THAT WERE MISSING NEXT, AND THE SAME DEFECT AS LAST TIME. Guided
    // capture added these to `EntryPaneStatus` on 2026-10-27 and this function kept
    // comparing seven of fourteen — so a response whose QUESTION, HINT or PILLS
    // changed while `captureVoice`'s string did not would be dropped by the host, and
    // the pane would hold a stale question with stale answers under it.
    //
    // ⚠️ IT WAS CAUGHT BY THE RATCHET BESIDE THIS FILE, NOT BY ME. `VARIANTS` in
    // `entry-status-guard.test.ts` is typed `[K in keyof EntryPaneStatus]-?`, which
    // strips optionality and therefore demands a variant for EVERY key — so adding a
    // field to the payload without extending this comparison is a type error. That is
    // the mechanism the docstring above asked for, working.
    //
    // ⚠️ AND IT WAS CAUGHT IN CI RATHER THAN LOCALLY, because I verified with
    // `npx tsc --noEmit` and the gate runs `npx tsc -b`. The second checks the test
    // projects; the first did not reach this file at all.
    cur.guidedQuestion === next.guidedQuestion &&
    cur.guidedHint === next.guidedHint &&
    cur.guidedFieldId === next.guidedFieldId &&
    cur.cremation === next.cremation &&
    cur.clearedNote === next.clearedNote &&
    cur.sessionId === next.sessionId &&
    samePills(cur.guidedPills, next.guidedPills)
  )
}
