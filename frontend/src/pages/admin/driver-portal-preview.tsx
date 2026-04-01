// driver-portal-preview.tsx — Admin preview of driver portal with live settings

import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Loader2, Smartphone, Tablet } from "lucide-react"
import type { DriverPortalSettings, DeliveryStop, DeliveryListItem } from "@/types/delivery"
import DriverRoutePage from "@/pages/driver/route"

// ── Sample data for preview when no real stops ──────────────────────────────

const SAMPLE_DELIVERY_1: DeliveryListItem = {
  id: "sample-1",
  company_id: "",
  delivery_type: "funeral_vault",
  order_id: null,
  customer_id: null,
  customer_name: "Johnson Funeral Home",
  carrier_id: null,
  carrier_name: null,
  carrier_tracking_reference: null,
  delivery_address: "1234 Cemetery Road, DeWitt, NY 13214",
  requested_date: new Date().toISOString().split("T")[0],
  status: "pending",
  priority: "normal",
  weight_lbs: null,
  scheduled_at: null,
  created_at: new Date().toISOString(),
  cemetery_name: "Oak Hill Cemetery",
  cemetery_city: "DeWitt",
  cemetery_state: "NY",
  service_location: "church",
  service_time: "10:00",
  service_time_display: "10:00 AM",
  eta: "11:15",
  eta_display: "11:15 AM",
  deceased_name: "Smith, Robert",
  vault_type: "Monticello",
  equipment_lines: [
    { description: "Lowering Device", quantity: 1 },
    { description: "Grass", quantity: 1 },
    { description: "Tent", quantity: 1 },
  ],
  funeral_home_contact: { name: "Sarah Johnson", phone: "315-555-0142", email: null },
  cemetery_contact: { name: "Tom Murphy", phone: "315-555-0198" },
  order_notes: "Family arriving from out of town — allow extra setup time",
}

const SAMPLE_DELIVERY_2: DeliveryListItem = {
  id: "sample-2",
  company_id: "",
  delivery_type: "funeral_vault",
  order_id: null,
  customer_id: null,
  customer_name: "White Chapel Funeral Home",
  carrier_id: null,
  carrier_name: null,
  carrier_tracking_reference: null,
  delivery_address: "567 Memorial Drive, Auburn, NY 13021",
  requested_date: new Date().toISOString().split("T")[0],
  status: "en_route",
  priority: "normal",
  weight_lbs: null,
  scheduled_at: null,
  created_at: new Date().toISOString(),
  cemetery_name: "St. Mary's Cemetery",
  cemetery_city: "Auburn",
  cemetery_state: "NY",
  service_location: "graveside",
  service_time: "13:00",
  service_time_display: "1:00 PM",
  deceased_name: "Miller, Dorothy",
  vault_type: "Graveliner",
  equipment_lines: [
    { description: "Lowering Device", quantity: 1 },
    { description: "Grass", quantity: 1 },
  ],
  funeral_home_contact: { name: "David Chapel", phone: "315-555-0211", email: null },
  cemetery_contact: null,
}

const SAMPLE_STOPS: DeliveryStop[] = [
  {
    id: "stop-1",
    route_id: "preview-route",
    delivery_id: "sample-1",
    delivery: SAMPLE_DELIVERY_1,
    sequence_number: 1,
    estimated_arrival: null,
    estimated_departure: null,
    actual_arrival: null,
    actual_departure: null,
    status: "pending",
    driver_notes: null,
    created_at: new Date().toISOString(),
  },
  {
    id: "stop-2",
    route_id: "preview-route",
    delivery_id: "sample-2",
    delivery: SAMPLE_DELIVERY_2,
    sequence_number: 2,
    estimated_arrival: null,
    estimated_departure: null,
    actual_arrival: null,
    actual_departure: null,
    status: "en_route",
    driver_notes: null,
    created_at: new Date().toISOString(),
  },
]

// ── Settings toggles config ─────────────────────────────────────────────────

const SETTING_TOGGLES: { key: keyof DriverPortalSettings; label: string }[] = [
  { key: "show_en_route_button", label: "En Route button" },
  { key: "show_exception_button", label: "Exception button" },
  { key: "show_delivered_button", label: "Delivered button" },
  { key: "show_equipment_checklist", label: "Equipment checklist" },
  { key: "show_funeral_home_contact", label: "FH contact" },
  { key: "show_cemetery_contact", label: "Cemetery contact" },
  { key: "show_get_directions", label: "Get directions" },
  { key: "show_call_office_button", label: "Call office" },
]

// ── Component ────────────────────────────────────────────────────────────────

export default function DriverPortalPreviewPage() {
  const navigate = useNavigate()
  const [settings, setSettings] = useState<DriverPortalSettings>({
    show_en_route_button: true,
    show_exception_button: true,
    show_delivered_button: true,
    show_equipment_checklist: false,
    show_funeral_home_contact: true,
    show_cemetery_contact: true,
    show_get_directions: true,
    show_call_office_button: true,
  })
  const [loading, setLoading] = useState(true)
  const [deviceSize, setDeviceSize] = useState<"iphone" | "ipad">("iphone")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    apiClient
      .get<DriverPortalSettings>("/driver/portal-settings")
      .then((r) => setSettings(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  async function handleToggle(key: keyof DriverPortalSettings, checked: boolean) {
    const prev = settings
    setSettings((s) => ({ ...s, [key]: checked }))
    setSaving(true)
    try {
      await apiClient.put("/settings/delivery", { [key]: checked })
    } catch {
      setSettings(prev)
      toast.error("Failed to save setting")
    } finally {
      setSaving(false)
    }
  }

  const frameWidth = deviceSize === "iphone" ? 375 : 768

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Left panel — settings */}
      <div className="w-80 border-r bg-white overflow-y-auto p-6 space-y-6 flex-shrink-0">
        <div>
          <h1 className="text-lg font-bold">Portal Preview</h1>
          <p className="text-sm text-gray-500 mt-1">
            Changes apply to all drivers immediately.
          </p>
        </div>

        {/* Toggles */}
        <div className="space-y-3">
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Visibility
          </h2>
          {SETTING_TOGGLES.map((t) => (
            <div key={t.key} className="flex items-center justify-between">
              <Label className="text-sm">{t.label}</Label>
              <Switch
                checked={settings[t.key]}
                onCheckedChange={(checked: boolean) => handleToggle(t.key, checked)}
              />
            </div>
          ))}
          {saving && (
            <p className="text-xs text-gray-400">Saving...</p>
          )}
        </div>

        {/* Device size */}
        <div className="space-y-2">
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Device
          </h2>
          <div className="flex gap-2">
            <button
              onClick={() => setDeviceSize("iphone")}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg border text-sm font-medium transition-colors ${
                deviceSize === "iphone" ? "bg-gray-900 text-white border-gray-900" : "border-gray-200 text-gray-600"
              }`}
            >
              <Smartphone className="h-4 w-4" /> iPhone
            </button>
            <button
              onClick={() => setDeviceSize("ipad")}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg border text-sm font-medium transition-colors ${
                deviceSize === "ipad" ? "bg-gray-900 text-white border-gray-900" : "border-gray-200 text-gray-600"
              }`}
            >
              <Tablet className="h-4 w-4" /> iPad
            </button>
          </div>
        </div>

        {/* Links */}
        <div className="pt-4 border-t space-y-2">
          <button
            onClick={() => navigate("/delivery/settings")}
            className="text-sm text-teal-600 font-medium"
          >
            Full delivery settings
          </button>
          <br />
          <button
            onClick={() => navigate("/admin/announcements")}
            className="text-sm text-teal-600 font-medium"
          >
            Manage announcements
          </button>
        </div>
      </div>

      {/* Right panel — device frame */}
      <div className="flex-1 bg-gray-100 flex items-start justify-center overflow-y-auto p-8">
        <div
          className="bg-gray-900 rounded-[40px] p-3 shadow-2xl"
          style={{ width: frameWidth + 24 }}
        >
          {/* Notch */}
          <div className="flex justify-center mb-1">
            <div className="w-24 h-5 bg-gray-900 rounded-b-xl" />
          </div>

          {/* Screen */}
          <div
            className="bg-white rounded-[28px] overflow-hidden"
            style={{ width: frameWidth, height: deviceSize === "iphone" ? 812 : 600 }}
          >
            <div className="h-full overflow-y-auto">
              {/* Sample data label */}
              <div className="bg-blue-50 text-blue-700 text-[11px] text-center py-1 font-medium">
                Preview — Sample data
              </div>
              <DriverRoutePage
                previewMode
                previewSettings={settings}
                previewStops={SAMPLE_STOPS}
              />
            </div>
          </div>

          {/* Home indicator */}
          <div className="flex justify-center mt-2">
            <div className="w-32 h-1 bg-gray-600 rounded-full" />
          </div>
        </div>
      </div>
    </div>
  )
}
