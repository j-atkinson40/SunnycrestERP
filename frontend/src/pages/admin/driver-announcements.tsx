// driver-announcements.tsx — Admin announcement composer + ack tracking

import { useState, useEffect } from "react"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Loader2, AlertTriangle, Bell, ShieldAlert, Send } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

interface AdminAnnouncement {
  id: string
  title: string
  body: string
  urgency: string
  audience: string
  is_active: boolean
  expires_at: string | null
  created_at: string | null
  ack_count: number
  total_targeted: number
}

const URGENCY_OPTIONS = [
  { value: "normal", label: "Normal", icon: Bell, desc: "Standard display", color: "border-gray-200" },
  { value: "urgent", label: "Urgent", icon: AlertTriangle, desc: "Pinned, amber styling", color: "border-amber-300 bg-amber-50" },
  { value: "safety", label: "Safety", icon: ShieldAlert, desc: "Must acknowledge before route", color: "border-red-300 bg-red-50" },
]

export default function DriverAnnouncementsPage() {
  const [announcements, setAnnouncements] = useState<AdminAnnouncement[]>([])
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)

  // Compose form
  const [title, setTitle] = useState("")
  const [body, setBody] = useState("")
  const [urgency, setUrgency] = useState("normal")
  const [audience, setAudience] = useState("all_drivers")
  const [expiryOption, setExpiryOption] = useState("end_of_day")

  useEffect(() => {
    apiClient
      .get<AdminAnnouncement[]>("/admin/announcements")
      .then((r) => setAnnouncements(r.data || []))
      .catch(() => toast.error("Could not load announcements"))
      .finally(() => setLoading(false))
  }, [])

  async function handleSend() {
    if (!title.trim() || !body.trim()) {
      toast.error("Title and message are required")
      return
    }
    setSending(true)
    try {
      let expires_at: string | null = null
      const now = new Date()
      if (expiryOption === "end_of_day") {
        const eod = new Date(now)
        eod.setHours(23, 59, 59, 0)
        expires_at = eod.toISOString()
      } else if (expiryOption === "end_of_week") {
        const eow = new Date(now)
        eow.setDate(eow.getDate() + (7 - eow.getDay()))
        eow.setHours(23, 59, 59, 0)
        expires_at = eow.toISOString()
      }

      await apiClient.post("/admin/announcements", {
        title: title.trim(),
        body: body.trim(),
        urgency,
        audience,
        target_driver_ids: [],
        expires_at,
      })

      toast.success("Announcement sent")
      setTitle("")
      setBody("")
      setUrgency("normal")

      // Refresh list
      const r = await apiClient.get<AdminAnnouncement[]>("/admin/announcements")
      setAnnouncements(r.data || [])
    } catch {
      toast.error("Failed to send announcement")
    } finally {
      setSending(false)
    }
  }

  async function handleDeactivate(id: string) {
    try {
      await apiClient.patch(`/admin/announcements/${id}`, { is_active: false })
      setAnnouncements((prev) => prev.map((a) => (a.id === id ? { ...a, is_active: false } : a)))
      toast.success("Announcement deactivated")
    } catch {
      toast.error("Failed to deactivate")
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  const active = announcements.filter((a) => a.is_active)
  const inactive = announcements.filter((a) => !a.is_active)

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Driver Announcements</h1>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Left: Active announcements */}
        <div className="lg:col-span-3 space-y-3">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">
            Active ({active.length})
          </h2>
          {active.length === 0 && (
            <p className="text-sm text-gray-400 py-4">No active announcements</p>
          )}
          {active.map((ann) => (
            <Card key={ann.id} className={`p-4 ${ann.urgency === "safety" ? "border-red-200 bg-red-50" : ann.urgency === "urgent" ? "border-amber-200 bg-amber-50" : ""}`}>
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-sm">{ann.title}</h3>
                  <p className="text-xs text-gray-500 mt-0.5">{ann.body}</p>
                </div>
                <button
                  onClick={() => handleDeactivate(ann.id)}
                  className="text-xs text-red-600 font-medium"
                >
                  Deactivate
                </button>
              </div>
              <div className="mt-2 flex items-center gap-3 text-xs text-gray-500">
                <span className={`font-medium ${ann.urgency === "safety" ? "text-red-700" : ann.urgency === "urgent" ? "text-amber-700" : "text-gray-600"}`}>
                  {ann.urgency.charAt(0).toUpperCase() + ann.urgency.slice(1)}
                </span>
                <span>Sent to {ann.audience === "all_drivers" ? "all drivers" : "specific drivers"}</span>
                <span className="font-medium">
                  Acknowledged: {ann.ack_count} of {ann.total_targeted}
                </span>
              </div>
            </Card>
          ))}

          {inactive.length > 0 && (
            <>
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mt-6">
                Past ({inactive.length})
              </h2>
              {inactive.slice(0, 5).map((ann) => (
                <Card key={ann.id} className="p-3 opacity-60">
                  <h3 className="font-medium text-sm text-gray-600">{ann.title}</h3>
                  <p className="text-xs text-gray-400">{ann.urgency} · {ann.ack_count} acknowledged</p>
                </Card>
              ))}
            </>
          )}
        </div>

        {/* Right: Compose */}
        <div className="lg:col-span-2">
          <Card className="p-5 space-y-4 sticky top-6">
            <h2 className="font-semibold text-base">New Announcement</h2>

            <div>
              <Label htmlFor="ann-title">Title</Label>
              <Input
                id="ann-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Road conditions, equipment update..."
                className="mt-1"
              />
            </div>

            <div>
              <Label htmlFor="ann-body">Message</Label>
              <textarea
                id="ann-body"
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="Details for drivers..."
                rows={4}
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>

            <div>
              <Label>Urgency</Label>
              <div className="grid grid-cols-3 gap-2 mt-1">
                {URGENCY_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setUrgency(opt.value)}
                    className={`p-3 rounded-lg border text-center transition-colors ${
                      urgency === opt.value ? opt.color + " ring-2 ring-offset-1 ring-gray-400" : "border-gray-200"
                    }`}
                  >
                    <opt.icon className={`h-4 w-4 mx-auto mb-1 ${opt.value === "safety" ? "text-red-600" : opt.value === "urgent" ? "text-amber-600" : "text-gray-500"}`} />
                    <div className="text-xs font-medium">{opt.label}</div>
                    <div className="text-[10px] text-gray-500">{opt.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <Label>Recipients</Label>
              <div className="space-y-1 mt-1">
                <label className="flex items-center gap-2 text-sm">
                  <input type="radio" name="audience" checked={audience === "all_drivers"} onChange={() => setAudience("all_drivers")} className="accent-teal-600" />
                  All drivers
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-400">
                  <input type="radio" name="audience" checked={audience === "specific_drivers"} onChange={() => setAudience("specific_drivers")} className="accent-teal-600" />
                  Specific drivers (coming soon)
                </label>
              </div>
            </div>

            <div>
              <Label>Expiry</Label>
              <div className="space-y-1 mt-1">
                {[
                  { value: "end_of_day", label: "End of today" },
                  { value: "end_of_week", label: "End of this week" },
                  { value: "none", label: "No expiry" },
                ].map((opt) => (
                  <label key={opt.value} className="flex items-center gap-2 text-sm">
                    <input type="radio" name="expiry" checked={expiryOption === opt.value} onChange={() => setExpiryOption(opt.value)} className="accent-teal-600" />
                    {opt.label}
                  </label>
                ))}
              </div>
            </div>

            <Button onClick={handleSend} disabled={sending || !title.trim() || !body.trim()} className="w-full">
              {sending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Send className="h-4 w-4 mr-2" />}
              Send Announcement
            </Button>
          </Card>
        </div>
      </div>
    </div>
  )
}
