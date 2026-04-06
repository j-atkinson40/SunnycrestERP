import { Factory } from "lucide-react"
import WidgetWrapper from "../WidgetWrapper"
import { useWidgetData } from "../useWidgetData"
import type { WidgetProps } from "../types"

interface ProductBreakdown {
  product: string
  units: number
}

export default function ProductionStatusWidget(props: WidgetProps) {
  const { data, isLoading, error, refresh } = useWidgetData<{
    total_units: number
    target: number | null
    by_product: ProductBreakdown[]
  }>("/widget-data/production/daily-summary", { refreshInterval: 300_000 })

  const progress =
    data?.target && data.target > 0
      ? Math.min(100, Math.round((data.total_units / data.target) * 100))
      : null

  return (
    <WidgetWrapper
      widgetId="production_status"
      title="Production Status"
      icon={<Factory className="h-4 w-4" />}
      size={(props._size as string) || "1x1"}
      editMode={(props._editMode as boolean) || false}
      dragHandleProps={props._dragHandleProps as Record<string, unknown>}
      onRemove={props._onRemove as () => void}
      onSizeChange={props._onSizeChange as (s: string) => void}
      supportedSizes={props._supportedSizes as string[]}
      isLoading={isLoading}
      error={error}
      onRefresh={refresh}
    >
      {data && (
        <div className="space-y-3">
          <div>
            <div className="text-2xl font-bold text-gray-900">
              {data.total_units}
              {data.target && (
                <span className="text-sm font-normal text-gray-500">
                  {" "}/ {data.target} target
                </span>
              )}
            </div>
            <div className="text-xs text-gray-500">Units produced today</div>
          </div>

          {progress !== null && (
            <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
              <div
                className="h-full rounded-full bg-green-500 transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
          )}

          {data.by_product.length > 0 && (
            <div className="space-y-1">
              {data.by_product.slice(0, 5).map((p) => (
                <div key={p.product} className="flex items-center justify-between text-xs">
                  <span className="text-gray-600 truncate">{p.product}</span>
                  <span className="font-medium text-gray-800 shrink-0 ml-2">{p.units}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </WidgetWrapper>
  )
}
