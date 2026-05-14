/**
 * ScrubbableButton — visual-authoring primitive (sub-arc C-1).
 *
 * A button-styled control whose value scrubs as the pointer drags
 * horizontally. Adapted from Sketch's inspector numeric inputs;
 * sits on a warm-cream/warm-charcoal substrate with brass accents
 * during active scrub.
 *
 * Idle state:
 *   - Renders as a tidy button. Cursor: ew-resize.
 *   - Label (IBM Plex Sans) + value (IBM Plex Mono) + optional unit.
 *
 * Active scrub:
 *   - pointerdown → setPointerCapture, brass border, cursor: grabbing.
 *   - Horizontal pointer delta drives the value at ~3 px per unit.
 *   - Holding Shift reduces the multiplier to 0.25× (finer).
 *
 * Release:
 *   - pointerup → release capture, return to idle, commit final value.
 *
 * Keyboard:
 *   - Arrow keys ±1 (or ±step). Shift+arrow ±0.25.
 *
 * Touch:
 *   - Pointer events handle touch + mouse uniformly.
 *
 * Future consumers (sub-arc C-2 + Tier 3 in-place editor + theme
 * editor refinements) should treat this primitive as the canonical
 * way to author bounded integer values.
 */
import * as React from "react"

import { cn } from "@/lib/utils"

export interface ScrubbableButtonProps {
  /** Current value (controlled). */
  value: number
  /** Inclusive lower bound. */
  min: number
  /** Inclusive upper bound. */
  max: number
  /** Increment per scrub-unit / keyboard tap. Default 1. */
  step?: number
  /**
   * Pixels of horizontal pointer movement that map to one unit of
   * value change at the base multiplier. Default 3. Higher numbers
   * → slower / more precise. The default is tuned so a full 100-unit
   * sweep takes ~300px of pointer travel.
   */
  scrubMultiplier?: number
  /** Visible label. */
  label: string
  /** Optional unit appended after the value, e.g. "%". */
  unit?: string
  /** Called on every scrub update + every keyboard arrow + on commit. */
  onChange: (value: number) => void
  /** Whether to disable the control. */
  disabled?: boolean
  /** Optional className for outer styling. */
  className?: string
}

const clamp = (n: number, lo: number, hi: number) =>
  Math.max(lo, Math.min(hi, n))

export function ScrubbableButton({
  value,
  min,
  max,
  step = 1,
  scrubMultiplier = 3,
  label,
  unit,
  onChange,
  disabled = false,
  className,
}: ScrubbableButtonProps) {
  const [isScrubbing, setIsScrubbing] = React.useState(false)
  const scrubState = React.useRef<{
    startX: number
    startValue: number
    shiftHeld: boolean
  } | null>(null)

  const handlePointerDown = React.useCallback(
    (e: React.PointerEvent<HTMLButtonElement>) => {
      if (disabled) return
      // Only primary button — ignore middle/right.
      if (e.button !== 0) return
      e.preventDefault()
      e.currentTarget.setPointerCapture(e.pointerId)
      scrubState.current = {
        startX: e.clientX,
        startValue: value,
        shiftHeld: e.shiftKey,
      }
      setIsScrubbing(true)
    },
    [disabled, value],
  )

  const handlePointerMove = React.useCallback(
    (e: React.PointerEvent<HTMLButtonElement>) => {
      const s = scrubState.current
      if (!s) return
      const deltaX = e.clientX - s.startX
      // `scrubMultiplier` is pixels-per-unit. Larger == slower / finer.
      // Shift held → 4× the multiplier (i.e. value moves at 0.25× the
      // base rate per pixel). Per locked decision: "Shift held → 0.25×
      // scrub multiplier (finer)" — semantics: 0.25× as much value
      // change per pixel.
      const mult = (e.shiftKey ? 4 : 1) * scrubMultiplier
      const rawDelta = deltaX / mult
      // Snap to step grid.
      const stepped = Math.round(rawDelta / step) * step
      const next = clamp(s.startValue + stepped, min, max)
      if (next !== value) {
        onChange(next)
      }
    },
    [scrubMultiplier, step, value, min, max, onChange],
  )

  const endScrub = React.useCallback(
    (e: React.PointerEvent<HTMLButtonElement>) => {
      if (scrubState.current === null) return
      try {
        e.currentTarget.releasePointerCapture(e.pointerId)
      } catch {
        // Already released — ignore.
      }
      scrubState.current = null
      setIsScrubbing(false)
    },
    [],
  )

  const handleKeyDown = React.useCallback(
    (e: React.KeyboardEvent<HTMLButtonElement>) => {
      if (disabled) return
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return
      e.preventDefault()
      const direction = e.key === "ArrowRight" ? 1 : -1
      const magnitude = e.shiftKey ? 0.25 * step : step
      const delta = direction * magnitude
      const next = clamp(value + delta, min, max)
      const snapped = Math.round(next / step) * step
      const final = clamp(snapped, min, max)
      if (final !== value) onChange(final)
    },
    [disabled, value, min, max, step, onChange],
  )

  const display = `${value}${unit ?? ""}`

  return (
    <button
      type="button"
      aria-label={`${label}: ${display}`}
      aria-valuenow={value}
      aria-valuemin={min}
      aria-valuemax={max}
      role="slider"
      disabled={disabled}
      data-scrubbing={isScrubbing || undefined}
      data-testid="scrubbable-button"
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={endScrub}
      onPointerCancel={endScrub}
      onKeyDown={handleKeyDown}
      onLostPointerCapture={() => {
        scrubState.current = null
        setIsScrubbing(false)
      }}
      className={cn(
        // Idle button styling — flat, restrained, IBM Plex.
        "flex w-full items-center justify-between gap-3 rounded-md border px-3 py-1.5",
        "select-none text-left",
        "border-[color:var(--border-subtle)] bg-[color:var(--surface-elevated)]",
        "text-[color:var(--content-base)]",
        "transition-[border-color,box-shadow] duration-150 ease-out",
        // Hover: subtle elevation hint via border-base.
        "hover:border-[color:var(--border-base)]",
        // Focus-visible: brass accent ring (DESIGN_LANGUAGE §6 focus canon).
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--accent-brass,#9C5640)]/40 focus-visible:border-[color:var(--accent-brass,#9C5640)]",
        // Active scrub: brass border, no hover transition shimmer.
        "data-[scrubbing]:border-[color:var(--accent-brass,#9C5640)] data-[scrubbing]:shadow-[0_0_0_1px_color-mix(in_oklch,_var(--accent-brass,#9C5640)_30%,_transparent)]",
        // Cursor: scrub-resize idle, grabbing during scrub.
        disabled
          ? "cursor-not-allowed opacity-50"
          : isScrubbing
            ? "cursor-grabbing"
            : "cursor-ew-resize",
        className,
      )}
    >
      <span
        className="pointer-events-none text-[11px] font-medium tracking-wide uppercase text-[color:var(--content-muted)]"
        style={{ fontFamily: "var(--font-plex-sans, ui-sans-serif)" }}
      >
        {label}
      </span>
      <span
        className="pointer-events-none text-[12px] tabular-nums text-[color:var(--content-base)]"
        style={{ fontFamily: "var(--font-plex-mono, ui-monospace)" }}
      >
        {display}
      </span>
    </button>
  )
}

export default ScrubbableButton
