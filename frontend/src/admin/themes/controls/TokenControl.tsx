/**
 * TokenControl — dispatcher that picks the right editor primitive
 * for a given catalog entry's `valueType`.
 */

import type { TokenEntry } from "../token-catalog"
import { OklchPicker } from "./OklchPicker"
import { NumericEditor } from "./NumericEditor"
import { EnumEditor, EASING_OPTIONS, FONT_FAMILY_OPTIONS } from "./EnumEditor"
import { ShadowDisplay } from "./ShadowDisplay"


export interface TokenControlProps {
  token: TokenEntry
  value: string
  onChange: (next: string) => void
  "data-testid"?: string
}


function boundsTuple(b: unknown, fallback: [number, number]): [number, number] {
  if (Array.isArray(b) && b.length === 2 && typeof b[0] === "number" && typeof b[1] === "number") {
    return [b[0], b[1]]
  }
  return fallback
}


export function TokenControl({
  token,
  value,
  onChange,
  "data-testid": testid = "token-control",
}: TokenControlProps) {
  const editable = token.editable ?? true
  const tid = `${testid}-${token.name}`

  if (token.valueType === "oklch" || token.valueType === "oklch-with-alpha") {
    return (
      <OklchPicker
        value={value}
        onChange={onChange}
        allowAlpha={token.valueType === "oklch-with-alpha"}
        readOnly={!editable}
        data-testid={tid}
      />
    )
  }

  if (token.valueType === "rgba") {
    // RGBA tokens — operators rarely edit these (they're alpha
    // alternates of the canonical accent). Phase 2 displays the
    // value read-only with a swatch.
    return (
      <div
        className="flex items-center gap-2 rounded-md border border-border-subtle bg-surface-sunken p-2"
        data-testid={tid}
      >
        <div
          className="h-9 w-9 rounded-sm border border-border-base"
          style={{ background: value }}
        />
        <code
          className="flex-1 truncate font-plex-mono text-caption text-content-base"
          data-testid={`${tid}-canonical`}
        >
          {value}
        </code>
      </div>
    )
  }

  if (token.valueType === "rem") {
    const [min, max] = boundsTuple(token.bounds, [0.5, 6])
    return (
      <NumericEditor
        value={value}
        unit="rem"
        min={min}
        max={max}
        step={0.01}
        onChange={onChange}
        disabled={!editable}
        data-testid={tid}
      />
    )
  }

  if (token.valueType === "px") {
    const [min, max] = boundsTuple(token.bounds, [0, 32])
    return (
      <NumericEditor
        value={value}
        unit="px"
        min={min}
        max={max}
        step={1}
        onChange={onChange}
        disabled={!editable}
        data-testid={tid}
      />
    )
  }

  if (token.valueType === "ms") {
    const [min, max] = boundsTuple(token.bounds, [0, 2000])
    return (
      <NumericEditor
        value={value}
        unit="ms"
        min={min}
        max={max}
        step={10}
        onChange={onChange}
        disabled={!editable}
        data-testid={tid}
      />
    )
  }

  if (token.valueType === "alpha") {
    return (
      <NumericEditor
        value={value}
        unit=""
        min={0}
        max={1}
        step={0.01}
        onChange={onChange}
        disabled={!editable}
        data-testid={tid}
      />
    )
  }

  if (token.valueType === "integer") {
    const [min, max] = boundsTuple(token.bounds, [0, 200])
    return (
      <NumericEditor
        value={value}
        unit="integer"
        min={min}
        max={max}
        step={1}
        onChange={onChange}
        disabled={!editable}
        data-testid={tid}
      />
    )
  }

  if (token.valueType === "cubic-bezier") {
    return (
      <EnumEditor
        value={value}
        options={EASING_OPTIONS}
        onChange={onChange}
        disabled={!editable}
        data-testid={tid}
      />
    )
  }

  if (token.valueType === "font-family") {
    return (
      <EnumEditor
        value={value}
        options={FONT_FAMILY_OPTIONS}
        onChange={onChange}
        disabled={!editable}
        data-testid={tid}
      />
    )
  }

  if (token.valueType === "shadow-composition") {
    return (
      <ShadowDisplay
        value={value}
        derivedFrom={token.derivedFrom}
        data-testid={tid}
      />
    )
  }

  if (token.valueType === "transform") {
    // Transform tokens are minor — read-only with raw text.
    return (
      <div
        className="rounded-md border border-border-subtle bg-surface-sunken p-2"
        data-testid={tid}
      >
        <code className="font-plex-mono text-caption text-content-base">
          {value}
        </code>
      </div>
    )
  }

  // Fallback — display the raw value.
  return (
    <div
      className="rounded-md border border-border-subtle bg-surface-sunken p-2"
      data-testid={tid}
    >
      <code className="font-plex-mono text-caption text-content-base">
        {value}
      </code>
    </div>
  )
}
