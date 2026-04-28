/**
 * SavedViewWidget — Phase W-3b cross-surface infrastructure widget.
 *
 * Generic widget rendering any tenant saved view. **Config-driven**:
 * each widget instance carries `config: {view_id: string}` selecting
 * which saved view to render. This makes "any saved view becomes a
 * widget instance" a first-class platform pattern — the
 * **user-authored widget catalog without widget code**.
 *
 * Per [DESIGN_LANGUAGE.md §12.10](../../../../DESIGN_LANGUAGE.md):
 * Brief + Detail + Deep variants — NO Glance because saved views
 * need at minimum a list to be informative; surface compatibility
 * excludes `spaces_pin` for the same reason (sidebar requires Glance
 * variant per §12.2 compatibility matrix).
 *
 * Three-component shape per established Phase W-3a precedent:
 *   1. Variant tablets (presentation, render-only) — wrap the existing
 *      V-1c `SavedViewWidget` from `frontend/src/components/saved-views/`
 *   2. Variant wrappers (data piping + config validation)
 *   3. Top-level dispatcher (selects variant via surface + variant_id)
 *
 * Reuse over rebuild: existing V-1c `SavedViewWidget` handles the
 * 7-mode SavedViewRenderer dispatch + visibility checks + cross-tenant
 * masking. Phase W-3b wraps it with the widget framework contract; no
 * changes to the underlying V-1c component.
 *
 * Phase W-3b Commit 0 (widget config plumbing) makes this widget
 * possible — `WidgetRendererProps.config` is now passed through every
 * dispatch site. saved_view widget reads `props.config.view_id`.
 *
 * Empty state UX: when `config.view_id` is missing or invalid, the
 * widget renders a CTA pointing to `/saved-views` library. Per spec
 * Q4 fallback (b): inline picker deferred until PATCH endpoint
 * `/spaces/{space}/pins/{pin}` ships. Phase W-3b is widget shipping,
 * not infrastructure expansion.
 */

import { Layers } from "lucide-react"
import { Link } from "react-router-dom"

import { SavedViewWidget as V1cSavedViewWidget } from "@/components/saved-views/SavedViewWidget"
import { cn } from "@/lib/utils"
import type { VariantId } from "@/components/widgets/types"


// ── Config shape ────────────────────────────────────────────────────


interface SavedViewConfig {
  view_id?: string
}


function readViewId(config: Record<string, unknown> | undefined): string | null {
  if (!config) return null
  const c = config as SavedViewConfig
  if (typeof c.view_id !== "string" || !c.view_id) return null
  return c.view_id
}


// ── Empty state ─────────────────────────────────────────────────────


/**
 * Empty state — config missing or invalid. Shipped per Phase W-3b
 * Q4 fallback (b): widget functions but lacks a configured view;
 * empty-state CTA points at `/saved-views` library where the user can
 * pick a saved view via the existing PinStar mechanism.
 *
 * Future enhancement (deferred): inline picker dropdown that updates
 * config in-place. Requires PATCH `/spaces/{space}/pins/{pin}`
 * endpoint or equivalent layout-config-update path. See spec Q4.
 */
function SavedViewEmptyState() {
  return (
    <div
      data-slot="saved-view-widget-empty"
      className={cn(
        "flex flex-col items-center justify-center gap-2",
        "px-4 py-8 text-center h-full",
      )}
    >
      <Layers
        className="h-8 w-8 text-content-subtle"
        aria-hidden
      />
      <p className="text-body-sm font-medium text-content-strong font-sans leading-tight">
        No saved view configured
      </p>
      <p className="text-caption text-content-muted font-sans leading-tight max-w-[280px]">
        Pick a saved view from the library to display it here.
      </p>
      <Link
        to="/saved-views"
        className={cn(
          "mt-1 text-caption text-accent font-sans",
          "hover:text-accent-hover",
          "transition-colors duration-quick ease-settle",
          "focus-ring-accent outline-none rounded-sm",
        )}
        data-slot="saved-view-widget-empty-cta"
      >
        Open saved views library →
      </Link>
    </div>
  )
}


// ── Variant tablets ─────────────────────────────────────────────────


interface VariantProps {
  view_id: string
  variant: "brief" | "detail" | "deep"
}


/**
 * Brief variant — compact saved view rendering with header chrome.
 *
 * Per Section 12.10: Brief = "Compact summary of view's primary
 * presentation mode". The existing V-1c SavedViewWidget renders the
 * full view in its declared presentation mode; for the Brief variant
 * we pass `showHeader=false` (the widget framework's container provides
 * card chrome) and let the SavedViewRenderer handle compact rendering.
 *
 * The V-1c SavedViewWidget caps the result limit at the saved view's
 * declared limit; widget surface size constraints (defined in
 * WidgetDefinition.variants[].canvas_size) handle overflow.
 */
function SavedViewBriefTablet({ view_id }: VariantProps) {
  return (
    <div
      data-slot="saved-view-widget"
      data-variant="brief"
      className="flex flex-col h-full overflow-hidden"
    >
      <V1cSavedViewWidget viewId={view_id} showHeader={false} />
    </div>
  )
}


/**
 * Detail variant — full saved view rendering at standard density.
 * Same V-1c renderer; surface size constraints come from
 * WidgetDefinition.variants.detail.canvas_size.
 */
function SavedViewDetailTablet({ view_id }: VariantProps) {
  return (
    <div
      data-slot="saved-view-widget"
      data-variant="detail"
      className="flex flex-col h-full overflow-hidden"
    >
      <V1cSavedViewWidget viewId={view_id} showHeader={true} />
    </div>
  )
}


/**
 * Deep variant — canvas-mounted maximum density rendering.
 * Same V-1c renderer; canvas_size 640×800 max per
 * WidgetDefinition.variants.deep.canvas_size.
 */
function SavedViewDeepTablet({ view_id }: VariantProps) {
  return (
    <div
      data-slot="saved-view-widget"
      data-variant="deep"
      className="flex flex-col h-full overflow-hidden"
    >
      <V1cSavedViewWidget viewId={view_id} showHeader={true} />
    </div>
  )
}


// ── Top-level dispatcher ────────────────────────────────────────────


export interface SavedViewWidgetProps {
  widgetId?: string
  variant_id?: VariantId
  surface?: "focus_canvas" | "focus_stack" | "spaces_pin"
  config?: Record<string, unknown>
}


/**
 * Top-level dispatcher.
 *
 * - When `config.view_id` is missing or invalid: renders empty state
 *   regardless of variant. (Variant taxonomy assumes a configured
 *   view; without one there's nothing to render.)
 * - When valid `view_id`: dispatches to Brief / Detail / Deep tablet
 *   based on `variant_id` (defaults to `detail` per WidgetDefinition).
 * - `spaces_pin` surface should never reach this widget per the
 *   `supported_surfaces` declaration excluding it. Defensive fallback:
 *   render Brief variant if the framework somehow lands a saved_view
 *   on `spaces_pin` (e.g., misconfigured pin). The widget's
 *   `add_pin` 4-axis filter rejects `spaces_pin` pins for saved_view
 *   server-side — this is belt + suspenders.
 */
export function SavedViewWidget(props: SavedViewWidgetProps) {
  const view_id = readViewId(props.config)

  if (!view_id) {
    return <SavedViewEmptyState />
  }

  const variant = props.variant_id ?? "detail"

  if (variant === "brief") {
    return <SavedViewBriefTablet view_id={view_id} variant="brief" />
  }
  if (variant === "deep") {
    return <SavedViewDeepTablet view_id={view_id} variant="deep" />
  }
  // Default + glance fallback: detail. Glance variant is not declared
  // in the catalog (saved_view excludes Glance); fallback ensures the
  // widget renders something if the dispatch lands here unexpectedly.
  return <SavedViewDetailTablet view_id={view_id} variant="detail" />
}


export default SavedViewWidget
