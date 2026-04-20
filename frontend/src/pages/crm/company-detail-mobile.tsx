// company-detail-mobile.tsx — Mobile CRM company detail page
// Full-screen overlay with header card, quick actions, swipeable tabs.

import { useState, useEffect, useCallback, useRef } from "react"
import { useNavigate, useParams, Link } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import {
  ChevronLeft, Phone, Mail, MapPin, Plus, ExternalLink,
  StickyNote, Mic, ClipboardList, CreditCard, Loader2, X,
} from "lucide-react"
import VoiceMemoBtn from "@/components/ai/VoiceMemoButton"

// ── Types ───────────────────────────────────────────────────────────────────

interface CompanyDetail {
  id: string
  name: string
  legal_name: string | null
  phone: string | null
  email: string | null
  website: string | null
  address_line1: string | null
  address_line2: string | null
  city: string | null
  state: string | null
  zip: string | null
  country: string | null
  is_customer: boolean
  is_vendor: boolean
  is_cemetery: boolean
  is_funeral_home: boolean
  is_licensee: boolean
  is_crematory: boolean
  is_print_shop: boolean
  is_active: boolean
  notes: string | null
  roles: string[]
  linked_customer_id: string | null
  linked_vendor_id: string | null
  linked_cemetery_id: string | null
  is_billing_group: boolean
  billing_preference: string | null
  parent_company_id: string | null
  created_at: string | null
  updated_at: string | null
}

interface ActivityItem {
  id: string
  activity_type: string
  is_system_generated: boolean
  title: string | null
  body: string | null
  outcome: string | null
  contact_id: string | null
  logged_by: string | null
  follow_up_date: string | null
  follow_up_assigned_to: string | null
  follow_up_completed: boolean
  related_order_id: string | null
  created_at: string | null
}

interface Contact {
  id: string
  first_name: string | null
  last_name: string | null
  title: string | null
  phone: string | null
  email: string | null
  is_primary: boolean
}

type MobileTab = "activity" | "orders" | "details"

const ROLE_BADGES: Record<string, { label: string; className: string }> = {
  customer: { label: "Customer", className: "bg-blue-100 text-blue-700" },
  vendor: { label: "Vendor", className: "bg-purple-100 text-purple-700" },
  cemetery: { label: "Cemetery", className: "bg-green-100 text-green-700" },
  funeral_home: { label: "Funeral Home", className: "bg-teal-100 text-teal-700" },
  licensee: { label: "Licensee", className: "bg-amber-100 text-amber-700" },
  crematory: { label: "Crematory", className: "bg-red-100 text-red-700" },
  print_shop: { label: "Print Shop", className: "bg-pink-100 text-pink-700" },
}

const ACTIVITY_TYPES = [
  { value: "call", icon: "📞", label: "Call" },
  { value: "note", icon: "📝", label: "Note" },
  { value: "visit", icon: "🤝", label: "Visit" },
  { value: "complaint", icon: "⚠", label: "Complaint" },
  { value: "follow_up", icon: "📅", label: "Follow-up" },
]

// ── Component ───────────────────────────────────────────────────────────────

export default function CompanyDetailMobile() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [company, setCompany] = useState<CompanyDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<MobileTab>("activity")

  // Contacts
  const [contacts, setContacts] = useState<Contact[]>([])
  const [showAllContacts, setShowAllContacts] = useState(false)

  // Activity
  const [activities, setActivities] = useState<ActivityItem[]>([])
  const [activityPage, setActivityPage] = useState(1)
  const [activityTotal, setActivityTotal] = useState(0)

  // Activity form bottom sheet
  const [showActivityForm, setShowActivityForm] = useState(false)
  const [actType, setActType] = useState("note")
  const [actTitle, setActTitle] = useState("")
  const [actBody, setActBody] = useState("")
  const [actSaving, setActSaving] = useState(false)

  // Quick note bottom sheet
  const [showQuickNote, setShowQuickNote] = useState(false)
  const [quickNoteText, setQuickNoteText] = useState("")
  const [quickNoteSaving, setQuickNoteSaving] = useState(false)
  const quickNoteRef = useRef<HTMLTextAreaElement>(null)

  // Orders & invoices
  const [invoiceData, setInvoiceData] = useState<{ items: any[]; total: number; total_outstanding?: string } | null>(null)

  // Stats
  const [stats, setStats] = useState<{ orders: number; ar: string; avgPay: string; health: string }>({
    orders: 0, ar: "$0", avgPay: "--", health: "🟢",
  })

  // ── Data loading ──────────────────────────────────────────────────────

  const loadCompany = useCallback(async () => {
    if (!id) return
    try {
      const res = await apiClient.get(`/companies/${id}`)
      setCompany(res.data)
    } catch {
      toast.error("Could not load company")
    } finally {
      setLoading(false)
    }
  }, [id])

  const loadContacts = useCallback(async () => {
    if (!id) return
    try {
      const res = await apiClient.get(`/companies/${id}/contacts`)
      const all = [...(res.data.confirmed || []), ...(res.data.suggested || [])]
      setContacts(all)
    } catch { /* silent */ }
  }, [id])

  const loadActivity = useCallback(async () => {
    if (!id) return
    try {
      const res = await apiClient.get(`/companies/${id}/activity?page=${activityPage}&per_page=20`)
      setActivities(res.data.items || [])
      setActivityTotal(res.data.total || 0)
    } catch { /* silent */ }
  }, [id, activityPage])

  const loadInvoices = useCallback(async () => {
    if (!id) return
    try {
      const res = await apiClient.get(`/companies/${id}/invoices?page=1&per_page=5`)
      setInvoiceData(res.data)
      const outstanding = res.data.total_outstanding
        ? `$${parseFloat(res.data.total_outstanding).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
        : "$0"
      setStats((s) => ({ ...s, orders: res.data.total || 0, ar: outstanding }))
    } catch { /* silent */ }
  }, [id])

  useEffect(() => { loadCompany() }, [loadCompany])
  useEffect(() => { loadContacts() }, [loadContacts])
  useEffect(() => { loadActivity() }, [loadActivity])
  useEffect(() => { if (company?.is_customer) loadInvoices() }, [company, loadInvoices])

  useEffect(() => {
    if (showQuickNote) {
      setTimeout(() => quickNoteRef.current?.focus(), 100)
    }
  }, [showQuickNote])

  // ── Actions ───────────────────────────────────────────────────────────

  async function handleCreateActivity() {
    if (!id || !actTitle.trim()) return
    setActSaving(true)
    try {
      await apiClient.post(`/companies/${id}/activity`, {
        activity_type: actType,
        title: actTitle,
        body: actBody || null,
      })
      toast.success("Activity logged")
      setShowActivityForm(false)
      setActTitle("")
      setActBody("")
      loadActivity()
    } catch {
      toast.error("Failed")
    } finally {
      setActSaving(false)
    }
  }

  async function handleQuickNote() {
    if (!id || !quickNoteText.trim()) return
    setQuickNoteSaving(true)
    try {
      await apiClient.post(`/companies/${id}/activity`, {
        activity_type: "note",
        title: "Quick note",
        body: quickNoteText,
      })
      toast.success("Note saved")
      setShowQuickNote(false)
      setQuickNoteText("")
      loadActivity()
    } catch {
      toast.error("Failed")
    } finally {
      setQuickNoteSaving(false)
    }
  }

  async function handleCompleteFollowup(activityId: string) {
    if (!id) return
    try {
      await apiClient.post(`/companies/${id}/activity/${activityId}/complete-followup`)
      loadActivity()
    } catch {
      toast.error("Failed")
    }
  }

  // ── Derived data ──────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="fixed inset-0 z-40 bg-white flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }
  if (!company) {
    return (
      <div className="fixed inset-0 z-40 bg-white flex items-center justify-center">
        <p className="text-gray-500">Company not found</p>
      </div>
    )
  }

  const primaryContact = contacts.find((c) => c.is_primary) || contacts[0] || null
  const primaryContactName = primaryContact
    ? [primaryContact.first_name, primaryContact.last_name].filter(Boolean).join(" ")
    : null
  const location = company.city && company.state ? `${company.city}, ${company.state}` : company.city || company.state || ""
  const address = [company.address_line1, company.address_line2, location, company.zip].filter(Boolean).join(", ")
  const mapUrl = address ? `https://maps.apple.com/?q=${encodeURIComponent(address)}` : null

  const mobileTabs: { key: MobileTab; label: string }[] = [
    { key: "activity", label: "Activity" },
    { key: "orders", label: "Orders" },
    { key: "details", label: "Details" },
  ]

  return (
    <div className="fixed inset-0 z-40 bg-gray-50 flex flex-col">
      {/* ── Header card ──────────────────────────────────────────────── */}
      <div className="bg-white border-b px-4 pt-3 pb-3">
        <button
          onClick={() => navigate("/vault/crm/companies")}
          className="flex items-center gap-1 text-sm text-gray-500 mb-2"
        >
          <ChevronLeft className="h-4 w-4" /> Companies
        </button>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">{company.name}</h1>
            <div className="flex items-center gap-2 mt-0.5">
              <div className="flex gap-1">
                {company.roles.slice(0, 2).map((r) => {
                  const b = ROLE_BADGES[r]
                  return b ? (
                    <Badge key={r} className={`text-[9px] px-1.5 py-0 ${b.className}`}>
                      {b.label}
                    </Badge>
                  ) : null
                })}
              </div>
              {location && <span className="text-xs text-gray-500">{location}</span>}
            </div>
          </div>
          <Badge
            className={`text-[10px] ${company.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}
          >
            {company.is_active ? "Active" : "Inactive"}
          </Badge>
        </div>
      </div>

      {/* ── Quick actions bar ────────────────────────────────────────── */}
      <div className="bg-white border-b px-4 py-2 overflow-x-auto">
        <div className="flex gap-2 min-w-max">
          {(company.phone || primaryContact?.phone) && (
            <a
              href={`tel:${primaryContact?.phone || company.phone}`}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium border border-gray-200 bg-white text-gray-700 whitespace-nowrap"
            >
              <Phone className="h-3.5 w-3.5" /> Call
            </a>
          )}
          <button
            onClick={() => { setShowQuickNote(true); setQuickNoteText("") }}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium border border-gray-200 bg-white text-gray-700 whitespace-nowrap"
          >
            <StickyNote className="h-3.5 w-3.5" /> Note
          </button>
          <div className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium border border-gray-200 bg-white text-gray-700 whitespace-nowrap">
            <Mic className="h-3.5 w-3.5" />
            <VoiceMemoBtn masterCompanyId={id} onComplete={loadActivity} compact />
          </div>
          {company.is_customer && company.linked_customer_id && (
            <Link
              to={`/customers/${company.linked_customer_id}`}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium border border-gray-200 bg-white text-gray-700 whitespace-nowrap"
            >
              <ClipboardList className="h-3.5 w-3.5" /> Orders
            </Link>
          )}
          {company.is_customer && invoiceData && (
            <button
              onClick={() => setTab("orders")}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium border border-gray-200 bg-white text-gray-700 whitespace-nowrap"
            >
              <CreditCard className="h-3.5 w-3.5" /> AR: {stats.ar}
            </button>
          )}
        </div>
      </div>

      {/* ── Primary contact card ─────────────────────────────────────── */}
      {primaryContact && (
        <div className="bg-white border-b px-4 py-2.5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900">{primaryContactName}</p>
              {primaryContact.title && (
                <p className="text-xs text-gray-500">{primaryContact.title}</p>
              )}
            </div>
            <div className="flex gap-3">
              {primaryContact.phone && (
                <a href={`tel:${primaryContact.phone}`} className="text-blue-600">
                  <Phone className="h-4 w-4" />
                </a>
              )}
              {primaryContact.email && (
                <a href={`mailto:${primaryContact.email}`} className="text-blue-600">
                  <Mail className="h-4 w-4" />
                </a>
              )}
            </div>
          </div>
          {contacts.length > 1 && (
            <button
              onClick={() => setShowAllContacts(!showAllContacts)}
              className="text-xs text-blue-600 mt-1"
            >
              {showAllContacts ? "Hide contacts" : `See all ${contacts.length} contacts`}
            </button>
          )}
          {showAllContacts && (
            <div className="mt-2 space-y-2 border-t pt-2">
              {contacts.filter((c) => c.id !== primaryContact.id).map((c) => (
                <div key={c.id} className="flex items-center justify-between text-sm">
                  <div>
                    <p className="text-gray-700">
                      {[c.first_name, c.last_name].filter(Boolean).join(" ")}
                    </p>
                    {c.title && <p className="text-xs text-gray-400">{c.title}</p>}
                  </div>
                  <div className="flex gap-3">
                    {c.phone && (
                      <a href={`tel:${c.phone}`} className="text-blue-600">
                        <Phone className="h-3.5 w-3.5" />
                      </a>
                    )}
                    {c.email && (
                      <a href={`mailto:${c.email}`} className="text-blue-600">
                        <Mail className="h-3.5 w-3.5" />
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Stats row ────────────────────────────────────────────────── */}
      {company.is_customer && (
        <div className="bg-white border-b px-4 py-2 overflow-x-auto">
          <div className="flex gap-3 min-w-max">
            <div className="px-3 py-1.5 rounded-lg bg-gray-50 text-xs">
              <span className="text-gray-500">Orders:</span>{" "}
              <span className="font-medium">{stats.orders}</span>
            </div>
            <div className="px-3 py-1.5 rounded-lg bg-gray-50 text-xs">
              <span className="text-gray-500">AR:</span>{" "}
              <span className="font-medium">{stats.ar}</span>
            </div>
            <div className="px-3 py-1.5 rounded-lg bg-gray-50 text-xs">
              <span className="text-gray-500">Health:</span>{" "}
              <span className="font-medium">{stats.health}</span>
            </div>
          </div>
        </div>
      )}

      {/* ── Tab bar ──────────────────────────────────────────────────── */}
      <div className="bg-white border-b flex">
        {mobileTabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 py-2.5 text-sm font-medium text-center border-b-2 transition-colors ${
              tab === t.key
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Tab content ──────────────────────────────────────────────── */}
      <div className="flex-1 overflow-auto">
        {/* ── Activity tab ───────────────────────────────────────────── */}
        {tab === "activity" && (
          <div className="px-4 py-3 space-y-3">
            <Button
              size="sm"
              className="w-full"
              onClick={() => { setShowActivityForm(true); setActTitle(""); setActBody("") }}
            >
              <Plus className="h-3.5 w-3.5 mr-1" /> Log activity
            </Button>

            {activities.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-8">No activity yet</p>
            ) : (
              activities.map((a) => (
                <div
                  key={a.id}
                  className={`border rounded-lg p-3 ${
                    a.is_system_generated ? "bg-gray-50 border-gray-100" : "border-gray-200"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">
                      {a.activity_type}
                    </span>
                    <span className="text-sm font-medium flex-1 truncate">{a.title}</span>
                    <span className="text-[10px] text-gray-400 flex-shrink-0">
                      {a.created_at ? new Date(a.created_at).toLocaleDateString() : ""}
                    </span>
                  </div>
                  {a.body && <p className="text-xs text-gray-600 mt-1">{a.body}</p>}
                  {a.outcome && <p className="text-[11px] text-gray-500 mt-1">Outcome: {a.outcome}</p>}
                  {a.follow_up_date && !a.follow_up_completed && (
                    <div className="flex items-center gap-2 mt-1.5">
                      <Badge className="text-[10px] bg-amber-100 text-amber-800">
                        Follow up {a.follow_up_date}
                      </Badge>
                      <button
                        onClick={() => handleCompleteFollowup(a.id)}
                        className="text-[11px] text-blue-600"
                      >
                        Complete
                      </button>
                    </div>
                  )}
                </div>
              ))
            )}

            {activityTotal > 20 && (
              <div className="flex justify-center gap-2 pt-2">
                <Button variant="outline" size="sm" disabled={activityPage <= 1} onClick={() => setActivityPage((p) => p - 1)}>
                  Prev
                </Button>
                <Button variant="outline" size="sm" disabled={activityPage >= Math.ceil(activityTotal / 20)} onClick={() => setActivityPage((p) => p + 1)}>
                  Next
                </Button>
              </div>
            )}
          </div>
        )}

        {/* ── Orders tab ─────────────────────────────────────────────── */}
        {tab === "orders" && (
          <div className="px-4 py-3 space-y-3">
            {company.is_customer && company.linked_customer_id ? (
              <>
                {invoiceData && invoiceData.total_outstanding && parseFloat(invoiceData.total_outstanding) > 0 && (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm">
                    <span className="text-amber-800">Outstanding:</span>{" "}
                    <span className="font-semibold text-amber-900">
                      ${parseFloat(invoiceData.total_outstanding).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                )}

                {invoiceData && invoiceData.items.length > 0 ? (
                  <div className="space-y-2">
                    {invoiceData.items.map((inv: any) => (
                      <div key={inv.id} className="bg-white border rounded-lg p-3 flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium">#{inv.number}</p>
                          {inv.deceased_name && (
                            <p className="text-xs text-gray-500">{inv.deceased_name}</p>
                          )}
                        </div>
                        <div className="text-right">
                          <p className="text-sm font-medium">
                            ${parseFloat(inv.total).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                          </p>
                          <Badge className="text-[10px]" variant="outline">
                            {inv.status}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-400 text-center py-8">No invoices yet</p>
                )}

                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => navigate(`/customers/${company.linked_customer_id}`)}
                >
                  <ExternalLink className="h-4 w-4 mr-1" /> View full customer record
                </Button>
              </>
            ) : (
              <p className="text-sm text-gray-400 text-center py-8">
                {company.is_customer ? "No linked customer record" : "Not a customer"}
              </p>
            )}
          </div>
        )}

        {/* ── Details tab ────────────────────────────────────────────── */}
        {tab === "details" && (
          <div className="px-4 py-3 space-y-4">
            {/* Contact info */}
            <Card className="p-4 space-y-3">
              <h3 className="font-semibold text-xs text-gray-500 uppercase tracking-wider">
                Contact Info
              </h3>
              {company.phone && (
                <a href={`tel:${company.phone}`} className="flex items-center gap-2 text-sm text-blue-600">
                  <Phone className="h-4 w-4 text-gray-400" /> {company.phone}
                </a>
              )}
              {company.email && (
                <a href={`mailto:${company.email}`} className="flex items-center gap-2 text-sm text-blue-600">
                  <Mail className="h-4 w-4 text-gray-400" /> {company.email}
                </a>
              )}
              {address && (
                <div className="flex items-start gap-2 text-sm">
                  <MapPin className="h-4 w-4 text-gray-400 mt-0.5" />
                  {mapUrl ? (
                    <a href={mapUrl} target="_blank" rel="noopener noreferrer" className="text-blue-600">
                      {address}
                    </a>
                  ) : (
                    <span className="text-gray-600">{address}</span>
                  )}
                </div>
              )}
            </Card>

            {/* Notes */}
            <Card className="p-4 space-y-2">
              <h3 className="font-semibold text-xs text-gray-500 uppercase tracking-wider">
                Notes
              </h3>
              <p className="text-sm text-gray-600 whitespace-pre-wrap">
                {company.notes || "No notes"}
              </p>
            </Card>

            {/* Roles */}
            <Card className="p-4 space-y-2">
              <h3 className="font-semibold text-xs text-gray-500 uppercase tracking-wider">
                Roles
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {company.roles.map((r) => {
                  const b = ROLE_BADGES[r]
                  return b ? (
                    <Badge key={r} className={`text-[10px] ${b.className}`}>
                      {b.label}
                    </Badge>
                  ) : null
                })}
              </div>
            </Card>

            {/* System records */}
            <Card className="p-4 space-y-2">
              <h3 className="font-semibold text-xs text-gray-500 uppercase tracking-wider">
                System Records
              </h3>
              {company.linked_customer_id && (
                <Link
                  to={`/customers/${company.linked_customer_id}`}
                  className="flex items-center gap-1.5 text-sm text-blue-600"
                >
                  <ExternalLink className="h-3.5 w-3.5" /> Customer record
                </Link>
              )}
              {company.linked_vendor_id && (
                <Link
                  to={`/ap/vendors/${company.linked_vendor_id}`}
                  className="flex items-center gap-1.5 text-sm text-blue-600"
                >
                  <ExternalLink className="h-3.5 w-3.5" /> Vendor record
                </Link>
              )}
              {company.linked_cemetery_id && (
                <Link
                  to={`/settings/cemeteries/${company.linked_cemetery_id}`}
                  className="flex items-center gap-1.5 text-sm text-blue-600"
                >
                  <ExternalLink className="h-3.5 w-3.5" /> Cemetery profile
                </Link>
              )}
              {!company.linked_customer_id && !company.linked_vendor_id && !company.linked_cemetery_id && (
                <p className="text-xs text-gray-400">No linked records</p>
              )}
            </Card>
          </div>
        )}
      </div>

      {/* ── Bottom action bar ────────────────────────────────────────── */}
      <div className="bg-white border-t px-4 py-2.5 flex gap-2 pb-[env(safe-area-inset-bottom)]">
        {(company.phone || primaryContact?.phone) && (
          <a
            href={`tel:${primaryContact?.phone || company.phone}`}
            className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-lg text-sm font-medium bg-blue-600 text-white active:bg-blue-700"
          >
            <Phone className="h-4 w-4" /> Call primary
          </a>
        )}
        <button
          onClick={() => { setShowActivityForm(true); setActTitle(""); setActBody("") }}
          className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-lg text-sm font-medium border border-gray-200 bg-white text-gray-700 active:bg-gray-100"
        >
          <Plus className="h-4 w-4" /> Log activity
        </button>
      </div>

      {/* ── Activity form bottom sheet ───────────────────────────────── */}
      {showActivityForm && (
        <div className="fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/40" onClick={() => setShowActivityForm(false)} />
          <div className="absolute bottom-0 left-0 right-0 bg-white rounded-t-2xl animate-in slide-in-from-bottom duration-200 max-h-[80vh] overflow-auto">
            <div className="flex items-center justify-between px-4 py-3 border-b sticky top-0 bg-white">
              <h3 className="font-semibold text-sm">Log activity</h3>
              <button onClick={() => setShowActivityForm(false)}>
                <X className="h-5 w-5 text-gray-400" />
              </button>
            </div>
            <div className="px-4 py-3 space-y-3">
              {/* Activity type selector */}
              <div className="flex flex-wrap gap-2">
                {ACTIVITY_TYPES.map((at) => (
                  <button
                    key={at.value}
                    onClick={() => setActType(at.value)}
                    className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                      actType === at.value
                        ? "border-blue-400 bg-blue-50"
                        : "border-gray-200"
                    }`}
                  >
                    {at.icon} {at.label}
                  </button>
                ))}
              </div>
              <Input
                value={actTitle}
                onChange={(e) => setActTitle(e.target.value)}
                placeholder="Title"
                autoFocus
              />
              <textarea
                value={actBody}
                onChange={(e) => setActBody(e.target.value)}
                placeholder="Notes (optional)"
                rows={3}
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm resize-none"
              />
              <div className="flex gap-2">
                <Button variant="outline" className="flex-1" onClick={() => setShowActivityForm(false)}>
                  Cancel
                </Button>
                <Button
                  className="flex-1"
                  disabled={!actTitle.trim() || actSaving}
                  onClick={handleCreateActivity}
                >
                  {actSaving ? "Saving..." : "Save"}
                </Button>
              </div>
            </div>
            <div className="h-6" />
          </div>
        </div>
      )}

      {/* ── Quick note bottom sheet ──────────────────────────────────── */}
      {showQuickNote && (
        <div className="fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/40" onClick={() => setShowQuickNote(false)} />
          <div className="absolute bottom-0 left-0 right-0 bg-white rounded-t-2xl animate-in slide-in-from-bottom duration-200">
            <div className="flex items-center justify-between px-4 py-3 border-b">
              <h3 className="font-semibold text-sm">Quick note</h3>
              <button onClick={() => setShowQuickNote(false)}>
                <X className="h-5 w-5 text-gray-400" />
              </button>
            </div>
            <div className="px-4 py-3 space-y-3">
              <textarea
                ref={quickNoteRef}
                value={quickNoteText}
                onChange={(e) => setQuickNoteText(e.target.value)}
                placeholder="Type a quick note..."
                rows={3}
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm resize-none"
              />
              <div className="flex gap-2">
                <Button variant="outline" className="flex-1" onClick={() => setShowQuickNote(false)}>
                  Cancel
                </Button>
                <Button
                  className="flex-1"
                  disabled={!quickNoteText.trim() || quickNoteSaving}
                  onClick={handleQuickNote}
                >
                  {quickNoteSaving ? "Saving..." : "Save note"}
                </Button>
              </div>
            </div>
            <div className="h-6" />
          </div>
        </div>
      )}
    </div>
  )
}
