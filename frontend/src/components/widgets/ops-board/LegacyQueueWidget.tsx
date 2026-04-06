import { Image, ChevronRight } from "lucide-react"
import { useNavigate } from "react-router-dom"
import WidgetWrapper from "../WidgetWrapper"
import { useWidgetData } from "../useWidgetData"

interface Proof {
  id: string
  customer_name: string
  print_name: string | null
  service_date: string | null
  status: string
}

export default function LegacyQueueWidget(props: Record<string, unknown>) {
  const navigate = useNavigate()
  const { data, isLoading, error, refresh } = useWidgetData<{
    pending_count: number
    approved_today_count: number
    pending: Proof[]
  }>("/widget-data/legacy-studio/queue-summary", { refreshInterval: 300_000 })

  return (
    <WidgetWrapper
      widgetId="legacy_queue"
      title="Legacy Proof Queue"
      icon={<Image className="h-4 w-4" />}
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
          <div className="flex gap-4">
            <div>
              <div className="text-2xl font-bold text-gray-900">{data.pending_count}</div>
              <div className="text-xs text-gray-500">Pending</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-green-600">{data.approved_today_count}</div>
              <div className="text-xs text-gray-500">Approved today</div>
            </div>
          </div>
          <div className="space-y-1.5">
            {data.pending.slice(0, 4).map((p) => (
              <button
                key={p.id}
                onClick={() => navigate(`/legacy/${p.id}`)}
                className="flex items-center gap-2 w-full rounded-md px-2 py-1 text-left hover:bg-gray-50"
              >
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-gray-800 truncate">{p.customer_name}</div>
                  <div className="text-xs text-gray-500 truncate">
                    {p.print_name || "—"}
                    {p.service_date && ` · ${new Date(p.service_date).toLocaleDateString()}`}
                  </div>
                </div>
                <ChevronRight className="h-3 w-3 text-gray-400 shrink-0" />
              </button>
            ))}
          </div>
          {data.pending_count > 0 && (
            <button
              onClick={() => navigate("/legacy")}
              className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800"
            >
              Review all <ChevronRight className="h-3 w-3" />
            </button>
          )}
        </div>
      )}
    </WidgetWrapper>
  )
}
