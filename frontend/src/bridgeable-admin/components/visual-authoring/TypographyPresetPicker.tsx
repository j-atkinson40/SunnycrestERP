/**
 * TypographyPresetPicker — visual-authoring primitive (sub-arc C-2.2b).
 *
 * Horizontal row of pill buttons; the active preset shows accent
 * fill. Matches the typography v1 vocabulary (sub-arc B-5):
 * card-text / frosted-text / headline / custom.
 *
 * "Custom" means "no preset; explicit overrides only" (handled by
 * the resolver). Selection emits the preset slug (or null when no
 * value is set).
 *
 * Mirror of ChromePresetPicker / SubstratePresetPicker — same visual
 * treatment, different slug vocabulary.
 */
import { cn } from "@/lib/utils"

export type TypographyPresetSlug =
  | "card-text"
  | "frosted-text"
  | "headline"
  | "custom"

const PRESETS: { slug: TypographyPresetSlug; label: string }[] = [
  { slug: "card-text", label: "Card" },
  { slug: "frosted-text", label: "Frosted" },
  { slug: "headline", label: "Headline" },
  { slug: "custom", label: "Custom" },
]

export interface TypographyPresetPickerProps {
  value: TypographyPresetSlug | null
  onChange: (preset: TypographyPresetSlug | null) => void
  className?: string
}

export function TypographyPresetPicker({
  value,
  onChange,
  className,
}: TypographyPresetPickerProps) {
  return (
    <div
      role="group"
      aria-label="Typography preset"
      data-testid="typography-preset-picker"
      className={cn("flex flex-wrap items-center gap-1", className)}
    >
      {PRESETS.map((p) => {
        const active = value === p.slug
        return (
          <button
            key={p.slug}
            type="button"
            data-testid={`typography-pill-${p.slug}`}
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

export default TypographyPresetPicker
