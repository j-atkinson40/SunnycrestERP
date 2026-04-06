import { CheckSquare, ChevronRight } from "lucide-react"
import { useNavigate } from "react-router-dom"
import WidgetWrapper from "../WidgetWrapper"
import { useWidgetData } from "../useWidgetData"
import type { WidgetProps } from "../types"

export default function QCStatusWidget(props: WidgetProps) {
  const navigate = useNavigate()
  const { data, isLoading, error, refresh } = useWidgetData<{
    total: number
    completed: number
    failed: number
    pass_rate: number
  }>("/widget-data/qc/daily-summary", { refreshInterval: 300_000 })

  return (
    <WidgetWrapper
      widgetId="qc_status"
      title="QC Inspection Status"
      icon={<CheckSquare className="h-4 w-4" />}
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
              <div className="text-2xl font-bold text-gray-900">{data.completed}</div>
              <div className="text-xs text-gray-500">Completed</div>
            </div>
            {data.failed > 0 && (
              <div>
                <div className="text-2xl font-bold text-red-600">{data.failed}</div>
                <div className="text-xs text-gray-500">Failed</div>
              </div>
            )}
          </div>
          {data.total > 0 && (
            <div className="text-xs text-gray-500">
              Pass rate: <span className="font-medium text-gray-800">{data.pass_rate}%</span>
            </div>
          )}
          <button
            onClick={() => navigate("/console/operations/qc")}
            className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800"
          >
            Log QC check <ChevronRight className="h-3 w-3" />
          </button>
        </div>
      )}
    </WidgetWrapper>
  )
}
