import { Sunrise, ChevronRight } from "lucide-react"
import { useNavigate } from "react-router-dom"
import WidgetWrapper from "../WidgetWrapper"
import { useWidgetData } from "../useWidgetData"
import type { WidgetProps } from "../types"

export default function BriefingSummaryWidget(props: WidgetProps) {
  const navigate = useNavigate()
  const { data, isLoading, error, refresh } = useWidgetData<{
    available: boolean
    narrative: string | null
    action_items: number
  }>("/widget-data/briefing/today", { refreshInterval: 0 }) // Once per session

  return (
    <WidgetWrapper
      widgetId="briefing_summary"
      title="Morning Briefing"
      icon={<Sunrise className="h-4 w-4" />}
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
        <div className="space-y-3">
          {data.available ? (
            <>
              <p className="text-sm text-gray-700 line-clamp-4 leading-relaxed">
                {data.narrative || "No briefing narrative for today."}
              </p>
              {data.action_items > 0 && (
                <div className="text-xs text-amber-700 bg-amber-50 rounded-md px-2 py-1">
                  {data.action_items} action item{data.action_items !== 1 && "s"} for today
                </div>
              )}
              <button
                onClick={() => navigate("/dashboard")}
                className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800"
              >
                View full briefing <ChevronRight className="h-3 w-3" />
              </button>
            </>
          ) : (
            <p className="text-sm text-gray-400">No briefing available for today</p>
          )}
        </div>
      )}
    </WidgetWrapper>
  )
}
