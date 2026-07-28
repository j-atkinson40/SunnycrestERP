/**
 * Park act-type registry — S-5 first slice.
 *
 * RULED (S-5 Type B #1): the escalation predicate is a DECLARATION owned
 * by the act-type, keyed to the Focus-type registry — NOT a hardcoded
 * list inside park. An act-type declares `escalatesTo: <focus-id>` (or
 * declares none = stays LIGHT). Park READS the declaration via
 * `escalationFocusFor`; park contains no `if act === "quote"`. New
 * escalating act-types (schedule-delivery → funeral-scheduling, …) are
 * added by registering an act with an `escalatesTo`, never by editing
 * park itself.
 *
 * Same side-effect-on-import registration pattern as `registerFocus` and
 * `registerWidgetRenderer`. Each act's `widgetType` is the
 * `getWidgetRenderer` key for its tablet surface (the 4th host).
 */

import { getFocusConfig } from "@/contexts/focus-registry"

export interface ParkActType {
  /** Stable act-type id (e.g. "reply-dm", "add-note", "start-quote"). */
  actType: string
  displayName: string
  /** `getWidgetRenderer` key for this act's tablet surface. */
  widgetType: string
  /** The Focus id this act escalates to, or undefined = stays LIGHT.
   *  Resolved against the LIVE Focus registry at read time. */
  escalatesTo?: string
  /** Initial tablet dimensions on summon (px, 8px-friendly). */
  defaultSize: { width: number; height: number }
}

const _acts = new Map<string, ParkActType>()

export function registerParkAct(act: ParkActType): void {
  _acts.set(act.actType, act)
}

export function getParkAct(actType: string): ParkActType | null {
  return _acts.get(actType) ?? null
}

export function listParkActs(): ParkActType[] {
  return Array.from(_acts.values())
}

/** The escalation-target Focus id for an act-type, or null if the act
 *  stays light. This IS the park spec's predicate ("does this act-type
 *  have a registered Focus?") — data-driven, no hardcode. A declared
 *  target that isn't actually registered resolves to null (the act stays
 *  light rather than escalating into a void). */
export function escalationFocusFor(actType: string): string | null {
  const act = _acts.get(actType)
  if (!act?.escalatesTo) return null
  return getFocusConfig(act.escalatesTo) ? act.escalatesTo : null
}

export function _resetParkActsForTests(): void {
  _acts.clear()
}

// ── Slice-1 catalog (RULED Type B #3): reply-DM + add-note stay light;
//    start-quote escalates. Email deferred to slice 2. ──────────────────

registerParkAct({
  actType: "reply-dm",
  displayName: "Reply",
  widgetType: "park.reply-dm",
  defaultSize: { width: 340, height: 300 },
  // LIGHT — no registered Focus; a message send is an atomic gesture.
})

registerParkAct({
  actType: "add-note",
  displayName: "Add note",
  widgetType: "park.add-note",
  defaultSize: { width: 340, height: 320 },
  // LIGHT — a note is an atomic gesture, committed at its own Save.
})

registerParkAct({
  actType: "start-quote",
  displayName: "Quote",
  widgetType: "park.start-quote",
  defaultSize: { width: 460, height: 440 },
  // ESCALATES — declares the quote-building Focus. The S-3a crossing,
  // now triggered from park; park suspends behind the Focus.
  escalatesTo: "quote-building",
})
