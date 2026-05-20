/**
 * PositionInspectorSection — sub-arc FF-6.
 *
 * Inspector-side surface for free-form widget positioning. Mounts
 * inside `WidgetInspectorSection` as a peer of the existing
 * Configuration / Placement / Chrome / Layer sections.
 *
 * Renders a 2x2 grid of numeric inputs (X / Y / Width / Height) that
 * commit to the placement via `onUpdate(field, clampedValue)` on
 * blur or Enter (NOT on each keystroke — avoids save-pulse storms
 * during typing).
 *
 * Per the FF-6 prompt:
 *   - Uncontrolled-with-sync pattern: each PositionInput holds local
 *     string state for the in-progress edit; commits on blur/Enter;
 *     syncs from `placementValue` when the input is NOT focused
 *     (allowing canvas drag/resize to update the displayed value,
 *     but NOT interrupting the operator's mid-edit).
 *   - Silent revert on invalid input (Figma/Sketch precedent — NaN
 *     resets the display to the current placement value; no toast).
 *   - Clamping done at the input layer via the closures supplied by
 *     this section (canvas + min + sibling-field-aware). Reuses the
 *     same canvas-bounds + min-dimension math FF-2 / FF-4 use at
 *     commit time, inlined here per rule-of-three — extracting a
 *     shared clamp helper waits for a 3rd consumer.
 *
 * Disabled state: when no placement is selected (`placement === null`)
 * OR the subject is the inherited core (`isCore === true`). Mirrors
 * FF-5's LayerInspectorSection disabled-state semantics.
 */
import * as React from "react"

import { PropertySection } from "@/bridgeable-admin/components/visual-authoring"
import type { WidgetPlacement } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"

export type PositionField = "x" | "y" | "width" | "height"

export interface PositionInspectorSectionProps {
  /** Currently selected placement; null when no widget selected. */
  placement: WidgetPlacement | null
  /** When true the subject is the inherited core and inputs are disabled. */
  isCore?: boolean
  /** Canvas dimensions in pixels (1200×800 platform fallback). */
  canvasDimensions: { width: number; height: number }
  /** Resolved per-widget minimum dimensions (80×40 platform fallback). */
  minDimensions: { width: number; height: number }
  /** Commit a clamped value for a positioning field. */
  onUpdate: (field: PositionField, value: number) => void
}

/**
 * Per-field clamp. Closures over the same canvas + min + sibling
 * geometry that FF-2's drop + FF-4's resize use at commit time.
 *
 * Semantics (mirrors Q-13 / Q-14 + FF-4 precedent):
 *   - X:      [0, canvas.width - placement.width]
 *   - Y:      [0, canvas.height - placement.height]
 *   - Width:  [min.width,  canvas.width  - placement.x]
 *   - Height: [min.height, canvas.height - placement.y]
 */
function clampFor(
  field: PositionField,
  placement: WidgetPlacement,
  canvas: { width: number; height: number },
  min: { width: number; height: number },
): (value: number) => number {
  const px = typeof placement.x === "number" ? placement.x : 0
  const py = typeof placement.y === "number" ? placement.y : 0
  const pw =
    typeof placement.width === "number" && placement.width > 0
      ? placement.width
      : min.width
  const ph =
    typeof placement.height === "number" && placement.height > 0
      ? placement.height
      : min.height

  switch (field) {
    case "x": {
      const max = Math.max(0, canvas.width - pw)
      return (v) => Math.max(0, Math.min(max, Math.round(v)))
    }
    case "y": {
      const max = Math.max(0, canvas.height - ph)
      return (v) => Math.max(0, Math.min(max, Math.round(v)))
    }
    case "width": {
      const max = Math.max(min.width, canvas.width - px)
      return (v) => Math.max(min.width, Math.min(max, Math.round(v)))
    }
    case "height": {
      const max = Math.max(min.height, canvas.height - py)
      return (v) => Math.max(min.height, Math.min(max, Math.round(v)))
    }
  }
}

interface FieldSpec {
  field: PositionField
  label: string
}

const FIELDS: FieldSpec[] = [
  { field: "x", label: "X" },
  { field: "y", label: "Y" },
  { field: "width", label: "Width" },
  { field: "height", label: "Height" },
]

export function PositionInspectorSection(props: PositionInspectorSectionProps) {
  const {
    placement,
    isCore = false,
    canvasDimensions,
    minDimensions,
    onUpdate,
  } = props
  const disabled = placement === null || isCore

  // Defensive placement reference for clamp + display. When null we
  // still render the four inputs (disabled) so the section's layout
  // is stable across selection changes.
  const safePlacement: WidgetPlacement | null = placement

  return (
    <PropertySection title="Position" defaultExpanded>
      <div
        data-testid="position-inspector-section"
        className="grid grid-cols-2 gap-1.5 px-1"
      >
        {FIELDS.map(({ field, label }) => {
          const placementValue = safePlacement
            ? readField(safePlacement, field, minDimensions)
            : 0
          const clamp = safePlacement
            ? clampFor(field, safePlacement, canvasDimensions, minDimensions)
            : (v: number) => v
          return (
            <PositionInput
              key={field}
              label={label}
              field={field}
              placementValue={placementValue}
              clamp={clamp}
              onCommit={(v) => onUpdate(field, v)}
              disabled={disabled}
            />
          )
        })}
      </div>
    </PropertySection>
  )
}

function readField(
  p: WidgetPlacement,
  field: PositionField,
  min: { width: number; height: number },
): number {
  switch (field) {
    case "x":
      return typeof p.x === "number" ? p.x : 0
    case "y":
      return typeof p.y === "number" ? p.y : 0
    case "width":
      return typeof p.width === "number" && p.width > 0 ? p.width : min.width
    case "height":
      return typeof p.height === "number" && p.height > 0
        ? p.height
        : min.height
  }
}

// ── PositionInput — inline sub-component ──────────────────────────
//
// Per FF-6 build report item 9: PositionInput is inlined within
// PositionInspectorSection (file remains under ~200 LOC; extraction
// adds an indirection without code-clarity benefit at this scale).

interface PositionInputProps {
  label: string
  field: PositionField
  /** Authoritative value from the placement (the "source"). */
  placementValue: number
  /** Per-field clamp applied at commit time. */
  clamp: (value: number) => number
  /** Commit clamped value (no-op fallback when disabled). */
  onCommit: (clampedValue: number) => void
  disabled?: boolean
}

export function PositionInput(props: PositionInputProps) {
  const { label, field, placementValue, clamp, onCommit, disabled } = props
  const inputRef = React.useRef<HTMLInputElement>(null)
  const [localValue, setLocalValue] = React.useState<string>(() =>
    placementValue.toString(),
  )

  // Sync from placementValue when input is NOT focused. This is the
  // load-bearing UX correctness contract: canvas drag/resize updates
  // placementValue → input reflects the new value, BUT only if the
  // operator isn't mid-edit. When the input has focus, the operator's
  // local string state dominates; placement updates do not stomp.
  React.useEffect(() => {
    if (typeof document === "undefined") {
      setLocalValue(placementValue.toString())
      return
    }
    if (document.activeElement === inputRef.current) {
      return // Operator is editing — don't overwrite.
    }
    setLocalValue(placementValue.toString())
  }, [placementValue])

  const commit = React.useCallback(() => {
    const parsed = parseInt(localValue, 10)
    if (Number.isNaN(parsed)) {
      // Silent revert on invalid input (Figma/Sketch precedent).
      setLocalValue(placementValue.toString())
      return
    }
    const clamped = clamp(parsed)
    if (clamped !== placementValue) {
      onCommit(clamped)
    }
    // Reset display to the clamped value (the source-of-truth shape
    // post-commit). The placement update flowing back through the
    // sync effect will set this anyway, but doing it here makes the
    // display consistent even when clamped===placementValue (no PUT).
    setLocalValue(clamped.toString())
  }, [localValue, placementValue, clamp, onCommit])

  return (
    <label
      className={[
        "flex items-center gap-1.5 rounded-sm px-2 py-1.5",
        "border border-[color:var(--border-subtle)]",
        "bg-[color:var(--surface-elevated)]",
        disabled
          ? "cursor-not-allowed opacity-50"
          : "focus-within:border-[color:var(--accent)]",
      ].join(" ")}
      style={{ fontFamily: "var(--font-plex-sans)" }}
    >
      <span
        className="shrink-0 text-[10px] font-medium uppercase tracking-[0.06em] text-[color:var(--content-muted)]"
        aria-hidden
      >
        {label}
      </span>
      <input
        ref={inputRef}
        type="number"
        inputMode="numeric"
        data-testid={`position-input-${field}`}
        aria-label={`${label} position`}
        value={localValue}
        disabled={disabled}
        onChange={(e) => setLocalValue(e.target.value)}
        onBlur={() => commit()}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault()
            inputRef.current?.blur()
          }
        }}
        className={[
          "min-w-0 flex-1 bg-transparent text-right text-[12px] outline-none",
          "text-[color:var(--content-base)]",
          // Hide spinner buttons for a cleaner look (Sketch/Figma do
          // not show native browser steppers either).
          "[appearance:textfield] [&::-webkit-inner-spin-button]:hidden [&::-webkit-outer-spin-button]:m-0",
        ].join(" ")}
      />
    </label>
  )
}

export default PositionInspectorSection
