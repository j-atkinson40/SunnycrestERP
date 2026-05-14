/**
 * ChromePresetPicker — visual-authoring primitive (sub-arc C-1).
 *
 * Horizontal row of pill buttons; the active preset shows brass
 * fill. Matches the chrome v2 vocabulary (sub-arc B-3.5 + C-1
 * substrate extension): card / modal / dropdown / toast / floating
 * / frosted / custom.
 *
 * "Custom" means "no preset; explicit overrides only" (handled by
 * the resolver). Selection emits the preset slug (or null when no
 * value is set).
 */
import { cn } from "@/lib/utils"

export type PresetSlug =
  | "card"
  | "modal"
  | "dropdown"
  | "toast"
  | "floating"
  | "frosted"
  | "custom"

const PRESETS: { slug: PresetSlug; label: string }[] = [
  { slug: "card", label: "Card" },
  { slug: "modal", label: "Modal" },
  { slug: "dropdown", label: "Dropdown" },
  { slug: "toast", label: "Toast" },
  { slug: "floating", label: "Floating" },
  { slug: "frosted", label: "Frosted" },
  { slug: "custom", label: "Custom" },
]

export interface ChromePresetPickerProps {
  value: PresetSlug | null
  onChange: (preset: PresetSlug | null) => void
  className?: string
}

export function ChromePresetPicker({
  value,
  onChange,
  className,
}: ChromePresetPickerProps) {
  return (
    <div
      role="group"
      aria-label="Chrome preset"
      data-testid="chrome-preset-picker"
      className={cn(
        "flex flex-wrap items-center gap-1",
        className,
      )}
    >
      {PRESETS.map((p) => {
        const active = value === p.slug
        return (
          <button
            key={p.slug}
            type="button"
            data-testid={`preset-pill-${p.slug}`}
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

export default ChromePresetPicker
