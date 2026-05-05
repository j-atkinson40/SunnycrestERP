/**
 * EnumEditor — dropdown for enum-shaped tokens (cubic-bezier
 * easings, font-family stacks). Each option carries a label +
 * the canonical value to emit.
 */


export interface EnumOption {
  value: string
  label: string
}


export interface EnumEditorProps {
  value: string
  onChange: (next: string) => void
  options: EnumOption[]
  disabled?: boolean
  "data-testid"?: string
}


export function EnumEditor({
  value,
  onChange,
  options,
  disabled,
  "data-testid": testid = "enum-editor",
}: EnumEditorProps) {
  // If the current value isn't in the option list, surface it as
  // a "Custom" option so the operator can still see what's in
  // effect even before they edit.
  const hasMatch = options.some((o) => o.value === value)

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      data-testid={testid}
      className="w-full rounded-md border border-border-base bg-surface-raised px-2 py-1.5 font-plex-mono text-caption text-content-base"
    >
      {!hasMatch && (
        <option value={value}>Custom: {value.slice(0, 40)}…</option>
      )}
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  )
}


// ─── Common option sets ─────────────────────────────────────


export const EASING_OPTIONS: EnumOption[] = [
  { value: "cubic-bezier(0.2, 0, 0.1, 1)", label: "Settle (canonical)" },
  { value: "cubic-bezier(0.4, 0, 0.4, 1)", label: "Gentle (canonical)" },
  { value: "linear", label: "Linear" },
  { value: "ease", label: "Ease (browser default)" },
  { value: "ease-in", label: "Ease-in" },
  { value: "ease-out", label: "Ease-out" },
  { value: "ease-in-out", label: "Ease-in-out" },
  {
    value: "cubic-bezier(0.32, 0.72, 0, 1)",
    label: "iOS spring approximation",
  },
]


export const FONT_FAMILY_OPTIONS: EnumOption[] = [
  {
    value:
      '"Geist Variable", "Geist", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    label: "Geist (canonical sans)",
  },
  {
    value: '"Fraunces Variable", "Fraunces", Georgia, "Times New Roman", serif',
    label: "Fraunces (canonical serif)",
  },
  {
    value:
      '"Geist Mono Variable", "Geist Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace',
    label: "Geist Mono (canonical mono)",
  },
  {
    value:
      '"IBM Plex Sans", "IBM Plex Sans Variable", -apple-system, sans-serif',
    label: "IBM Plex Sans (legacy)",
  },
  {
    value: 'system-ui, -apple-system, BlinkMacSystemFont, sans-serif',
    label: "System UI",
  },
]
