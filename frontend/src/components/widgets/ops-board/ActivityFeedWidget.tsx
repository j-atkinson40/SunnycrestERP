import { Activity } from "lucide-react"
import WidgetWrapper from "../WidgetWrapper"
import { useWidgetData } from "../useWidgetData"

interface ActivityEvent {
  id: string
  action: string | null
  description: string | null
  entity_type: string | null
  user_name: string | null
  created_at: string | null
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export default function ActivityFeedWidget(props: Record<string, unknown>) {
  const { data, isLoading, error, refresh } = useWidgetData<{
    events: ActivityEvent[]
  }>("/widget-data/activity/recent?limit=10", { refreshInterval: 300_000 })

  return (
    <WidgetWrapper
      widgetId="activity_feed"
      title="Recent Activity"
      icon={<Activity className="h-4 w-4" />}
      size={(props._size as string) || "1x2"}
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
          {data.events.length === 0 ? (
            <p className="text-sm text-gray-400">No recent activity</p>
          ) : (
            data.events.map((evt) => (
              <div key={evt.id} className="flex gap-2 px-1 py-1.5 border-b border-gray-50 last:border-0">
                <div className="h-1.5 w-1.5 rounded-full bg-blue-400 mt-1.5 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-gray-700 truncate">
                    {evt.description || evt.action || "Activity"}
                  </p>
                  <div className="text-[10px] text-gray-400">
                    {evt.user_name && <span>{evt.user_name} · </span>}
                    {evt.created_at && timeAgo(evt.created_at)}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </WidgetWrapper>
  )
}
