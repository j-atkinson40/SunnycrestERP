/**
 * SubstratePresetPicker — visual-authoring primitive (sub-arc C-2.2b).
 *
 * Horizontal row of pill buttons; the active preset shows accent
 * fill. Matches the substrate v1 vocabulary (sub-arc B-4):
 * morning-warm / morning-cool / evening-lounge / neutral / custom.
 *
 * "Custom" means "no preset; explicit overrides only" (handled by
 * the resolver). Selection emits the preset slug (or null when no
 * value is set).
 *
 * Mirror of ChromePresetPicker — same visual treatment, different
 * slug vocabulary. Shipped in C-2.2b alongside TypographyPresetPicker
 * to enable the three-section Tier 2 editor inspector.
 */
import { cn } from "@/lib/utils"

export type SubstratePresetSlug =
  | "morning-warm"
  | "morning-cool"
  | "evening-lounge"
  | "neutral"
  | "custom"

const PRESETS: { slug: SubstratePresetSlug; label: string }[] = [
  { slug: "morning-warm", label: "Morning warm" },
  { slug: "morning-cool", label: "Morning cool" },
  { slug: "evening-lounge", label: "Evening" },
  { slug: "neutral", label: "Neutral" },
  { slug: "custom", label: "Custom" },
]

export interface SubstratePresetPickerProps {
  value: SubstratePresetSlug | null
  onChange: (preset: SubstratePresetSlug | null) => void
  className?: string
}

export function SubstratePresetPicker({
  value,
  onChange,
  className,
}: SubstratePresetPickerProps) {
  return (
    <div
      role="group"
      aria-label="Substrate preset"
      data-testid="substrate-preset-picker"
      className={cn("flex flex-wrap items-center gap-1", className)}
    >
      {PRESETS.map((p) => {
        const active = value === p.slug
        return (
          <button
            key={p.slug}
            type="button"
            data-testid={`substrate-pill-${p.slug}`}
            data-active={active || undefined}
            aria-pressed={active}
            onClick={() => onChange(active ? null : p.slug)}
            className={cn(
              "rounded-full border px-3 py-1 text-[11px] tracking-wide",
              "transition-[background-color,border-color,color] duration-150 ease-out",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--accent-brass,#9C5640)]/40",
              active
                ? "border-[color:var(--accent-brass,#9C5640)] bg-[color:var(--accent-brass,#9C5640)] text-[color:var(--content-on-brass,#ffffff)]"
                : "border-[color:var(--border-subtle)] bg-[color:var(--surface-elevated)] text-[color:var(--content-base)] hover:border-[color:var(--border-base)]",
            )}
            style={{ fontFamily: "var(--font-plex-sans, ui-sans-serif)" }}
          >
            {p.label}
          </button>
        )
      })}
    </div>
  )
}

export default SubstratePresetPicker
