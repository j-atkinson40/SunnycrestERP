/**
 * Prop editor controls — Phase 3 of the Admin Visual Editor.
 *
 * Auto-generated controls per ConfigPropSchema type. Each control
 * is a controlled-component pattern: receives `value` + `onChange`,
 * emits the new value on user interaction. Bounds enforcement
 * happens here at the input layer (the slider can't exceed max,
 * the string input enforces maxLength) so the operator can't
 * produce out-of-bounds states the backend would reject.
 */

import { useMemo, useState } from "react"
import { ChevronDown, ChevronRight, ChevronUp, Plus, Trash2 } from "lucide-react"

import type { ConfigPropSchema } from "@/lib/visual-editor/registry"
import {
  TOKEN_CATALOG,
  getCategoryLabel,
  getTokensByCategory,
  type TokenCategory as CatalogTokenCategory,
  type TokenEntry,
} from "@/lib/visual-editor/themes/token-catalog"
import { getAllRegistered } from "@/lib/visual-editor/registry"


/** The registry's `TokenCategory` (broad family enum: "accent",
 * "status", "surface", etc.) overlaps but isn't identical to the
 * catalog's more granular `TokenCategory` (e.g.,
 * "motion-duration", "shadow-color"). The picker accepts the
 * registry shape (broader) and resolves to candidates by best-
 * effort matching: exact match if the catalog has the value,
 * otherwise filter by category prefix, otherwise show all. */
function resolveCandidatesForCategory(
  category: string | undefined,
): TokenEntry[] {
  if (!category || category === "any") return TOKEN_CATALOG
  // Exact match against catalog category
  const exact = getTokensByCategory(category as CatalogTokenCategory)
  if (exact.length > 0) return exact
  // Prefix match (e.g., "shadow" → "shadow-color" + "shadow-elevation")
  const prefixed = TOKEN_CATALOG.filter((t) =>
    t.category.startsWith(category),
  )
  if (prefixed.length > 0) return prefixed
  // Subcategory match (e.g., "error" → status tokens with subcategory "error")
  const sub = TOKEN_CATALOG.filter((t) => t.subcategory === category)
  if (sub.length > 0) return sub
  // No match — fall back to full catalog so the picker is at least usable.
  return TOKEN_CATALOG
}


// ─── Boolean ────────────────────────────────────────────────────


export interface BooleanControlProps {
  value: boolean
  onChange: (next: boolean) => void
  disabled?: boolean
  "data-testid"?: string
}

export function BooleanControl({
  value,
  onChange,
  disabled,
  "data-testid": testid = "prop-bool",
}: BooleanControlProps) {
  return (
    <label
      className="flex cursor-pointer items-center gap-2"
      data-testid={testid}
    >
      <input
        type="checkbox"
        role="switch"
        aria-checked={value}
        checked={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        data-testid={`${testid}-switch`}
        className="h-4 w-4 cursor-pointer accent-[var(--accent)]"
      />
      <span className="font-plex-mono text-caption text-content-base">
        {value ? "true" : "false"}
      </span>
    </label>
  )
}


// ─── String ──────────────────────────────────────────────────────


export interface StringControlProps {
  value: string
  onChange: (next: string) => void
  maxLength?: number
  placeholder?: string
  multiline?: boolean
  disabled?: boolean
  "data-testid"?: string
}

export function StringControl({
  value,
  onChange,
  maxLength,
  placeholder,
  multiline,
  disabled,
  "data-testid": testid = "prop-string",
}: StringControlProps) {
  const Input = multiline ? "textarea" : "input"
  return (
    <div
      className="flex flex-col gap-1"
      data-testid={testid}
    >
      <Input
        value={value}
        onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
          const next = e.target.value
          if (maxLength === undefined || next.length <= maxLength) {
            onChange(next)
          } else {
            onChange(next.slice(0, maxLength))
          }
        }}
        placeholder={placeholder}
        disabled={disabled}
        maxLength={maxLength}
        data-testid={`${testid}-input`}
        className="rounded-md border border-border-base bg-surface-raised px-2 py-1.5 font-plex-mono text-caption text-content-base"
        rows={multiline ? 3 : undefined}
      />
      {maxLength !== undefined && (
        <span className="text-right text-micro text-content-muted">
          {value.length}/{maxLength}
        </span>
      )}
    </div>
  )
}


// ─── Number ──────────────────────────────────────────────────────


export interface NumberControlProps {
  value: number
  onChange: (next: number) => void
  min?: number
  max?: number
  step?: number
  disabled?: boolean
  "data-testid"?: string
}

export function NumberControl({
  value,
  onChange,
  min = 0,
  max = 100,
  step,
  disabled,
  "data-testid": testid = "prop-number",
}: NumberControlProps) {
  const computedStep = step ?? ((max - min) / 100)
  const numericValue = typeof value === "number" && Number.isFinite(value) ? value : min

  return (
    <div
      className="flex items-center gap-2 rounded-md border border-border-subtle bg-surface-sunken p-2"
      data-testid={testid}
    >
      <input
        type="range"
        min={min}
        max={max}
        step={computedStep}
        value={numericValue}
        onChange={(e) => {
          const next = Number(e.target.value)
          if (Number.isFinite(next)) onChange(Math.max(min, Math.min(max, next)))
        }}
        disabled={disabled}
        data-testid={`${testid}-slider`}
        className="h-2 flex-1 cursor-ew-resize"
      />
      <input
        type="number"
        value={numericValue}
        min={min}
        max={max}
        step={computedStep}
        onChange={(e) => {
          const next = Number(e.target.value)
          if (Number.isFinite(next)) {
            onChange(Math.max(min, Math.min(max, next)))
          }
        }}
        disabled={disabled}
        data-testid={`${testid}-input`}
        className="w-24 rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-right font-plex-mono text-caption text-content-base"
      />
    </div>
  )
}


// ─── Enum ────────────────────────────────────────────────────────


export interface EnumControlProps {
  value: string
  onChange: (next: string) => void
  options: string[]
  disabled?: boolean
  "data-testid"?: string
}

export function EnumControl({
  value,
  onChange,
  options,
  disabled,
  "data-testid": testid = "prop-enum",
}: EnumControlProps) {
  // Segmented control for ≤6 options; dropdown for more.
  if (options.length <= 6) {
    return (
      <div
        role="radiogroup"
        className="flex flex-wrap gap-1 rounded-md border border-border-subtle bg-surface-raised p-0.5"
        data-testid={testid}
      >
        {options.map((opt) => (
          <button
            key={opt}
            type="button"
            role="radio"
            aria-checked={value === opt}
            disabled={disabled}
            onClick={() => onChange(opt)}
            data-testid={`${testid}-${opt}`}
            className={`rounded-sm px-2 py-1 text-caption font-plex-mono ${
              value === opt
                ? "bg-accent-subtle text-content-strong"
                : "text-content-muted hover:bg-accent-subtle/40"
            }`}
          >
            {opt}
          </button>
        ))}
      </div>
    )
  }
  return (
    <select
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      data-testid={testid}
      className="w-full rounded-md border border-border-base bg-surface-raised px-2 py-1.5 font-plex-mono text-caption text-content-base"
    >
      {options.map((opt) => (
        <option key={opt} value={opt}>
          {opt}
        </option>
      ))}
    </select>
  )
}


// ─── Token reference ─────────────────────────────────────────────


export interface TokenReferenceControlProps {
  value: string
  onChange: (next: string) => void
  /** Restrict the picker to one category. "any" / undefined shows
   * all tokens. Accepts the registry's broader category shape;
   * matched against the catalog via `resolveCandidatesForCategory`. */
  tokenCategory?: string
  disabled?: boolean
  "data-testid"?: string
}

export function TokenReferenceControl({
  value,
  onChange,
  tokenCategory,
  disabled,
  "data-testid": testid = "prop-token-ref",
}: TokenReferenceControlProps) {
  const candidates: TokenEntry[] = useMemo(
    () => resolveCandidatesForCategory(tokenCategory),
    [tokenCategory],
  )

  const [open, setOpen] = useState(false)

  const selected = candidates.find((t) => t.name === value)

  return (
    <div
      className="rounded-md border border-border-subtle bg-surface-sunken p-2"
      data-testid={testid}
    >
      <button
        type="button"
        onClick={() => setOpen((cur) => !cur)}
        disabled={disabled}
        data-testid={`${testid}-toggle`}
        className="flex w-full items-center justify-between gap-2 rounded-sm border border-border-base bg-surface-raised px-2 py-1.5 text-left"
      >
        <code
          className="flex-1 truncate font-plex-mono text-caption text-content-base"
          data-testid={`${testid}-current`}
        >
          {value || "—"}
        </code>
        {selected && (
          <span className="text-caption text-content-muted">
            {selected.displayName}
          </span>
        )}
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </button>
      {open && (
        <div
          className="mt-1 max-h-64 overflow-y-auto rounded-sm border border-border-subtle bg-surface-raised"
          data-testid={`${testid}-list`}
        >
          {candidates.length === 0 ? (
            <p className="p-2 text-caption text-content-muted">
              No tokens in this category.
            </p>
          ) : (
            <ul>
              {candidates.map((t) => (
                <li key={t.name}>
                  <button
                    type="button"
                    onClick={() => {
                      onChange(t.name)
                      setOpen(false)
                    }}
                    data-testid={`${testid}-option-${t.name}`}
                    className={`flex w-full items-center justify-between px-2 py-1 text-left hover:bg-accent-subtle ${
                      t.name === value ? "bg-accent-subtle" : ""
                    }`}
                  >
                    <code className="font-plex-mono text-caption text-content-base">
                      {t.name}
                    </code>
                    <span className="text-caption text-content-muted">
                      {getCategoryLabel(t.category)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}


// ─── Component reference ─────────────────────────────────────────


export interface ComponentReferenceControlProps {
  value: string
  onChange: (next: string) => void
  /** Restrict the picker to specific component kinds. */
  componentTypes?: string[]
  disabled?: boolean
  "data-testid"?: string
}

export function ComponentReferenceControl({
  value,
  onChange,
  componentTypes,
  disabled,
  "data-testid": testid = "prop-comp-ref",
}: ComponentReferenceControlProps) {
  const candidates = useMemo(() => {
    const all = getAllRegistered()
    if (!componentTypes || componentTypes.length === 0) return all
    return all.filter((e) => componentTypes.includes(e.metadata.type))
  }, [componentTypes])

  return (
    <select
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      data-testid={testid}
      className="w-full rounded-md border border-border-base bg-surface-raised px-2 py-1.5 font-plex-mono text-caption text-content-base"
    >
      <option value="">— select component —</option>
      {candidates.map((c) => (
        <option key={`${c.metadata.type}:${c.metadata.name}`} value={c.metadata.name}>
          {c.metadata.displayName} ({c.metadata.type})
        </option>
      ))}
    </select>
  )
}


// ─── Array ──────────────────────────────────────────────────────


export interface ArrayControlProps {
  value: unknown[]
  onChange: (next: unknown[]) => void
  /** Schema describing each item's type. */
  itemSchema?: ConfigPropSchema
  disabled?: boolean
  "data-testid"?: string
}

export function ArrayControl({
  value,
  onChange,
  itemSchema,
  disabled,
  "data-testid": testid = "prop-array",
}: ArrayControlProps) {
  const items = Array.isArray(value) ? value : []
  const itemDefault =
    itemSchema?.default ?? (itemSchema?.type === "number" ? 0 : "")

  return (
    <div
      className="flex flex-col gap-1 rounded-md border border-border-subtle bg-surface-sunken p-2"
      data-testid={testid}
    >
      {items.length === 0 ? (
        <p className="text-caption text-content-muted">No entries.</p>
      ) : (
        items.map((item, idx) => (
          <div
            key={idx}
            className="flex items-center gap-1"
            data-testid={`${testid}-row-${idx}`}
          >
            <input
              value={String(item)}
              disabled={disabled}
              onChange={(e) => {
                const next = [...items]
                next[idx] =
                  itemSchema?.type === "number"
                    ? Number(e.target.value)
                    : e.target.value
                onChange(next)
              }}
              data-testid={`${testid}-row-${idx}-input`}
              className="flex-1 rounded-sm border border-border-base bg-surface-raised px-2 py-1 font-plex-mono text-caption text-content-base"
            />
            <button
              type="button"
              disabled={disabled}
              onClick={() => onChange(items.filter((_, i) => i !== idx))}
              data-testid={`${testid}-row-${idx}-remove`}
              aria-label="Remove entry"
              className="rounded-sm border border-border-base bg-surface-raised p-1 text-content-muted hover:bg-status-error-muted hover:text-status-error"
            >
              <Trash2 size={12} />
            </button>
          </div>
        ))
      )}
      <button
        type="button"
        disabled={disabled}
        onClick={() => onChange([...items, itemDefault])}
        data-testid={`${testid}-add`}
        className="flex items-center gap-1 self-start rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-caption text-content-muted hover:bg-accent-subtle"
      >
        <Plus size={12} /> Add entry
      </button>
    </div>
  )
}


// ─── Object (JSON) ──────────────────────────────────────────────


export interface ObjectControlProps {
  value: Record<string, unknown>
  onChange: (next: Record<string, unknown>) => void
  disabled?: boolean
  "data-testid"?: string
}

export function ObjectControl({
  value,
  onChange,
  disabled,
  "data-testid": testid = "prop-object",
}: ObjectControlProps) {
  // Phase 3 ships object-prop editing as a JSON textarea (per the
  // prompt: "Phase 3 can ship this as a stub that renders the
  // JSON; full nested editing is a later phase").
  const [draft, setDraft] = useState<string>(() => JSON.stringify(value ?? {}, null, 2))
  const [error, setError] = useState<string | null>(null)

  return (
    <div
      className="flex flex-col gap-1 rounded-md border border-border-subtle bg-surface-sunken p-2"
      data-testid={testid}
    >
      <textarea
        value={draft}
        disabled={disabled}
        onChange={(e) => {
          setDraft(e.target.value)
          try {
            const parsed = JSON.parse(e.target.value || "{}")
            if (typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)) {
              setError(null)
              onChange(parsed)
            } else {
              setError("Must be a JSON object.")
            }
          } catch (parseErr) {
            setError("Invalid JSON.")
          }
        }}
        rows={5}
        data-testid={`${testid}-textarea`}
        className="rounded-sm border border-border-base bg-surface-raised p-2 font-plex-mono text-caption text-content-base"
      />
      {error && (
        <span className="text-caption text-status-error" data-testid={`${testid}-error`}>
          {error}
        </span>
      )}
    </div>
  )
}


// ─── Arc 4b.1a — Bespoke array-of-records controls ──────────────
//
// Block-kind config shapes that the canonical ArrayControl cannot
// render cleanly: each row is a record with named fields whose
// per-row controls + ordering semantics + per-row validation diverge
// from a single-typed-value array.
//
// Pattern: each control is a fully-controlled component matching
// the canonical Boolean/String/Number contract — accepts `value`
// (typed array) + `onChange(next)` + `disabled` + `data-testid`.
// Add/remove/reorder affordances render as inline buttons. Per-row
// fields render via per-control internal markup (not nested
// PropControlDispatcher dispatch — keeps semantics bounded; row
// shape is the contract).
//
// PropControlDispatcher (below) routes the new ConfigPropType
// discriminators to these controls additively; existing 8 types
// unchanged.


// ─── TableOfColumns (line_items.columns) ─────────────────────────


export interface ColumnDef {
  header: string
  field: string
  format?: string
}

export interface TableOfColumnsControlProps {
  value: ColumnDef[]
  onChange: (next: ColumnDef[]) => void
  disabled?: boolean
  "data-testid"?: string
}

const COLUMN_DEFAULT: ColumnDef = { header: "", field: "" }

function moveItem<T>(items: T[], from: number, to: number): T[] {
  if (to < 0 || to >= items.length || from === to) return items
  const next = [...items]
  const [it] = next.splice(from, 1)
  next.splice(to, 0, it)
  return next
}

export function TableOfColumnsControl({
  value,
  onChange,
  disabled,
  "data-testid": testid = "prop-table-of-columns",
}: TableOfColumnsControlProps) {
  const items = Array.isArray(value) ? value : []

  const updateRow = (idx: number, patch: Partial<ColumnDef>) => {
    const next = items.map((row, i) => (i === idx ? { ...row, ...patch } : row))
    onChange(next)
  }

  return (
    <div
      className="flex flex-col gap-2 rounded-md border border-border-subtle bg-surface-sunken p-2"
      data-testid={testid}
    >
      {items.length === 0 ? (
        <p className="text-caption text-content-muted" data-testid={`${testid}-empty`}>
          No columns.
        </p>
      ) : (
        items.map((row, idx) => (
          <div
            key={idx}
            className="flex items-start gap-1 rounded-sm border border-border-subtle bg-surface-raised p-2"
            data-testid={`${testid}-row-${idx}`}
          >
            <div className="flex flex-1 flex-col gap-1">
              <input
                type="text"
                value={row.header ?? ""}
                placeholder="Header"
                disabled={disabled}
                onChange={(e) => updateRow(idx, { header: e.target.value })}
                data-testid={`${testid}-row-${idx}-header`}
                className="rounded-sm border border-border-base bg-surface-raised px-2 py-1 font-plex-mono text-caption text-content-base"
              />
              <input
                type="text"
                value={row.field ?? ""}
                placeholder="Field path (e.g. item.description)"
                disabled={disabled}
                onChange={(e) => updateRow(idx, { field: e.target.value })}
                data-testid={`${testid}-row-${idx}-field`}
                className="rounded-sm border border-border-base bg-surface-raised px-2 py-1 font-plex-mono text-caption text-content-base"
              />
              <input
                type="text"
                value={row.format ?? ""}
                placeholder="Format filter (optional, e.g. currency)"
                disabled={disabled}
                onChange={(e) => {
                  const v = e.target.value
                  updateRow(idx, v ? { format: v } : { format: undefined })
                }}
                data-testid={`${testid}-row-${idx}-format`}
                className="rounded-sm border border-border-base bg-surface-raised px-2 py-1 font-plex-mono text-caption text-content-base"
              />
            </div>
            <div className="flex flex-col gap-1">
              <button
                type="button"
                disabled={disabled || idx === 0}
                onClick={() => onChange(moveItem(items, idx, idx - 1))}
                data-testid={`${testid}-row-${idx}-up`}
                aria-label="Move column up"
                className="rounded-sm border border-border-base bg-surface-raised p-1 text-content-muted hover:bg-accent-subtle disabled:opacity-30"
              >
                <ChevronUp size={12} />
              </button>
              <button
                type="button"
                disabled={disabled || idx === items.length - 1}
                onClick={() => onChange(moveItem(items, idx, idx + 1))}
                data-testid={`${testid}-row-${idx}-down`}
                aria-label="Move column down"
                className="rounded-sm border border-border-base bg-surface-raised p-1 text-content-muted hover:bg-accent-subtle disabled:opacity-30"
              >
                <ChevronDown size={12} />
              </button>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onChange(items.filter((_, i) => i !== idx))}
                data-testid={`${testid}-row-${idx}-remove`}
                aria-label="Remove column"
                className="rounded-sm border border-border-base bg-surface-raised p-1 text-content-muted hover:bg-status-error-muted hover:text-status-error"
              >
                <Trash2 size={12} />
              </button>
            </div>
          </div>
        ))
      )}
      <button
        type="button"
        disabled={disabled}
        onClick={() => onChange([...items, { ...COLUMN_DEFAULT }])}
        data-testid={`${testid}-add`}
        className="flex items-center gap-1 self-start rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-caption text-content-muted hover:bg-accent-subtle"
      >
        <Plus size={12} /> Add column
      </button>
    </div>
  )
}


// ─── TableOfRows (totals.rows) ───────────────────────────────────


export interface TotalsRowDef {
  label: string
  variable: string
  emphasis?: boolean
}

export interface TableOfRowsControlProps {
  value: TotalsRowDef[]
  onChange: (next: TotalsRowDef[]) => void
  disabled?: boolean
  "data-testid"?: string
}

const TOTALS_ROW_DEFAULT: TotalsRowDef = { label: "", variable: "" }

export function TableOfRowsControl({
  value,
  onChange,
  disabled,
  "data-testid": testid = "prop-table-of-rows",
}: TableOfRowsControlProps) {
  const items = Array.isArray(value) ? value : []

  const updateRow = (idx: number, patch: Partial<TotalsRowDef>) => {
    const next = items.map((row, i) => (i === idx ? { ...row, ...patch } : row))
    onChange(next)
  }

  return (
    <div
      className="flex flex-col gap-2 rounded-md border border-border-subtle bg-surface-sunken p-2"
      data-testid={testid}
    >
      {items.length === 0 ? (
        <p className="text-caption text-content-muted" data-testid={`${testid}-empty`}>
          No rows.
        </p>
      ) : (
        items.map((row, idx) => (
          <div
            key={idx}
            className="flex items-start gap-1 rounded-sm border border-border-subtle bg-surface-raised p-2"
            data-testid={`${testid}-row-${idx}`}
          >
            <div className="flex flex-1 flex-col gap-1">
              <input
                type="text"
                value={row.label ?? ""}
                placeholder="Label (e.g. Subtotal)"
                disabled={disabled}
                onChange={(e) => updateRow(idx, { label: e.target.value })}
                data-testid={`${testid}-row-${idx}-label`}
                className="rounded-sm border border-border-base bg-surface-raised px-2 py-1 font-plex-mono text-caption text-content-base"
              />
              <input
                type="text"
                value={row.variable ?? ""}
                placeholder="Variable (e.g. subtotal)"
                disabled={disabled}
                onChange={(e) => updateRow(idx, { variable: e.target.value })}
                data-testid={`${testid}-row-${idx}-variable`}
                className="rounded-sm border border-border-base bg-surface-raised px-2 py-1 font-plex-mono text-caption text-content-base"
              />
              <label
                className="flex cursor-pointer items-center gap-2 px-1"
                data-testid={`${testid}-row-${idx}-emphasis-label`}
              >
                <input
                  type="checkbox"
                  role="switch"
                  aria-checked={!!row.emphasis}
                  checked={!!row.emphasis}
                  disabled={disabled}
                  onChange={(e) =>
                    updateRow(idx, { emphasis: e.target.checked || undefined })
                  }
                  data-testid={`${testid}-row-${idx}-emphasis`}
                  className="h-3.5 w-3.5 cursor-pointer accent-[var(--accent)]"
                />
                <span className="text-caption text-content-muted">
                  Emphasis (final total)
                </span>
              </label>
            </div>
            <div className="flex flex-col gap-1">
              <button
                type="button"
                disabled={disabled || idx === 0}
                onClick={() => onChange(moveItem(items, idx, idx - 1))}
                data-testid={`${testid}-row-${idx}-up`}
                aria-label="Move row up"
                className="rounded-sm border border-border-base bg-surface-raised p-1 text-content-muted hover:bg-accent-subtle disabled:opacity-30"
              >
                <ChevronUp size={12} />
              </button>
              <button
                type="button"
                disabled={disabled || idx === items.length - 1}
                onClick={() => onChange(moveItem(items, idx, idx + 1))}
                data-testid={`${testid}-row-${idx}-down`}
                aria-label="Move row down"
                className="rounded-sm border border-border-base bg-surface-raised p-1 text-content-muted hover:bg-accent-subtle disabled:opacity-30"
              >
                <ChevronDown size={12} />
              </button>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onChange(items.filter((_, i) => i !== idx))}
                data-testid={`${testid}-row-${idx}-remove`}
                aria-label="Remove row"
                className="rounded-sm border border-border-base bg-surface-raised p-1 text-content-muted hover:bg-status-error-muted hover:text-status-error"
              >
                <Trash2 size={12} />
              </button>
            </div>
          </div>
        ))
      )}
      <button
        type="button"
        disabled={disabled}
        onClick={() => onChange([...items, { ...TOTALS_ROW_DEFAULT }])}
        data-testid={`${testid}-add`}
        className="flex items-center gap-1 self-start rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-caption text-content-muted hover:bg-accent-subtle"
      >
        <Plus size={12} /> Add row
      </button>
    </div>
  )
}


// ─── ListOfParties (signature.parties) ──────────────────────────


export interface PartyDef {
  role: string
  /** ISO date string; rendered via native date picker. */
  signature_date?: string
}

export interface ListOfPartiesControlProps {
  value: PartyDef[]
  onChange: (next: PartyDef[]) => void
  disabled?: boolean
  "data-testid"?: string
}

const PARTY_DEFAULT: PartyDef = { role: "" }

export function ListOfPartiesControl({
  value,
  onChange,
  disabled,
  "data-testid": testid = "prop-list-of-parties",
}: ListOfPartiesControlProps) {
  const items = Array.isArray(value) ? value : []

  const updateRow = (idx: number, patch: Partial<PartyDef>) => {
    const next = items.map((row, i) => (i === idx ? { ...row, ...patch } : row))
    onChange(next)
  }

  return (
    <div
      className="flex flex-col gap-2 rounded-md border border-border-subtle bg-surface-sunken p-2"
      data-testid={testid}
    >
      {items.length === 0 ? (
        <p className="text-caption text-content-muted" data-testid={`${testid}-empty`}>
          No parties.
        </p>
      ) : (
        items.map((row, idx) => (
          <div
            key={idx}
            className="flex items-start gap-1 rounded-sm border border-border-subtle bg-surface-raised p-2"
            data-testid={`${testid}-row-${idx}`}
          >
            <div className="flex flex-1 flex-col gap-1">
              <input
                type="text"
                value={row.role ?? ""}
                placeholder="Role (e.g. Customer, Funeral Director)"
                disabled={disabled}
                onChange={(e) => updateRow(idx, { role: e.target.value })}
                data-testid={`${testid}-row-${idx}-role`}
                className="rounded-sm border border-border-base bg-surface-raised px-2 py-1 font-plex-mono text-caption text-content-base"
              />
              <input
                type="date"
                value={row.signature_date ?? ""}
                disabled={disabled}
                onChange={(e) => {
                  const v = e.target.value
                  updateRow(idx, v ? { signature_date: v } : { signature_date: undefined })
                }}
                data-testid={`${testid}-row-${idx}-date`}
                className="rounded-sm border border-border-base bg-surface-raised px-2 py-1 font-plex-mono text-caption text-content-base"
              />
            </div>
            <div className="flex flex-col gap-1">
              <button
                type="button"
                disabled={disabled || idx === 0}
                onClick={() => onChange(moveItem(items, idx, idx - 1))}
                data-testid={`${testid}-row-${idx}-up`}
                aria-label="Move party up"
                className="rounded-sm border border-border-base bg-surface-raised p-1 text-content-muted hover:bg-accent-subtle disabled:opacity-30"
              >
                <ChevronUp size={12} />
              </button>
              <button
                type="button"
                disabled={disabled || idx === items.length - 1}
                onClick={() => onChange(moveItem(items, idx, idx + 1))}
                data-testid={`${testid}-row-${idx}-down`}
                aria-label="Move party down"
                className="rounded-sm border border-border-base bg-surface-raised p-1 text-content-muted hover:bg-accent-subtle disabled:opacity-30"
              >
                <ChevronDown size={12} />
              </button>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onChange(items.filter((_, i) => i !== idx))}
                data-testid={`${testid}-row-${idx}-remove`}
                aria-label="Remove party"
                className="rounded-sm border border-border-base bg-surface-raised p-1 text-content-muted hover:bg-status-error-muted hover:text-status-error"
              >
                <Trash2 size={12} />
              </button>
            </div>
          </div>
        ))
      )}
      <button
        type="button"
        disabled={disabled}
        onClick={() => onChange([...items, { ...PARTY_DEFAULT }])}
        data-testid={`${testid}-add`}
        className="flex items-center gap-1 self-start rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-caption text-content-muted hover:bg-accent-subtle"
      >
        <Plus size={12} /> Add party
      </button>
    </div>
  )
}


// ─── ConditionalRule (conditional_wrapper.condition) ─────────────


/** Bounded operator vocabulary. NOT a Jinja expression language.
 *  Each operator translates to a deterministic Jinja fragment via
 *  `renderConditionalRule`; future operator additions register
 *  here additively. */
export const CONDITIONAL_RULE_OPERATORS = [
  "equals",
  "not_equals",
  "contains",
  "not_contains",
  "exists",
  "not_exists",
  "greater_than",
  "less_than",
] as const

export type ConditionalRuleOperator = (typeof CONDITIONAL_RULE_OPERATORS)[number]

export interface ConditionalRule {
  field: string
  operator: ConditionalRuleOperator
  value?: string
}

export interface ConditionalRuleControlProps {
  value: ConditionalRule
  onChange: (next: ConditionalRule) => void
  /** Optional list of known context field names for the field picker
   *  (rendered as datalist suggestions; field input remains free-text
   *  to support arbitrary Jinja paths). */
  fieldSuggestions?: string[]
  disabled?: boolean
  "data-testid"?: string
}

/** Operators that don't read the `value` field — UX hides the value
 *  input when one of these is selected. */
const NULLARY_OPERATORS = new Set<ConditionalRuleOperator>([
  "exists",
  "not_exists",
])

export function ConditionalRuleControl({
  value,
  onChange,
  fieldSuggestions,
  disabled,
  "data-testid": testid = "prop-conditional-rule",
}: ConditionalRuleControlProps) {
  const rule: ConditionalRule =
    value && typeof value === "object" && "operator" in value
      ? value
      : { field: "", operator: "equals", value: "" }

  const showValueInput = !NULLARY_OPERATORS.has(rule.operator)
  const datalistId = `${testid}-field-suggestions`

  return (
    <div
      className="flex flex-col gap-2 rounded-md border border-border-subtle bg-surface-sunken p-2"
      data-testid={testid}
    >
      <div className="flex flex-col gap-1">
        <label className="text-micro uppercase tracking-wider text-content-muted">
          Field
        </label>
        <input
          type="text"
          value={rule.field ?? ""}
          placeholder="Field path (e.g. case.disposition)"
          disabled={disabled}
          list={fieldSuggestions && fieldSuggestions.length > 0 ? datalistId : undefined}
          onChange={(e) => onChange({ ...rule, field: e.target.value })}
          data-testid={`${testid}-field`}
          className="rounded-sm border border-border-base bg-surface-raised px-2 py-1 font-plex-mono text-caption text-content-base"
        />
        {fieldSuggestions && fieldSuggestions.length > 0 && (
          <datalist id={datalistId}>
            {fieldSuggestions.map((s) => (
              <option key={s} value={s} />
            ))}
          </datalist>
        )}
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-micro uppercase tracking-wider text-content-muted">
          Operator
        </label>
        <select
          value={rule.operator}
          disabled={disabled}
          onChange={(e) => {
            const op = e.target.value as ConditionalRuleOperator
            const next: ConditionalRule = { ...rule, operator: op }
            if (NULLARY_OPERATORS.has(op)) {
              next.value = undefined
            } else if (next.value === undefined) {
              next.value = ""
            }
            onChange(next)
          }}
          data-testid={`${testid}-operator`}
          className="rounded-sm border border-border-base bg-surface-raised px-2 py-1 font-plex-mono text-caption text-content-base"
        >
          {CONDITIONAL_RULE_OPERATORS.map((op) => (
            <option key={op} value={op}>
              {op.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </div>
      {showValueInput && (
        <div className="flex flex-col gap-1">
          <label className="text-micro uppercase tracking-wider text-content-muted">
            Value
          </label>
          <input
            type="text"
            value={rule.value ?? ""}
            placeholder="Comparison value"
            disabled={disabled}
            onChange={(e) => onChange({ ...rule, value: e.target.value })}
            data-testid={`${testid}-value`}
            className="rounded-sm border border-border-base bg-surface-raised px-2 py-1 font-plex-mono text-caption text-content-base"
          />
        </div>
      )}
    </div>
  )
}


// ─── Dispatcher ──────────────────────────────────────────────────


export interface PropControlDispatcherProps {
  schema: ConfigPropSchema
  value: unknown
  onChange: (next: unknown) => void
  disabled?: boolean
  "data-testid"?: string
}

export function PropControlDispatcher({
  schema,
  value,
  onChange,
  disabled,
  "data-testid": testid = "prop-control",
}: PropControlDispatcherProps) {
  const t = schema.type

  if (t === "boolean") {
    return (
      <BooleanControl
        value={Boolean(value)}
        onChange={onChange}
        disabled={disabled}
        data-testid={testid}
      />
    )
  }
  if (t === "number") {
    const bounds =
      Array.isArray(schema.bounds) && schema.bounds.length === 2
        ? (schema.bounds as [number, number])
        : ([0, 100] as [number, number])
    return (
      <NumberControl
        value={typeof value === "number" ? value : Number(value) || bounds[0]}
        onChange={onChange}
        min={bounds[0]}
        max={bounds[1]}
        disabled={disabled}
        data-testid={testid}
      />
    )
  }
  if (t === "string") {
    const maxLen =
      typeof schema.bounds === "object" &&
      schema.bounds !== null &&
      "maxLength" in (schema.bounds as Record<string, unknown>)
        ? Number((schema.bounds as Record<string, unknown>).maxLength)
        : undefined
    return (
      <StringControl
        value={value !== undefined && value !== null ? String(value) : ""}
        onChange={onChange}
        maxLength={maxLen}
        disabled={disabled}
        data-testid={testid}
      />
    )
  }
  if (t === "enum") {
    const options = Array.isArray(schema.bounds)
      ? (schema.bounds as string[])
      : []
    return (
      <EnumControl
        value={String(value)}
        onChange={onChange}
        options={options}
        disabled={disabled}
        data-testid={testid}
      />
    )
  }
  if (t === "tokenReference") {
    return (
      <TokenReferenceControl
        value={String(value ?? "")}
        onChange={onChange}
        tokenCategory={schema.tokenCategory}
        disabled={disabled}
        data-testid={testid}
      />
    )
  }
  if (t === "componentReference") {
    return (
      <ComponentReferenceControl
        value={String(value ?? "")}
        onChange={onChange}
        componentTypes={schema.componentTypes}
        disabled={disabled}
        data-testid={testid}
      />
    )
  }
  if (t === "array") {
    return (
      <ArrayControl
        value={Array.isArray(value) ? value : []}
        onChange={onChange}
        itemSchema={schema.itemSchema}
        disabled={disabled}
        data-testid={testid}
      />
    )
  }
  if (t === "object") {
    return (
      <ObjectControl
        value={
          typeof value === "object" && value !== null && !Array.isArray(value)
            ? (value as Record<string, unknown>)
            : {}
        }
        onChange={onChange}
        disabled={disabled}
        data-testid={testid}
      />
    )
  }
  if (t === "tableOfColumns") {
    return (
      <TableOfColumnsControl
        value={Array.isArray(value) ? (value as ColumnDef[]) : []}
        onChange={onChange as (next: ColumnDef[]) => void}
        disabled={disabled}
        data-testid={testid}
      />
    )
  }
  if (t === "tableOfRows") {
    return (
      <TableOfRowsControl
        value={Array.isArray(value) ? (value as TotalsRowDef[]) : []}
        onChange={onChange as (next: TotalsRowDef[]) => void}
        disabled={disabled}
        data-testid={testid}
      />
    )
  }
  if (t === "listOfParties") {
    return (
      <ListOfPartiesControl
        value={Array.isArray(value) ? (value as PartyDef[]) : []}
        onChange={onChange as (next: PartyDef[]) => void}
        disabled={disabled}
        data-testid={testid}
      />
    )
  }
  if (t === "conditionalRule") {
    const rule =
      value && typeof value === "object" && "operator" in (value as object)
        ? (value as ConditionalRule)
        : { field: "", operator: "equals" as ConditionalRuleOperator, value: "" }
    return (
      <ConditionalRuleControl
        value={rule}
        onChange={onChange as (next: ConditionalRule) => void}
        disabled={disabled}
        data-testid={testid}
      />
    )
  }

  // Fallback — display raw JSON.
  return (
    <pre
      className="rounded-md border border-border-subtle bg-surface-sunken p-2 font-plex-mono text-caption text-content-base"
      data-testid={testid}
    >
      {JSON.stringify(value)}
    </pre>
  )
}
