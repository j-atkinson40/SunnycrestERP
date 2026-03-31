/**
 * Operations Board — mobile-first production interface.
 * Route: /console/operations
 *
 * Renders dynamically from OperationsBoardRegistry. Core features and extensions
 * register as contributors. The board never needs modification to accommodate
 * new features — new contributors register themselves and the board picks them up.
 */

import { useState, useEffect, useCallback, useRef } from "react"
import { useNavigate } from "react-router-dom"
import { cn } from "@/lib/utils"
import { useAuth } from "@/contexts/auth-context"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import {
  AlertTriangle,
  CheckCircle,
  Package,
  ClipboardList,
  Wrench,
  Search,
  RefreshCw,
  PackageCheck,
  ChevronRight,
  Settings,
  Truck,
  AlertCircle,
  RotateCcw,
  X,
  ShieldAlert,
  CheckSquare,
} from "lucide-react"
import OpsContextCard from "@/components/mobile/ops-context-card"
import offlineQueue from "@/services/offline-queue"
import "@/styles/mobile-console.css"

// Import registry and register all contributors
import OperationsBoardRegistry from "@/services/operations-board-registry"
import "@/services/board-contributors"

import type { OperationsBoardSettings } from "@/types/operations-board"
import { VaultReplenishmentWidget } from "@/components/dashboard/vault-replenishment-widget"

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
    <div className="mobile-card">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1">
        <ShieldAlert className="h-3.5 w-3.5" /> Safety
      </h3>
      <p className="text-sm text-green-600">No open incidents</p>
    </div>
  )
}

function DriverSchedulePanel() {
  return (
    <div className="mobile-card">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1">
        <Truck className="h-3.5 w-3.5" /> Today's Deliveries
      </h3>
      <p className="text-sm text-gray-400">No deliveries scheduled</p>
    </div>
  )
}

function WorkOrdersOverviewPanel() {
  return (
    <div className="mobile-card">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1">
        <CheckSquare className="h-3.5 w-3.5" /> Work Orders
      </h3>
      <p className="text-sm text-gray-400">No active work orders</p>
    </div>
  )
}

const PANEL_COMPONENTS: Record<string, React.ComponentType> = {
  SafetyStatusPanel,
  DriverSchedulePanel,
  WorkOrdersOverviewPanel,
  VaultReplenishmentWidget,
}

// ── Production entry type ──

interface ProductionEntry {
  id: string
  product_name_raw: string
  product_name?: string
  quantity: number
  logged_at: string | null
  logged_by_name: string
  qc_status: string
  qc_notes: string | null
  entry_method: string
  summary_id: string | null
  contributor_key: string | null
}

// ── Expected PO type ──

interface ExpectedPO {
  id: string
  po_number: string
  vendor_name: string
  total_amount: number
  expected_delivery_date: string | null
  status: string
}

// ── ActionTile sub-component ──

function ActionTile({
  icon,
  label,
  onClick,
  color,
}: {
  icon: React.ReactNode
  label: string
  onClick: () => void
  color: string
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "mobile-action-tile border-2 p-4 w-full flex flex-col items-center justify-center gap-2 rounded-xl",
        color,
      )}
    >
      {icon}
      <span className="text-sm font-semibold text-gray-700">{label}</span>
    </button>
  )
}

// ── ProductionSummaryCard ──

function ProductionSummaryCard({
  entries,
  onLog,
}: {
  entries: ProductionEntry[]
  onLog: () => void
}) {
  const totalUnits = entries.reduce((sum, e) => sum + (e.quantity || 0), 0)
  const isAfter8am = new Date().getHours() >= 8

  return (
    <div className="mobile-card mb-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
          Today's Production
        </h3>
        {entries.length > 0 && (
          <button onClick={onLog} className="text-sm text-blue-600 font-medium">
            Edit
          </button>
        )}
      </div>

      {entries.length > 0 ? (
        <>
          {entries.map((e, i) => (
            <div
              key={e.id || i}
              className="flex justify-between items-center py-2 border-b border-gray-100 last:border-0"
            >
              <span className="text-base text-gray-800">
                {e.product_name_raw || e.product_name}
              </span>
              <span className="text-lg font-bold text-gray-900">{e.quantity}</span>
            </div>
          ))}
          <div className="flex justify-between items-center pt-3 mt-1">
            <span className="font-semibold text-gray-700">Total</span>
            <span className="text-xl font-bold text-gray-900">{totalUnits} units</span>
          </div>
        </>
      ) : (
        <div className="py-4 text-center">
          {isAfter8am ? (
            <>
              <p className="text-gray-400 mb-4">Nothing logged yet</p>
              <button
                onClick={onLog}
                className="mobile-primary-btn bg-blue-600 text-white px-6 py-2 rounded-xl font-semibold text-sm"
              >
                Log Today's Production
              </button>
            </>
          ) : (
            <p className="text-gray-400">Production logging opens at 8am</p>
          )}
        </div>
      )}
    </div>
  )
}

// ── ReceivingCard ──

function ReceivingCard({
  expectedPOs,
  navigate,
}: {
  expectedPOs: ExpectedPO[]
  navigate: (p: string) => void
}) {
  if (expectedPOs.length === 0) return null

  const todayStr = new Date().toISOString().split("T")[0]

  return (
    <div className="mobile-card border-blue-200 bg-blue-50/50 mb-4">
      <h3 className="text-xs font-semibold text-blue-700 uppercase tracking-wider mb-3 flex items-center gap-1.5">
        <PackageCheck className="h-3.5 w-3.5" />
        Deliveries Expected ({expectedPOs.length})
      </h3>
      {expectedPOs.map((po) => (
        <div
          key={po.id}
          className="bg-white rounded-xl border border-blue-200 p-4 mb-2"
        >
          <div className="flex justify-between items-start">
            <div>
              <p className="font-bold text-base">{po.vendor_name}</p>
              <p className="text-sm text-gray-500">PO #{po.po_number}</p>
            </div>
            <span className="text-sm font-medium">
              ${po.total_amount?.toLocaleString()}
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Expected{" "}
            {po.expected_delivery_date === todayStr ? "today" : "tomorrow"}
          </p>
          <button
            onClick={() => navigate(`/console/operations/receive/${po.id}`)}
            className="mt-3 w-full py-3 bg-blue-600 text-white rounded-xl font-semibold text-sm flex items-center justify-center gap-2"
          >
            <PackageCheck className="h-4 w-4" /> Receive Delivery
          </button>
        </div>
      ))}
    </div>
  )
}

// ── DeliveriesCard ──

interface DeliveryItem {
  id: string
  funeral_home_name?: string
  customer_name?: string
  address?: string
  status?: string
}

function DeliveriesCard({
  navigate,
}: {
  navigate: (p: string) => void
}) {
  const [deliveries, setDeliveries] = useState<DeliveryItem[]>([])

  useEffect(() => {
    const todayStr = new Date().toISOString().split("T")[0]
    apiClient
      .get<DeliveryItem[]>(`/deliveries?date=${todayStr}`)
      .then((r) => setDeliveries(r.data || []))
      .catch(() => {})
  }, [])

  if (deliveries.length === 0) return null

  return (
    <div className="mobile-card mb-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-1.5">
          <Truck className="h-3.5 w-3.5" />
          Today's Deliveries ({deliveries.length})
        </h3>
        <button
          onClick={() => navigate("/deliveries")}
          className="text-sm text-blue-600 font-medium flex items-center gap-0.5"
        >
          All <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
      {deliveries.slice(0, 3).map((d) => (
        <div
          key={d.id}
          className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0"
        >
          <div>
            <p className="text-sm font-medium text-gray-900">
              {d.funeral_home_name || d.customer_name || "Delivery"}
            </p>
            {d.address && (
              <p className="text-xs text-gray-400">{d.address}</p>
            )}
          </div>
          <span
            className={cn(
              "text-xs px-2 py-0.5 rounded-full font-medium",
              d.status === "delivered"
                ? "bg-green-100 text-green-700"
                : d.status === "in_transit"
                  ? "bg-blue-100 text-blue-700"
                  : "bg-gray-100 text-gray-500",
            )}
          >
            {d.status ?? "scheduled"}
          </span>
        </div>
      ))}
    </div>
  )
}

// ── EODPromptCard ──

function EODPromptCard({
  productionLogged,
  onClick,
}: {
  productionLogged: boolean
  onClick: () => void
}) {
  return (
    <div className="mobile-card border-amber-300 bg-amber-50 mb-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-amber-900 mb-1">
            Ready to close out today?
          </h3>
          <p className="text-sm text-amber-700">
            {productionLogged
              ? "Production logged. Submit your end-of-day report."
              : "Don't forget to log today's production before closing out."}
          </p>
        </div>
        <AlertCircle className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
      </div>
      <button
        onClick={onClick}
        className="mt-3 w-full py-3 bg-amber-500 text-white rounded-xl font-semibold text-sm"
      >
        End of Day Report
      </button>
    </div>
  )
}

// ── Setting toggle ──

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

// ── Main Component ──

export default function OperationsBoardPage() {
  const { hasModule, company } = useAuth()
  const navigate = useNavigate()

  const [settings, setSettings] = useState<OperationsBoardSettings | null>(null)
  const [todayEntries, setTodayEntries] = useState<ProductionEntry[]>([])
  const [expectedPOs, setExpectedPOs] = useState<ExpectedPO[]>([])
  const [loading, setLoading] = useState(true)
  const [showSettings, setShowSettings] = useState(false)
  const [pendingCount, setPendingCount] = useState(0)
  const [currentTime, setCurrentTime] = useState("")
  const [todayDate, setTodayDate] = useState("")

  const now = new Date()
  const isAfternoon = now.getHours() >= 14
  const todayKey = now.toISOString().slice(0, 10)
  const eodSubmitted =
    typeof localStorage !== "undefined" &&
    localStorage.getItem(`eod-submitted-${todayKey}`) === "true"

  // Determine active extensions
  const activeExtensions: string[] = []
  if (hasModule("work_orders")) activeExtensions.push("work_orders")
  if (hasModule("qc_module_full")) activeExtensions.push("qc_module_full")
  if (
    company?.vault_fulfillment_mode === "purchase" ||
    company?.vault_fulfillment_mode === "hybrid"
  ) {
    activeExtensions.push("vault_purchase_mode")
  }

  // Clock updater
  useEffect(() => {
    function updateClock() {
      const d = new Date()
      setCurrentTime(
        d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }),
      )
      setTodayDate(
        d.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" }),
      )
    }
    updateClock()
    const interval = setInterval(updateClock, 60_000)
    return () => clearInterval(interval)
  }, [])

  // Pending count from offline queue
  useEffect(() => {
    offlineQueue.getPendingCount().then(setPendingCount)

    function handleQueueUpdate() {
      offlineQueue.getPendingCount().then(setPendingCount)
    }
    window.addEventListener("queue-updated", handleQueueUpdate)
    return () => window.removeEventListener("queue-updated", handleQueueUpdate)
  }, [])

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const [settingsRes, entriesRes] = await Promise.all([
        apiClient.get("/operations-board/settings"),
        apiClient.get("/operations-board/production-log/today"),
      ])
      setSettings(settingsRes.data)
      setTodayEntries(entriesRes.data)
    } catch {
      toast.error("Failed to load operations board")
    } finally {
      setLoading(false)
    }
  }, [])

  // Fetch expected POs
  useEffect(() => {
    apiClient
      .get("/purchasing/orders")
      .then((r) => {
        const tomorrow = new Date(Date.now() + 86_400_000)
          .toISOString()
          .split("T")[0]
        const expected = (r.data as ExpectedPO[]).filter(
          (p) =>
            p.expected_delivery_date &&
            p.expected_delivery_date <= tomorrow &&
            ["approved", "sent", "partially_received"].includes(p.status),
        )
        setExpectedPOs(expected)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const patchSetting = async (key: string, value: boolean | string) => {
    try {
      await apiClient.patch("/operations-board/settings", {
        updates: { [key]: value },
      })
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

  // Read from registry
  const panels = OperationsBoardRegistry.getOverviewPanels(activeExtensions, settings)
  const settingsGroups = OperationsBoardRegistry.getSettingsItemsByGroup(activeExtensions)

  return (
    <div className="mobile-page-container min-h-screen bg-gray-50">
      {/* HEADER */}
      <div className="flex items-center justify-between pt-4 pb-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Operations</h1>
          <p className="text-sm text-gray-500">
            {currentTime} · {todayDate}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Sync status */}
          {pendingCount > 0 ? (
            <div className="flex items-center gap-1 bg-amber-100 text-amber-700 px-3 py-1.5 rounded-full text-sm font-medium">
              <RotateCcw className="h-3.5 w-3.5 animate-spin" />
              {pendingCount} pending
            </div>
          ) : (
            <div className="flex items-center gap-1 text-green-600 text-sm">
              <CheckCircle className="h-4 w-4" />
              Synced
            </div>
          )}
          <button
            onClick={() => setShowSettings(true)}
            className="p-2 rounded-xl bg-white border border-gray-200"
          >
            <Settings className="h-5 w-5 text-gray-600" />
          </button>
        </div>
      </div>

      {/* CONTEXT CARD (AI briefing) */}
      <div className="mb-4">
        <OpsContextCard />
      </div>

      {/* Overview panels from registry (e.g. vault replenishment) */}
      {panels.length > 0 && (
        <div className="grid grid-cols-1 gap-3 mb-4">
          {panels.map((panel) => {
            const PanelComponent = PANEL_COMPONENTS[panel.component]
            if (!PanelComponent) return null
            return <PanelComponent key={panel.key} />
          })}
        </div>
      )}

      {/* PRODUCTION SUMMARY CARD */}
      <ProductionSummaryCard
        entries={todayEntries}
        onLog={() => navigate("/console/operations/product-entry")}
      />

      {/* RECEIVING ZONE — PO deliveries */}
      <ReceivingCard expectedPOs={expectedPOs} navigate={navigate} />

      {/* QUICK ACTION GRID — 2x2 */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <ActionTile
          icon={<AlertTriangle className="h-8 w-8 text-red-500" />}
          label="Safety Log"
          onClick={() => navigate("/console/operations/incident")}
          color="bg-red-50 border-red-200"
        />
        <ActionTile
          icon={<CheckCircle className="h-8 w-8 text-blue-500" />}
          label="QC Check"
          onClick={() => navigate("/console/operations/qc")}
          color="bg-blue-50 border-blue-200"
        />
        <ActionTile
          icon={<Wrench className="h-8 w-8 text-gray-600" />}
          label="Inspection"
          onClick={() => navigate("/console/operations/inspection")}
          color="bg-gray-50 border-gray-200"
        />
        <ActionTile
          icon={<ClipboardList className="h-8 w-8 text-purple-500" />}
          label="End of Day"
          onClick={() => navigate("/console/operations/end-of-day")}
          color="bg-purple-50 border-purple-200"
        />
      </div>

      {/* TODAY'S DELIVERIES */}
      <DeliveriesCard navigate={navigate} />

      {/* END OF DAY PROMPT — shown after 2pm */}
      {isAfternoon && !eodSubmitted && (
        <EODPromptCard
          productionLogged={todayEntries.length > 0}
          onClick={() => navigate("/console/operations/end-of-day")}
        />
      )}

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
