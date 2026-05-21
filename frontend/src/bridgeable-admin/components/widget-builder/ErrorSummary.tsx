/**
 * ErrorSummary — WB-4b inline error chrome.
 *
 * Compact summary chip in the top chrome ("X errors"). Click expands
 * a dropdown listing each error with a "Locate" button that scrolls
 * the canvas to the offending atom + selects it.
 *
 * No errors → renders null (the chrome's space is reclaimed).
 */
import { useState } from "react"
import { AlertCircle, ChevronDown, ChevronUp } from "lucide-react"

import { cn } from "@/lib/utils"
import type { ValidationResult } from "@/bridgeable-admin/hooks/useWidgetValidation"


export function ErrorSummary({
  validation,
  onLocate,
}: {
  validation: ValidationResult
  /** Selecting an atom from the list should select + scroll-into-view. */
  onLocate: (atom_id: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  if (!validation.hasErrors) return null
  const count = validation.errorList.length
  return (
    <div
      data-testid="widget-builder-error-summary"
      data-error-count={count}
      className="relative"
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-md border px-2 py-1",
          "border-status-error/40 bg-status-error-muted text-status-error",
          "text-caption font-medium",
        )}
        data-testid="widget-builder-error-summary-toggle"
      >
        <AlertCircle size={12} />
        <span>
          {count} {count === 1 ? "error" : "errors"}
        </span>
        {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>
      {expanded ? (
        <div
          data-testid="widget-builder-error-summary-list"
          className={cn(
            "absolute right-0 top-full z-50 mt-1 w-80 rounded-md border",
            "border-border-base bg-surface-raised shadow-md",
          )}
        >
          <ul className="max-h-72 overflow-auto py-1 text-body-sm">
            {validation.errorList.map((item, i) => (
              <li
                key={`${item.atom_id}-${i}`}
                className="flex items-start gap-2 px-2 py-1.5 hover:bg-surface-elevated"
              >
                <button
                  type="button"
                  onClick={() => {
                    onLocate(item.atom_id)
                    setExpanded(false)
                  }}
                  data-testid={`widget-builder-error-summary-item-${item.atom_id}`}
                  className="flex flex-1 flex-col items-start gap-0.5 text-left"
                >
                  <span className="text-caption text-content-muted">
                    {item.atom_type}
                  </span>
                  <span className="text-content-base">{item.message}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}
