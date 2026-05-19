/**
 * FocusBuilderThemePicker — sub-arc F-4.
 *
 * Right-rail bottom section. Fast-path preset picking for substrate +
 * typography. Coexists with F-2 inspector's substrate/typography
 * sections (fine-grained editing path) — both write through the same
 * `updateSubstrate` / `updateTypography` hook methods, single source
 * of truth, single backend persistence path, single canvas
 * re-render.
 *
 * Direct reuse of C-1 SubstratePresetPicker + TypographyPresetPicker
 * primitives — they are already chip-strip shape with selected-state
 * indicator. F-4 wraps them in a labeled section + handles the
 * core-disabled state.
 *
 * Click chip → immediate save via existing debounced save path in
 * useFocusTemplateDraft (the hook's queueSave fires on every
 * updateSubstrate / updateTypography call). No staged "apply" button.
 */
import * as React from "react"

import {
  SubstratePresetPicker,
  TypographyPresetPicker,
  type SubstratePresetSlug,
  type TypographyPresetSlug,
} from "@/bridgeable-admin/components/visual-authoring"
import {
  expandSubstratePreset,
  substrateViewFromBlob,
  type SubstratePreset,
} from "@/bridgeable-admin/lib/visual-editor/substrate-resolver"
import {
  expandTypographyPreset,
  typographyViewFromBlob,
  type TypographyPreset,
} from "@/bridgeable-admin/lib/visual-editor/typography-resolver"
import type { UseFocusTemplateDraftResult } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"

export interface FocusBuilderThemePickerProps {
  /**
   * Mirrors FocusBuilderRightRail's `mode` discriminator.
   * - "template" — picker is active.
   * - "core"     — picker shows the disabled hint ("Themes apply to
   *                templates, not cores"), matching the F-3 widget
   *                palette disabled-on-core pattern.
   * - "empty"    — no subject loaded; renders the disabled hint as well.
   */
  mode: "core" | "template" | "empty"
  /** Hook result; required for template mode. */
  templateHook?: UseFocusTemplateDraftResult | null
}

export function FocusBuilderThemePicker(props: FocusBuilderThemePickerProps) {
  const { mode, templateHook } = props

  // Disabled state — cores have no substrate/typography vocabulary.
  if (mode !== "template" || !templateHook) {
    const hint =
      mode === "core"
        ? "Themes apply to templates, not cores"
        : "Load a template to edit theme"
    return (
      <div
        data-testid="focus-builder-theme-picker-disabled"
        className="flex flex-col gap-1 px-4 py-3 text-[12px]"
      >
        <span
          className="text-[10px] font-semibold uppercase tracking-[0.08em] text-[color:var(--content-muted)]"
          style={{ fontFamily: "var(--font-plex-sans)" }}
        >
          Theme
        </span>
        <span
          className="text-[color:var(--content-muted)] opacity-60"
          style={{ fontFamily: "var(--font-plex-mono)" }}
          data-testid="focus-builder-theme-picker-disabled-hint"
        >
          {hint}
        </span>
      </div>
    )
  }

  const substrateView = React.useMemo(
    () => expandSubstratePreset(substrateViewFromBlob(templateHook.substrateDraft)),
    [templateHook.substrateDraft],
  )
  const typographyView = React.useMemo(
    () => expandTypographyPreset(typographyViewFromBlob(templateHook.typographyDraft)),
    [templateHook.typographyDraft],
  )

  return (
    <div
      data-testid="focus-builder-theme-picker"
      className="flex flex-col gap-3 px-4 py-3"
    >
      <span
        className="text-[10px] font-semibold uppercase tracking-[0.08em] text-[color:var(--content-muted)]"
        style={{ fontFamily: "var(--font-plex-sans)" }}
      >
        Theme
      </span>

      <div
        className="flex flex-col gap-1.5"
        data-testid="focus-builder-theme-picker-substrate"
      >
        <span
          className="text-[10px] uppercase tracking-[0.08em] text-[color:var(--content-muted)] opacity-80"
          style={{ fontFamily: "var(--font-plex-sans)" }}
        >
          Substrate
        </span>
        <SubstratePresetPicker
          value={(substrateView.preset ?? null) as SubstratePresetSlug | null}
          onChange={(p) =>
            // F-4.1 — chip-click semantic = "apply preset wholesale".
            // Null out specific fields so the resolver's
            // expandSubstratePreset applies the preset's defaults
            // (specifics-win priority is correct for the F-2 inspector's
            // fine-grained scrubbing path; chip click is the
            // operator-intent override).
            templateHook.updateSubstrate({
              preset: p as SubstratePreset | null,
              intensity: null,
              base_token: null,
              accent_token_1: null,
              accent_token_2: null,
            })
          }
        />
      </div>

      <div
        className="flex flex-col gap-1.5"
        data-testid="focus-builder-theme-picker-typography"
      >
        <span
          className="text-[10px] uppercase tracking-[0.08em] text-[color:var(--content-muted)] opacity-80"
          style={{ fontFamily: "var(--font-plex-sans)" }}
        >
          Typography
        </span>
        <TypographyPresetPicker
          value={(typographyView.preset ?? null) as TypographyPresetSlug | null}
          onChange={(p) =>
            // F-4.1 — chip-click semantic = "apply preset wholesale".
            // Null out specific fields so the resolver's
            // expandTypographyPreset applies the preset's defaults
            // (resolver's specifics-win priority is correct for F-2
            // inspector scrubbing; chip click is the operator-intent
            // wholesale override).
            templateHook.updateTypography({
              preset: p as TypographyPreset | null,
              heading_weight: null,
              body_weight: null,
              heading_color_token: null,
              body_color_token: null,
            })
          }
        />
      </div>
    </div>
  )
}

export default FocusBuilderThemePicker
