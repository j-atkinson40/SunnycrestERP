import { BookOpen, ChevronRight } from "lucide-react"
import { Link } from "react-router-dom"
import WidgetWrapper from "../WidgetWrapper"
import { useWidgetData } from "../useWidgetData"
import type { WidgetProps } from "../types"

interface KbItem {
  id: string
  title: string
  category: string | null
  updated_at: string | null
}

export default function KbRecentWidget(props: WidgetProps) {
  const { data, isLoading, error, refresh } = useWidgetData<{ items: KbItem[] }>(
    "/widget-data/kb/recent?limit=3",
    { refreshInterval: 900_000 },
  )

  const items = data?.items || []

  return (
    <WidgetWrapper
      widgetId="kb_recent"
      title="Knowledge Base"
      icon={<BookOpen className="h-4 w-4" />}
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
      {items.length === 0 ? (
        <div className="text-sm text-slate-500 py-4 text-center">
          No knowledge base entries yet.
          <div className="mt-2">
            <Link to="/knowledge-base" className="text-xs text-slate-600 hover:text-slate-900">
              Open Knowledge Base →
            </Link>
          </div>
        </div>
      ) : (
        <div className="space-y-1.5">
          {items.map((it) => (
            <Link
              key={it.id}
              to={`/knowledge-base`}
              className="flex items-start gap-2 text-sm hover:bg-slate-50 rounded px-1.5 py-1.5"
            >
              <div className="flex-1 min-w-0">
                <div className="font-medium text-slate-800 truncate">{it.title}</div>
                <div className="text-xs text-slate-500">
                  {it.category && <span>{it.category}</span>}
                  {it.category && it.updated_at && <span className="mx-1">·</span>}
                  {it.updated_at && <span>{_relative(it.updated_at)}</span>}
                </div>
              </div>
              <ChevronRight className="h-3.5 w-3.5 text-slate-300 mt-0.5" />
            </Link>
          ))}
          <Link to="/knowledge-base" className="block text-xs text-slate-500 hover:text-slate-900 pt-1">
            View all →
          </Link>
        </div>
      )}
    </WidgetWrapper>
  )
}

function _relative(iso: string): string {
  try {
    const then = new Date(iso).getTime()
    const now = Date.now()
    const diff = Math.floor((now - then) / 1000)
    if (diff < 60) return "just now"
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
    return `${Math.floor(diff / 86400)}d ago`
  } catch {
    return ""
  }
}
