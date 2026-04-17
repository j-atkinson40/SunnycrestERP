import { Users, ChevronRight } from "lucide-react"
import { Link } from "react-router-dom"
import WidgetWrapper from "../WidgetWrapper"
import { useWidgetData } from "../useWidgetData"
import type { WidgetProps } from "../types"

interface Cert {
  employee_id: string
  employee_name: string
  cert_type: string
  expires_at: string
  days_remaining: number
}

export default function TeamCertificationsWidget(props: WidgetProps) {
  const { data, isLoading, error, refresh } = useWidgetData<{ certs: Cert[] }>(
    "/widget-data/employees/expiring-certifications?days=60",
    { refreshInterval: 600_000 },
  )

  const certs = data?.certs || []

  return (
    <WidgetWrapper
      widgetId="team_certifications"
      title="Team Certifications"
      icon={<Users className="h-4 w-4" />}
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
      {certs.length === 0 ? (
        <div className="text-sm text-slate-500 py-4 text-center">
          No certifications expiring in the next 60 days.
        </div>
      ) : (
        <div className="space-y-1">
          {certs.slice(0, 6).map((c) => {
            const urgent = c.days_remaining <= 14
            const soon = c.days_remaining <= 30
            const color = urgent ? "text-red-700" : soon ? "text-amber-700" : "text-slate-700"
            return (
              <Link
                key={`${c.employee_id}-${c.cert_type}`}
                to={`/team`}
                className="flex items-center gap-2 text-sm hover:bg-slate-50 rounded px-1.5 py-1"
              >
                <span className={`font-medium truncate flex-1 ${color}`}>{c.employee_name}</span>
                <span className="text-xs text-slate-500 truncate max-w-[90px]">{c.cert_type}</span>
                <span className={`text-xs font-medium ${color}`}>{c.days_remaining}d</span>
                <ChevronRight className="h-3.5 w-3.5 text-slate-300" />
              </Link>
            )
          })}
        </div>
      )}
    </WidgetWrapper>
  )
}
