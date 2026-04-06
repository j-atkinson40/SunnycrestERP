import { ShieldCheck, ChevronRight } from "lucide-react"
import { useNavigate } from "react-router-dom"
import WidgetWrapper from "../WidgetWrapper"
import { useWidgetData } from "../useWidgetData"
import type { WidgetProps } from "../types"

export default function SafetyWidget(props: WidgetProps) {
  const navigate = useNavigate()
  const { data, isLoading, error, refresh } = useWidgetData<{
    open_incidents: number
    overdue_inspections: number
    training_overdue: number
  }>("/widget-data/safety/dashboard-summary", { refreshInterval: 300_000 })

  return (
    <WidgetWrapper
      widgetId="safety_status"
      title="Safety Dashboard"
      icon={<ShieldCheck className="h-4 w-4" />}
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
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600">Open incidents</span>
              <span className={`font-semibold ${data.open_incidents > 0 ? "text-red-600" : "text-green-600"}`}>
                {data.open_incidents}
              </span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600">Overdue inspections</span>
              <span className={`font-semibold ${data.overdue_inspections > 0 ? "text-amber-600" : "text-green-600"}`}>
                {data.overdue_inspections}
              </span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600">Training overdue</span>
              <span className={`font-semibold ${data.training_overdue > 0 ? "text-amber-600" : "text-green-600"}`}>
                {data.training_overdue}
              </span>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => navigate("/safety")}
              className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800"
            >
              View all <ChevronRight className="h-3 w-3" />
            </button>
          </div>
        </div>
      )}
    </WidgetWrapper>
  )
}
