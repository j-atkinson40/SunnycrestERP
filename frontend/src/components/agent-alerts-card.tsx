/**
 * AgentAlertsCard — dashboard widget showing top unresolved
 * action_required alerts.
 *
 * Aesthetic Arc Session 3 refresh — migrated to the status-key-keyed
 * dict pattern per CLAUDE.md convention. Pre-S3 had raw color strings
 * (`color: "text-red-600"`, `bg: "bg-red-50"`). Post-S3 declares a
 * `StatusFamily` key per severity and looks up DESIGN_LANGUAGE status
 * tokens from a centralized helper — removes 3 raw-color tuples and
 * aligns with the platform's status-family vocabulary.
 *
 * Severity → family mapping:
 *   action_required → error
 *   warning         → warning
 *   info            → info
 *   (unknown)       → info fallback
 */

import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { AlertTriangle, Bell, Info, ChevronRight, type LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import apiClient from "@/lib/api-client"
import type { StatusFamily } from "@/components/ui/status-pill"

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

interface SeverityConfig {
  icon: LucideIcon
  status: StatusFamily
}

/**
 * Severity → { icon, status family }. Status family drives the
 * background + icon color at render time via DESIGN_LANGUAGE tokens.
 * Adding a new severity = one row here; no raw color strings.
 */
const SEVERITY_CONFIG: Record<string, SeverityConfig> = {
  action_required: { icon: AlertTriangle, status: "error" },
  warning: { icon: Bell, status: "warning" },
  info: { icon: Info, status: "info" },
}

/**
 * Maps a status family to its background + foreground + border
 * DESIGN_LANGUAGE status-muted / status-saturation class pair.
 * Shared pattern across banners, pills, and alert surfaces.
 */
const FAMILY_STYLES: Record<StatusFamily, { bg: string; fg: string; border: string }> = {
  error: { bg: "bg-status-error-muted", fg: "text-status-error", border: "border-status-error/30" },
  warning: { bg: "bg-status-warning-muted", fg: "text-status-warning", border: "border-status-warning/30" },
  info: { bg: "bg-status-info-muted", fg: "text-status-info", border: "border-status-info/30" },
  success: { bg: "bg-status-success-muted", fg: "text-status-success", border: "border-status-success/30" },
  neutral: { bg: "bg-surface-sunken", fg: "text-content-muted", border: "border-border-subtle" },
}

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
      <CardContent>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-micro font-medium uppercase tracking-wider text-content-subtle flex items-center gap-1.5">
            <Bell className="h-3.5 w-3.5" /> Agent Alerts
          </h3>
          <button
            onClick={() => navigate("/alerts")}
            className="rounded-sm text-caption text-content-muted transition-colors duration-quick ease-settle hover:text-content-strong focus-ring-brass flex items-center gap-0.5"
          >
            View all <ChevronRight className="h-3 w-3" />
          </button>
        </div>

        <div className="space-y-2">
          {displayAlerts.map((alert) => {
            const config = SEVERITY_CONFIG[alert.severity] ?? SEVERITY_CONFIG.info
            const Icon = config.icon
            const styles = FAMILY_STYLES[config.status]
            return (
              <div
                key={alert.id}
                className={cn(
                  "rounded-md border p-3 transition-colors duration-quick ease-settle",
                  styles.border,
                  styles.bg,
                )}
              >
                <div className="flex items-start gap-2.5">
                  <Icon className={cn("h-4 w-4 mt-0.5 shrink-0", styles.fg)} />
                  <div className="flex-1 min-w-0">
                    <p className="text-body-sm font-medium text-content-strong">{alert.title}</p>
                    <p className="text-caption text-content-muted mt-0.5 line-clamp-2">{alert.message}</p>
                    <div className="flex items-center gap-2 mt-2">
                      {alert.action_label && alert.action_url && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 text-caption"
                          onClick={() => navigate(alert.action_url!)}
                        >
                          {alert.action_label}
                        </Button>
                      )}
                      {alert.severity === "info" && (
                        <button
                          onClick={() => handleResolve(alert.id)}
                          className="rounded-sm text-caption text-content-muted transition-colors duration-quick ease-settle hover:text-content-strong focus-ring-brass"
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
