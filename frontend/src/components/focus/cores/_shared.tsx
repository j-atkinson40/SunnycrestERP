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
      <kbd className="rounded border border-border-subtle bg-surface-elevated px-2 py-0.5 font-plex-mono text-micro">
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
      <h2 className="text-h2 font-plex-serif text-content-strong">{title}</h2>
    </header>
  )
}
