/**
 * UrnCatalogStatusWidget — Phase W-3d extension-gated widget.
 *
 * **First widget exercising the `required_extension` axis of the
 * 5-axis filter end-to-end**. Visible only to tenants with the
 * `urn_sales` extension activated.
 *
 * Per [DESIGN_LANGUAGE.md §12.10](../../../../DESIGN_LANGUAGE.md):
 * Glance + Brief variants. Glance pinnable to sidebar; Brief on
 * grid + canvas. No Detail/Deep — catalog management lives at
 * /urns/catalog (the page); the widget surfaces health.
 *
 * Per [§12.6a Widget Interactivity Discipline](../../../../DESIGN_LANGUAGE.md):
 * view-only with click-through. Adjusting stock levels, reorder
 * points, SKU activation happens on the catalog page.
 *
 * Three-component shape per established Phase W-3a/W-3b/W-3d Commits
 * 1-2 precedent.
 */

import { useNavigate } from "react-router-dom"
import { Package, AlertTriangle, ExternalLink } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { SkeletonLines } from "@/components/ui/skeleton"
import { useWidgetData } from "../useWidgetData"
import { cn } from "@/lib/utils"
import type { VariantId } from "@/components/widgets/types"


// ── Data shape (mirrors backend `get_urn_catalog_status` response) ─


interface LowStockItem {
  product_id: string
  sku: string | null
  name: string
  qty_on_hand: number
  qty_reserved: number
  reorder_point: number
}


interface UrnCatalogStatusData {
  total_skus: number
  stocked_skus: number
  drop_ship_skus: number
  low_stock_count: number
  low_stock_items: LowStockItem[]
  recent_order_count: number
  navigation_target: string
}


// ── Glance variant (Pattern 1 sidebar) ─────────────────────────────


function UrnCatalogGlance({
  data,
  isLoading,
}: {
  data: UrnCatalogStatusData | null
  isLoading: boolean
}) {
  const navigate = useNavigate()

  return (
    <button
      type="button"
      onClick={() => navigate(data?.navigation_target || "/urns/catalog")}
      data-slot="urn-catalog-status-widget"
      data-variant="glance"
      className={cn(
        "flex items-center gap-2 px-3 py-2 w-full",
        "text-sm font-sans text-content-base",
        "hover:bg-surface-muted",
        "focus-ring-accent outline-none rounded-sm",
        "transition-colors duration-quick ease-settle",
      )}
    >
      <Package className="h-4 w-4 text-accent flex-shrink-0" aria-hidden />
      <span className="truncate flex-1 text-left">
        {isLoading
          ? "…"
          : data == null || data.total_skus === 0
          ? "No catalog yet"
          : `${data.total_skus} SKUs`}
      </span>
      {data?.low_stock_count && data.low_stock_count > 0 ? (
        <span
          data-slot="urn-catalog-low-stock-dot"
          className="h-2 w-2 rounded-full bg-status-warning flex-shrink-0"
          aria-label={`${data.low_stock_count} low-stock SKUs`}
        />
      ) : null}
    </button>
  )
}


// ── Brief variant (Pattern 2 grid card) ────────────────────────────


function UrnCatalogBrief({
  data,
  isLoading,
  error,
}: VariantProps) {
  const navigate = useNavigate()

  if (isLoading) {
    return (
      <div
        data-slot="urn-catalog-status-widget"
        data-variant="brief"
        className="p-4"
      >
        <SkeletonLines count={3} />
      </div>
    )
  }

  if (error) {
    return (
      <div
        data-slot="urn-catalog-status-widget"
        data-variant="brief"
        className="p-4"
      >
        <p
          className="text-caption text-status-error font-sans"
          data-slot="urn-catalog-error"
        >
          {error}
        </p>
      </div>
    )
  }

  if (!data || data.total_skus === 0) {
    return (
      <div
        data-slot="urn-catalog-status-widget"
        data-variant="brief"
        className="flex flex-col items-center justify-center gap-2 px-4 py-8 h-full text-center"
      >
        <Package className="h-8 w-8 text-content-subtle" aria-hidden />
        <p
          className="text-body-sm font-medium text-content-strong font-sans"
          data-slot="urn-catalog-empty"
        >
          Catalog is empty
        </p>
        <p className="text-caption text-content-muted font-sans max-w-[280px]">
          Add urn products to see catalog health here.
        </p>
        <button
          type="button"
          onClick={() => navigate("/urns/catalog")}
          className={cn(
            "mt-1 text-caption text-accent font-sans",
            "hover:text-accent-hover",
            "focus-ring-accent outline-none rounded-sm",
          )}
          data-slot="urn-catalog-empty-cta"
        >
          Open catalog →
        </button>
      </div>
    )
  }

  return (
    <div
      data-slot="urn-catalog-status-widget"
      data-variant="brief"
      data-low-stock={data.low_stock_count > 0 ? "true" : "false"}
      className="flex flex-col h-full p-4 gap-3"
    >
      <div className="flex items-center gap-2">
        <Package className="h-4 w-4 text-accent" aria-hidden />
        <h3 className="text-body-sm font-medium text-content-strong font-sans flex-1">
          Urn catalog
        </h3>
        <span className="text-caption text-content-muted font-plex-mono">
          {data.total_skus} SKUs
        </span>
      </div>

      <ul className="flex-1 min-h-0 overflow-hidden space-y-1">
        <li
          data-slot="urn-catalog-row-stocked"
          className="flex items-center justify-between text-caption font-sans"
        >
          <span className="text-content-base">Stocked</span>
          <span className="text-content-muted font-plex-mono">
            {data.stocked_skus}
          </span>
        </li>
        <li
          data-slot="urn-catalog-row-drop-ship"
          className="flex items-center justify-between text-caption font-sans"
        >
          <span className="text-content-base">Drop-ship</span>
          <span className="text-content-muted font-plex-mono">
            {data.drop_ship_skus}
          </span>
        </li>
        <li
          data-slot="urn-catalog-row-low-stock"
          className={cn(
            "flex items-center justify-between text-caption font-sans rounded-sm px-1",
            data.low_stock_count > 0
              ? "bg-status-warning-muted"
              : "",
          )}
        >
          <span
            className={cn(
              "inline-flex items-center gap-1",
              data.low_stock_count > 0
                ? "text-status-warning"
                : "text-content-base",
            )}
          >
            {data.low_stock_count > 0 ? (
              <AlertTriangle className="h-3 w-3" aria-hidden />
            ) : null}
            Low stock
          </span>
          <span
            className={cn(
              "font-plex-mono",
              data.low_stock_count > 0
                ? "text-status-warning font-medium"
                : "text-content-muted",
            )}
          >
            {data.low_stock_count}
          </span>
        </li>
        <li
          data-slot="urn-catalog-row-recent-orders"
          className="flex items-center justify-between text-caption font-sans"
        >
          <span className="text-content-base">Orders (7 days)</span>
          <span className="text-content-muted font-plex-mono">
            {data.recent_order_count}
          </span>
        </li>
      </ul>

      {data.low_stock_count > 0 && data.low_stock_items.length > 0 ? (
        <section
          data-slot="urn-catalog-low-stock-list"
          className="space-y-1 pt-1 border-t border-border-subtle"
        >
          <p className="text-caption font-medium text-content-muted font-sans uppercase tracking-wide">
            Lowest stock
          </p>
          <ul className="space-y-0.5">
            {data.low_stock_items.slice(0, 3).map((item) => (
              <li
                key={item.product_id}
                className="flex items-baseline justify-between text-caption font-sans"
                data-slot="urn-catalog-low-stock-item"
              >
                <span className="text-content-base truncate flex-1">
                  {item.sku ? (
                    <span className="font-plex-mono text-content-muted mr-1">
                      {item.sku}
                    </span>
                  ) : null}
                  {item.name}
                </span>
                <span className="text-status-warning font-plex-mono ml-2">
                  {item.qty_on_hand}/{item.reorder_point}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <button
        type="button"
        onClick={() => navigate(data.navigation_target || "/urns/catalog")}
        className={cn(
          "inline-flex items-center gap-1",
          "text-caption text-accent font-sans",
          "hover:text-accent-hover",
          "focus-ring-accent outline-none rounded-sm",
          "transition-colors duration-quick ease-settle",
        )}
        data-slot="urn-catalog-open-link"
      >
        Open catalog <ExternalLink className="h-3 w-3" />
      </button>
    </div>
  )
}


// ── Common props ──────────────────────────────────────────────────


interface VariantProps {
  data: UrnCatalogStatusData | null
  isLoading: boolean
  error: string | null
}


// ── Top-level dispatcher ──────────────────────────────────────────


export interface UrnCatalogStatusWidgetProps {
  widgetId?: string
  variant_id?: VariantId
  surface?:
    | "focus_canvas"
    | "focus_stack"
    | "spaces_pin"
    | "pulse_grid"
    | "dashboard_grid"
  config?: Record<string, unknown>
}


export function UrnCatalogStatusWidget(props: UrnCatalogStatusWidgetProps) {
  const { data, isLoading, error } = useWidgetData<UrnCatalogStatusData>(
    "/widget-data/urn-catalog-status",
    { refreshInterval: 5 * 60 * 1000 },
  )

  const variant = props.variant_id ?? "brief"

  if (variant === "glance") {
    return <UrnCatalogGlance data={data} isLoading={isLoading} />
  }
  // Default + detail/deep fallback: Brief. urn_catalog_status declares
  // Glance + Brief only; defensive fallback ensures any unexpected
  // variant_id renders the canonical Brief content.
  return <UrnCatalogBrief data={data} isLoading={isLoading} error={error} />
}


export default UrnCatalogStatusWidget
