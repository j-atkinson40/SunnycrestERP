import { Truck, Phone, ChevronRight } from "lucide-react"
import { useNavigate } from "react-router-dom"
import WidgetWrapper from "../WidgetWrapper"
import { useWidgetData } from "../useWidgetData"

interface DriverInfo {
  id: string
  name: string
  status: string
  current_stop: string | null
  next_stop: string | null
  phone: string | null
}

const STATUS_COLORS: Record<string, string> = {
  available: "bg-green-100 text-green-700",
  en_route: "bg-blue-100 text-blue-700",
  at_stop: "bg-amber-100 text-amber-700",
  off_duty: "bg-gray-100 text-gray-600",
}

export default function DriverStatusWidget(props: Record<string, unknown>) {
  const navigate = useNavigate()
  const { data, isLoading, error, refresh } = useWidgetData<{
    count: number
    drivers: DriverInfo[]
  }>("/widget-data/drivers/status-summary", { refreshInterval: 120_000 })

  return (
    <WidgetWrapper
      widgetId="driver_status"
      title="Driver Status"
      icon={<Truck className="h-4 w-4" />}
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
          {data.drivers.length === 0 ? (
            <p className="text-sm text-gray-400">No active drivers</p>
          ) : (
            <div className="space-y-1.5">
              {data.drivers.map((d) => (
                <div
                  key={d.id}
                  className="flex items-center gap-3 rounded-md px-2 py-1.5 hover:bg-gray-50"
                >
                  <div className="h-8 w-8 rounded-full bg-gray-200 flex items-center justify-center text-xs font-bold text-gray-600 shrink-0">
                    {d.name.charAt(0)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-800">{d.name}</div>
                    <div className="text-xs text-gray-500 truncate">
                      {d.next_stop || "No stops assigned"}
                    </div>
                  </div>
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${STATUS_COLORS[d.status] || "bg-gray-100 text-gray-600"}`}
                  >
                    {d.status.replace("_", " ")}
                  </span>
                  {d.phone && (
                    <a
                      href={`tel:${d.phone}`}
                      className="shrink-0 text-gray-400 hover:text-blue-600"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Phone className="h-3.5 w-3.5" />
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
          <button
            onClick={() => navigate("/delivery/operations")}
            className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800"
          >
            View routes <ChevronRight className="h-3 w-3" />
          </button>
        </div>
      )}
    </WidgetWrapper>
  )
}
