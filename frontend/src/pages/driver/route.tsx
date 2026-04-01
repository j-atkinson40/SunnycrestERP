// route.tsx — Driver route page with collapsed/expanded delivery cards.

import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { driverService } from "@/services/driver-service"
import { getApiErrorMessage } from "@/lib/api-error"
import apiClient from "@/lib/api-client"
import offlineQueue from "@/services/offline-queue"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { toast } from "sonner"
import {
  getDeliveryTypeName,
} from "@/lib/delivery-types"
import type {
  DeliveryRoute,
  DeliveryStop,
  DeliveryListItem,
  DriverPortalSettings,
} from "@/types/delivery"
import {
  ChevronDown,
  ChevronUp,
  Navigation,
  Phone,
  AlertTriangle,
  CheckCircle,
  WifiOff,
} from "lucide-react"

// ── Helpers ──────────────────────────────────────────────────────────────────

function serviceLocationIcon(loc?: string): string {
  switch (loc) {
    case "church": return "⛪"
    case "funeral_home": return "🏛"
    case "graveside": return "⚰"
    default: return "📍"
  }
}

function serviceLocationLabel(loc?: string, other?: string): string {
  switch (loc) {
    case "church": return "Church"
    case "funeral_home": return "Funeral Home"
    case "graveside": return "Graveside"
    case "other": return other || "Other"
    default: return ""
  }
}

function etaCountdown(etaStr?: string, serviceTimeStr?: string): { text: string; color: string } | null {
  const timeStr = etaStr || serviceTimeStr
  if (!timeStr || !timeStr.includes(":")) return null
  const [h, m] = timeStr.split(":").map(Number)
  const now = new Date()
  const target = new Date()
  target.setHours(h, m, 0, 0)
  const diffMin = Math.round((target.getTime() - now.getTime()) / 60000)
  if (diffMin < -30) return null // too far past
  if (diffMin < 0) return { text: `${Math.abs(diffMin)}m ago`, color: "text-red-600" }
  if (diffMin < 60) return { text: `${diffMin}m`, color: "text-amber-600" }
  const hrs = Math.floor(diffMin / 60)
  const mins = diffMin % 60
  return { text: `${hrs}h ${mins}m`, color: "text-green-600" }
}

function cemeteryDisplay(d: DeliveryListItem): { name: string; location: string } {
  const name = d.cemetery_name || ""
  const parts = [d.cemetery_city, d.cemetery_state].filter(Boolean)
  return { name, location: parts.join(", ") }
}

function borderColor(status: string): string {
  switch (status) {
    case "en_route": return "border-l-amber-500"
    case "arrived": case "in_progress": return "border-l-blue-500"
    case "completed": return "border-l-green-500"
    default: return "border-l-gray-300"
  }
}

function mapsUrl(address?: string | null): string {
  if (!address) return "#"
  const encoded = encodeURIComponent(address)
  // iOS opens Apple Maps, Android opens Google Maps
  return `https://maps.google.com/maps?daddr=${encoded}`
}

// ── Component ────────────────────────────────────────────────────────────────

export default function DriverRoutePage() {
  const navigate = useNavigate()
  const [route, setRoute] = useState<DeliveryRoute | null>(null)
  const [settings, setSettings] = useState<DriverPortalSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [expandedStopId, setExpandedStopId] = useState<string | null>(null)
  const [checkedEquipment, setCheckedEquipment] = useState<Record<string, Set<number>>>({})
  const [isOffline, setIsOffline] = useState(!navigator.onLine)
  const [updating, setUpdating] = useState<string | null>(null)
  const [showExceptionFor, setShowExceptionFor] = useState<string | null>(null)
  const [exceptionItems, setExceptionItems] = useState<{ desc: string; checked: boolean; reason: string; notes: string }[]>([])

  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      const [r, s] = await Promise.all([
        driverService.getTodayRoute(),
        driverService.getPortalSettings(),
      ])
      setRoute(r)
      setSettings(s)
    } catch (err) {
      toast.error(getApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  useEffect(() => {
    const on = () => setIsOffline(false)
    const off = () => setIsOffline(true)
    window.addEventListener("online", on)
    window.addEventListener("offline", off)
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off) }
  }, [])

  // ── Actions ────────────────────────────────────────────────────────────

  async function handleStatusUpdate(stopId: string, newStatus: string) {
    setUpdating(stopId)
    try {
      await driverService.updateStopStatus(stopId, newStatus)
      toast.success(`Stop marked as ${newStatus}`)
      loadData()
    } catch {
      // Offline fallback
      if (!navigator.onLine) {
        await offlineQueue.enqueue("driver_stop_status" as Parameters<typeof offlineQueue.enqueue>[0], {
          stop_id: stopId,
          status: newStatus,
        })
        toast.success("Queued — will sync when connected")
        // Optimistic update
        setRoute((prev) => {
          if (!prev) return prev
          return {
            ...prev,
            stops: prev.stops.map((s) =>
              s.id === stopId ? { ...s, status: newStatus } : s
            ),
          }
        })
      } else {
        toast.error("Failed to update stop")
      }
    } finally {
      setUpdating(null)
    }
  }

  async function handleSubmitException(stopId: string) {
    const checked = exceptionItems.filter((i) => i.checked)
    if (checked.length === 0) return
    try {
      await apiClient.post(`/driver/stops/${stopId}/exception`, {
        exceptions: checked.map((i) => ({
          item_description: i.desc,
          reason: i.reason,
          notes: i.notes || null,
        })),
      })
      toast.success("Exception reported")
    } catch {
      toast.error("Failed to submit exception")
    }
    setShowExceptionFor(null)
    handleStatusUpdate(stopId, "completed")
  }

  function toggleEquipment(stopId: string, idx: number) {
    setCheckedEquipment((prev) => {
      const set = new Set(prev[stopId] || [])
      if (set.has(idx)) set.delete(idx)
      else set.add(idx)
      return { ...prev, [stopId]: set }
    })
  }

  function toggleExpand(stopId: string) {
    setExpandedStopId((prev) => (prev === stopId ? null : stopId))
  }

  // ── Render ─────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex h-48 items-center justify-center">
        <p className="text-muted-foreground">Loading route...</p>
      </div>
    )
  }

  if (!route) {
    return (
      <div className="space-y-4 p-6 text-center">
        <h1 className="text-xl font-bold">No route today</h1>
        <Button onClick={() => navigate("/driver")}>Back</Button>
      </div>
    )
  }

  const activeStops = route.stops.filter((s) => s.status !== "completed" && s.status !== "skipped")
  const completedStops = route.stops.filter((s) => s.status === "completed" || s.status === "skipped")
  const completedCount = completedStops.length
  const totalStops = route.stops.length
  const allComplete = completedCount === totalStops && totalStops > 0

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      {/* Offline banner */}
      {isOffline && (
        <div className="bg-amber-100 text-amber-800 text-sm px-4 py-2 flex items-center gap-2">
          <WifiOff className="h-4 w-4" />
          You're offline — actions will sync when connected
        </div>
      )}

      {/* Header */}
      <div className="bg-white border-b px-4 py-3">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold">Today's Route</h1>
            <p className="text-sm text-muted-foreground">
              {new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}
              {" · "}{totalStops} stop{totalStops !== 1 ? "s" : ""}
              {completedCount > 0 && ` · ${completedCount} complete`}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => navigate("/driver")}>
            Back
          </Button>
        </div>
        {/* Progress bar */}
        {totalStops > 0 && (
          <div className="mt-2 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 rounded-full transition-all"
              style={{ width: `${(completedCount / totalStops) * 100}%` }}
            />
          </div>
        )}
      </div>

      {/* Active stops */}
      <div className="px-4 pt-4 space-y-3">
        {activeStops.map((stop) => (
          <StopCard
            key={stop.id}
            stop={stop}
            settings={settings}
            isExpanded={expandedStopId === stop.id}
            onToggle={() => toggleExpand(stop.id)}
            onStatusUpdate={(status) => handleStatusUpdate(stop.id, status)}
            updating={updating === stop.id}
            checkedEquipment={checkedEquipment[stop.id] || new Set()}
            onToggleEquipment={(idx) => toggleEquipment(stop.id, idx)}
            showException={showExceptionFor === stop.id}
            onShowException={() => {
              const d = stop.delivery
              const items = (d?.equipment_lines || []).map((l) => ({
                desc: l.description, checked: false, reason: "other", notes: "",
              }))
              if (items.length === 0) items.push({ desc: "Delivery", checked: false, reason: "other", notes: "" })
              setExceptionItems(items)
              setShowExceptionFor(stop.id)
            }}
            onCancelException={() => setShowExceptionFor(null)}
            exceptionItems={exceptionItems}
            onExceptionItemChange={(items) => setExceptionItems(items)}
            onSubmitException={() => handleSubmitException(stop.id)}
          />
        ))}
      </div>

      {/* Completed stops */}
      {completedStops.length > 0 && (
        <div className="px-4 pt-6">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
            Completed ({completedStops.length})
          </p>
          <div className="space-y-2 opacity-60">
            {completedStops.map((stop) => (
              <div
                key={stop.id}
                className={`rounded-lg border-l-4 ${borderColor("completed")} bg-white p-3 border border-gray-100`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-sm">{stop.delivery?.customer_name || "Delivery"}</p>
                    {stop.delivery?.cemetery_name && (
                      <p className="text-xs text-gray-500">{stop.delivery.cemetery_name}</p>
                    )}
                  </div>
                  <span className="text-xs text-green-600 flex items-center gap-1">
                    <CheckCircle className="h-3 w-3" /> Delivered
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* All complete */}
      {allComplete && (
        <div className="px-4 pt-6">
          <Button className="w-full" onClick={() => navigate("/driver/mileage")}>
            Complete Route
          </Button>
        </div>
      )}
    </div>
  )
}

// ── StopCard ─────────────────────────────────────────────────────────────────

function StopCard({
  stop,
  settings,
  isExpanded,
  onToggle,
  onStatusUpdate,
  updating,
  checkedEquipment,
  onToggleEquipment,
  showException,
  onShowException,
  onCancelException,
  exceptionItems,
  onExceptionItemChange,
  onSubmitException,
}: {
  stop: DeliveryStop
  settings: DriverPortalSettings | null
  isExpanded: boolean
  onToggle: () => void
  onStatusUpdate: (status: string) => void
  updating: boolean
  checkedEquipment: Set<number>
  onToggleEquipment: (idx: number) => void
  showException: boolean
  onShowException: () => void
  onCancelException: () => void
  exceptionItems: { desc: string; checked: boolean; reason: string; notes: string }[]
  onExceptionItemChange: (items: typeof exceptionItems) => void
  onSubmitException: () => void
}) {
  const d = stop.delivery
  if (!d) return null

  const isFuneral = d.delivery_type === "funeral_vault"
  const cem = cemeteryDisplay(d)
  const countdown = etaCountdown(d.eta, d.service_time)
  const locLabel = serviceLocationLabel(d.service_location, d.service_location_other)
  const locIcon = serviceLocationIcon(d.service_location)
  const equipmentSummary = d.equipment_lines?.map((l) => l.description).join(" · ") || ""
  const vaultLine = [d.vault_type, equipmentSummary].filter(Boolean).join(" · ")

  const allEquipmentChecked =
    !settings?.show_equipment_checklist ||
    !d.equipment_lines?.length ||
    d.equipment_lines.every((_, idx) => checkedEquipment.has(idx))

  return (
    <div className={`rounded-lg border-l-4 ${borderColor(stop.status)} bg-white border border-gray-200 shadow-sm overflow-hidden`}>
      {/* Collapsed content — always visible */}
      <button
        onClick={onToggle}
        className="w-full text-left p-4"
      >
        {/* Row 1: Location icon + type + ETA countdown */}
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-1.5 text-xs text-gray-500">
            {isFuneral && locLabel && (
              <>
                <span>{locIcon}</span>
                <span>{locLabel}</span>
              </>
            )}
            {!isFuneral && (
              <Badge variant="outline" className="text-[10px]">
                {getDeliveryTypeName(d.delivery_type)}
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            {countdown && (
              <span className={`text-xs font-medium ${countdown.color}`}>
                ETA {countdown.text}
              </span>
            )}
            {isExpanded ? (
              <ChevronUp className="h-4 w-4 text-gray-400" />
            ) : (
              <ChevronDown className="h-4 w-4 text-gray-400" />
            )}
          </div>
        </div>

        {/* Row 2: FH name + deceased */}
        <p className="font-medium text-sm text-gray-900">{d.customer_name || "Delivery"}</p>
        {d.deceased_name && (
          <p className="text-xs text-gray-500 mt-0.5">RE: {d.deceased_name}</p>
        )}

        {/* Row 3: Vault · Equipment */}
        {vaultLine && (
          <p className="text-xs text-gray-600 mt-1">{vaultLine}</p>
        )}

        {/* Row 4: Cemetery */}
        {cem.name && (
          <div className="mt-1.5">
            <p className="text-xs font-medium text-gray-700">{cem.name}</p>
            {cem.location && <p className="text-[11px] text-gray-400">{cem.location}</p>}
          </div>
        )}

        {/* Row 5: Times */}
        {isFuneral && (
          <div className="mt-1.5 text-xs text-gray-600">
            {d.service_location === "graveside" ? (
              d.service_time_display || <span className="text-amber-600">Time TBD</span>
            ) : (
              <>
                {d.service_time_display ? `Service: ${d.service_time_display}` : ""}
                {d.eta_display ? (
                  <span className="font-medium ml-2">ETA: {d.eta_display}</span>
                ) : d.service_time_display ? (
                  <span className="text-amber-600 ml-2">ETA: TBD</span>
                ) : (
                  <span className="text-amber-600">Time TBD</span>
                )}
              </>
            )}
          </div>
        )}
      </button>

      {/* Expanded content */}
      {isExpanded && (
        <div className="border-t border-gray-100 px-4 pb-4 pt-3 space-y-4">
          {/* Equipment checklist */}
          {settings?.show_equipment_checklist && d.equipment_lines && d.equipment_lines.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Before you go</h4>
              <div className="space-y-1.5">
                {d.equipment_lines.map((line, idx) => (
                  <label key={idx} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={checkedEquipment.has(idx)}
                      onChange={() => onToggleEquipment(idx)}
                      className="rounded accent-teal-600"
                    />
                    {line.quantity > 1 ? `${line.quantity}x ` : ""}{line.description}
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Contacts */}
          {settings?.show_funeral_home_contact && d.funeral_home_contact && (
            <div className="flex items-center justify-between text-sm">
              <div>
                <p className="font-medium">{d.funeral_home_contact.name}</p>
                <p className="text-xs text-gray-500">{d.customer_name}</p>
              </div>
              {d.funeral_home_contact.phone && (
                <a
                  href={`tel:${d.funeral_home_contact.phone}`}
                  className="flex items-center gap-1 text-teal-600 text-xs font-medium"
                >
                  <Phone className="h-3.5 w-3.5" /> Call
                </a>
              )}
            </div>
          )}

          {settings?.show_cemetery_contact && d.cemetery_contact && (
            <div className="flex items-center justify-between text-sm">
              <div>
                <p className="font-medium">{d.cemetery_contact.name}</p>
                <p className="text-xs text-gray-500">{cem.name}</p>
              </div>
              {d.cemetery_contact.phone && (
                <a
                  href={`tel:${d.cemetery_contact.phone}`}
                  className="flex items-center gap-1 text-teal-600 text-xs font-medium"
                >
                  <Phone className="h-3.5 w-3.5" /> Call
                </a>
              )}
            </div>
          )}

          {/* Notes */}
          {d.order_notes && (
            <div className="bg-gray-50 rounded-lg p-3">
              <h4 className="text-xs font-semibold text-gray-500 mb-1">Notes</h4>
              <p className="text-sm text-gray-700">{d.order_notes}</p>
            </div>
          )}

          {/* Get directions */}
          {settings?.show_get_directions && d.delivery_address && (
            <a
              href={mapsUrl(d.delivery_address)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 w-full py-3 bg-blue-50 text-blue-700 rounded-lg text-sm font-medium"
            >
              <Navigation className="h-4 w-4" /> Get directions
            </a>
          )}

          {/* Exception modal */}
          {showException && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 space-y-3">
              <h4 className="font-semibold text-sm">What couldn't be completed?</h4>
              {exceptionItems.map((item, idx) => (
                <div key={idx} className={`rounded-lg border p-2 ${item.checked ? "border-amber-300 bg-white" : "border-gray-200"}`}>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={item.checked}
                      onChange={() => {
                        const next = [...exceptionItems]
                        next[idx] = { ...next[idx], checked: !next[idx].checked }
                        onExceptionItemChange(next)
                      }}
                      className="accent-amber-600"
                    />
                    {item.desc}
                  </label>
                  {item.checked && (
                    <div className="mt-2 pl-6 space-y-1">
                      <select
                        value={item.reason}
                        onChange={(e) => {
                          const next = [...exceptionItems]
                          next[idx] = { ...next[idx], reason: e.target.value }
                          onExceptionItemChange(next)
                        }}
                        className="w-full border rounded p-1.5 text-xs"
                      >
                        <option value="weather">Weather</option>
                        <option value="access_issue">Access issue</option>
                        <option value="family_request">Family request</option>
                        <option value="equipment_failure">Equipment failure</option>
                        <option value="other">Other</option>
                      </select>
                      <input
                        value={item.notes}
                        onChange={(e) => {
                          const next = [...exceptionItems]
                          next[idx] = { ...next[idx], notes: e.target.value }
                          onExceptionItemChange(next)
                        }}
                        placeholder="Notes (optional)"
                        className="w-full border rounded p-1.5 text-xs"
                      />
                    </div>
                  )}
                </div>
              ))}
              <div className="flex gap-2">
                <Button
                  size="sm"
                  className="flex-1 bg-amber-600 hover:bg-amber-700"
                  onClick={onSubmitException}
                  disabled={exceptionItems.every((i) => !i.checked)}
                >
                  Submit Exception
                </Button>
                <Button size="sm" variant="outline" className="flex-1" onClick={onCancelException}>
                  Cancel
                </Button>
              </div>
            </div>
          )}

          {/* Action buttons */}
          {!showException && (
            <div className="space-y-2">
              {stop.status === "pending" && settings?.show_en_route_button && (
                <Button
                  className="w-full"
                  onClick={() => onStatusUpdate("en_route")}
                  disabled={updating || !allEquipmentChecked}
                >
                  {updating ? "Updating..." : !allEquipmentChecked ? "Check all equipment first" : "En Route"}
                </Button>
              )}

              {(stop.status === "en_route" || stop.status === "arrived" || stop.status === "in_progress") && (
                <div className="flex gap-2">
                  {settings?.show_exception_button && (
                    <Button
                      variant="outline"
                      className="flex-1 text-amber-700 border-amber-300"
                      onClick={onShowException}
                    >
                      <AlertTriangle className="h-4 w-4 mr-1" /> Exception
                    </Button>
                  )}
                  {settings?.show_delivered_button && (
                    <Button
                      className="flex-1 bg-green-600 hover:bg-green-700"
                      onClick={() => onStatusUpdate("completed")}
                      disabled={updating}
                    >
                      {updating ? "..." : "Delivered"}
                    </Button>
                  )}
                </div>
              )}

              {settings?.show_call_office_button && (
                <a
                  href="tel:"
                  className="flex items-center justify-center gap-1.5 w-full py-2 text-sm text-gray-500 hover:text-gray-700"
                >
                  <Phone className="h-3.5 w-3.5" /> Call office
                </a>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
