/**
 * SingleRecordCore — stub renderer for Focus `singleRecord` mode.
 *
 * Phase A Session 2 stub. Renders a form-style vertical stack of 5–6
 * placeholder field rows with labels visible. The mode is the shape
 * Arrangement Conference Focus will use in Phase B+ (case file +
 * live completion panel), as well as detail-editing Focuses for
 * proof review, invoice detail, etc.
 *
 * Real form behavior (field editing, validation, Scribe integration
 * for Arrangement) lands with the first real single-record Focus.
 */

import { CoreHeader, EscToDismissHint, type CoreProps } from "./_shared"


const FIELDS = [
  "Deceased name",
  "Date of death",
  "Place of death",
  "Next of kin",
  "Service date",
  "Cemetery",
]


export function SingleRecordCore({ config }: CoreProps) {
  return (
    <div className="flex h-full flex-col gap-4">
      <CoreHeader modeLabel="singleRecord" title={config.displayName} />

      <div className="flex flex-1 flex-col gap-4 overflow-auto rounded-md border border-border-subtle bg-surface-sunken/40 p-6">
        {FIELDS.map((label) => (
          <div key={label} className="flex flex-col gap-1.5">
            <label className="text-body-sm font-medium text-content-strong">
              {label}
            </label>
            <div className="rounded-md border border-border-base bg-surface-elevated px-3 py-2">
              <span className="text-body-sm text-content-muted">
                placeholder value
              </span>
            </div>
          </div>
        ))}
      </div>

      <EscToDismissHint />
    </div>
  )
}
