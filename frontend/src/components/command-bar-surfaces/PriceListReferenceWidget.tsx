/**
 * S-2 (§4.3) price-list-reference surface widget
 * (surface.price-list-reference).
 *
 * The tenant's PUBLISHED tiered price list for the products being quoted
 * — the reference display (§4.3 purpose 2). Tiered columns (standard /
 * contractor / homeowner) are correct HERE: this is what the published
 * list shows. This is the deliberate counterpart to the quote-preview,
 * which uses the order resolver. Suppressed by CONTEXTUAL_SURFACES until
 * a product resolves, so it never renders as an empty shell.
 *
 * HOST-AGNOSTIC (S-3/S-5 re-host seam): self-fetches from config; the
 * §4.3 Act discipline lives in the host, not here.
 */

import { useEffect, useRef, useState } from "react"
import { Loader2 } from "lucide-react"

import type { WidgetRendererProps } from "@/components/focus/canvas/widget-renderers"
import { registerWidgetRenderer } from "@/components/focus/canvas/widget-renderers"
import { Card } from "@/components/ui/card"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import {
  fetchPriceListReference,
  type PriceListReferenceResponse,
} from "@/services/quote-preview-service"

interface PriceListReferenceConfig {
  products?: string[]
  customerId?: string | null
}

export function PriceListReferenceWidget({ config }: WidgetRendererProps) {
  const cfg = (config ?? {}) as PriceListReferenceConfig
  const debounced = useDebouncedValue(
    JSON.stringify({ p: cfg.products ?? [], c: cfg.customerId ?? null }),
    200,
  )

  const [data, setData] = useState<PriceListReferenceResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    const parsed = JSON.parse(debounced) as {
      p: string[]
      c: string | null
    }
    if (parsed.p.length === 0) {
      setData(null)
      return
    }
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setLoading(true)
    setError(false)
    fetchPriceListReference(parsed.p, parsed.c, ctrl.signal)
      .then((res) => {
        setData(res)
        setLoading(false)
      })
      .catch((e) => {
        if (ctrl.signal.aborted) return
        if ((e as { code?: string })?.code === "ERR_CANCELED") return
        setError(true)
        setLoading(false)
      })
    return () => ctrl.abort()
  }, [debounced])

  return (
    <Card
      elevation="raised"
      size="sm"
      className="w-full gap-2"
      data-testid="price-list-reference-surface"
    >
      <div className="flex items-center justify-between">
        <span className="text-body-sm font-medium text-content-strong">
          Price list
        </span>
        <span className="flex items-center gap-1 text-caption text-content-muted">
          {loading && <Loader2 className="h-3 w-3 animate-spin" />}
          {data?.version_label ?? "Published"}
        </span>
      </div>

      {error ? (
        <div className="py-4 text-center text-body-sm text-content-muted">
          Couldn't load the price list.
        </div>
      ) : data && data.rows.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-caption">
            <thead>
              <tr className="text-content-muted">
                <th className="py-1 pr-2 text-left font-medium">Product</th>
                <th className="py-1 px-2 text-right font-medium">Standard</th>
                <th className="py-1 px-2 text-right font-medium">Contractor</th>
                <th className="py-1 pl-2 text-right font-medium">Homeowner</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => (
                <tr
                  key={row.product_name}
                  className="border-t border-border-subtle"
                >
                  <td className="py-1 pr-2 text-content-base">
                    {row.product_name}
                    {!row.on_list && (
                      <span className="ml-1 text-content-muted">
                        · not on list
                      </span>
                    )}
                  </td>
                  <td className="py-1 px-2 text-right tabular-nums text-content-strong">
                    {row.standard_price_formatted}
                  </td>
                  <td className="py-1 px-2 text-right tabular-nums text-content-base">
                    {row.contractor_price_formatted}
                  </td>
                  <td className="py-1 pl-2 text-right tabular-nums text-content-base">
                    {row.homeowner_price_formatted}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="py-4 text-center text-body-sm text-content-muted">
          {loading ? "Looking up prices…" : "No published prices."}
        </div>
      )}
    </Card>
  )
}

registerWidgetRenderer(
  "surface.price-list-reference",
  PriceListReferenceWidget,
)
