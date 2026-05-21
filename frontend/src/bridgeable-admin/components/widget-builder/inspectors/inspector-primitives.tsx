/**
 * inspector-primitives — shared building blocks for WB-4b per-atom
 * inspectors.
 *
 * Three primitives:
 *   • `InspectorSection` — labeled section wrapper (h6-like heading +
 *     padded body), aligns with DESIGN_LANGUAGE.md typography tokens.
 *   • `InspectorField` — single labeled control row.
 *   • `TextFieldUncontrolled` — FF-6 uncontrolled-with-sync text input
 *     (local string state; commit on blur OR Enter; sync from prop
 *     when input is NOT focused; silent revert is N/A for free-text).
 *   • `SelectField` — wraps shadcn Select with InspectorField label.
 *   • `BindingPlaceholderField` — disabled-but-visible binding picker
 *     stub. Surfaces "binding will activate in WB-6/7".
 *
 * All keep error-aware affordances: an optional `error` prop renders a
 * caption-style status message + 1px red border on the control.
 */
import * as React from "react"

import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"


export function InspectorSection({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="mb-4 flex flex-col gap-2">
      <h6 className="text-caption font-medium uppercase tracking-wide text-content-muted">
        {title}
      </h6>
      <div className="flex flex-col gap-2">{children}</div>
    </section>
  )
}


export function InspectorField({
  label,
  htmlFor,
  error,
  children,
}: {
  label: string
  htmlFor?: string
  error?: string | undefined
  children: React.ReactNode
}) {
  return (
    <label
      htmlFor={htmlFor}
      className="flex flex-col gap-1 text-body-sm text-content-base"
    >
      <span className="text-caption font-medium text-content-muted">
        {label}
      </span>
      {children}
      {error ? (
        <span
          data-testid="inspector-field-error"
          className="text-caption text-status-error"
        >
          {error}
        </span>
      ) : null}
    </label>
  )
}


/** Uncontrolled-with-sync text input (FF-6 pattern).
 *
 *  Holds local string state. Commits on blur OR Enter via `onCommit`.
 *  Syncs from `value` prop when the input is NOT focused — canvas
 *  drag / external mutation reflects without stomping mid-edit.
 *  Empty-string commits propagate as `""` (caller decides whether
 *  to drop the key from config). */
export function TextFieldUncontrolled({
  value,
  onCommit,
  placeholder,
  disabled,
  error,
  testId,
}: {
  value: string
  onCommit: (next: string) => void
  placeholder?: string
  disabled?: boolean
  error?: string | undefined
  testId?: string
}) {
  const inputRef = React.useRef<HTMLInputElement>(null)
  const [local, setLocal] = React.useState<string>(value ?? "")

  React.useEffect(() => {
    if (typeof document === "undefined") {
      setLocal(value ?? "")
      return
    }
    if (document.activeElement === inputRef.current) return
    setLocal(value ?? "")
  }, [value])

  const commit = React.useCallback(() => {
    if (local !== value) onCommit(local)
  }, [local, value, onCommit])

  return (
    <Input
      ref={inputRef}
      data-testid={testId}
      value={local}
      placeholder={placeholder}
      disabled={disabled}
      onChange={(e) => setLocal(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault()
          commit()
        }
      }}
      className={cn(error ? "border-status-error" : "")}
    />
  )
}


export function SelectField<T extends string>({
  value,
  onChange,
  options,
  placeholder,
  disabled,
  testId,
}: {
  value: T | undefined
  onChange: (next: T) => void
  options: ReadonlyArray<{ value: T; label: string }>
  placeholder?: string
  disabled?: boolean
  testId?: string
}) {
  return (
    <Select
      value={value ?? ""}
      onValueChange={(v) => onChange(v as T)}
      disabled={disabled}
    >
      <SelectTrigger data-testid={testId} className="w-full">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {options.map((opt) => (
          <SelectItem key={opt.value} value={opt.value}>
            {opt.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}


/** Disabled-but-visible binding picker stub.
 *
 *  Surfaces the inspector control for a forthcoming binding picker
 *  (WB-6 saved-view bindings, WB-7 action picker) without operator
 *  interaction today. Shows a placeholder caption indicating which
 *  arc activates it. */
export function BindingPlaceholderField({
  label,
  activatedIn,
  testId,
}: {
  label: string
  activatedIn: "WB-6" | "WB-7"
  testId?: string
}) {
  return (
    <InspectorField label={label}>
      <div
        data-testid={testId}
        className="rounded-md border border-dashed border-border-subtle bg-surface-sunken px-2 py-1.5 text-caption text-content-subtle"
      >
        Binding picker activates in {activatedIn}
      </div>
    </InspectorField>
  )
}
