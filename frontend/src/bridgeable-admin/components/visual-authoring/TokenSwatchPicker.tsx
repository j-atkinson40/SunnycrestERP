/**
 * TokenSwatchPicker — visual-authoring primitive (sub-arc C-1).
 *
 * Swatch + token-name display that opens an anchored popover with
 * the family's valid swatches. Adapted from Sketch's color-token
 * picker; rendered on the same warm-cream / warm-charcoal substrate
 * as the rest of the inspector.
 *
 * Three token families v1: `surface` (color), `border` (color),
 * `padding` (non-color — renders a box illustration showing the
 * spacing the token represents). A single component handles all
 * three via a `tokenFamily` discriminator, keeping coupling to
 * external consumers minimal.
 *
 * Storage shape: token NAME (e.g. "surface-elevated"), not resolved
 * color. The caller supplies a `themeTokens` map keyed on token
 * name so the swatch can preview the resolved value without the
 * component fetching the theme itself. This separation lets the
 * demo route's parent decide how to source tokens (live API,
 * fallback, frozen seed).
 *
 * Interaction:
 *   - Click trigger → popover open
 *   - Click swatch → close + emit new token name
 *   - Click outside → close without emitting
 *   - Escape → close without emitting
 *   - "None" option (when `allowNone` truthy) → emit null
 */
import * as React from "react"

import { cn } from "@/lib/utils"

export type TokenFamily = "surface" | "border" | "padding"

const TOKENS_BY_FAMILY: Record<TokenFamily, string[]> = {
  surface: [
    "surface-base",
    "surface-elevated",
    "surface-raised",
    "surface-sunken",
  ],
  border: [
    "border-subtle",
    "border-base",
    "border-strong",
    "border-brass",
  ],
  padding: [
    "space-2",
    "space-4",
    "space-6",
    "space-8",
  ],
}

/** Pixel sizes the `space-*` tokens resolve to. Mirrors tokens.css. */
const PADDING_PX: Record<string, number> = {
  "space-2": 8,
  "space-4": 16,
  "space-6": 24,
  "space-8": 32,
}

export interface TokenSwatchPickerProps {
  /** Token name (e.g. "surface-elevated") or null for "None". */
  value: string | null
  /** Which token family the picker selects from. */
  tokenFamily: TokenFamily
  /**
   * Map of token name → resolved color (or arbitrary string for
   * non-color families). Caller supplies this from the active
   * theme. Tokens missing from the map render as a neutral
   * placeholder.
   */
  themeTokens: Record<string, string>
  /** Called on user selection (or null when "None"). */
  onChange: (tokenName: string | null) => void
  /** Visible label rendered alongside the swatch. */
  label: string
  /** When true, include a "None" option. Default: true. */
  allowNone?: boolean
  /** Optional className for outer container. */
  className?: string
}

function PaddingPreview({ token }: { token: string }) {
  const px = PADDING_PX[token] ?? 8
  const dim = 24
  return (
    <div
      aria-hidden
      className="flex items-center justify-center rounded-sm border border-[color:var(--border-subtle)] bg-[color:var(--surface-sunken)]"
      style={{ width: dim, height: dim }}
    >
      <div
        className="rounded-[2px] bg-[color:var(--accent-brass,#9C5640)]/40"
        style={{
          width: Math.max(2, dim - px / 2),
          height: Math.max(2, dim - px / 2),
        }}
      />
    </div>
  )
}

function ColorPreview({ color }: { color: string | undefined }) {
  return (
    <div
      aria-hidden
      className="rounded-sm border border-[color:var(--border-subtle)]"
      style={{
        width: 24,
        height: 24,
        background: color ?? "transparent",
        backgroundImage: color
          ? undefined
          : "linear-gradient(45deg, var(--surface-sunken) 25%, transparent 25%, transparent 75%, var(--surface-sunken) 75%)",
        backgroundSize: "8px 8px",
      }}
    />
  )
}

function SwatchPreview({
  family,
  token,
  themeTokens,
}: {
  family: TokenFamily
  token: string | null
  themeTokens: Record<string, string>
}) {
  if (token === null) {
    return (
      <div
        aria-hidden
        className="flex items-center justify-center rounded-sm border border-dashed border-[color:var(--border-base)] text-[10px] text-[color:var(--content-muted)]"
        style={{ width: 24, height: 24, fontFamily: "var(--font-plex-mono)" }}
      >
        ∅
      </div>
    )
  }
  if (family === "padding") {
    return <PaddingPreview token={token} />
  }
  return <ColorPreview color={themeTokens[token]} />
}

export function TokenSwatchPicker({
  value,
  tokenFamily,
  themeTokens,
  onChange,
  label,
  allowNone = true,
  className,
}: TokenSwatchPickerProps) {
  const [open, setOpen] = React.useState(false)
  const rootRef = React.useRef<HTMLDivElement>(null)

  // Close on outside click + Escape.
  React.useEffect(() => {
    if (!open) return
    function onDocPointer(e: MouseEvent | TouchEvent) {
      const target = e.target as Node | null
      if (target && rootRef.current && !rootRef.current.contains(target)) {
        setOpen(false)
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onDocPointer)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onDocPointer)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  const tokens = TOKENS_BY_FAMILY[tokenFamily]

  return (
    <div ref={rootRef} className={cn("relative", className)}>
      <button
        type="button"
        data-testid="token-swatch-trigger"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex w-full items-center justify-between gap-3 rounded-md border px-3 py-1.5",
          "border-[color:var(--border-subtle)] bg-[color:var(--surface-elevated)]",
          "text-[color:var(--content-base)] hover:border-[color:var(--border-base)]",
          "transition-[border-color] duration-150 ease-out",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--accent-brass,#9C5640)]/40 focus-visible:border-[color:var(--accent-brass,#9C5640)]",
          open && "border-[color:var(--accent-brass,#9C5640)]",
        )}
      >
        <span className="flex items-center gap-2">
          <SwatchPreview
            family={tokenFamily}
            token={value}
            themeTokens={themeTokens}
          />
          <span
            className="text-[11px] font-medium tracking-wide uppercase text-[color:var(--content-muted)]"
            style={{ fontFamily: "var(--font-plex-sans, ui-sans-serif)" }}
          >
            {label}
          </span>
        </span>
        <span
          className="text-[11px] tabular-nums text-[color:var(--content-base)]"
          style={{ fontFamily: "var(--font-plex-mono, ui-monospace)" }}
        >
          {value ?? "None"}
        </span>
      </button>

      {open ? (
        <div
          data-testid="token-swatch-popover"
          role="dialog"
          aria-label={`${label} tokens`}
          className={cn(
            "absolute right-0 top-full z-50 mt-1 w-[260px]",
            "rounded-md border border-[color:var(--border-subtle)] bg-[color:var(--surface-raised)] p-3 shadow-[0_8px_24px_rgba(0,0,0,0.18)]",
          )}
        >
          <div className="grid grid-cols-2 gap-2">
            {allowNone && (
              <button
                type="button"
                data-testid="token-swatch-option-none"
                onClick={() => {
                  onChange(null)
                  setOpen(false)
                }}
                className={cn(
                  "flex items-center gap-2 rounded-sm border px-2 py-1.5 text-left",
                  "border-[color:var(--border-subtle)] hover:border-[color:var(--accent-brass,#9C5640)]",
                  value === null
                    ? "ring-1 ring-[color:var(--accent-brass,#9C5640)]"
                    : undefined,
                )}
              >
                <SwatchPreview
                  family={tokenFamily}
                  token={null}
                  themeTokens={themeTokens}
                />
                <span
                  className="text-[11px] text-[color:var(--content-base)]"
                  style={{ fontFamily: "var(--font-plex-mono)" }}
                >
                  None
                </span>
              </button>
            )}
            {tokens.map((tok) => (
              <button
                key={tok}
                type="button"
                data-testid={`token-swatch-option-${tok}`}
                title={tok}
                onClick={() => {
                  onChange(tok)
                  setOpen(false)
                }}
                className={cn(
                  "flex items-center gap-2 rounded-sm border px-2 py-1.5 text-left",
                  "border-[color:var(--border-subtle)] hover:border-[color:var(--accent-brass,#9C5640)]",
                  value === tok
                    ? "ring-1 ring-[color:var(--accent-brass,#9C5640)]"
                    : undefined,
                )}
              >
                <SwatchPreview
                  family={tokenFamily}
                  token={tok}
                  themeTokens={themeTokens}
                />
                <span
                  className="text-[10px] text-[color:var(--content-base)]"
                  style={{ fontFamily: "var(--font-plex-mono)" }}
                >
                  {tok}
                </span>
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}

export default TokenSwatchPicker
