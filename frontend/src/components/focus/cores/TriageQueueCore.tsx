/**
 * TriageQueueCore — stub renderer for Focus `triageQueue` mode.
 *
 * Phase A Session 2 stub. Renders 4–5 placeholder rows with keyboard-
 * shortcut badges (1 / 2 / 3 / 4 / 5) on the left — visually matches
 * the superhuman-style queue-processing pattern described in PA §5.2.
 * The mode is what PO Review Focus + Personalization Request
 * Processing Focus + Compliance Gap Resolution Focus will use.
 *
 * Real triage keyboard handling (approve / skip / snooze shortcuts,
 * auto-advance to next item, queue depletion UI) lands when the first
 * real triage-queue Focus ships. Existing Phase 5 triage-workspace
 * surfaces (/triage/*) are a separate non-Focus implementation — the
 * triageQueue core mode will subsume them in post-September cleanup.
 *
 * Distinct from backend `"triage_queue"` pin_type literal: that's a
 * pinnable-target-kind namespace (what you can pin to a space);
 * `triageQueue` is a core-mode namespace (how a Focus renders). Same
 * word, different concepts.
 */

import { CoreHeader, EscToDismissHint, type CoreProps } from "./_shared"


const ITEMS = [
  { title: "Review PO #1042", subtitle: "Acme Supplies · $3,200" },
  { title: "Approve proof — Hopkins FH", subtitle: "Monticello · engraving v2" },
  { title: "Resolve compliance gap", subtitle: "OSHA 300 log — missing Q2 entries" },
  { title: "Personalization request — Andersen", subtitle: "Vault customization" },
  { title: "Check cash-receipt mismatch", subtitle: "Invoice 2026-0033 · $4,750" },
]


export function TriageQueueCore({ config }: CoreProps) {
  return (
    <div className="flex h-full flex-col gap-4">
      <CoreHeader modeLabel="triageQueue" title={config.displayName} />

      <div className="flex flex-1 flex-col overflow-auto rounded-md border border-border-subtle bg-surface-sunken/40">
        {ITEMS.map((item, i) => (
          <div
            key={i}
            className="flex items-center gap-3 border-b border-border-subtle/60 px-4 py-3 last:border-b-0 hover:bg-surface-elevated/60"
          >
            <span
              aria-label={`Shortcut ${i + 1}`}
              className="flex h-6 w-6 flex-none items-center justify-center rounded-md border border-border-subtle bg-surface-elevated font-plex-mono text-micro text-content-strong"
            >
              {i + 1}
            </span>
            <div className="flex flex-1 flex-col">
              <span className="text-body-sm font-medium text-content-strong">
                {item.title}
              </span>
              <span className="text-body-sm text-content-muted">
                {item.subtitle}
              </span>
            </div>
          </div>
        ))}
      </div>

      <EscToDismissHint />
    </div>
  )
}
