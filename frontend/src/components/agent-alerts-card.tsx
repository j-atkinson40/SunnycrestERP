/**
 * AgentAlertsCard — dashboard widget showing top unresolved action_required alerts.
 */

import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { AlertTriangle, Bell, Info, ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"
import apiClient from "@/lib/api-client"

interface Alert {
  id: string
  alert_type: string
  severity: string
  title: string
  message: string
  action_label: string | null
  action_url: string | null
  resolved: boolean
  created_at: string | null
}

const SEVERITY_CONFIG = {
  action_required: { icon: AlertTriangle, color: "text-red-600", bg: "bg-red-50", border: "border-red-200" },
  warning: { icon: Bell, color: "text-amber-600", bg: "bg-amber-50", border: "border-amber-200" },
  info: { icon: Info, color: "text-blue-600", bg: "bg-blue-50", border: "border-blue-200" },
} as const

export function AgentAlertsCard() {
  const navigate = useNavigate()
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiClient
      .get("/agents/alerts", { params: { resolved: false, limit: 5 } })
      .then((res) => setAlerts(res.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const handleResolve = async (alertId: string) => {
    try {
      await apiClient.post(`/agents/alerts/${alertId}/resolve`)
      setAlerts((prev) => prev.filter((a) => a.id !== alertId))
    } catch {}
  }

  if (loading || alerts.length === 0) return null

  const actionAlerts = alerts.filter((a) => a.severity === "action_required")
  const otherAlerts = alerts.filter((a) => a.severity !== "action_required")
  const displayAlerts = [...actionAlerts, ...otherAlerts].slice(0, 3)

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-1.5">
            <Bell className="h-3.5 w-3.5" /> Agent Alerts
          </h3>
          <button
            onClick={() => navigate("/alerts")}
            className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-0.5"
          >
            View all <ChevronRight className="h-3 w-3" />
          </button>
        </div>

        <div className="space-y-2">
          {displayAlerts.map((alert) => {
            const config = SEVERITY_CONFIG[alert.severity as keyof typeof SEVERITY_CONFIG] || SEVERITY_CONFIG.info
            const Icon = config.icon
            return (
              <div
                key={alert.id}
                className={cn("rounded-lg border p-3", config.border, config.bg)}
              >
                <div className="flex items-start gap-2.5">
                  <Icon className={cn("h-4 w-4 mt-0.5 shrink-0", config.color)} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900">{alert.title}</p>
                    <p className="text-xs text-gray-600 mt-0.5 line-clamp-2">{alert.message}</p>
                    <div className="flex items-center gap-2 mt-2">
                      {alert.action_label && alert.action_url && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 text-xs"
                          onClick={() => navigate(alert.action_url!)}
                        >
                          {alert.action_label}
                        </Button>
                      )}
                      {alert.severity === "info" && (
                        <button
                          onClick={() => handleResolve(alert.id)}
                          className="text-xs text-gray-400 hover:text-gray-600"
                        >
                          Dismiss
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
