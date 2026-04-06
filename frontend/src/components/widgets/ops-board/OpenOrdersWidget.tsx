import { ClipboardList, ChevronRight } from "lucide-react"
import { useNavigate } from "react-router-dom"
import WidgetWrapper from "../WidgetWrapper"
import { useWidgetData } from "../useWidgetData"

export default function OpenOrdersWidget(props: Record<string, unknown>) {
  const navigate = useNavigate()
  const { data, isLoading, error, refresh } = useWidgetData<{
    unscheduled: number
    scheduled: number
    in_production: number
    total: number
  }>("/widget-data/orders/pending-summary", { refreshInterval: 300_000 })

  const rows = data
    ? [
        { label: "Unscheduled", count: data.unscheduled, filter: "pending" },
        { label: "Scheduled", count: data.scheduled, filter: "scheduled" },
        { label: "In production", count: data.in_production, filter: "in_production" },
      ]
    : []

  return (
    <WidgetWrapper
      widgetId="open_orders"
      title="Open Orders"
      icon={<ClipboardList className="h-4 w-4" />}
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
            <div className="text-2xl font-bold text-gray-900">{data.total}</div>
            <div className="text-xs text-gray-500">Total open</div>
          </div>
          <div className="space-y-1">
            {rows.map((r) => (
              <button
                key={r.filter}
                onClick={() => navigate(`/sales-orders?status=${r.filter}`)}
                className="flex items-center justify-between w-full rounded-md px-2 py-1 text-left hover:bg-gray-50"
              >
                <span className="text-sm text-gray-600">{r.label}</span>
                <span className="text-sm font-semibold text-gray-800">{r.count}</span>
              </button>
            ))}
          </div>
          <button
            onClick={() => navigate("/sales-orders")}
            className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800"
          >
            View all <ChevronRight className="h-3 w-3" />
          </button>
        </div>
      )}
    </WidgetWrapper>
  )
}
