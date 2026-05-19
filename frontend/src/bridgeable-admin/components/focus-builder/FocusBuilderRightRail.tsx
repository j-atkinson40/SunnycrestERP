/**
 * FocusBuilderRightRail — sub-arc F-2.
 *
 * Three stacked sections:
 *   1. Inspector (top) — FocusBuilderInspector (selection-driven).
 *   2. Widget palette placeholder — F-3 territory.
 *   3. Theme placeholder         — F-4 territory.
 *
 * The middle + bottom slots are deliberate placeholders so the layout
 * primitive's structure is established without making operators wonder
 * where future surfaces will go.
 */
import { FocusBuilderInspector, type FocusBuilderInspectorProps } from "./FocusBuilderInspector"
import { FocusBuilderPalette } from "./FocusBuilderPalette"

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
        className="flex flex-col gap-1 px-4 py-3 text-[12px] text-content-muted"
      >
        <span
          className="text-[10px] font-semibold uppercase tracking-[0.08em]"
          style={{ fontFamily: "var(--font-plex-sans)" }}
        >
          Theme
        </span>
        <span style={{ fontFamily: "var(--font-plex-mono)" }}>
          Arrives in F-4.
        </span>
      </section>
    </div>
  )
}

export default FocusBuilderRightRail
