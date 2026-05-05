/**
 * CanonicalOptionsPalette — canonical 4-options vocabulary palette per
 * Phase 1B Burial Vault Personalization Studio + DESIGN_LANGUAGE
 * §14.14.2 canonical canvas + palette visual canon.
 *
 * **Canonical 4-options vocabulary post-r74** per §3.26.11.12.19.2:
 *   - `legacy_print` — printed paper artifact insert
 *   - `physical_nameplate` — engraved metal nameplate
 *   - `physical_emblem` — physical emblem affixed to vault cover
 *   - `vinyl` — vinyl-applied personalization (Wilbert tenant displays
 *     "Life's Reflections" via per-tenant Workshop Tune mode)
 *
 * **Canonical visual canon per §14.14.2 palette chrome composition**:
 * - Selection surface: `bg-surface-raised` panel with categorized
 *   component selection
 * - Per-category section: `text-caption font-medium text-content-muted
 *   uppercase tracking-wider` section headers
 * - Per-component item: `text-body-sm font-plex-sans text-content-strong`
 *   with selection state radio/checkbox + per-item icon
 * - Selected component: `bg-accent-subtle/30` background highlight
 *   per §6 selection canonical chrome
 *
 * **Per-tenant display label customization**: tenant-display-label
 * customization stored at `Company.settings_json.personalization_display_labels`
 * per §3.26.11.12.19.2 + r74 migration. This component accepts an
 * optional `displayLabels` prop to surface canonical per-tenant labels
 * (e.g., Wilbert tenant displays "Life's Reflections" for canonical
 * `vinyl` substrate value).
 */

import { Check, Circle } from "lucide-react"

import { cn } from "@/lib/utils"
import type { CanonicalOptionType } from "@/types/personalization-studio"
import {
  CANONICAL_OPTION_TYPES,
  DEFAULT_DISPLAY_LABELS,
} from "@/types/personalization-studio"

import { usePersonalizationCanvasState } from "./canvas-state-context"
import { usePersonalizationStudioTenantConfig } from "./tenant-config-context"

interface CanonicalOptionsPaletteProps {
  /** Per-tenant display labels override (Workshop Tune mode customization).
   *  When undefined, canonical context-resolved labels apply per
   *  Phase 1G runtime wiring. Canonical prop preserved for canonical
   *  Storybook / test scope canonical-bypass per Phase 1B canonical-
   *  pattern-establisher discipline. */
  displayLabels?: Partial<Record<CanonicalOptionType, string>>
  /** Canonical read-only mode for `manufacturer_from_fh_share` per §14.14.5. */
  readOnly?: boolean
}

export function CanonicalOptionsPalette({
  displayLabels,
  readOnly = false,
}: CanonicalOptionsPaletteProps) {
  const { canvasState, setCanvasState } = usePersonalizationCanvasState()

  // Phase 1G — canonical chrome-canvas runtime wiring. Context-resolved
  // per-tenant display labels canonical-flow from canonical
  // PersonalizationStudioTenantConfigProvider when canonical provider is
  // present. Canonical prop override canonical-wins for canonical
  // Storybook / test scope canonical-bypass.
  const tenantConfig = usePersonalizationStudioTenantConfig()
  const contextDisplayLabels = tenantConfig?.config?.display_labels

  const resolveLabel = (option: CanonicalOptionType): string =>
    displayLabels?.[option] ??
    contextDisplayLabels?.[option] ??
    DEFAULT_DISPLAY_LABELS[option]

  const isOptionActive = (option: CanonicalOptionType): boolean =>
    canvasState.options[option] !== null

  const toggleOption = (option: CanonicalOptionType) => {
    if (readOnly) return
    setCanvasState({
      ...canvasState,
      options: {
        ...canvasState.options,
        [option]: isOptionActive(option) ? null : optionDefaultPayload(option),
      },
    })
  }

  return (
    <div
      data-slot="canonical-options-palette"
      className={cn(
        // Canonical palette chrome per §14.14.2.
        "flex flex-col gap-3 rounded-md border border-border-subtle bg-surface-raised p-4",
      )}
    >
      <div
        data-slot="canonical-options-palette-header"
        className="text-caption font-medium uppercase tracking-wider text-content-muted"
      >
        Personalization options
      </div>

      <div data-slot="canonical-options-palette-items" className="flex flex-col gap-1">
        {CANONICAL_OPTION_TYPES.map((option) => {
          const active = isOptionActive(option)
          return (
            <button
              key={option}
              type="button"
              data-slot="canonical-option-item"
              data-option-type={option}
              data-active={active ? "true" : "false"}
              onClick={() => toggleOption(option)}
              disabled={readOnly}
              className={cn(
                // Canonical per-component item chrome per §14.14.2.
                "flex items-center gap-3 rounded-sm px-3 py-2 text-left transition-colors",
                "text-body-sm font-plex-sans text-content-strong",
                // Canonical selection state per §6 selection canonical
                // chrome: `bg-accent-subtle/30` background highlight
                // when selected.
                active
                  ? "bg-accent-subtle/30 border border-accent"
                  : "border border-transparent hover:bg-surface-elevated",
                readOnly && "cursor-not-allowed opacity-60",
              )}
            >
              <div
                data-slot="canonical-option-checkbox"
                className={cn(
                  "flex h-4 w-4 items-center justify-center rounded-sm border",
                  active
                    ? "border-accent bg-accent text-content-on-accent"
                    : "border-border-base bg-surface-base text-content-muted",
                )}
              >
                {active ? <Check className="h-3 w-3" /> : <Circle className="h-2 w-2" />}
              </div>
              <span>{resolveLabel(option)}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

/** Canonical default payload per option type — populates canonical
 *  option-type-specific fields when option is canonically activated.
 *  Empty payload (`{}`) when option type has no canonical fields beyond
 *  presence (canonical post-r74 vocabulary discipline). */
function optionDefaultPayload(option: CanonicalOptionType): Record<string, unknown> {
  switch (option) {
    case "legacy_print":
      return { print_name: "" }
    case "vinyl":
      return { symbol: "" }
    case "physical_nameplate":
    case "physical_emblem":
      return {}
  }
}
