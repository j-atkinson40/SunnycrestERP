/**
 * Shared primitives for Focus core stubs (Phase A Session 2).
 *
 * Session 2 scope: only the `CoreProps` contract + the Esc-dismiss
 * hint. Later sessions expand this as cores grow real render logic.
 */

import type { FocusConfig } from "@/contexts/focus-registry"


/** Prop contract every core-mode renderer implements. The dispatcher
 *  passes these identically to whichever core matches `config.mode`.
 *  Stubs in Session 2 don't consume `config` beyond the displayName;
 *  later sessions will use the full config for layout seeding + mode-
 *  specific configuration. */
export interface CoreProps {
  focusId: string
  config: FocusConfig
  /** ⚠️ The user may SEE this and not change it. Computed once by the
   *  dispatcher via `useFocusReadOnly`, never re-derived per core.
   *
   *  A core receiving `readOnly` DISABLES its actions; it does not hide them.
   *  A control that vanishes tells the user nothing about why, and a Focus
   *  that silently drops an action the user could otherwise have taken is
   *  indistinguishable from one that is broken. */
  readOnly: boolean
  /** The open Focus's PREDICATE — what this entrance means.
   *
   *  ⚠️ NOT the expansion. The fragment contract splits them: a predicate
   *  ("tasks due 2026-09-10 assigned to this user") re-derives and survives a
   *  shared link; the id list it selected at composition is payload and never
   *  reaches a URL. A core scopes itself from this and queries for itself.
   *
   *  Empty when the Focus was opened unscoped, which is a real state — not
   *  every entrance names a subset. */
  scope: Record<string, unknown>
}


/** Footer row shared across all core-mode stubs. Identical treatment
 *  to the Session 1 placeholder footer so the Focus chrome stays
 *  consistent across modes. */
export function EscToDismissHint() {
  return (
    <footer
      data-slot="focus-core-footer"
      className="flex items-center gap-2 text-body-sm text-content-muted"
    >
      <kbd className="rounded border border-border-subtle bg-surface-elevated px-2 py-0.5 font-mono text-micro">
        Esc
      </kbd>
      <span>or click outside to dismiss</span>
    </footer>
  )
}


/** Header row shared across all core-mode stubs. Micro-caps eyebrow
 *  ("Core mode · <mode>") + serif display title (the Focus's
 *  displayName). */
export function CoreHeader({
  modeLabel,
  title,
}: {
  modeLabel: string
  title: string
}) {
  return (
    <header className="flex flex-col gap-1">
      <p className="text-micro uppercase tracking-wider text-content-muted">
        Core mode · {modeLabel}
      </p>
      <h2 className="text-h2 font-display text-content-strong">{title}</h2>
    </header>
  )
}


/** States the read-only condition once, where the actions are.
 *
 *  ⚠️ THE REASON IS THE POINT. "Disabled" with no explanation reads as broken;
 *  this says the permission is absent, which is a different thing and is
 *  actionable — the user knows to ask for it rather than to report a bug.
 */
export function ReadOnlyNotice({ permission }: { permission?: string }) {
  return (
    <div
      data-testid="focus-read-only-notice"
      className="flex items-baseline gap-2 border-b border-border-subtle px-4 py-2 text-body-sm text-content-muted"
    >
      <span>View only — you can see this and not change it.</span>
      {permission ? (
        <span className="font-mono text-caption">requires {permission}</span>
      ) : null}
    </div>
  )
}
