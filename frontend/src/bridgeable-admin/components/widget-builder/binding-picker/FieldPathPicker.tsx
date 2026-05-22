/**
 * FieldPathPicker — WB-6 cascading combobox for field_path selection.
 *
 * Disabled until a saved view is picked. Once enabled, populates from
 * `EntityTypeMetadata.available_fields` for the chosen view's entity
 * type. Free-text fallback below the picker accepts manually-typed
 * paths (covers vault_item metadata_json gaps per Area 10 Risk 1).
 *
 * Cascades from SavedViewPicker via the `entityType` + `disabled`
 * props. Free-text falls back to typing for nested paths.
 */
import { useMemo, useState } from "react"

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { TextFieldUncontrolled } from "@/bridgeable-admin/components/widget-builder/inspectors/inspector-primitives"
import { cn } from "@/lib/utils"
import type {
  EntityType,
  EntityTypeMetadata,
} from "@/types/saved-views"


export interface FieldPathPickerProps {
  entityType: EntityType | null
  entityTypes: EntityTypeMetadata[]
  value: string | null
  onChange: (fieldPath: string | null) => void
  disabled?: boolean
  testId?: string
}


export function FieldPathPicker({
  entityType,
  entityTypes,
  value,
  onChange,
  disabled = false,
  testId,
}: FieldPathPickerProps) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState("")

  const fields = useMemo(() => {
    if (!entityType) return []
    const meta = entityTypes.find((e) => e.entity_type === entityType)
    if (!meta) return []
    const q = search.trim().toLowerCase()
    if (!q) return meta.available_fields
    return meta.available_fields.filter(
      (f) =>
        f.field_name.toLowerCase().includes(q) ||
        f.display_name.toLowerCase().includes(q),
    )
  }, [entityType, entityTypes, search])

  const effectiveDisabled = disabled || !entityType

  return (
    <div className="flex flex-col gap-1">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger
          data-testid={testId}
          disabled={effectiveDisabled}
          className={cn(
            "w-full rounded-md border border-border-base bg-surface-raised px-2 py-1.5 text-left text-body-sm text-content-base hover:border-border-strong focus:outline-none focus-ring-accent disabled:cursor-not-allowed disabled:opacity-50",
            !value && "text-content-subtle italic",
          )}
        >
          {value ?? (effectiveDisabled ? "Pick a saved view first" : "Pick a field")}
        </PopoverTrigger>
        <PopoverContent
          align="start"
          className="w-(--anchor-width) min-w-[16rem] max-w-md p-0"
        >
          <div className="border-b border-border-subtle p-2">
            <input
              data-testid={testId ? `${testId}-search` : undefined}
              type="text"
              placeholder="Search fields…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-md border border-border-base bg-surface-base px-2 py-1 text-body-sm focus:outline-none focus-ring-accent"
              autoFocus
            />
          </div>
          <div
            data-testid={testId ? `${testId}-results` : undefined}
            className="max-h-72 overflow-y-auto p-1"
          >
            {fields.length === 0 ? (
              <div className="px-2 py-3 text-caption text-content-subtle">
                No fields available. Try the free-text input below.
              </div>
            ) : (
              <ul className="flex flex-col">
                {fields.map((f) => (
                  <li key={f.field_name}>
                    <button
                      type="button"
                      data-testid={
                        testId ? `${testId}-option-${f.field_name}` : undefined
                      }
                      onClick={() => {
                        onChange(f.field_name)
                        setOpen(false)
                        setSearch("")
                      }}
                      className={cn(
                        "flex w-full items-center justify-between rounded-sm px-2 py-1.5 text-left text-body-sm hover:bg-accent-subtle focus:bg-accent-subtle focus:outline-none",
                        value === f.field_name && "bg-accent-subtle",
                      )}
                    >
                      <span className="flex flex-col">
                        <span className="font-medium text-content-strong">
                          {f.display_name}
                        </span>
                        <span className="font-plex-mono text-caption text-content-muted">
                          {f.field_name} · {f.field_type}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </PopoverContent>
      </Popover>
      {/* Free-text fallback for nested paths + vault_item metadata_json. */}
      <div className="flex flex-col gap-0.5">
        <span className="text-caption text-content-muted">
          Or type a custom path (dot-notation, e.g. <code className="font-plex-mono">items.0.name</code>):
        </span>
        <TextFieldUncontrolled
          testId={testId ? `${testId}-freetext` : undefined}
          value={value ?? ""}
          placeholder="custom.field_path"
          disabled={effectiveDisabled}
          onCommit={(v) => onChange(v === "" ? null : v)}
        />
      </div>
    </div>
  )
}
