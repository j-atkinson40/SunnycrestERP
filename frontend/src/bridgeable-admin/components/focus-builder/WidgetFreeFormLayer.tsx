/**
 * WidgetFreeFormLayer — sub-arc FF-2.
 *
 * Renders free-form-shape placements as absolute-positioned widgets
 * inside a canvas-dimensioned container. Replaces `WidgetRowsLayer`
 * for free-form templates per Q-28 (replace, not refactor).
 *
 * Layer responsibilities:
 *   - Read canvas dimensions from `template.canvas_config.width` /
 *     `.height`. Per Q-2 and FF-1 refinement, defensive fallback to
 *     1200×800 when fields absent (partial canvas_configs from
 *     pre-FF templates carrying only e.g. `{gap_size: 4}`).
 *   - Render the inherited (or canonical) core at the canonical
 *     anchored position per Q-20 formula:
 *       core_width  = canvas_width  * (default_column_span / 12)
 *       core_x      = (canvas_width - core_width) / 2
 *       core_y      = 40 (top margin)
 *     The core is anchored — operators cannot move it (structural-
 *     immutability canon). Renders BEFORE widgets in DOM order so
 *     widgets paint above the core by default (Q-22: widgets may
 *     overlap the core; `z_index` governs explicit cases).
 *   - Render every free-form placement via `FreeFormPlacedWidget`.
 *
 * Identity payload (kind / title / slug / version / preset) for the
 * inherited core is computed by the caller (FocusBuilderCanvas) and
 * passed via `coreIdentity` + `coreCardStyle` + `headingStyle` +
 * `bodyStyle` props — keeps this layer focused on layout while
 * preserving F-3.1c's identity rendering verbatim.
 */
import * as React from "react"

import { useFocusBuilderSelection } from "./FocusBuilderSelectionContext"
import { FreeFormPlacedWidget } from "./FreeFormPlacedWidget"
import type { WidgetPlacement } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"

/**
 * FF-2 — defensive canvas-dimension fallbacks. Mirror backend
 * `DEFAULT_CANVAS_WIDTH` / `DEFAULT_CANVAS_HEIGHT` from FF-1.
 * Per Q-2 refinement: partial `canvas_config` blobs (e.g. F-series
 * fixtures carrying `{gap_size: 4}`) lack width/height; this layer
 * MUST fall back gracefully so render-side rendering of round-tripped
 * templates doesn't crash with NaN-driven CSS values.
 */
export const FREE_FORM_DEFAULT_CANVAS_WIDTH = 1200
export const FREE_FORM_DEFAULT_CANVAS_HEIGHT = 800

export interface FreeFormCoreIdentity {
  kind: string
  title: string
  slug: string
  version: number | null
  /** preset label rendered at the bottom of the core card. */
  presetLabel: string | null | undefined
  /** Body description text. */
  description: string
}

export interface WidgetFreeFormLayerProps {
  /** Free-form placements drawn from the template's rows. Caller has
   * already filtered to free-form shape (placement-shape detection
   * happens at FocusBuilderCanvas mode-detection time). */
  placements: WidgetPlacement[]
  themeTokens: Record<string, string>
  /** Canvas dimensions from the template's `canvas_config`. Optional
   * — defensive fallback to 1200×800 when absent. */
  canvasWidth: number | null | undefined
  canvasHeight: number | null | undefined
  /** Inherited core's `default_column_span` — drives core_width per
   * Q-20 formula. Falls back to 12 (full-canvas) when absent. */
  coreDefaultColumnSpan: number | null | undefined
  /** Core identity payload — same render as F-3.1c's inline core
   * placement card (caption + title + description + slug/version
   * caption). */
  coreIdentity: FreeFormCoreIdentity
  /** Chrome-resolved style for the core card (computed by
   * FocusBuilderCanvas via `mergeChromeWithOverrides` +
   * `resolveChromeStyle`; identical to grid path's `cardStyle`). */
  coreCardStyle: React.CSSProperties
  /** Optional typography heading/body styles (template mode). */
  headingStyle: React.CSSProperties | undefined
  bodyStyle: React.CSSProperties | undefined
}

export function WidgetFreeFormLayer(props: WidgetFreeFormLayerProps) {
  const {
    placements,
    themeTokens,
    canvasWidth,
    canvasHeight,
    coreDefaultColumnSpan,
    coreIdentity,
    coreCardStyle,
    headingStyle,
    bodyStyle,
  } = props
  const { selection, setSelection } = useFocusBuilderSelection()

  // Defensive canvas-dimension fallback (Q-2 refinement).
  const width =
    typeof canvasWidth === "number" && canvasWidth > 0
      ? canvasWidth
      : FREE_FORM_DEFAULT_CANVAS_WIDTH
  const height =
    typeof canvasHeight === "number" && canvasHeight > 0
      ? canvasHeight
      : FREE_FORM_DEFAULT_CANVAS_HEIGHT

  // Q-20 — canonical core anchor formula.
  const span =
    typeof coreDefaultColumnSpan === "number" && coreDefaultColumnSpan > 0
      ? Math.max(1, Math.min(12, coreDefaultColumnSpan))
      : 12
  const coreWidth = width * (span / 12)
  const coreX = (width - coreWidth) / 2
  const coreY = 40
  // Min visible height for the core card; matches F-3 grid path's
  // `minHeight: 200`.
  const coreMinHeight = 200

  const coreSelected = selection.kind === "core"

  return (
    <div
      data-testid="focus-builder-freeform-layer"
      data-canvas-width={String(width)}
      data-canvas-height={String(height)}
      className="relative"
      style={{
        width: `${width}px`,
        height: `${height}px`,
        margin: "0 auto",
      }}
    >
      {/* Inherited / canonical core at anchored position per Q-20.
         Selection wires to { kind: "core" } — same semantics as the
         grid path. */}
      <div
        data-testid="focus-builder-core-placement"
        data-canvas-inherited-core="true"
        data-selected={coreSelected ? "true" : "false"}
        onClick={(e) => {
          e.stopPropagation()
          setSelection({ kind: "core" })
        }}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault()
            e.stopPropagation()
            setSelection({ kind: "core" })
          }
        }}
        style={{
          ...coreCardStyle,
          position: "absolute",
          left: `${coreX}px`,
          top: `${coreY}px`,
          width: `${coreWidth}px`,
          minHeight: coreMinHeight,
          zIndex: 0,
          outline: coreSelected
            ? "2px solid var(--accent)"
            : "2px solid transparent",
          outlineOffset: "4px",
          transition: "outline-color 120ms ease-out",
          cursor: "pointer",
        }}
        className="flex flex-col gap-2"
      >
        <span
          className="text-[10px] uppercase tracking-[0.08em] text-[color:var(--content-muted)]"
          style={{ fontFamily: "var(--font-plex-sans)" }}
        >
          {coreIdentity.kind}
        </span>
        <h2
          className="text-[20px] font-medium"
          style={headingStyle ?? { fontFamily: "var(--font-plex-serif)" }}
        >
          {coreIdentity.title}
        </h2>
        <p
          className="text-[13px] leading-relaxed"
          style={
            bodyStyle ?? {
              fontFamily: "var(--font-plex-sans)",
              color: "var(--content-base)",
            }
          }
        >
          {coreIdentity.description}
        </p>
        <span
          className="mt-2 text-[11px] tabular-nums text-[color:var(--content-muted)]"
          style={{ fontFamily: "var(--font-plex-mono)" }}
        >
          {coreIdentity.slug}
          {coreIdentity.version != null ? ` · v${coreIdentity.version}` : ""}
          {" · "}preset: {coreIdentity.presetLabel ?? "—"}
        </span>
      </div>

      {/* Free-form placements. Rendered AFTER the core in DOM order
         so widgets at the same `z_index` paint above the core by
         default (Q-22). */}
      {placements.map((p) => (
        <FreeFormPlacedWidget
          key={p.id}
          placement={p}
          selected={selection.kind === "widget" && selection.id === p.id}
          onSelect={(id) => setSelection({ kind: "widget", id })}
          themeTokens={themeTokens}
        />
      ))}
    </div>
  )
}

export default WidgetFreeFormLayer
