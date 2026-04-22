/**
 * Dev test page for the Focus primitive.
 *
 * Phase A Session 1 shipped the overlay scaffolding; Session 2 adds
 * the mode dispatcher + five registered test Focuses (one per core
 * mode). This page is the manual-verification surface. Not in nav.
 * Delete when Phase A ships its first real Focus consumer.
 *
 * Route: /dev/focus-test
 *
 * Exercises:
 *   - All 5 core modes render distinctively
 *   - open() via mode-labeled buttons
 *   - URL sync (?focus=<id>)
 *   - Browser back/forward
 *   - ESC dismissal
 *   - Backdrop click dismissal
 *   - Return pill appearance + click-to-reopen + X dismiss
 *   - Command bar hidden during Focus (Cmd+K suppressed)
 *   - Focus trap (Tab inside core stays within core)
 *   - Push-back scale: main content scales to 0.98 while Focus is
 *     open; sidebar + top header + mobile tab bar remain viewport-
 *     anchored
 */

import { useFocus } from "@/contexts/focus-context"
import { listFocusConfigs } from "@/contexts/focus-registry"
import { Button } from "@/components/ui/button"


export default function FocusTestPage() {
  const { currentFocus, lastClosedFocus, open, isOpen } = useFocus()
  const configs = listFocusConfigs()

  const resolvedMode = currentFocus
    ? (configs.find((c) => c.id === currentFocus.id)?.mode ?? "(unknown id)")
    : "—"

  // Render buttons per mode in the canonical order from the type
  // union — matches the MODE_RENDERERS map order in mode-dispatcher.
  const modeButtons: Array<{ id: string; label: string }> = [
    { id: "test-kanban", label: "Open Kanban Focus" },
    { id: "test-single-record", label: "Open Single-Record Focus" },
    { id: "test-edit-canvas", label: "Open Edit-Canvas Focus" },
    { id: "test-triage-queue", label: "Open Triage-Queue Focus" },
    { id: "test-matrix", label: "Open Matrix Focus" },
  ]

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-8">
      <header className="space-y-1">
        <p className="text-micro uppercase tracking-wider text-content-muted">
          Phase A · Session 2 · dev
        </p>
        <h1 className="text-h2 font-plex-serif text-content-strong">
          Focus primitive — manual test
        </h1>
        <p className="text-body-sm text-content-muted">
          Five core modes registered. Each button opens a Focus with
          the corresponding stub core so modes are visually
          distinguishable at a glance. Not in nav.
        </p>
      </header>

      <section className="space-y-3 rounded-md border border-border-subtle bg-surface-elevated p-4">
        <h2 className="text-body font-medium text-content-strong">
          Open a core-mode Focus
        </h2>
        <div className="flex flex-wrap gap-2">
          {modeButtons.map((btn, i) => (
            <Button
              key={btn.id}
              onClick={() => open(btn.id)}
              variant={i === 0 ? "default" : "outline"}
              size="sm"
            >
              {btn.label}
            </Button>
          ))}
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
          <dt className="text-content-muted">resolved mode</dt>
          <dd className="font-plex-mono text-content-base">
            {resolvedMode}
          </dd>
          <dt className="text-content-muted">layoutState</dt>
          <dd className="font-plex-mono text-content-base">
            {currentFocus?.layoutState === null
              ? "null (session-ephemeral, not yet set)"
              : currentFocus?.layoutState
                ? `widgets=${Object.keys(currentFocus.layoutState.widgets).length}`
                : "—"}
          </dd>
          <dt className="text-content-muted">lastClosedFocus.id</dt>
          <dd className="font-plex-mono text-content-base">
            {lastClosedFocus?.id ?? "—"}
          </dd>
        </dl>
      </section>

      <section className="space-y-2 text-body-sm text-content-muted">
        <p>
          <strong className="text-content-base">Try (Session 3):</strong>{" "}
          Open the Kanban Focus — a "Recent Cases" mock widget
          appears in the canvas around the core. Hover the widget to
          reveal chrome (drag handle top-left, dismiss X top-right,
          resize corner bottom-right). Drag by the handle to
          reposition (snaps to 8px). Drag the corner to resize
          (respects min 200×100). Click X to dismiss. Append{" "}
          <code className="rounded bg-surface-elevated px-1.5 py-0.5 font-plex-mono text-micro">
            &amp;dev-canvas=1
          </code>{" "}
          to the URL after opening a Focus to see the 8px grid.
        </p>
        <p>
          <strong className="text-content-base">Regression checks:</strong>{" "}
          refresh reopens Focus from URL, browser back dismisses,
          Cmd+K still suppressed, main content still scales to 0.98.
        </p>
      </section>
    </div>
  )
}
