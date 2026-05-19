/**
 * FocusBuilderRightRail — sub-arcs F-2 → F-4.
 *
 * Three stacked sections:
 *   1. Inspector (top) — FocusBuilderInspector (selection-driven, F-2).
 *   2. Widget palette  — FocusBuilderPalette (F-3).
 *   3. Theme picker    — FocusBuilderThemePicker (F-4, fast-path
 *                        substrate + typography preset selection).
 *
 * F-2 inspector's substrate + typography sections coexist with the
 * F-4 theme picker — both write through the same hook methods. The
 * inspector is the fine-grained path (preset + intensity scrubber +
 * token swatches); the theme picker is the fast-path preset chip
 * strip.
 */
import { FocusBuilderInspector, type FocusBuilderInspectorProps } from "./FocusBuilderInspector"
import { FocusBuilderPalette } from "./FocusBuilderPalette"
import { FocusBuilderThemePicker } from "./FocusBuilderThemePicker"

export type FocusBuilderRightRailProps = FocusBuilderInspectorProps

export function FocusBuilderRightRail(props: FocusBuilderRightRailProps) {
  const paletteDisabled = props.mode !== "template"
  return (
    <div
      data-testid="focus-builder-right-rail"
      className="flex h-full flex-col"
    >
      <section
        data-testid="focus-builder-inspector-region"
        className="flex min-h-0 flex-[2] flex-col overflow-y-auto border-b border-[color:var(--border-subtle)]"
      >
        <FocusBuilderInspector {...props} />
      </section>

      <section
        data-testid="focus-builder-widget-palette-region"
        className="flex max-h-[40%] flex-col overflow-y-auto border-b border-[color:var(--border-subtle)] py-2"
      >
        <div className="flex items-center justify-between px-4 pb-1">
          <span
            className="text-[10px] font-semibold uppercase tracking-[0.08em] text-[color:var(--content-muted)]"
            style={{ fontFamily: "var(--font-plex-sans)" }}
          >
            Widget palette
          </span>
          {paletteDisabled && (
            <span
              className="text-[10px] text-[color:var(--content-muted)]"
              style={{ fontFamily: "var(--font-plex-mono)" }}
              data-testid="focus-builder-palette-disabled-hint"
            >
              cores have no widgets
            </span>
          )}
        </div>
        <FocusBuilderPalette disabled={paletteDisabled} />
      </section>

      <section
        data-testid="focus-builder-theme-region"
        className="flex flex-col overflow-y-auto"
      >
        <FocusBuilderThemePicker
          mode={props.mode}
          templateHook={props.templateHook ?? null}
        />
      </section>
    </div>
  )
}

export default FocusBuilderRightRail
