/**
 * FocusBuilderCanvas — sub-arc F-2.
 *
 * Replaces F-1's FocusBuilderCanvasPlaceholder. Renders the canonical
 * four-layer atmospheric backdrop (matching the canonical mockup at
 * docs/design/canonical-mockups/funeral_scheduling_apple_pre_liquid_glass.html
 * and Tier1CoresEditor's preview pane) when editing a core, OR the
 * template's resolved substrate when editing a template, with the
 * inherited (or canonical) core placement card rendered on top.
 *
 * Click handlers wire into FocusBuilderSelectionContext:
 *   - Wrapper click  → selection { kind: 'background' }
 *   - Placement click → selection { kind: 'core' }  (stopPropagation)
 *
 * F-2 renders ONE core placement (inherited from Tier 1 when editing a
 * template; canonical core when editing a core directly). Widget
 * placements + drag-to-canvas land in F-3.
 */
import * as React from "react"
import { useDroppable } from "@dnd-kit/core"

import { resolveEffectiveTokens } from "@/lib/visual-editor/themes/resolve-effective-tokens"
import { BASE_TOKENS } from "@/lib/visual-editor/themes/base-tokens"
import {
  chromeViewFromDraft,
  expandPreset,
  mergeChromeWithOverrides,
  resolveChromeStyle,
} from "@/bridgeable-admin/lib/visual-editor/chrome-resolver"
import {
  expandSubstratePreset,
  resolveSubstrateStyle,
  substrateViewFromBlob,
} from "@/bridgeable-admin/lib/visual-editor/substrate-resolver"
import {
  expandTypographyPreset,
  resolveTypographyBodyStyle,
  resolveTypographyHeadingStyle,
  typographyViewFromBlob,
} from "@/bridgeable-admin/lib/visual-editor/typography-resolver"
import type { CoreRecord } from "@/bridgeable-admin/services/focus-cores-service"
import type { TemplateRecord } from "@/bridgeable-admin/services/focus-templates-service"
import type { RowsBlob } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"

import { useFocusBuilderSelection } from "./FocusBuilderSelectionContext"
import { PlacedWidget } from "./PlacedWidget"
import { WidgetFreeFormLayer } from "./WidgetFreeFormLayer"
import type { WidgetPlacement } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"

/**
 * Canonical four-layer atmospheric composition. Mirrors
 * Tier1CoresEditor's preview-pane chrome and the canonical mockup at
 * docs/design/canonical-mockups/funeral_scheduling_apple_pre_liquid_glass.html.
 * Used as the canvas fallback when editing a Tier 1 core (cores have
 * no substrate vocabulary — locked Aesthetic Arc decision).
 */
export const CANONICAL_FOUR_LAYER_FALLBACK: React.CSSProperties = {
  background: [
    "radial-gradient(ellipse at 15% 10%, rgba(252, 220, 180, 0.55) 0%, transparent 50%)",
    "radial-gradient(ellipse at 85% 15%, rgba(220, 170, 200, 0.40) 0%, transparent 55%)",
    "radial-gradient(ellipse at 50% 90%, rgba(180, 200, 220, 0.45) 0%, transparent 60%)",
    "linear-gradient(180deg, #f7ebe0 0%, #f0dfd0 100%)",
  ].join(", "),
  isolation: "isolate",
}

export interface FocusBuilderCanvasProps {
  /** Subject mode: 'core' = direct core editing; 'template' = template editing. */
  mode: "core" | "template" | "empty"
  /** Resolved theme tokens (light mode only in F-2). */
  themeTokens: Record<string, string>
  /** Core record when editing a core subject. */
  core: CoreRecord | null
  /** Template record when editing a template subject. */
  template: TemplateRecord | null
  /**
   * Inherited core when editing a template — used as the placement
   * card's identity (display_name + core_slug + version pin).
   */
  inheritedCore: CoreRecord | null
  /**
   * Live chrome overrides draft (template editing only). When mode ===
   * 'core', chromeOverridesDraft is ignored — the canonical core's
   * chrome blob is used directly.
   */
  chromeOverridesDraft?: Record<string, unknown>
  /** Live substrate draft (template editing only). */
  substrateDraft?: Record<string, unknown>
  /** Live typography draft (template editing only). */
  typographyDraft?: Record<string, unknown>
  /** Live core chrome draft when mode === 'core'. */
  coreChromeDraft?: Record<string, unknown>
  /** F-3 — widget placements from the template's rows draft. */
  rowsDraft?: RowsBlob
  /**
   * FF-5 — right-click context menu request. Passed through to
   * WidgetFreeFormLayer → FreeFormPlacedWidget. The page-level
   * dispatcher owns menu state + renders CanvasContextMenu once at
   * the page root. */
  onWidgetContextMenuRequest?: (
    placementId: string,
    position: { x: number; y: number },
  ) => void
  /** FF-7 — shift+click forwarded to FreeFormPlacedWidget. */
  onWidgetShiftSelect?: (id: string) => void
  /** FF-7 — marquee + snap state passed through to WidgetFreeFormLayer. */
  marqueeStart?: { x: number; y: number } | null
  marqueeCurrent?: { x: number; y: number } | null
  marqueeActive?: boolean
  snapLines?: import("./computeSnapAdjustment").SnapLine[]
  onLayerPointerDown?: (e: React.PointerEvent<HTMLDivElement>) => void
  onLayerPointerMove?: (e: React.PointerEvent<HTMLDivElement>) => void
  onLayerPointerUp?: (e: React.PointerEvent<HTMLDivElement>) => void
}

export const CANVAS_DROP_ZONE_ID = "focus-builder-canvas-drop-zone"

/**
 * FF-2 — template-shape detection. Per Q-28 the canvas selects which
 * layer to render based on the placement-shape of the template's
 * existing placements. A placement is free-form when it carries any
 * of `x` / `y` / `width` / `height`; otherwise grid. Template-level
 * shape consistency is enforced at the FF-1 backend validator, so
 * checking the FIRST placement in the FIRST non-empty row is
 * sufficient — mixed-shape templates can't round-trip through save.
 *
 * Templates with no placements default to `"grid"` (preserves F-3
 * empty-template behavior; drop handlers can opt into free-form per
 * Q-27's per-template defaulting policy — FF-2 ships free-form-by-
 * default for the drop handler).
 */
export type TemplateShape = "freeform" | "grid"

export function detectTemplateShape(rows: RowsBlob | undefined): TemplateShape {
  if (!rows) return "grid"
  for (const row of rows) {
    if (!row.placements) continue
    for (const p of row.placements) {
      if (
        typeof p.x === "number" ||
        typeof p.y === "number" ||
        typeof p.width === "number" ||
        typeof p.height === "number"
      ) {
        return "freeform"
      }
      // First grid-shape placement encountered → grid. Template-
      // level consistency means we don't need to keep scanning.
      if (
        typeof p.column_start === "number" ||
        typeof p.column_span === "number"
      ) {
        return "grid"
      }
    }
  }
  return "grid"
}

/**
 * FF-2 — compute drop position for a free-form widget. Pure function
 * extracted from the page-level `handleDragEnd` so the Q-4 centering
 * + Q-14 clamping logic is unit-testable without staging a full
 * dnd-kit gesture in JSDOM (per investigation Q-40 — JSDOM doesn't
 * implement pointer events robustly enough for integration drag
 * coverage; that lands in Playwright at FF-7).
 *
 * Per Q-4 (centered on cursor): `x = cursorX - width/2`, `y =
 * cursorY - height/2`. Per Q-14 (canvas-bounded clamp): `x ∈ [0,
 * canvasWidth - width]`, `y ∈ [0, canvasHeight - height]`.
 *
 * `cursorX` / `cursorY` are canvas-RELATIVE coordinates — callers
 * subtract the canvas's bounding-rect offset before calling.
 */
export function computeFreeFormDropPosition(input: {
  cursorX: number
  cursorY: number
  width: number
  height: number
  canvasWidth: number
  canvasHeight: number
}): { x: number; y: number } {
  const { cursorX, cursorY, width, height, canvasWidth, canvasHeight } = input
  // Q-4 — center on cursor.
  let x = cursorX - width / 2
  let y = cursorY - height / 2
  // Q-14 — clamp to canvas bounds.
  x = Math.max(0, Math.min(x, canvasWidth - width))
  y = Math.max(0, Math.min(y, canvasHeight - height))
  return { x, y }
}

/**
 * FF-2 — flatten free-form placements out of the row blob. The rows
 * blob is the canonical storage shape (FF-1 keeps it for both
 * shapes), but for free-form rendering only the placements matter —
 * row metadata is meaningless. Returns the flat list across all rows
 * for `WidgetFreeFormLayer.placements`.
 */
export function flattenFreeFormPlacements(
  rows: RowsBlob | undefined,
): WidgetPlacement[] {
  if (!rows) return []
  const out: WidgetPlacement[] = []
  for (const row of rows) {
    if (!row.placements) continue
    for (const p of row.placements) {
      out.push(p)
    }
  }
  return out
}

export function FocusBuilderCanvas(props: FocusBuilderCanvasProps) {
  const {
    mode,
    themeTokens,
    core,
    template,
    inheritedCore,
    chromeOverridesDraft,
    substrateDraft,
    typographyDraft,
    coreChromeDraft,
    rowsDraft,
    onWidgetContextMenuRequest,
    onWidgetShiftSelect,
    marqueeStart,
    marqueeCurrent,
    marqueeActive,
    snapLines,
    onLayerPointerDown,
    onLayerPointerMove,
    onLayerPointerUp,
  } = props
  const { selection, setSelection } = useFocusBuilderSelection()

  // F-3 — drop target. Only enabled for templates; cores have no
  // widget placements. Identifier read by the page-level DndContext
  // onDragEnd handler.
  const { setNodeRef: setDropRef, isOver } = useDroppable({
    id: CANVAS_DROP_ZONE_ID,
    disabled: mode !== "template",
    data: { kind: "focus-builder-canvas" },
  })

  // ── Canvas backdrop ────────────────────────────────────────────────
  //
  // Template editing: resolved substrate via substrate-resolver.
  // Core editing (cores have no substrate): canonical four-layer
  // fallback — locked decision.
  const canvasStyle: React.CSSProperties = React.useMemo(() => {
    if (mode === "template" && substrateDraft && typographyDraft) {
      const substrateView = expandSubstratePreset(
        substrateViewFromBlob(substrateDraft),
      )
      const typographyView = expandTypographyPreset(
        typographyViewFromBlob(typographyDraft),
      )
      return {
        ...resolveSubstrateStyle(substrateView, themeTokens),
        ["--focus-builder-heading-weight" as string]: String(
          typographyView.heading_weight ?? 500,
        ),
        ["--focus-builder-body-weight" as string]: String(
          typographyView.body_weight ?? 400,
        ),
        ["--focus-builder-heading-color" as string]:
          (typographyView.heading_color_token &&
            themeTokens[typographyView.heading_color_token]) ||
          "var(--content-strong)",
        ["--focus-builder-body-color" as string]:
          (typographyView.body_color_token &&
            themeTokens[typographyView.body_color_token]) ||
          "var(--content-base)",
      }
    }
    // Core editing or empty: canonical fallback.
    return { ...CANONICAL_FOUR_LAYER_FALLBACK }
  }, [mode, substrateDraft, typographyDraft, themeTokens])

  // ── Core placement chrome ──────────────────────────────────────────
  //
  // Template mode: cascade inherited core's chrome with template's
  // overrides via the resolver.
  // Core mode: live chrome draft from useFocusCoreDraft.
  const coreChromeView = React.useMemo(() => {
    if (mode === "template") {
      return expandPreset(
        mergeChromeWithOverrides(
          inheritedCore?.chrome ?? null,
          chromeOverridesDraft ?? {},
        ),
      )
    }
    if (mode === "core") {
      return expandPreset(
        mergeChromeWithOverrides(
          (coreChromeDraft as Record<string, unknown> | null) ?? null,
          {},
        ),
      )
    }
    return expandPreset(chromeViewFromDraft({}))
  }, [mode, inheritedCore, chromeOverridesDraft, coreChromeDraft])

  const cardStyle = React.useMemo(
    () => resolveChromeStyle(coreChromeView, themeTokens),
    [coreChromeView, themeTokens],
  )

  // Live typography on the inner card (template only). For cores there
  // is no typography vocabulary, so heading/body inherit defaults.
  const headingStyle = React.useMemo(() => {
    if (mode !== "template" || !typographyDraft) return undefined
    const view = expandTypographyPreset(typographyViewFromBlob(typographyDraft))
    return resolveTypographyHeadingStyle(view, themeTokens)
  }, [mode, typographyDraft, themeTokens])

  const bodyStyle = React.useMemo(() => {
    if (mode !== "template" || !typographyDraft) return undefined
    const view = expandTypographyPreset(typographyViewFromBlob(typographyDraft))
    return resolveTypographyBodyStyle(view, themeTokens)
  }, [mode, typographyDraft, themeTokens])

  // ── Empty state ────────────────────────────────────────────────────
  if (mode === "empty") {
    return (
      <div
        data-testid="focus-builder-canvas"
        data-canvas-mode="empty"
        className="grid h-full place-items-center text-[13px] text-content-muted"
        style={canvasStyle}
      >
        Select a focus from the tree to preview.
      </div>
    )
  }

  // Identity used by the placement card.
  const identity = mode === "core"
    ? {
        kind: "CANONICAL CORE",
        title: core?.display_name ?? "Focus Core",
        slug: core?.core_slug ?? "—",
        version: core?.version ?? null,
      }
    : {
        kind: "INHERITED CORE",
        title: inheritedCore?.display_name ?? template?.display_name ?? "Focus Template",
        slug: inheritedCore?.core_slug ?? "—",
        version: template?.inherits_from_core_version ?? inheritedCore?.version ?? null,
      }

  const coreSelected = selection.kind === "core"

  // FF-2 — template-shape detection. Free-form templates take the
  // WidgetFreeFormLayer path (absolute-positioned canvas with the
  // inherited core anchored at Q-20's canonical position); grid
  // templates take the WidgetRowsLayer path (unchanged from F-3).
  const templateShape: TemplateShape =
    mode === "template" ? detectTemplateShape(rowsDraft) : "grid"

  // Body copy reused by both layers. Mode === "core" shows core
  // description; mode === "template" shows template description.
  const bodyDescription =
    mode === "core"
      ? core?.description ??
        "Edit chrome on the right. Saves apply automatically."
      : template?.description ??
        "Edit chrome, substrate, or typography on the right. The canvas updates live."

  return (
    <div
      data-testid="focus-builder-canvas"
      data-canvas-mode={mode}
      data-canvas-shape={mode === "template" ? templateShape : "core"}
      data-drop-over={isOver ? "true" : "false"}
      ref={setDropRef}
      className="relative flex h-full w-full overflow-hidden"
      style={{
        ...canvasStyle,
        outline: isOver && mode === "template" ? "2px dashed var(--accent)" : undefined,
        outlineOffset: isOver && mode === "template" ? "-6px" : undefined,
      }}
      onClick={() => setSelection({ kind: "background" })}
    >
      {mode === "template" && templateShape === "freeform" ? (
        // ── FF-2 free-form path ──────────────────────────────────────
        // Layer owns the inherited core's canonical anchored render
        // + every free-form placement's absolute positioning. The
        // outer canvas div still owns substrate + drop-target +
        // background-click selection wiring.
        <div
          data-testid="focus-builder-canvas-placements"
          className="relative h-full w-full overflow-auto p-8"
        >
          <WidgetFreeFormLayer
            placements={flattenFreeFormPlacements(rowsDraft)}
            themeTokens={themeTokens}
            canvasWidth={
              (template?.canvas_config as Record<string, unknown> | undefined)
                ?.width as number | undefined
            }
            canvasHeight={
              (template?.canvas_config as Record<string, unknown> | undefined)
                ?.height as number | undefined
            }
            coreDefaultColumnSpan={inheritedCore?.default_column_span}
            coreIdentity={{
              kind: identity.kind,
              title: identity.title,
              slug: identity.slug,
              version: identity.version,
              presetLabel: coreChromeView.preset,
              description: bodyDescription,
            }}
            coreCardStyle={cardStyle}
            headingStyle={headingStyle}
            bodyStyle={bodyStyle}
            onContextMenuRequest={onWidgetContextMenuRequest}
            onWidgetShiftSelect={onWidgetShiftSelect}
            marqueeStart={marqueeStart}
            marqueeCurrent={marqueeCurrent}
            marqueeActive={marqueeActive}
            snapLines={snapLines}
            onLayerPointerDown={onLayerPointerDown}
            onLayerPointerMove={onLayerPointerMove}
            onLayerPointerUp={onLayerPointerUp}
          />
        </div>
      ) : (
        // ── F-3 grid path (preserved unchanged) ──────────────────────
        <div
          data-testid="focus-builder-canvas-placements"
          className="relative flex h-full w-full flex-col items-center justify-start gap-3 overflow-y-auto p-8"
        >
          <div
            data-testid="focus-builder-core-placement"
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
              ...cardStyle,
              width: "min(440px, 80%)",
              minHeight: 200,
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
              {identity.kind}
            </span>
            <h2
              className="text-[20px] font-medium"
              style={
                headingStyle ?? { fontFamily: "var(--font-plex-serif)" }
              }
            >
              {identity.title}
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
              {bodyDescription}
            </p>
            <span
              className="mt-2 text-[11px] tabular-nums text-[color:var(--content-muted)]"
              style={{ fontFamily: "var(--font-plex-mono)" }}
            >
              {identity.slug}
              {identity.version != null ? ` · v${identity.version}` : ""}
              {" · "}preset: {coreChromeView.preset ?? "—"}
            </span>
          </div>

          {mode === "template" && rowsDraft && rowsDraft.length > 0 && (
            <WidgetRowsLayer
              rows={rowsDraft}
              selectedWidgetId={
                selection.kind === "widget" ? selection.id : null
              }
              onSelectWidget={(id) =>
                setSelection({ kind: "widget", id })
              }
              themeTokens={themeTokens}
            />
          )}
        </div>
      )}
    </div>
  )
}

// ── F-3 widget rows layer ──────────────────────────────────────────
//
// Renders rows of placed widgets BELOW the core placement card.
// Each placement is wrapped in an outline + click target via
// `PlacedWidget` (extracted to its own file in FF-2, consuming
// `PlacedWidgetCore` for chrome / selection / click / render).
interface WidgetRowsLayerProps {
  rows: RowsBlob
  selectedWidgetId: string | null
  onSelectWidget: (id: string) => void
  themeTokens: Record<string, string>
}

function WidgetRowsLayer(props: WidgetRowsLayerProps) {
  const { rows, selectedWidgetId, onSelectWidget, themeTokens } = props
  const sorted = React.useMemo(
    () => [...rows].sort((a, b) => a.row_index - b.row_index),
    [rows],
  )
  return (
    <div
      data-testid="focus-builder-widget-rows-layer"
      className="flex w-[min(700px,90%)] flex-col gap-2"
    >
      {sorted.map((row) => {
        const columns = row.column_count || 12
        return (
          <div
            key={row.row_index}
            data-testid="focus-builder-widget-row"
            data-row-index={row.row_index}
            className="grid w-full gap-2"
            style={{
              gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
            }}
          >
            {row.placements.map((p) => (
              <PlacedWidget
                key={p.id}
                placement={p}
                selected={selectedWidgetId === p.id}
                onSelect={onSelectWidget}
                columns={columns}
                themeTokens={themeTokens}
              />
            ))}
          </div>
        )
      })}
    </div>
  )
}

export interface FocusBuilderCanvasMountProps {
  mode: "core" | "template" | "empty"
  core: CoreRecord | null
  template: TemplateRecord | null
  inheritedCore: CoreRecord | null
  chromeOverridesDraft?: Record<string, unknown>
  substrateDraft?: Record<string, unknown>
  typographyDraft?: Record<string, unknown>
  coreChromeDraft?: Record<string, unknown>
  rowsDraft?: RowsBlob
  /** Optional pre-resolved theme tokens override (tests). */
  themeTokens?: Record<string, string>
  /** FF-5 — widget right-click context menu request. */
  onWidgetContextMenuRequest?: (
    placementId: string,
    position: { x: number; y: number },
  ) => void
  /** FF-7 — multi-select + marquee + snap state. */
  onWidgetShiftSelect?: (id: string) => void
  marqueeStart?: { x: number; y: number } | null
  marqueeCurrent?: { x: number; y: number } | null
  marqueeActive?: boolean
  snapLines?: import("./computeSnapAdjustment").SnapLine[]
  onLayerPointerDown?: (e: React.PointerEvent<HTMLDivElement>) => void
  onLayerPointerMove?: (e: React.PointerEvent<HTMLDivElement>) => void
  onLayerPointerUp?: (e: React.PointerEvent<HTMLDivElement>) => void
}

/**
 * Convenience mount that owns the theme tokens fetch. Page mounts this.
 */
export function FocusBuilderCanvasMount(props: FocusBuilderCanvasMountProps) {
  const tokens = props.themeTokens ?? { ...BASE_TOKENS.light }
  // F-2 keeps theme tokens hardcoded to BASE_TOKENS.light — Theme picker
  // (F-4) is the surface that brings in resolveEffectiveTokens.
  void resolveEffectiveTokens
  return <FocusBuilderCanvas {...props} themeTokens={tokens} />
}

export default FocusBuilderCanvas
