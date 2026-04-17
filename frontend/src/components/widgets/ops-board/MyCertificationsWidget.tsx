import { Award, Check, AlertTriangle, X } from "lucide-react"
import WidgetWrapper from "../WidgetWrapper"
import { useWidgetData } from "../useWidgetData"
import type { WidgetProps } from "../types"

interface Cert {
  cert_type: string
  expires_at: string | null
  days_remaining: number | null
  status: "current" | "expiring_soon" | "expired"
}

export default function MyCertificationsWidget(props: WidgetProps) {
  const { data, isLoading, error, refresh } = useWidgetData<{ certs: Cert[] }>(
    "/widget-data/me/certifications",
    { refreshInterval: 600_000 },
  )

  const certs = data?.certs || []

  return (
    <WidgetWrapper
      widgetId="my_certifications"
      title="My Certifications"
      icon={<Award className="h-4 w-4" />}
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
          No certifications on file.
        </div>
      ) : (
        <div className="space-y-1.5">
          {certs.map((c, i) => {
            const Icon = c.status === "current" ? Check : c.status === "expiring_soon" ? AlertTriangle : X
            const color =
              c.status === "current" ? "text-green-600" : c.status === "expiring_soon" ? "text-amber-600" : "text-red-600"
            return (
              <div key={i} className="flex items-center gap-2 text-sm">
                <Icon className={`h-4 w-4 ${color}`} />
                <span className="text-slate-800 flex-1">{c.cert_type}</span>
                <span className={`text-xs ${color}`}>
                  {c.status === "expired"
                    ? "Expired"
                    : c.days_remaining !== null
                      ? `${c.days_remaining}d`
                      : "—"}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </WidgetWrapper>
  )
}
