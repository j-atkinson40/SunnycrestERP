/**
 * OklchPicker — Phase 2 of the Admin Visual Editor.
 *
 * Genuine OKLCH editing (not hex-to-oklch under the hood). Three
 * sliders — Lightness (0..1), Chroma (0..0.4), Hue (0..360) —
 * plus an optional Alpha slider (0..1). Values format/parse via
 * `theme-resolver`'s `parseOklch` + `formatOklch`. The swatch
 * preview converts to sRGB via Ottosson 2020.
 *
 * Important: editing happens in OKLCH space. Channel sliders
 * operate on OKLCH coordinates directly so the warm-family hue
 * rules from DESIGN_LANGUAGE.md remain interpretable to the
 * operator. No round-tripping through RGB to feel "more familiar."
 */

import { useEffect, useMemo, useRef, useState } from "react"

import {
  formatOklch,
  oklchToCssRgb,
  parseOklch,
  type OklchValue,
} from "../theme-resolver"


export interface OklchPickerProps {
  value: string // oklch(...) literal
  onChange: (next: string) => void
  /** When true, exposes the alpha slider. Used by tokens whose
   * `valueType === "oklch-with-alpha"`. */
  allowAlpha?: boolean
  /** Read-only mode — sliders disabled, swatch + numeric values
   * still rendered. */
  readOnly?: boolean
  /** Forwarded to root for testing. */
  "data-testid"?: string
}


const DEFAULT: OklchValue = { l: 0.5, c: 0.1, h: 50, alpha: 1 }


export function OklchPicker({
  value,
  onChange,
  allowAlpha = false,
  readOnly = false,
  "data-testid": testid = "oklch-picker",
}: OklchPickerProps) {
  // Internal local state lets the user drag a slider smoothly even
  // when the parent's `value` prop is the canonical formatted
  // string. We sync from `value` whenever it changes externally.
  const [local, setLocal] = useState<OklchValue>(() => parseOklch(value) ?? DEFAULT)
  const lastEmitted = useRef<string>(value)

  // External value changes (e.g., reset-to-inherited) flow into
  // the local state. We guard against echoing our own emissions
  // back as if they were external.
  useEffect(() => {
    if (value === lastEmitted.current) return
    const parsed = parseOklch(value)
    if (parsed) setLocal(parsed)
  }, [value])

  const swatchColor = useMemo(() => oklchToCssRgb(local), [local])

  function emit(next: OklchValue) {
    setLocal(next)
    const formatted = formatOklch(next)
    lastEmitted.current = formatted
    onChange(formatted)
  }

  const onL = (e: React.ChangeEvent<HTMLInputElement>) =>
    emit({ ...local, l: Number(e.target.value) })
  const onC = (e: React.ChangeEvent<HTMLInputElement>) =>
    emit({ ...local, c: Number(e.target.value) })
  const onH = (e: React.ChangeEvent<HTMLInputElement>) =>
    emit({ ...local, h: Number(e.target.value) })
  const onA = (e: React.ChangeEvent<HTMLInputElement>) =>
    emit({ ...local, alpha: Number(e.target.value) })

  return (
    <div
      className="flex flex-col gap-2 rounded-md border border-border-subtle bg-surface-sunken p-2"
      data-testid={testid}
    >
      <div className="flex items-center gap-2">
        <div
          className="h-9 w-9 shrink-0 rounded-sm border border-border-base"
          style={{ background: swatchColor }}
          data-testid={`${testid}-swatch`}
          aria-label={`Color preview ${formatOklch(local)}`}
        />
        <code
          className="flex-1 truncate font-plex-mono text-caption text-content-base"
          data-testid={`${testid}-canonical`}
        >
          {formatOklch(local)}
        </code>
      </div>

      <SliderRow
        label="L"
        min={0}
        max={1}
        step={0.001}
        value={local.l}
        onChange={onL}
        format={(v) => v.toFixed(3)}
        disabled={readOnly}
        testid={`${testid}-l`}
      />
      <SliderRow
        label="C"
        min={0}
        max={0.4}
        step={0.001}
        value={local.c}
        onChange={onC}
        format={(v) => v.toFixed(3)}
        disabled={readOnly}
        testid={`${testid}-c`}
      />
      <SliderRow
        label="H"
        min={0}
        max={360}
        step={1}
        value={local.h}
        onChange={onH}
        format={(v) => `${Math.round(v)}°`}
        disabled={readOnly}
        testid={`${testid}-h`}
      />
      {allowAlpha && (
        <SliderRow
          label="α"
          min={0}
          max={1}
          step={0.01}
          value={local.alpha}
          onChange={onA}
          format={(v) => v.toFixed(2)}
          disabled={readOnly}
          testid={`${testid}-alpha`}
        />
      )}
    </div>
  )
}


function SliderRow({
  label,
  min,
  max,
  step,
  value,
  onChange,
  format,
  disabled,
  testid,
}: {
  label: string
  min: number
  max: number
  step: number
  value: number
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  format: (v: number) => string
  disabled?: boolean
  testid: string
}) {
  return (
    <label className="grid grid-cols-[20px_1fr_56px] items-center gap-2">
      <span className="font-plex-mono text-micro text-content-muted">
        {label}
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={onChange}
        disabled={disabled}
        data-testid={testid}
        className="h-2 cursor-ew-resize"
      />
      <span className="text-right font-plex-mono text-caption text-content-base">
        {format(value)}
      </span>
    </label>
  )
}
