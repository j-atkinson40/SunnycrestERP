import { ShieldCheck, ChevronRight } from "lucide-react"
import { Link } from "react-router-dom"
import WidgetWrapper from "../WidgetWrapper"
import { useWidgetData } from "../useWidgetData"
import type { WidgetProps } from "../types"

interface ComplianceItem {
  id: string
  title: string
  category: string
  due_at: string | null
  days_until: number | null
  status: "overdue" | "this_week" | "upcoming"
}

interface Data {
  items: ComplianceItem[]
  total: number
}

export default function ComplianceUpcomingWidget(props: WidgetProps) {
  // Reuse the existing compliance summary endpoint if it exists; the widget
  // is tolerant of empty/missing data so it stays friendly before content is
  // seeded for a tenant.
  const { data, isLoading, error, refresh } = useWidgetData<Data>(
    "/widget-data/compliance/upcoming?days=30",
    { refreshInterval: 300_000 },
  )

  const items = data?.items || []

  return (
    <WidgetWrapper
      widgetId="compliance_upcoming"
      title="Compliance — Upcoming"
      icon={<ShieldCheck className="h-4 w-4" />}
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
          No upcoming compliance items in the next 30 days.
        </div>
      ) : (
        <div className="space-y-1.5">
          {items.slice(0, 6).map((it) => {
            const badge =
              it.status === "overdue"
                ? "bg-red-100 text-red-700"
                : it.status === "this_week"
                  ? "bg-amber-100 text-amber-800"
                  : "bg-slate-100 text-slate-700"
            return (
              <Link
                key={it.id}
                to={`/compliance`}
                className="flex items-center gap-2 text-sm hover:bg-slate-50 rounded px-1.5 py-1"
              >
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${badge}`}>
                  {it.status === "overdue" ? "Overdue" : it.days_until !== null ? `${it.days_until}d` : "—"}
                </span>
                <span className="text-slate-800 truncate flex-1">{it.title}</span>
                <ChevronRight className="h-3.5 w-3.5 text-slate-300" />
              </Link>
            )
          })}
          {items.length > 6 && (
            <Link
              to="/compliance"
              className="block text-xs text-slate-500 hover:text-slate-900 pt-1"
            >
              +{items.length - 6} more →
            </Link>
          )}
        </div>
      )}
    </WidgetWrapper>
  )
}
