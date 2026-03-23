/**
 * Operations Board — tablet-first unified production interface.
 * Route: /console/operations
 *
 * Renders dynamically from OperationsBoardRegistry. Core features and extensions
 * register as contributors. The board never needs modification to accommodate
 * new features — new contributors register themselves and the board picks them up.
 */

import { useState, useEffect, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  Settings,
  AlertTriangle,
  Search,
  CheckCircle,
  Package,
  ClipboardList,
  Wrench,
  CheckSquare,
  ShieldAlert,
  Truck,
  RefreshCw,
  X,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useAuth } from "@/contexts/auth-context"
import { MorningBriefingCard } from "@/components/morning-briefing-card"
import apiClient from "@/lib/api-client"

// Import registry and register all contributors
import OperationsBoardRegistry from "@/services/operations-board-registry"
import "@/services/board-contributors"

import type { OperationsBoardSettings } from "@/types/operations-board"

// ── Icon map — resolves contributor icon strings to Lucide components ──

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  "alert-triangle": AlertTriangle,
  search: Search,
  "check-circle": CheckCircle,
  package: Package,
  "clipboard-list": ClipboardList,
  wrench: Wrench,
  "check-square": CheckSquare,
}

const ICON_COLORS: Record<string, string> = {
  "alert-triangle": "text-red-600",
  search: "text-amber-600",
  "check-circle": "text-blue-600",
  package: "text-green-600",
  "clipboard-list": "text-purple-600",
  wrench: "text-gray-600",
  "check-square": "text-indigo-600",
}

// ── Overview panel components — contributors reference by string key ──

function SafetyStatusPanel() {
  return (
    <Card>
      <CardContent className="p-4">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1">
          <ShieldAlert className="h-3.5 w-3.5" /> Safety
        </h3>
        <p className="text-sm text-green-600">No open incidents</p>
      </CardContent>
    </Card>
  )
}

function DriverSchedulePanel() {
  return (
    <Card>
      <CardContent className="p-4">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1">
          <Truck className="h-3.5 w-3.5" /> Today's Deliveries
        </h3>
        <p className="text-sm text-gray-400">No deliveries scheduled</p>
      </CardContent>
    </Card>
  )
}

function WorkOrdersOverviewPanel() {
  return (
    <Card>
      <CardContent className="p-4">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1">
          <CheckSquare className="h-3.5 w-3.5" /> Work Orders
        </h3>
        <p className="text-sm text-gray-400">No active work orders</p>
      </CardContent>
    </Card>
  )
}

const PANEL_COMPONENTS: Record<string, React.ComponentType> = {
  SafetyStatusPanel,
  DriverSchedulePanel,
  WorkOrdersOverviewPanel,
}

// ── Production entry type ──

interface ProductionEntry {
  id: string
  product_name_raw: string
  quantity: number
  logged_at: string | null
  logged_by_name: string
  qc_status: string
  qc_notes: string | null
  entry_method: string
  summary_id: string | null
  contributor_key: string | null
}

// ── Component ──

export default function OperationsBoardPage() {
  const { hasModule } = useAuth()
  const navigate = useNavigate()
  const [settings, setSettings] = useState<OperationsBoardSettings | null>(null)
  const [entries, setEntries] = useState<ProductionEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [showSettings, setShowSettings] = useState(false)

  // Determine active extensions
  const activeExtensions: string[] = []
  if (hasModule("work_orders")) activeExtensions.push("work_orders")
  if (hasModule("qc_module_full")) activeExtensions.push("qc_module_full")

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const [settingsRes, entriesRes] = await Promise.all([
        apiClient.get("/operations-board/settings"),
        apiClient.get("/operations-board/production-log/today"),
      ])
      setSettings(settingsRes.data)
      setEntries(entriesRes.data)
    } catch {
      toast.error("Failed to load operations board")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const patchSetting = async (key: string, value: boolean | string) => {
    try {
      await apiClient.patch("/operations-board/settings", { updates: { [key]: value } })
      setSettings((prev) => (prev ? { ...prev, [key]: value } : prev))
    } catch {
      toast.error("Failed to save setting")
    }
  }

  if (loading || !settings) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <RefreshCw className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  // ── Read everything from registry ──

  const buttons = OperationsBoardRegistry.getButtons(activeExtensions, settings)
  const panels = OperationsBoardRegistry.getOverviewPanels(activeExtensions, settings)
  const settingsGroups = OperationsBoardRegistry.getSettingsItemsByGroup(activeExtensions)

  const now = new Date()
  const timeStr = now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
  const dateStr = now.toLocaleDateString([], { month: "long", day: "numeric" })

  const totalUnits = entries.reduce((sum, e) => sum + e.quantity, 0)
  const productCount = new Set(entries.map((e) => e.product_name_raw)).size
  const isSubmitted = entries.some((e) => e.summary_id)

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b px-4 py-3 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-gray-900">Operations Board</h1>
          <p className="text-xs text-gray-500">
            {dateStr} · {timeStr}
          </p>
        </div>
        <button
          onClick={() => setShowSettings(!showSettings)}
          className="p-2 rounded-lg hover:bg-gray-100"
        >
          <Settings className="h-5 w-5 text-gray-500" />
        </button>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-4 space-y-4">
        {/* ZONE 1 — Morning Briefing */}
        {settings.zone_briefing_visible !== false && <MorningBriefingCard />}

        {/* ZONE 2 — Operations Announcements */}
        {settings.zone_announcements_visible !== false && (
          <Card className="border-amber-200 bg-amber-50/30">
            <CardContent className="p-4">
              <h3 className="text-xs font-semibold text-amber-800 uppercase tracking-wider mb-2">
                From the Office
              </h3>
              <p className="text-sm text-gray-500">
                Operations announcements will appear here.
              </p>
            </CardContent>
          </Card>
        )}

        {/* ZONE 3 — Overview Panels (from registry) */}
        {panels.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {panels.map((panel) => {
              const PanelComponent = PANEL_COMPONENTS[panel.component]
              if (!PanelComponent) return null
              return <PanelComponent key={panel.key} />
            })}
          </div>
        )}

        {/* ZONE 4 — Quick Actions Grid (from registry) */}
        {buttons.length > 0 && (
          <div
            className="grid gap-3"
            style={{
              gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
            }}
          >
            {buttons.map((btn) => {
              const Icon = ICON_MAP[btn.icon]
              const color = ICON_COLORS[btn.icon] || "text-gray-600"
              return (
                <button
                  key={btn.key}
                  onClick={() => navigate(btn.route)}
                  className="flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-gray-200 bg-white p-5 hover:border-gray-300 hover:bg-gray-50 active:bg-gray-100 transition-colors min-h-[80px]"
                >
                  {Icon && <Icon className={cn("h-7 w-7", color)} />}
                  <span className="text-sm font-semibold text-gray-700">
                    {btn.label}
                  </span>
                </button>
              )
            })}
          </div>
        )}

        {/* ZONE 5 — Today's Production Log */}
        {settings.zone_production_log_visible !== false && (
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  Today's Production
                </h3>
                <Button
                  size="sm"
                  variant="outline"
                  className="text-xs gap-1"
                  onClick={() => navigate("/console/operations/product-entry")}
                >
                  <Package className="h-3.5 w-3.5" /> Log more
                </Button>
              </div>

              {entries.length === 0 ? (
                <p className="text-sm text-gray-400 py-4 text-center">
                  No production logged yet today
                </p>
              ) : (
                <>
                  <div className="space-y-2">
                    {entries.map((e) => (
                      <div
                        key={e.id}
                        className="flex items-center justify-between text-sm py-1.5 border-b border-gray-100 last:border-0"
                      >
                        <div className="flex items-center gap-3">
                          <span className="text-xs text-gray-400 w-16">
                            {e.logged_at
                              ? new Date(e.logged_at).toLocaleTimeString([], {
                                  hour: "numeric",
                                  minute: "2-digit",
                                })
                              : "—"}
                          </span>
                          <span className="font-medium text-gray-900">
                            {e.product_name_raw}
                          </span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-gray-700">{e.quantity}</span>
                          <span
                            className={cn(
                              "text-xs px-1.5 py-0.5 rounded",
                              e.qc_status === "pass" && "bg-green-100 text-green-700",
                              e.qc_status === "fail" && "bg-red-100 text-red-700",
                              e.qc_status === "not_checked" &&
                                "bg-gray-100 text-gray-500"
                            )}
                          >
                            {e.qc_status === "pass"
                              ? "✓ QC"
                              : e.qc_status === "fail"
                                ? "✗ QC"
                                : "— QC"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-3 pt-3 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
                    <span>
                      Total: {totalUnits} units · {productCount} products
                    </span>
                    <span>
                      {isSubmitted ? (
                        <span className="text-green-600">✓ Submitted</span>
                      ) : (
                        <span>Draft — not yet submitted</span>
                      )}
                    </span>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        )}
      </div>

      {/* Settings slide-over — registry-driven */}
      {showSettings && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div
            className="absolute inset-0 bg-black/30"
            onClick={() => setShowSettings(false)}
          />
          <div className="relative w-80 bg-white shadow-xl overflow-y-auto">
            <div className="p-4 border-b flex items-center justify-between">
              <h2 className="text-sm font-semibold">Board Settings</h2>
              <button
                onClick={() => setShowSettings(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="p-4 space-y-4">
              {/* Sections group */}
              {settingsGroups.sections?.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                    Sections
                  </h3>
                  {/* Core zones not from contributors */}
                  <SettingToggle
                    label="Morning Briefing"
                    checked={settings.zone_briefing_visible !== false}
                    onChange={(v) => patchSetting("zone_briefing_visible", v)}
                  />
                  <SettingToggle
                    label="Announcements"
                    checked={settings.zone_announcements_visible !== false}
                    onChange={(v) => patchSetting("zone_announcements_visible", v)}
                  />
                  <SettingToggle
                    label="Production Log"
                    checked={settings.zone_production_log_visible !== false}
                    onChange={(v) => patchSetting("zone_production_log_visible", v)}
                  />
                  {settingsGroups.sections.map((item) => (
                    <SettingToggle
                      key={item.key}
                      label={item.label}
                      description={item.description}
                      checked={settings[item.key] !== false}
                      onChange={(v) => patchSetting(item.key, v)}
                    />
                  ))}
                </div>
              )}

              {/* Buttons group */}
              {settingsGroups.buttons?.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                    Quick Actions
                  </h3>
                  {settingsGroups.buttons.map((item) => (
                    <SettingToggle
                      key={item.key}
                      label={item.label}
                      description={item.description}
                      checked={settings[item.key] !== false}
                      onChange={(v) => patchSetting(item.key, v)}
                    />
                  ))}
                </div>
              )}

              {/* Behavior group */}
              {settingsGroups.behavior?.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                    Behavior
                  </h3>
                  {settingsGroups.behavior.map((item) => (
                    <SettingToggle
                      key={item.key}
                      label={item.label}
                      description={item.description}
                      checked={settings[item.key] !== false}
                      onChange={(v) => patchSetting(item.key, v)}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Setting toggle component ──

function SettingToggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string
  description?: string
  checked: boolean
  onChange: (value: boolean) => void
}) {
  return (
    <label className="flex items-start justify-between py-1.5 cursor-pointer">
      <div className="pr-2">
        <span className="text-sm text-gray-700">{label}</span>
        {description && (
          <p className="text-xs text-gray-400 mt-0.5">{description}</p>
        )}
      </div>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded border-gray-300 mt-0.5 shrink-0"
      />
    </label>
  )
}
