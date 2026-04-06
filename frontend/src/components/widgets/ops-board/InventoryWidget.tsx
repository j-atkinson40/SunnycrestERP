import { Package } from "lucide-react"
import WidgetWrapper from "../WidgetWrapper"
import { useWidgetData } from "../useWidgetData"
import type { WidgetProps } from "../types"

interface InventoryItem {
  id: string
  product_name: string
  quantity: number
  min_level: number
  status: "ok" | "low" | "out"
}

const STATUS_INDICATOR: Record<string, { dot: string; label: string }> = {
  ok: { dot: "bg-green-500", label: "OK" },
  low: { dot: "bg-amber-500", label: "Low" },
  out: { dot: "bg-red-500", label: "Out" },
}

export default function InventoryWidget(props: WidgetProps) {
  const { data, isLoading, error, refresh } = useWidgetData<{
    items: InventoryItem[]
  }>("/widget-data/inventory/key-items", { refreshInterval: 600_000 })

  return (
    <WidgetWrapper
      widgetId="inventory_levels"
      title="Key Inventory"
      icon={<Package className="h-4 w-4" />}
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
        <div className="space-y-1">
          {data.items.length === 0 ? (
            <p className="text-sm text-gray-400">No inventory items</p>
          ) : (
            data.items.slice(0, 8).map((item) => {
              const s = STATUS_INDICATOR[item.status] || STATUS_INDICATOR.ok
              return (
                <div
                  key={item.id}
                  className="flex items-center gap-2 rounded-md px-2 py-1 text-xs"
                >
                  <span className={`h-2 w-2 rounded-full shrink-0 ${s.dot}`} />
                  <span className="flex-1 text-gray-700 truncate">{item.product_name}</span>
                  <span className="font-medium text-gray-900 shrink-0">{item.quantity}</span>
                </div>
              )
            })
          )}
        </div>
      )}
    </WidgetWrapper>
  )
}
