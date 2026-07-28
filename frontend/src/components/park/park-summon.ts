/**
 * Park summon bridge (S-5).
 *
 * Park tablets are summoned from the command bar (intent-shaped, never
 * app-launcher grammar). Command-bar actions are registered statically
 * and aren't React-context aware, so they can't call `usePark().summon`
 * directly. This module is the thin bridge: `ParkProvider` publishes its
 * `summon` function here on mount; command-bar action handlers (and the
 * witness) call `summonParkAct(actType)`. No React coupling, one seam.
 */

type SummonFn = (actType: string) => string | null

let _summon: SummonFn | null = null

/** ParkProvider publishes its summon fn here (and clears it on unmount). */
export function _setParkSummon(fn: SummonFn | null): void {
  _summon = fn
}

/** Summon a park tablet by act-type. No-op (returns null) if park isn't
 *  mounted. Called by command-bar summon actions. */
export function summonParkAct(actType: string): string | null {
  return _summon ? _summon(actType) : null
}

/** The command-bar dispatch plan for a park-summon action.
 *
 *  RULED (b): a park summon keeps the command-bar palette OPEN so the user
 *  can chain the next summon — assemble a working set in one burst (summon
 *  reply · note · quote) instead of re-invoking the bar between every
 *  tablet. `keepPaletteOpen` is the load-bearing contract: the dispatch
 *  site (CommandBar.executeAction) MUST NOT call onClose on a park summon.
 *  If a future edit re-adds a close to the summon path, this contract (and
 *  its test) is what catches the regression. Dismiss stays Esc / click-
 *  away, unchanged. */
export interface ParkSummonDispatch {
  actType: string
  keepPaletteOpen: true
}

/** Parse a command-bar action handler into a park-summon dispatch plan, or
 *  null if it isn't a park summon. Pure — the testable seam that locks the
 *  (b) palette-stays-open behavior (CommandBar isn't render-unit-testable). */
export function planParkSummon(
  handler: string | undefined | (() => void),
): ParkSummonDispatch | null {
  if (typeof handler === "string" && handler.startsWith("park:summon:")) {
    return {
      actType: handler.slice("park:summon:".length),
      keepPaletteOpen: true,
    }
  }
  return null
}
