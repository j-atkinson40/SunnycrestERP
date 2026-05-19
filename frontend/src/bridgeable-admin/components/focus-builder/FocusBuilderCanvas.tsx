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
import { getByName } from "@/lib/visual-editor/registry"
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
}

export const CANVAS_DROP_ZONE_ID = "focus-builder-canvas-drop-zone"

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

  return (
    <div
      data-testid="focus-builder-canvas"
      data-canvas-mode={mode}
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
            {mode === "core"
              ? core?.description ??
                "Edit chrome on the right. Saves apply automatically."
              : template?.description ??
                "Edit chrome, substrate, or typography on the right. The canvas updates live."}
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
          />
        )}
      </div>
    </div>
  )
}

// ── F-3 widget rows layer ──────────────────────────────────────────
//
// Renders rows of placed widgets BELOW the core placement card.
// Each placement is wrapped in an outline + click target that drives
// selection { kind: 'widget', id }. The widget render itself comes
// from the component registry's React component for the slug.
interface WidgetRowsLayerProps {
  rows: RowsBlob
  selectedWidgetId: string | null
  onSelectWidget: (id: string) => void
}

function WidgetRowsLayer(props: WidgetRowsLayerProps) {
  const { rows, selectedWidgetId, onSelectWidget } = props
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
              />
            ))}
          </div>
        )
      })}
    </div>
  )
}

interface PlacedWidgetProps {
  placement: import("@/bridgeable-admin/hooks/useFocusTemplateDraft").WidgetPlacement
  selected: boolean
  onSelect: (id: string) => void
  columns: number
}

function PlacedWidget(props: PlacedWidgetProps) {
  const { placement, selected, onSelect, columns } = props
  const entry = React.useMemo(
    () => getByName("widget", placement.widget_slug),
    [placement.widget_slug],
  )
  // `display: contents` boundary div from the HOC means rendering the
  // Component directly will still emit the boundary; we wrap our own
  // selection chrome around it.
  const Component = entry?.component as React.ComponentType<unknown> | undefined
  const span = Math.max(1, Math.min(columns, placement.column_span || 4))
  const start = Math.max(1, Math.min(columns, placement.column_start || 1))
  return (
    <div
      data-testid="focus-builder-placed-widget"
      data-widget-id={placement.id}
      data-widget-slug={placement.widget_slug}
      data-selected={selected ? "true" : "false"}
      role="button"
      tabIndex={0}
      onClick={(e) => {
        e.stopPropagation()
        onSelect(placement.id)
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          e.stopPropagation()
          onSelect(placement.id)
        }
      }}
      style={{
        gridColumn: `${start} / span ${span}`,
        outline: selected ? "2px solid var(--accent)" : "2px solid transparent",
        outlineOffset: "2px",
        borderRadius: 12,
        transition: "outline-color 120ms ease-out",
        cursor: "pointer",
        minHeight: 56,
      }}
    >
      {Component ? (
        <Component {...(placement.chrome ?? {})} />
      ) : (
        <div className="rounded-md border border-dashed border-[color:var(--border-subtle)] bg-surface-base px-3 py-2 text-[12px] text-content-muted">
          Unknown widget: {placement.widget_slug}
        </div>
      )}
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
