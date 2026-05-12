/**
 * Arc 4a.1 — IconPicker shared component.
 *
 * Sixth canonical shared authoring component primitive (after
 * NodeConfigForm / BlockConfigEditor / BlockKindPicker /
 * InteractivePlacementCanvas / deep-link-state).
 *
 * Renders a curated lucide icon grid (~40 icons across 5 groups —
 * Actions / Navigation / Objects / Status / Misc) for visual picking,
 * plus a free-form text input fallback so admins can still type any
 * valid lucide-react export name not in the curated subset. The
 * runtime R-4 button substrate accepts either — IconPicker honors the
 * existing `iconName: string` field shape verbatim.
 *
 * Consumption pattern:
 *
 *   <IconPicker
 *     value={current}
 *     onChange={(name) => onPropChange(name)}
 *     label="Button icon"
 *   />
 *
 * Reusable consumers (today + Arc 4a.1):
 *   - R-4 button registration authoring (future arc — Compose tab)
 *   - Class-level icon configs (future class registrations introducing
 *     iconName props at class scope)
 *   - Widget metadata authoring (future arc — widget registration UI)
 *
 * Chrome per DESIGN_LANGUAGE §14: bg-surface-elevated grid +
 * border-border-subtle, brass selection ring (border-accent +
 * bg-accent-subtle/40 on selected), radius-base corners. Hover state
 * uses accent-subtle/20 to match CompactPropControl row hover.
 */
import { useMemo, useState } from "react"

import {
  ICON_GROUP_LABELS,
  ICON_GROUPS,
  ICON_SUBSET,
  resolveSubsetIcon,
} from "./icon-subset"


export interface IconPickerProps {
  /** Current value — lucide-react export name. Empty string disables
   *  the icon at runtime (per R-4 contract). */
  value: string
  /** Emit on user pick OR free-form text edit. */
  onChange: (next: string) => void
  /** Optional label. When omitted, the picker renders without a
   *  heading — useful for embedding inside CompactPropControl rows
   *  which already render the prop label. */
  label?: string
  /** Optional disabled flag. */
  disabled?: boolean
  /** Optional data-testid root override. */
  "data-testid"?: string
}


export function IconPicker({
  value,
  onChange,
  label,
  disabled,
  "data-testid": testid = "icon-picker",
}: IconPickerProps) {
  const [textInput, setTextInput] = useState(value)

  // Keep the text input in sync if the parent updates `value` (e.g.,
  // user picks from the grid, parent re-renders with new value).
  useMemo(() => {
    setTextInput(value)
  }, [value])

  const SelectedIcon = resolveSubsetIcon(value)
  const valueInSubset = SelectedIcon != null
  const hasFreeFormValue = value !== "" && !valueInSubset

  return (
    <div
      className="flex flex-col gap-2 rounded-md border border-border-subtle bg-surface-elevated p-3"
      data-testid={testid}
    >
      {label && (
        <div className="text-caption font-medium text-content-strong">
          {label}
        </div>
      )}

      {/* Current selection summary */}
      <div
        className="flex items-center gap-2 rounded-sm border border-border-base bg-surface-raised px-2 py-1.5"
        data-testid={`${testid}-selection`}
      >
        {SelectedIcon ? (
          <SelectedIcon size={16} className="text-content-strong" />
        ) : (
          <div className="h-4 w-4 rounded-sm border border-dashed border-border-base" />
        )}
        <span className="flex-1 font-plex-mono text-caption text-content-base">
          {value === "" ? "No icon" : value}
        </span>
        {hasFreeFormValue && (
          <span
            className="rounded-sm border border-status-warning/30 bg-status-warning-muted px-1.5 py-0.5 text-[10px] font-medium text-status-warning"
            title="Free-form name — not in curated subset"
            data-testid={`${testid}-free-form-flag`}
          >
            custom
          </span>
        )}
      </div>

      {/* Grouped grid */}
      <div className="flex flex-col gap-2" data-testid={`${testid}-grid`}>
        {ICON_GROUPS.map((group) => {
          const entries = ICON_SUBSET.filter((e) => e.group === group)
          if (entries.length === 0) return null
          return (
            <div
              key={group}
              className="flex flex-col gap-1"
              data-testid={`${testid}-group-${group}`}
            >
              <div className="text-[10px] font-medium uppercase tracking-wider text-content-muted">
                {ICON_GROUP_LABELS[group]}
              </div>
              <div className="grid grid-cols-8 gap-1">
                {entries.map((entry) => {
                  const isSelected = value === entry.name
                  const Icon = entry.Icon
                  return (
                    <button
                      key={entry.name}
                      type="button"
                      disabled={disabled}
                      onClick={() => onChange(entry.name)}
                      title={entry.name}
                      data-testid={`${testid}-cell-${entry.name}`}
                      aria-pressed={isSelected}
                      aria-label={`Pick ${entry.name} icon`}
                      className={[
                        "flex h-7 w-7 items-center justify-center rounded-sm border transition-colors",
                        isSelected
                          ? "border-accent bg-accent-subtle/40 text-content-strong"
                          : "border-border-subtle bg-surface-raised text-content-muted hover:border-border-base hover:bg-accent-subtle/20 hover:text-content-strong",
                      ].join(" ")}
                    >
                      <Icon size={14} />
                    </button>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>

      {/* Free-form fallback */}
      <div className="flex flex-col gap-1">
        <label
          htmlFor={`${testid}-text-input`}
          className="text-[10px] font-medium uppercase tracking-wider text-content-muted"
        >
          Or type a lucide name
        </label>
        <div className="flex items-center gap-1">
          <input
            id={`${testid}-text-input`}
            type="text"
            value={textInput}
            disabled={disabled}
            onChange={(e) => setTextInput(e.target.value)}
            onBlur={() => {
              if (textInput !== value) onChange(textInput)
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault()
                if (textInput !== value) onChange(textInput)
              }
            }}
            placeholder="e.g. CalendarPlus"
            data-testid={`${testid}-text-input`}
            className="flex-1 rounded-sm border border-border-base bg-surface-raised px-2 py-1 font-plex-mono text-caption text-content-base focus-ring-accent"
          />
          {value !== "" && (
            <button
              type="button"
              disabled={disabled}
              onClick={() => {
                onChange("")
                setTextInput("")
              }}
              data-testid={`${testid}-clear`}
              aria-label="Clear icon"
              className="rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-caption text-content-muted hover:bg-status-error-muted hover:text-status-error"
            >
              Clear
            </button>
          )}
        </div>
        <p className="text-[10px] text-content-muted">
          Any valid lucide-react export name works. Use the grid above
          for the curated subset.
        </p>
      </div>
    </div>
  )
}
