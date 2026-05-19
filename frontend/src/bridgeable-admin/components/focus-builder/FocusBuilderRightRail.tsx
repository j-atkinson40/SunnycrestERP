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

export type FocusBuilderRightRailProps = FocusBuilderInspectorProps

export function FocusBuilderRightRail(props: FocusBuilderRightRailProps) {
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
        className="flex flex-col gap-1 border-b border-[color:var(--border-subtle)] px-4 py-3 text-[12px] text-content-muted"
      >
        <span
          className="text-[10px] font-semibold uppercase tracking-[0.08em]"
          style={{ fontFamily: "var(--font-plex-sans)" }}
        >
          Widget palette
        </span>
        <span style={{ fontFamily: "var(--font-plex-mono)" }}>
          Arrives in F-3.
        </span>
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
