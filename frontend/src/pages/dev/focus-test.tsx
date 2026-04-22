/**
 * Dev test page for the Phase A Session 1 Focus primitive.
 *
 * Not in nav. Not permission-gated beyond the tenant auth wrapper.
 * Route: /dev/focus-test
 *
 * Exercises:
 *   - open() via three buttons (multiple ids)
 *   - URL sync (?focus=<id>)
 *   - Browser back/forward
 *   - ESC dismissal
 *   - Backdrop click dismissal
 *   - Return pill appearance + click-to-reopen + X dismiss
 *   - Command bar hidden during Focus (Cmd+K suppressed)
 *   - Focus trap (Tab inside core stays within core)
 */

import { useFocus } from "@/contexts/focus-context"
import { Button } from "@/components/ui/button"


export default function FocusTestPage() {
  const { currentFocus, lastClosedFocus, open, isOpen } = useFocus()

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-8">
      <header className="space-y-1">
        <p className="text-micro uppercase tracking-wider text-content-muted">
          Phase A · Session 1 · dev
        </p>
        <h1 className="text-h2 font-plex-serif text-content-strong">
          Focus primitive — manual test
        </h1>
        <p className="text-body-sm text-content-muted">
          Exercise open, close, ESC dismiss, backdrop click, URL sync,
          return pill, and command-bar suppression. Not in nav.
        </p>
      </header>

      <section className="space-y-3 rounded-md border border-border-subtle bg-surface-elevated p-4">
        <h2 className="text-body font-medium text-content-strong">
          Open a placeholder Focus
        </h2>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => open("test-a")}>
            Open Test Focus A
          </Button>
          <Button onClick={() => open("test-b")} variant="outline">
            Open Test Focus B
          </Button>
          <Button
            onClick={() => open("long-name-for-pill-testing")}
            variant="outline"
          >
            Open long-named Focus
          </Button>
        </div>
      </section>

      <section className="space-y-2 rounded-md border border-border-subtle bg-surface-elevated p-4">
        <h2 className="text-body font-medium text-content-strong">
          Current state
        </h2>
        <dl className="grid grid-cols-2 gap-y-1 text-body-sm">
          <dt className="text-content-muted">isOpen</dt>
          <dd className="font-plex-mono text-content-base">
            {String(isOpen)}
          </dd>
          <dt className="text-content-muted">currentFocus.id</dt>
          <dd className="font-plex-mono text-content-base">
            {currentFocus?.id ?? "—"}
          </dd>
          <dt className="text-content-muted">lastClosedFocus.id</dt>
          <dd className="font-plex-mono text-content-base">
            {lastClosedFocus?.id ?? "—"}
          </dd>
        </dl>
      </section>

      <section className="space-y-2 text-body-sm text-content-muted">
        <p>
          <strong className="text-content-base">Try:</strong> refresh the
          page while a Focus is open — the Focus should reopen from the
          URL. Press the browser back button to dismiss. Press Cmd+K
          while the Focus is open — it should not open the command bar.
        </p>
      </section>
    </div>
  )
}
