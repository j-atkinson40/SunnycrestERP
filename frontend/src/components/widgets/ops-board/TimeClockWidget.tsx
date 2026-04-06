import { Clock } from "lucide-react"
import WidgetWrapper from "../WidgetWrapper"
import { useWidgetData } from "../useWidgetData"
import type { WidgetProps } from "../types"

export default function TimeClockWidget(props: WidgetProps) {
  const { isLoading, error, refresh } = useWidgetData<{
    clocked_in: number
    employees: string[]
    overtime_alerts: number
  } | null>("/widget-data/time-clock/summary", { refreshInterval: 300_000 })

  return (
    <WidgetWrapper
      widgetId="time_clock"
      title="Time Clock"
      icon={<Clock className="h-4 w-4" />}
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
      <div className="text-center py-4">
        <p className="text-sm text-gray-400">Time clock module coming soon</p>
      </div>
    </WidgetWrapper>
  )
}
