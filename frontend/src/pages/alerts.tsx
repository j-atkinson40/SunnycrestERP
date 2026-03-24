/**
 * Full alerts page — /alerts
 * Shows all agent alerts with filtering by severity and resolved status.
 */

import { useState, useEffect, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { AlertTriangle, Bell, Info, CheckCircle, Filter } from "lucide-react"
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
  action_payload: Record<string, unknown> | null
  resolved: boolean
  auto_resolved: boolean
  created_at: string | null
}

const SEVERITY_STYLES = {
  action_required: { icon: AlertTriangle, color: "text-red-600", bg: "bg-red-50", border: "border-red-200", label: "Action Required" },
  warning: { icon: Bell, color: "text-amber-600", bg: "bg-amber-50", border: "border-amber-200", label: "Warning" },
  info: { icon: Info, color: "text-blue-600", bg: "bg-blue-50", border: "border-blue-200", label: "Info" },
} as const

export default function AlertsPage() {
  const navigate = useNavigate()
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)
  const [severityFilter, setSeverityFilter] = useState<string | null>(null)
  const [showResolved, setShowResolved] = useState(false)

  const fetchAlerts = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, unknown> = { limit: 200 }
      if (severityFilter) params.severity = severityFilter
      if (!showResolved) params.resolved = false
      const res = await apiClient.get("/agents/alerts", { params })
      setAlerts(res.data)
    } catch {
      toast.error("Failed to load alerts")
    } finally {
      setLoading(false)
    }
  }, [severityFilter, showResolved])

  useEffect(() => { fetchAlerts() }, [fetchAlerts])

  const handleResolve = async (id: string) => {
    try {
      await apiClient.post(`/agents/alerts/${id}/resolve`)
      setAlerts((prev) => prev.map((a) => a.id === id ? { ...a, resolved: true } : a))
    } catch {
      toast.error("Failed to resolve alert")
    }
  }

  const resolveAllInfo = async () => {
    const infoAlerts = alerts.filter((a) => a.severity === "info" && !a.resolved)
    for (const alert of infoAlerts) {
      await apiClient.post(`/agents/alerts/${alert.id}/resolve`).catch(() => {})
    }
    fetchAlerts()
    toast.success(`${infoAlerts.length} info alerts dismissed`)
  }

  const unresolvedCount = alerts.filter((a) => !a.resolved).length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Agent Alerts</h1>
          <p className="text-sm text-gray-500 mt-1">
            {unresolvedCount} unresolved alerts
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={resolveAllInfo} className="text-xs">
            Dismiss all info
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        <Filter className="h-4 w-4 text-gray-400" />
        {[null, "action_required", "warning", "info"].map((sev) => (
          <button
            key={sev || "all"}
            onClick={() => setSeverityFilter(sev)}
            className={cn(
              "px-3 py-1 rounded-full text-xs font-medium transition-colors",
              severityFilter === sev
                ? "bg-gray-900 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            )}
          >
            {sev ? (SEVERITY_STYLES[sev as keyof typeof SEVERITY_STYLES]?.label || sev) : "All"}
          </button>
        ))}
        <label className="flex items-center gap-1.5 ml-4 text-xs text-gray-500">
          <input
            type="checkbox"
            checked={showResolved}
            onChange={(e) => setShowResolved(e.target.checked)}
            className="h-3.5 w-3.5 rounded border-gray-300"
          />
          Show resolved
        </label>
      </div>

      {/* Alert list */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-300 border-t-gray-600" />
        </div>
      ) : alerts.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <CheckCircle className="mx-auto h-10 w-10 text-green-300 mb-3" />
            <p className="text-sm text-gray-600">No alerts to show</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {alerts.map((alert) => {
            const config = SEVERITY_STYLES[alert.severity as keyof typeof SEVERITY_STYLES] || SEVERITY_STYLES.info
            const Icon = config.icon
            return (
              <Card
                key={alert.id}
                className={cn(
                  "transition-opacity",
                  alert.resolved && "opacity-50",
                  !alert.resolved && config.border
                )}
              >
                <CardContent className={cn("p-4", !alert.resolved && config.bg)}>
                  <div className="flex items-start gap-3">
                    <Icon className={cn("h-4 w-4 mt-0.5 shrink-0", alert.resolved ? "text-gray-400" : config.color)} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <p className={cn("text-sm font-medium", alert.resolved ? "text-gray-500" : "text-gray-900")}>
                          {alert.title}
                        </p>
                        <span className="text-xs text-gray-400 whitespace-nowrap">
                          {alert.created_at ? new Date(alert.created_at).toLocaleDateString() : ""}
                        </span>
                      </div>
                      <p className="text-xs text-gray-600 mt-0.5">{alert.message}</p>
                      {!alert.resolved && (
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
                          <button
                            onClick={() => handleResolve(alert.id)}
                            className="text-xs text-gray-400 hover:text-gray-600"
                          >
                            {alert.severity === "info" ? "Dismiss" : "Resolve"}
                          </button>
                        </div>
                      )}
                      {alert.resolved && (
                        <span className="inline-flex items-center gap-1 text-xs text-gray-400 mt-1">
                          <CheckCircle className="h-3 w-3" />
                          {alert.auto_resolved ? "Auto-resolved" : "Resolved"}
                        </span>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
