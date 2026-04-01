// announcements.tsx — Unified announcements page: compose + list + ack tracking
// Merges the original employee announcements page and the driver announcements page.

import { useState, useEffect, useCallback } from "react"
import { toast } from "sonner"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import apiClient from "@/lib/api-client"
import {
  Megaphone,
  Bell,
  AlertTriangle,
  ShieldAlert,
  Loader2,
  ChevronDown,
  ChevronUp,
  X,
  Send,
} from "lucide-react"

// ── Types ────────────────────────────────────────────────────────────────────

interface Permissions {
  can_create: boolean
}

interface Announcement {
  id: string
  title: string
  body: string | null
  priority: "info" | "warning" | "critical"
  content_type: string
  target_type: string
  target_value: string | null
  pin_to_top: boolean
  expires_at: string | null
  is_active: boolean
  created_at: string
  created_by_name: string | null
  safety_category: string | null
  requires_acknowledgment: boolean
  is_compliance_relevant: boolean
  document_url: string | null
  acknowledgment_deadline: string | null
  // Ack stats (from admin endpoint or computed)
  ack_count?: number
  total_targeted?: number
}

interface AckDetail {
  user_id: string
  user_name: string
  acknowledged: boolean
  acknowledged_at: string | null
}

// ── Constants ────────────────────────────────────────────────────────────────

const FUNCTIONAL_AREAS = [
  { value: "full_admin", label: "Full Admin" },
  { value: "funeral_scheduling", label: "Funeral Scheduling" },
  { value: "invoicing_ar", label: "Invoicing / AR" },
  { value: "production_log", label: "Production Log" },
  { value: "customer_management", label: "Customer Management" },
  { value: "safety_compliance", label: "Safety & Compliance" },
]

const SAFETY_CATEGORIES = [
  { value: "near_miss", label: "Near Miss" },
  { value: "hazard", label: "Hazard" },
  { value: "procedure", label: "Procedure Update" },
  { value: "training_assignment", label: "Training Required" },
  { value: "equipment_alert", label: "Equipment Notice" },
  { value: "general", label: "General Safety" },
]

type Filter = "all" | "active" | "expired" | "safety" | "drivers"

// ── Helpers ──────────────────────────────────────────────────────────────────

function urgencyLabel(a: Announcement): { text: string; className: string } {
  if (a.priority === "critical" || a.content_type === "safety_notice")
    return { text: "Safety", className: "bg-red-100 text-red-700" }
  if (a.priority === "warning")
    return { text: "Urgent", className: "bg-amber-100 text-amber-700" }
  return { text: "Normal", className: "bg-blue-100 text-blue-700" }
}

function audienceLabel(a: Announcement): string {
  if (a.target_type === "everyone") return "Everyone"
  if (a.target_type === "employee_type" && a.target_value === "driver") return "All drivers"
  if (a.target_type === "functional_area") {
    const area = FUNCTIONAL_AREAS.find((f) => f.value === a.target_value)
    return area ? area.label : a.target_value || "Functional area"
  }
  if (a.target_type === "specific_employees") return "Specific employees"
  return a.target_type
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

function isExpired(a: Announcement): boolean {
  return !!a.expires_at && new Date(a.expires_at) < new Date()
}

function isDriverTargeted(a: Announcement): boolean {
  return a.target_type === "employee_type" && a.target_value === "driver"
}

// ── Component ────────────────────────────────────────────────────────────────

export default function AnnouncementsPage() {
  const [permissions, setPermissions] = useState<Permissions | null>(null)
  const [permLoading, setPermLoading] = useState(true)
  const [announcements, setAnnouncements] = useState<Announcement[]>([])
  const [listLoading, setListLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  // Compose state
  const [title, setTitle] = useState("")
  const [body, setBody] = useState("")
  const [urgency, setUrgency] = useState<"normal" | "urgent" | "safety">("normal")
  const [recipient, setRecipient] = useState<"everyone" | "all_drivers" | "functional_area" | "specific_employees">("everyone")
  const [functionalArea, setFunctionalArea] = useState("")
  const [expiryOption, setExpiryOption] = useState<"none" | "end_of_day" | "end_of_week" | "custom">("none")
  const [customExpiry, setCustomExpiry] = useState("")

  // Safety extras
  const [safetyCategory, setSafetyCategory] = useState("")
  const [ackDeadline, setAckDeadline] = useState("")
  const [isComplianceRelevant, setIsComplianceRelevant] = useState(false)

  // More options
  const [showMoreOptions, setShowMoreOptions] = useState(false)
  const [pinToTop, setPinToTop] = useState(false)

  // List filter
  const [filter, setFilter] = useState<Filter>("active")

  // Ack detail modal
  const [ackModalId, setAckModalId] = useState<string | null>(null)
  const [ackDetails, setAckDetails] = useState<AckDetail[]>([])
  const [ackLoading, setAckLoading] = useState(false)

  // ── Data loading ───────────────────────────────────────────────────────

  const fetchPermissions = useCallback(async () => {
    try {
      const res = await apiClient.get<Permissions>("/announcements/permissions")
      setPermissions(res.data)
    } catch {
      setPermissions({ can_create: false })
    } finally {
      setPermLoading(false)
    }
  }, [])

  const fetchAnnouncements = useCallback(async () => {
    try {
      const res = await apiClient.get<Announcement[]>("/announcements/")
      setAnnouncements(res.data)
    } catch {
      // fail silently
    } finally {
      setListLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchPermissions()
    fetchAnnouncements()
  }, [fetchPermissions, fetchAnnouncements])

  // ── Compose handlers ──────────────────────────────────────────────────

  function resetForm() {
    setTitle("")
    setBody("")
    setUrgency("normal")
    setRecipient("everyone")
    setFunctionalArea("")
    setExpiryOption("none")
    setCustomExpiry("")
    setSafetyCategory("")
    setAckDeadline("")
    setIsComplianceRelevant(false)
    setPinToTop(false)
    setShowMoreOptions(false)
  }

  function computeExpiresAt(): string | null {
    const now = new Date()
    if (expiryOption === "end_of_day") {
      const eod = new Date(now)
      eod.setHours(23, 59, 59, 0)
      return eod.toISOString()
    }
    if (expiryOption === "end_of_week") {
      const eow = new Date(now)
      eow.setDate(eow.getDate() + (7 - eow.getDay()))
      eow.setHours(23, 59, 59, 0)
      return eow.toISOString()
    }
    if (expiryOption === "custom" && customExpiry) {
      return new Date(customExpiry + "T23:59:59").toISOString()
    }
    return null
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!title.trim()) { toast.error("Title is required"); return }
    setSubmitting(true)

    // Map urgency to model fields
    const isSafety = urgency === "safety"
    const priority = urgency === "safety" ? "critical" : urgency === "urgent" ? "warning" : "info"
    const content_type = isSafety ? "safety_notice" : "announcement"

    // Map recipient to target fields
    let target_type = "everyone"
    let target_value: string | null = null
    if (recipient === "all_drivers") {
      target_type = "employee_type"
      target_value = "driver"
    } else if (recipient === "functional_area") {
      target_type = "functional_area"
      target_value = functionalArea || null
    } else if (recipient === "specific_employees") {
      target_type = "specific_employees"
    }

    try {
      await apiClient.post("/announcements/", {
        title: title.trim(),
        body: body.trim() || null,
        priority,
        content_type,
        target_type,
        target_value,
        pin_to_top: urgency === "urgent" ? true : pinToTop,
        expires_at: computeExpiresAt(),
        requires_acknowledgment: isSafety,
        ...(isSafety && {
          safety_category: safetyCategory || null,
          acknowledgment_deadline: ackDeadline || null,
          is_compliance_relevant: isComplianceRelevant,
        }),
      })
      toast.success("Announcement posted")
      resetForm()
      fetchAnnouncements()
    } catch {
      toast.error("Failed to post announcement")
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDeactivate(id: string) {
    try {
      await apiClient.delete(`/announcements/${id}`)
      setAnnouncements((prev) => prev.map((a) => (a.id === id ? { ...a, is_active: false } : a)))
      toast.success("Announcement deactivated")
    } catch {
      toast.error("Failed to deactivate")
    }
  }

  async function openAckModal(id: string) {
    setAckModalId(id)
    setAckLoading(true)
    try {
      const res = await apiClient.get(`/announcements/safety-notices/${id}/status`)
      setAckDetails(res.data?.acknowledgments || [])
    } catch {
      setAckDetails([])
    } finally {
      setAckLoading(false)
    }
  }

  // ── Filtered list ─────────────────────────────────────────────────────

  const filtered = announcements.filter((a) => {
    if (filter === "active") return a.is_active && !isExpired(a)
    if (filter === "expired") return isExpired(a)
    if (filter === "safety") return a.priority === "critical" || a.content_type === "safety_notice"
    if (filter === "drivers") return isDriverTargeted(a)
    return true
  })

  // ── Render ────────────────────────────────────────────────────────────

  if (permLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  if (!permissions?.can_create) {
    return (
      <div className="max-w-3xl mx-auto py-8 px-4">
        <Card>
          <CardContent className="p-8 text-center">
            <Megaphone className="h-10 w-10 text-gray-300 mx-auto mb-3" />
            <h2 className="text-lg font-semibold">No Permission</h2>
            <p className="text-sm text-gray-500">You do not have permission to manage announcements.</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto py-8 px-4 lg:px-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Announcements</h1>
        <p className="text-sm text-gray-500 mt-1">
          Post announcements to your team and drivers. Safety announcements require acknowledgment before drivers can start their route.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* ── LEFT: List ──────────────────────────────────────────────── */}
        <div className="lg:col-span-3 space-y-4">
          {/* Filter bar */}
          <div className="flex gap-2 flex-wrap">
            {(["active", "all", "safety", "drivers", "expired"] as Filter[]).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                  filter === f
                    ? "bg-gray-900 text-white border-gray-900"
                    : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
                }`}
              >
                {f === "active" ? "Active" : f === "all" ? "All" : f === "safety" ? "Safety" : f === "drivers" ? "Drivers only" : "Expired"}
              </button>
            ))}
          </div>

          {listLoading && <p className="text-sm text-gray-400 py-4">Loading...</p>}

          {!listLoading && filtered.length === 0 && (
            <p className="text-sm text-gray-400 py-8 text-center">No announcements match this filter.</p>
          )}

          {filtered.map((a) => {
            const urg = urgencyLabel(a)
            const expired = isExpired(a)
            return (
              <Card key={a.id} className={`p-4 ${expired ? "opacity-50" : ""} ${!a.is_active ? "opacity-40" : ""}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${urg.className}`}>
                        {urg.text}
                      </span>
                      {a.content_type === "note" && (
                        <span className="inline-flex items-center rounded-full bg-purple-100 px-2 py-0.5 text-[11px] font-medium text-purple-700">Note</span>
                      )}
                      {!a.is_active && (
                        <span className="text-[11px] text-gray-400">Deactivated</span>
                      )}
                      {expired && a.is_active && (
                        <span className="text-[11px] text-amber-600">Expired</span>
                      )}
                    </div>
                    <h3 className="font-semibold text-sm text-gray-900">{a.title}</h3>
                    {a.body && (
                      <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{a.body}</p>
                    )}
                    <div className="flex items-center gap-3 mt-2 text-[11px] text-gray-400 flex-wrap">
                      <span>{audienceLabel(a)}</span>
                      {a.expires_at && (
                        <span>Expires {new Date(a.expires_at).toLocaleDateString()}</span>
                      )}
                      {a.requires_acknowledgment && a.ack_count !== undefined && (
                        <span className="font-medium text-gray-600">
                          Acknowledged: {a.ack_count} of {a.total_targeted}
                        </span>
                      )}
                      {a.created_at && <span>{timeAgo(a.created_at)}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    {a.requires_acknowledgment && (
                      <button
                        onClick={() => openAckModal(a.id)}
                        className="text-[11px] text-blue-600 font-medium hover:underline whitespace-nowrap"
                      >
                        View details
                      </button>
                    )}
                    {a.is_active && (
                      <button
                        onClick={() => handleDeactivate(a.id)}
                        className="text-[11px] text-red-500 font-medium hover:underline ml-2"
                      >
                        Deactivate
                      </button>
                    )}
                  </div>
                </div>
              </Card>
            )
          })}
        </div>

        {/* ── RIGHT: Compose ──────────────────────────────────────────── */}
        <div className="lg:col-span-2">
          <Card className="p-5 space-y-4 sticky top-20">
            <h2 className="font-semibold text-base">New Announcement</h2>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Title */}
              <div>
                <Label htmlFor="ann-title">Title</Label>
                <Input
                  id="ann-title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Road conditions, schedule change..."
                  className="mt-1"
                />
              </div>

              {/* Body */}
              <div>
                <Label htmlFor="ann-body">Message</Label>
                <textarea
                  id="ann-body"
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  placeholder="Details..."
                  rows={3}
                  className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                />
              </div>

              {/* Urgency tiles */}
              <div>
                <Label>Urgency</Label>
                <div className="grid grid-cols-3 gap-2 mt-1">
                  {([
                    { value: "normal" as const, label: "Normal", Icon: Bell, desc: "Standard display", color: "border-gray-200" },
                    { value: "urgent" as const, label: "Urgent", Icon: AlertTriangle, desc: "Pinned, amber", color: "border-amber-300 bg-amber-50" },
                    { value: "safety" as const, label: "Safety", Icon: ShieldAlert, desc: "Must acknowledge", color: "border-red-300 bg-red-50" },
                  ]).map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setUrgency(opt.value)}
                      className={`p-3 rounded-lg border text-center transition-colors ${
                        urgency === opt.value ? opt.color + " ring-2 ring-offset-1 ring-gray-400" : "border-gray-200"
                      }`}
                    >
                      <opt.Icon className={`h-4 w-4 mx-auto mb-1 ${opt.value === "safety" ? "text-red-600" : opt.value === "urgent" ? "text-amber-600" : "text-gray-500"}`} />
                      <div className="text-xs font-medium">{opt.label}</div>
                      <div className="text-[10px] text-gray-500">{opt.desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Safety details (expanded when safety selected) */}
              {urgency === "safety" && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-3 space-y-3">
                  <h4 className="text-xs font-semibold text-red-700 uppercase tracking-wider">Safety Details</h4>
                  <div>
                    <Label className="text-xs">Category</Label>
                    <select
                      value={safetyCategory}
                      onChange={(e) => setSafetyCategory(e.target.value)}
                      className="mt-1 w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                    >
                      <option value="">Select category...</option>
                      {SAFETY_CATEGORIES.map((c) => (
                        <option key={c.value} value={c.value}>{c.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <Label className="text-xs">Acknowledgment deadline (optional)</Label>
                    <Input
                      type="datetime-local"
                      value={ackDeadline}
                      onChange={(e) => setAckDeadline(e.target.value)}
                      className="mt-1"
                    />
                  </div>
                  <label className="flex items-center gap-2 text-xs">
                    <input
                      type="checkbox"
                      checked={isComplianceRelevant}
                      onChange={(e) => setIsComplianceRelevant(e.target.checked)}
                      className="rounded accent-red-600"
                    />
                    Compliance relevant
                  </label>
                </div>
              )}

              {/* Recipients */}
              <div>
                <Label>Recipients</Label>
                <div className="grid grid-cols-2 gap-1.5 mt-1">
                  {([
                    { value: "everyone" as const, label: "Everyone" },
                    { value: "all_drivers" as const, label: "All drivers" },
                    { value: "functional_area" as const, label: "Functional area" },
                    { value: "specific_employees" as const, label: "Specific people" },
                  ]).map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setRecipient(opt.value)}
                      className={`py-2 text-xs font-medium rounded-lg border transition-colors ${
                        recipient === opt.value
                          ? "bg-gray-900 text-white border-gray-900"
                          : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
                {recipient === "functional_area" && (
                  <select
                    value={functionalArea}
                    onChange={(e) => setFunctionalArea(e.target.value)}
                    className="mt-2 w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                  >
                    <option value="">Select area...</option>
                    {FUNCTIONAL_AREAS.map((a) => (
                      <option key={a.value} value={a.value}>{a.label}</option>
                    ))}
                  </select>
                )}
                {(recipient === "all_drivers" || recipient === "specific_employees") && (
                  <p className="text-[11px] text-gray-500 mt-1.5">
                    This announcement will appear in the driver portal for any drivers in the audience.
                  </p>
                )}
              </div>

              {/* Expiry presets */}
              <div>
                <Label>Expiry</Label>
                <div className="flex gap-1.5 mt-1 flex-wrap">
                  {([
                    { value: "none" as const, label: "No expiry" },
                    { value: "end_of_day" as const, label: "End of today" },
                    { value: "end_of_week" as const, label: "End of week" },
                    { value: "custom" as const, label: "Custom..." },
                  ]).map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setExpiryOption(opt.value)}
                      className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                        expiryOption === opt.value
                          ? "bg-gray-900 text-white border-gray-900"
                          : "bg-white text-gray-600 border-gray-200"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
                {expiryOption === "custom" && (
                  <Input
                    type="date"
                    value={customExpiry}
                    onChange={(e) => setCustomExpiry(e.target.value)}
                    className="mt-2"
                  />
                )}
              </div>

              {/* More options */}
              <button
                type="button"
                onClick={() => setShowMoreOptions(!showMoreOptions)}
                className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700"
              >
                {showMoreOptions ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                More options
              </button>
              {showMoreOptions && (
                <div className="space-y-2 pl-1">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={urgency === "urgent" ? true : pinToTop}
                      onChange={(e) => setPinToTop(e.target.checked)}
                      disabled={urgency === "urgent"}
                      className="rounded"
                    />
                    Pin to top {urgency === "urgent" && <span className="text-xs text-gray-400">(auto for urgent)</span>}
                  </label>
                </div>
              )}

              {/* Submit */}
              <Button type="submit" disabled={submitting || !title.trim()} className="w-full">
                {submitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Send className="h-4 w-4 mr-2" />}
                Post Announcement
              </Button>
            </form>
          </Card>
        </div>
      </div>

      {/* ── Ack detail modal ──────────────────────────────────────────── */}
      {ackModalId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-6 mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-base">Acknowledgment Status</h3>
              <button onClick={() => setAckModalId(null)}>
                <X className="h-5 w-5 text-gray-400" />
              </button>
            </div>
            {ackLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
              </div>
            ) : ackDetails.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-4">No acknowledgment data available.</p>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {ackDetails.map((d) => (
                  <div key={d.user_id} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                    <span className="text-sm font-medium">{d.user_name}</span>
                    {d.acknowledged ? (
                      <span className="text-xs text-green-600">
                        Acknowledged {d.acknowledged_at ? new Date(d.acknowledged_at).toLocaleString() : ""}
                      </span>
                    ) : (
                      <span className="text-xs text-amber-600">Not yet</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
