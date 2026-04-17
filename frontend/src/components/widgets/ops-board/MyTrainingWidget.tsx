import { GraduationCap, Check, Clock } from "lucide-react"
import { Link } from "react-router-dom"
import WidgetWrapper from "../WidgetWrapper"
import { useWidgetData } from "../useWidgetData"
import type { WidgetProps } from "../types"

interface TrainingItem {
  id: string
  title: string
  due_at: string | null
  is_complete: boolean
  days_until: number | null
}

export default function MyTrainingWidget(props: WidgetProps) {
  const { data, isLoading, error, refresh } = useWidgetData<{ items: TrainingItem[] }>(
    "/widget-data/me/training",
    { refreshInterval: 600_000 },
  )

  const items = data?.items || []

  return (
    <WidgetWrapper
      widgetId="my_training"
      title="My Training"
      icon={<GraduationCap className="h-4 w-4" />}
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
      {items.length === 0 ? (
        <div className="text-sm text-slate-500 py-4 text-center">
          No training assigned.
          <div className="mt-2">
            <Link to="/training" className="text-xs text-slate-600 hover:text-slate-900">
              Open Training →
            </Link>
          </div>
        </div>
      ) : (
        <div className="space-y-1.5">
          {items.slice(0, 5).map((it) => {
            const overdue = !it.is_complete && it.days_until !== null && it.days_until < 0
            return (
              <Link
                key={it.id}
                to="/training"
                className="flex items-center gap-2 text-sm hover:bg-slate-50 rounded px-1.5 py-1"
              >
                {it.is_complete ? (
                  <Check className="h-4 w-4 text-green-600" />
                ) : (
                  <Clock className={`h-4 w-4 ${overdue ? "text-red-600" : "text-slate-400"}`} />
                )}
                <span className={`truncate flex-1 ${it.is_complete ? "text-slate-400 line-through" : "text-slate-800"}`}>
                  {it.title}
                </span>
                {!it.is_complete && it.days_until !== null && (
                  <span className={`text-xs ${overdue ? "text-red-600" : "text-slate-500"}`}>
                    {overdue ? `${Math.abs(it.days_until)}d late` : `${it.days_until}d`}
                  </span>
                )}
              </Link>
            )
          })}
        </div>
      )}
    </WidgetWrapper>
  )
}
