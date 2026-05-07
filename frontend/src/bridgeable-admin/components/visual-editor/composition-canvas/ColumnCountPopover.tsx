/**
 * ColumnCountPopover — 1-12 column count picker with overflow rejection.
 *
 * Per R-3.1 column count change behavior:
 *   - Increase: always permitted (whitespace appears right of placements)
 *   - Decrease: disable values that would clip placements; tooltip
 *     surfaces the reason ("N placements would overflow")
 *   - No auto-clipping; admin must explicitly resolve overflow first
 *
 * Rendered both:
 *   - Inside RowControlsStrip per-row (compact trigger badge)
 *   - Inside CompositionEditorPage right rail RowControls (label + trigger)
 *
 * Reuses base-ui Popover for consistency with the rest of the editor.
 */
import { Popover } from "@base-ui/react/popover"
import { useState } from "react"
import {
  validateColumnCountChange,
  _internals,
} from "./use-canvas-interactions"
import type { CompositionRow } from "@/lib/visual-editor/compositions/types"


interface Props {
  row: CompositionRow
  onChange: (newColumnCount: number) => void
  /** Trigger element. Defaults to a compact badge showing current count. */
  trigger?: React.ReactNode
  /** Optional className passed to the trigger button (when default trigger). */
  triggerClassName?: string
  /** Test-id for the trigger button (default "column-count-trigger"). */
  triggerTestId?: string
}


// Re-export for callers that need to pre-validate before render
// (e.g., RowControls inspector showing a disabled-summary line).
export { validateColumnCountChange }
void _internals // type-only; suppress unused-import warning


export function ColumnCountPopover({
  row,
  onChange,
  trigger,
  triggerClassName,
  triggerTestId = "column-count-trigger",
}: Props) {
  const [open, setOpen] = useState(false)
  const values = Array.from({ length: 12 }, (_, i) => i + 1)

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger
        data-testid={triggerTestId}
        className={
          trigger
            ? undefined
            : (triggerClassName ??
              "rounded-sm border border-border-base bg-surface-raised px-1.5 py-0.5 font-plex-mono text-caption text-content-strong hover:bg-accent-subtle/40")
        }
        aria-label={`Column count: ${row.column_count}. Click to change.`}
      >
        {trigger ?? row.column_count}
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Positioner>
          <Popover.Popup
            className="z-[var(--z-popover,60)] rounded-md border border-border-subtle bg-surface-raised p-2 shadow-level-2 duration-settle ease-settle data-[open]:animate-in data-[closed]:animate-out data-[open]:fade-in-0 data-[closed]:fade-out-0"
            data-testid="column-count-popover"
          >
            <div className="mb-1.5 text-micro uppercase tracking-wider text-content-muted">
              Column count
            </div>
            <div className="grid grid-cols-6 gap-1">
              {values.map((n) => {
                const validation = validateColumnCountChange(row, n)
                const disabled = !validation.ok
                const isCurrent = n === row.column_count
                const blockingCount = !validation.ok
                  ? validation.blockingCount
                  : 0
                return (
                  <button
                    key={n}
                    type="button"
                    disabled={disabled}
                    onClick={() => {
                      if (disabled || isCurrent) return
                      onChange(n)
                      setOpen(false)
                    }}
                    title={
                      disabled
                        ? `Cannot reduce: ${blockingCount} placement${blockingCount === 1 ? "" : "s"} would overflow. Move or delete first.`
                        : isCurrent
                          ? `Current value: ${n}`
                          : `Set to ${n} columns`
                    }
                    aria-disabled={disabled}
                    data-testid={`column-count-option-${n}`}
                    data-disabled={disabled ? "true" : "false"}
                    data-current={isCurrent ? "true" : "false"}
                    className={[
                      "h-7 w-7 rounded-sm font-plex-mono text-caption",
                      isCurrent
                        ? "bg-accent text-content-on-accent"
                        : disabled
                          ? "cursor-not-allowed bg-surface-sunken text-content-subtle opacity-50"
                          : "border border-border-subtle bg-surface-elevated text-content-strong hover:bg-accent-subtle/40",
                    ].join(" ")}
                  >
                    {n}
                  </button>
                )
              })}
            </div>
            <div className="mt-1.5 text-micro text-content-muted">
              Disabled values would clip placements.
            </div>
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  )
}
