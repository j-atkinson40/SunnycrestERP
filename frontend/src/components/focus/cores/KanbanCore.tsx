/**
 * KanbanCore — stub renderer for Focus `kanban` mode.
 *
 * Phase A Session 2 stub. Renders three placeholder columns with 2–3
 * placeholder cards each — visually distinct from the other core-mode
 * stubs (single-record is a stacked form; triage-queue is a vertical
 * list with keyboard shortcuts; edit-canvas is a centered canvas;
 * matrix is a grid with headers).
 *
 * Real kanban mechanics (drag-drop across columns, card editing,
 * column-order persistence) land in Phase B when Funeral Scheduling
 * Focus ships.
 */

import { CoreHeader, EscToDismissHint, type CoreProps } from "./_shared"


const COLUMNS = [
  { title: "To do", cardCount: 3 },
  { title: "In progress", cardCount: 2 },
  { title: "Done", cardCount: 2 },
]


export function KanbanCore({ config }: CoreProps) {
  return (
    <div className="flex h-full flex-col gap-4">
      <CoreHeader modeLabel="kanban" title={config.displayName} />

      <div className="grid flex-1 grid-cols-3 gap-3">
        {COLUMNS.map((col) => (
          <div
            key={col.title}
            className="flex flex-col gap-2 rounded-md border border-border-subtle bg-surface-sunken/40 p-3"
          >
            <h3 className="text-body-sm font-medium text-content-strong">
              {col.title}
            </h3>
            <div className="flex flex-col gap-2">
              {Array.from({ length: col.cardCount }).map((_, i) => (
                <div
                  key={i}
                  className="rounded-md border border-border-subtle bg-surface-elevated p-3"
                >
                  <p className="text-body-sm text-content-base">
                    Card {i + 1}
                  </p>
                  <p className="text-micro text-content-muted">
                    placeholder
                  </p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <EscToDismissHint />
    </div>
  )
}
