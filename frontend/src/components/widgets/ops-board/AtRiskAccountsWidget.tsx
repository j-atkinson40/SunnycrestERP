import { AlertTriangle, ChevronRight } from "lucide-react"
import { useNavigate } from "react-router-dom"
import WidgetWrapper from "../WidgetWrapper"
import { useWidgetData } from "../useWidgetData"
import type { WidgetProps } from "../types"

interface AtRiskAccount {
  id: string
  name: string
  reason: string
}

export default function AtRiskAccountsWidget(props: WidgetProps) {
  const navigate = useNavigate()
  const { data, isLoading, error, refresh } = useWidgetData<{
    count: number
    accounts: AtRiskAccount[]
  }>("/widget-data/crm/at-risk-summary", { refreshInterval: 600_000 })

  return (
    <WidgetWrapper
      widgetId="at_risk_accounts"
      title="At-Risk Accounts"
      icon={<AlertTriangle className="h-4 w-4" />}
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
          {data.count === 0 ? (
            <div className="text-center py-2">
              <div className="text-2xl font-bold text-green-600">0</div>
              <div className="text-xs text-gray-500">All accounts healthy</div>
            </div>
          ) : (
            <>
              <div>
                <div className="text-2xl font-bold text-red-600">{data.count}</div>
                <div className="text-xs text-gray-500">Accounts need attention</div>
              </div>
              <div className="space-y-1.5">
                {data.accounts.slice(0, 3).map((a) => (
                  <button
                    key={a.id}
                    onClick={() => navigate(`/vault/crm/companies/${a.id}`)}
                    className="flex items-center gap-2 w-full rounded-md px-2 py-1 text-left hover:bg-gray-50"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-gray-800 truncate">{a.name}</div>
                      <div className="text-xs text-red-500 truncate">{a.reason}</div>
                    </div>
                    <ChevronRight className="h-3 w-3 text-gray-400 shrink-0" />
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </WidgetWrapper>
  )
}
