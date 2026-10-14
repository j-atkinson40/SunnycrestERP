/**
 * Whether a pane is for ENTERING something or for LOOKING AT something.
 *
 * ⚠️ A PROPERTY OF THE PANE TYPE, NOT OF THE PANE, BY RULING (2026-10-12). The
 * distinction decides two things — where a pane grows from, and whether the command
 * line is its text field — and both are true of the KIND. A per-pane flag would let
 * two panes of the same kind disagree, which is not a state anything should be able
 * to reach.
 *
 *   entry   the director is putting something in. The pane grows from the bar,
 *           because the bar is where they are typing, and the bar IS its input.
 *   info    the director is reading. The pane cascades from the top right and the
 *           bar stays a request line.
 *
 * ⚠️ EVERY KIND IS CLASSIFIED, AND A TEST ENFORCES THAT RATHER THAN A DEFAULT. An
 * `?? "info"` fallback would silently classify a new entry pane as info — it would
 * open in the wrong place, the bar would not be its input, and nothing would fail.
 * `paneMode` is typed `Record<OpasPaneKind, PaneMode>`, so adding a kind without
 * classifying it is a TYPE ERROR, and `pane-mode.test.ts` checks the map against the
 * union at runtime too, because the union is declared in another file and a widened
 * `string` there would make the type check vacuous.
 */
import type { OpasPaneKind } from "@/contexts/opas-context"

export type PaneMode = "entry" | "info"

/** ⚠️ EXHAUSTIVE BY TYPE. Adding a kind without a row here will not compile. */
export const PANE_MODE: Record<OpasPaneKind, PaneMode> = {
  capture: "entry",
  product: "info",
  "product-list": "info",
  "order-list": "info",
  "sales-order": "info",
}

/** ⚠️ NO FALLBACK, DELIBERATELY — see the module docstring. */
export function paneMode(kind: OpasPaneKind): PaneMode {
  return PANE_MODE[kind]
}

export function isEntryPane(kind: OpasPaneKind): boolean {
  return paneMode(kind) === "entry"
}
