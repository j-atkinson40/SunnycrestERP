/**
 * NumericEditor — numeric token control (rem, px, ms, alpha, integer).
 *
 * Slider + numeric input pair, bounds-aware. Emits the formatted
 * string with the unit suffix attached (so `rem` editor emits
 * `"1.25rem"`, not `1.25`).
 */

import { useEffect, useState } from "react"


export type NumericUnit = "rem" | "px" | "ms" | "" | "integer"


export interface NumericEditorProps {
  value: string
  onChange: (next: string) => void
  unit: NumericUnit
  min: number
  max: number
  step?: number
  disabled?: boolean
  "data-testid"?: string
}


function parseValue(value: string, unit: NumericUnit): number {
  if (!value) return 0
  if (unit === "rem") {
    const match = value.match(/^([0-9.]+)rem$/)
    if (match) return Number(match[1])
  }
  if (unit === "px") {
    const match = value.match(/^([0-9.]+)px$/)
    if (match) return Number(match[1])
  }
  if (unit === "ms") {
    const match = value.match(/^([0-9.]+)ms$/)
    if (match) return Number(match[1])
  }
  // alpha (no unit) or integer — parse direct
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}


function formatValue(n: number, unit: NumericUnit): string {
  if (unit === "rem") return `${+n.toFixed(4)}rem`
  if (unit === "px") return `${+n.toFixed(2)}px`
  if (unit === "ms") return `${Math.round(n)}ms`
  if (unit === "integer") return String(Math.round(n))
  return String(+n.toFixed(3)) // alpha / unitless
}


export function NumericEditor({
  value,
  onChange,
  unit,
  min,
  max,
  step,
  disabled,
  "data-testid": testid = "numeric-editor",
}: NumericEditorProps) {
  const [local, setLocal] = useState<number>(() => parseValue(value, unit))

  useEffect(() => {
    setLocal(parseValue(value, unit))
  }, [value, unit])

  const computedStep = step ?? (unit === "ms" || unit === "integer" ? 1 : 0.01)

  function emit(n: number) {
    const clamped = Math.max(min, Math.min(max, n))
    setLocal(clamped)
    onChange(formatValue(clamped, unit))
  }

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
        value={local}
        onChange={(e) => emit(Number(e.target.value))}
        disabled={disabled}
        data-testid={`${testid}-slider`}
        className="h-2 flex-1 cursor-ew-resize"
      />
      <input
        type="number"
        min={min}
        max={max}
        step={computedStep}
        value={local}
        onChange={(e) => {
          const n = Number(e.target.value)
          if (Number.isFinite(n)) emit(n)
        }}
        disabled={disabled}
        data-testid={`${testid}-input`}
        className="w-20 rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-right font-plex-mono text-caption text-content-base"
      />
      {unit && unit !== "integer" && (
        <span className="font-plex-mono text-caption text-content-muted">
          {unit}
        </span>
      )}
    </div>
  )
}
