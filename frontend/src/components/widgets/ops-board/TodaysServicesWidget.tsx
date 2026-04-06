import { Calendar, ChevronRight } from "lucide-react"
import { useNavigate } from "react-router-dom"
import WidgetWrapper from "../WidgetWrapper"
import { useWidgetData } from "../useWidgetData"

interface Order {
  id: string
  order_number: string | null
  customer_name: string
  cemetery_name: string | null
  service_time: string | null
  status: string
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-gray-100 text-gray-700",
  scheduled: "bg-blue-100 text-blue-700",
  confirmed: "bg-blue-100 text-blue-700",
  in_production: "bg-amber-100 text-amber-700",
  delivered: "bg-green-100 text-green-700",
  completed: "bg-green-100 text-green-700",
}

export default function TodaysServicesWidget(props: Record<string, unknown>) {
  const navigate = useNavigate()
  const { data, isLoading, error, refresh } = useWidgetData<{
    count: number
    orders: Order[]
  }>("/widget-data/orders/today", { refreshInterval: 300_000 })

  return (
    <WidgetWrapper
      widgetId="todays_services"
      title="Today's Services"
      icon={<Calendar className="h-4 w-4" />}
      size={(props._size as string) || "2x1"}
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
        <div className="space-y-2">
          <div className="text-2xl font-bold text-gray-900">{data.count}</div>
          <div className="space-y-1.5 max-h-48 overflow-y-auto">
            {data.orders.map((o) => (
              <button
                key={o.id}
                onClick={() => navigate(`/sales-orders/${o.id}`)}
                className="flex items-center gap-2 w-full rounded-md px-2 py-1.5 text-left hover:bg-gray-50 transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-800 truncate">
                    {o.customer_name}
                  </div>
                  <div className="text-xs text-gray-500 truncate">
                    {o.cemetery_name || "No cemetery"}
                    {o.service_time && ` · ${new Date(o.service_time).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`}
                  </div>
                </div>
                <span
                  className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${STATUS_COLORS[o.status] || "bg-gray-100 text-gray-600"}`}
                >
                  {o.status}
                </span>
              </button>
            ))}
          </div>
          {data.count > 0 && (
            <button
              onClick={() => navigate("/sales-orders")}
              className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800"
            >
              View all <ChevronRight className="h-3 w-3" />
            </button>
          )}
        </div>
      )}
    </WidgetWrapper>
  )
}
