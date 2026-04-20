// company-detail.tsx — CRM company detail page with tabs
// Route: /vault/crm/companies/:id
// Uses DeviceAwarePage: desktop shows two-column tabs, mobile shows card layout.

import { useState, useEffect, useCallback } from "react"
import { useNavigate, useParams, Link } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { ChevronLeft, Plus, ExternalLink, Phone, Mail, Globe, MapPin, Loader2 } from "lucide-react"
import ContactList from "@/components/crm/ContactList"
import CompanyChat from "@/components/ai/CompanyChat"
import { HistoryButton } from "@/components/core/HistoryButton"
import VoiceMemoBtn from "@/components/ai/VoiceMemoButton"
import DeviceAwarePage from "@/components/ui/DeviceAwarePage"
import CompanyDetailMobile from "./company-detail-mobile"

// ── Types ────────────────────────────────────────────────────────────────────

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

type Tab = "overview" | "activity" | "orders" | "contacts" | "invoices" | "bills" | "legacy"

const ROLE_BADGES: Record<string, { label: string; className: string }> = {
  customer: { label: "Customer", className: "bg-blue-100 text-blue-700" },
  vendor: { label: "Vendor", className: "bg-purple-100 text-purple-700" },
  cemetery: { label: "Cemetery", className: "bg-green-100 text-green-700" },
  funeral_home: { label: "Funeral Home", className: "bg-teal-100 text-teal-700" },
  licensee: { label: "Licensee", className: "bg-amber-100 text-amber-700" },
  crematory: { label: "Crematory", className: "bg-red-100 text-red-700" },
  print_shop: { label: "Print Shop", className: "bg-pink-100 text-pink-700" },
}

const ALL_ROLES = ["customer", "vendor", "cemetery", "funeral_home", "licensee", "crematory", "print_shop"]
const ACTIVITY_TYPES = [
  { value: "call", icon: "📞", label: "Call" },
  { value: "note", icon: "📝", label: "Note" },
  { value: "visit", icon: "🤝", label: "Visit" },
  { value: "complaint", icon: "⚠", label: "Complaint" },
  { value: "follow_up", icon: "📅", label: "Follow-up" },
]

// ── Component ────────────────────────────────────────────────────────────────

export default function CompanyDetailPage() {
  return (
    <DeviceAwarePage
      desktop={() => <CompanyDetailDesktop />}
      mobile={() => <CompanyDetailMobile />}
    />
  )
}

function CompanyDetailDesktop() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [company, setCompany] = useState<CompanyDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<Tab>("overview")
  const [, setSaving] = useState(false)

  // Editable fields
  const [editPhone, setEditPhone] = useState("")
  const [editEmail, setEditEmail] = useState("")
  const [editWebsite, setEditWebsite] = useState("")
  const [editNotes, setEditNotes] = useState("")

  // Activity
  const [activities, setActivities] = useState<ActivityItem[]>([])
  const [activityPage, setActivityPage] = useState(1)
  const [activityTotal, setActivityTotal] = useState(0)
  const [showActivityForm, setShowActivityForm] = useState(false)
  const [actType, setActType] = useState("note")
  const [actTitle, setActTitle] = useState("")
  const [actBody, setActBody] = useState("")
  const [actOutcome, setActOutcome] = useState("")
  const [actFollowDate, setActFollowDate] = useState("")
  const [actSaving, setActSaving] = useState(false)

  // Billing group context
  const [parentGroup, setParentGroup] = useState<{ id: string; name: string; billing_preference: string } | null>(null)
  const [groupLocations, setGroupLocations] = useState<{ name: string; company_entity_id: string }[]>([])

  const loadCompany = useCallback(async () => {
    if (!id) return
    try {
      const res = await apiClient.get(`/companies/${id}`)
      setCompany(res.data)
      setEditPhone(res.data.phone || "")
      setEditEmail(res.data.email || "")
      setEditWebsite(res.data.website || "")
      setEditNotes(res.data.notes || "")
    } catch {
      toast.error("Could not load company")
    } finally {
      setLoading(false)
    }
  }, [id])

  const loadActivity = useCallback(async () => {
    if (!id) return
    try {
      const res = await apiClient.get(`/companies/${id}/activity?page=${activityPage}&per_page=20`)
      setActivities(res.data.items || [])
      setActivityTotal(res.data.total || 0)
    } catch { /* silent */ }
  }, [id, activityPage])

  useEffect(() => { loadCompany() }, [loadCompany])
  useEffect(() => { if (tab === "activity") loadActivity() }, [tab, loadActivity])

  // Load billing group context
  useEffect(() => {
    if (!company) return
    if (company.parent_company_id) {
      // This is a child location — load parent group info
      apiClient.get(`/billing-groups/${company.parent_company_id}`).then(r => {
        setParentGroup({ id: r.data.id, name: r.data.name, billing_preference: r.data.billing_preference })
      }).catch(() => {})
    } else if (company.is_billing_group) {
      // This is a billing group — load locations
      apiClient.get(`/billing-groups/${company.id}`).then(r => {
        setGroupLocations(r.data.locations || [])
      }).catch(() => {})
    }
  }, [company])

  async function handleSaveField(field: string, value: string) {
    if (!id) return
    setSaving(true)
    try {
      await apiClient.patch(`/companies/${id}`, { [field]: value || null })
      loadCompany()
    } catch {
      toast.error("Failed to save")
    } finally {
      setSaving(false)
    }
  }

  async function handleAddRole(roleKey: string) {
    if (!id) return
    try {
      await apiClient.patch(`/companies/${id}`, { [`is_${roleKey}`]: true })
      toast.success(`Added ${roleKey} role`)
      loadCompany()
    } catch {
      toast.error("Failed")
    }
  }

  async function handleCreateActivity() {
    if (!id || !actTitle.trim()) return
    setActSaving(true)
    try {
      await apiClient.post(`/companies/${id}/activity`, {
        activity_type: actType,
        title: actTitle,
        body: actBody || null,
        outcome: actOutcome || null,
        follow_up_date: actFollowDate || null,
      })
      toast.success("Activity logged")
      setShowActivityForm(false)
      setActTitle(""); setActBody(""); setActOutcome(""); setActFollowDate("")
      loadActivity()
    } catch {
      toast.error("Failed")
    } finally {
      setActSaving(false)
    }
  }

  async function handleCompleteFollowup(activityId: string) {
    if (!id) return
    try {
      await apiClient.post(`/companies/${id}/activity/${activityId}/complete-followup`)
      loadActivity()
    } catch { toast.error("Failed") }
  }

  if (loading) return <div className="flex justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-gray-400" /></div>
  if (!company) return <div className="text-center py-16 text-gray-500">Company not found</div>

  const missingRoles = ALL_ROLES.filter((r) => !company.roles.includes(r))

  // Determine available tabs
  const tabs: { key: Tab; label: string }[] = [
    { key: "overview", label: "Overview" },
    { key: "activity", label: "Activity" },
  ]
  if (company.is_customer) tabs.push({ key: "orders", label: "Orders" })
  if (company.is_customer) tabs.push({ key: "invoices", label: "Invoices" })
  if (company.is_vendor) tabs.push({ key: "bills", label: "Bills" })
  if (company.is_customer) tabs.push({ key: "legacy", label: "Legacy" })
  tabs.push({ key: "contacts", label: "Contacts" })

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 space-y-6">
      {/* Header */}
      <div>
        <Link to="/vault/crm/companies" className="flex items-center gap-1 text-sm text-gray-500 mb-2">
          <ChevronLeft className="h-4 w-4" /> Back to companies
        </Link>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{company.name}</h1>
            {company.legal_name && company.legal_name !== company.name && (
              <p className="text-sm text-gray-400">{company.legal_name}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <HistoryButton
              entityType="company"
              entityId={id!}
              entityName={company.name}
              variant="outline"
              size="sm"
            />
            {company.roles.map((r) => {
              const b = ROLE_BADGES[r]
              return b ? <Badge key={r} className={b.className}>{b.label}</Badge> : null
            })}
          </div>
        </div>
      </div>

      {/* Two-column layout */}
      <div className="flex flex-col lg:flex-row gap-6">
        {/* Left — Tabs */}
        <div className="flex-1 min-w-0 space-y-4">
          {/* Tab bar */}
          <div className="flex gap-1 border-b border-gray-200">
            {tabs.map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  tab === t.key ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* ── Overview Tab ───────────────────────────────────────── */}
          {tab === "overview" && (
            <div className="space-y-6">
              {/* Contact info */}
              <Card className="p-5 space-y-3">
                <h3 className="font-semibold text-sm text-gray-500 uppercase tracking-wider">Contact Info</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="flex items-center gap-2 text-sm">
                    <Phone className="h-4 w-4 text-gray-400" />
                    <Input value={editPhone} onChange={(e) => setEditPhone(e.target.value)} onBlur={() => handleSaveField("phone", editPhone)} placeholder="Add phone" className="h-8" />
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <Mail className="h-4 w-4 text-gray-400" />
                    <Input value={editEmail} onChange={(e) => setEditEmail(e.target.value)} onBlur={() => handleSaveField("email", editEmail)} placeholder="Add email" className="h-8" />
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <Globe className="h-4 w-4 text-gray-400" />
                    <Input value={editWebsite} onChange={(e) => setEditWebsite(e.target.value)} onBlur={() => handleSaveField("website", editWebsite)} placeholder="Add website" className="h-8" />
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <MapPin className="h-4 w-4 text-gray-400" />
                    <span className="text-gray-600">
                      {company.city && company.state ? `${company.city}, ${company.state}` : company.address_line1 || "No address"}
                    </span>
                  </div>
                </div>
              </Card>

              {/* Notes */}
              <Card className="p-5 space-y-2">
                <h3 className="font-semibold text-sm text-gray-500 uppercase tracking-wider">Notes</h3>
                <textarea
                  value={editNotes}
                  onChange={(e) => setEditNotes(e.target.value)}
                  onBlur={() => handleSaveField("notes", editNotes)}
                  placeholder="Add notes about this company..."
                  rows={3}
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm resize-none"
                />
              </Card>

              {/* Conversational lookup */}
              <CompanyChat masterCompanyId={id!} companyName={company.name} />
            </div>
          )}

          {/* ── Activity Tab ───────────────────────────────────────── */}
          {tab === "activity" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-sm">Activity Log</h3>
                <div className="flex gap-2">
                  <VoiceMemoBtn masterCompanyId={id} onComplete={loadActivity} />
                  {!showActivityForm && (
                    <Button size="sm" onClick={() => setShowActivityForm(true)}>
                      <Plus className="h-3.5 w-3.5 mr-1" /> Log activity
                    </Button>
                  )}
                </div>
              </div>

              {showActivityForm && (
                <Card className="p-4 space-y-3 border-blue-200">
                  <div className="flex flex-wrap gap-2">
                    {ACTIVITY_TYPES.map((at) => (
                      <button
                        key={at.value}
                        onClick={() => setActType(at.value)}
                        className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                          actType === at.value ? "border-blue-400 bg-blue-50" : "border-gray-200 hover:border-blue-300"
                        }`}
                      >
                        {at.icon} {at.label}
                      </button>
                    ))}
                  </div>
                  <Input value={actTitle} onChange={(e) => setActTitle(e.target.value)} placeholder="Title" />
                  <textarea
                    value={actBody}
                    onChange={(e) => setActBody(e.target.value)}
                    placeholder="Notes (optional)"
                    rows={2}
                    className="w-full rounded-md border bg-background px-3 py-2 text-sm resize-none"
                  />
                  <Input value={actOutcome} onChange={(e) => setActOutcome(e.target.value)} placeholder="Outcome (optional)" />
                  <div>
                    <label className="text-xs text-gray-500">Follow-up date (optional)</label>
                    <Input type="date" value={actFollowDate} onChange={(e) => setActFollowDate(e.target.value)} className="mt-0.5" />
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => setShowActivityForm(false)}>Cancel</Button>
                    <Button size="sm" onClick={handleCreateActivity} disabled={actSaving || !actTitle.trim()}>
                      {actSaving ? "Saving..." : "Save activity"}
                    </Button>
                  </div>
                </Card>
              )}

              {/* Feed */}
              {activities.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-8">No activity yet</p>
              ) : (
                <div className="space-y-3">
                  {activities.map((a) => (
                    <div key={a.id} className={`border rounded-lg p-3 ${a.is_system_generated ? "bg-gray-50 border-gray-100" : "border-gray-200"}`}>
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">{a.activity_type}</span>
                            <span className="text-sm font-medium">{a.title}</span>
                          </div>
                          {a.body && <p className="text-sm text-gray-600 mt-1">{a.body}</p>}
                          {a.outcome && <p className="text-xs text-gray-500 mt-1">Outcome: {a.outcome}</p>}
                          {a.follow_up_date && !a.follow_up_completed && (
                            <div className="flex items-center gap-2 mt-1.5">
                              <Badge className="text-[10px] bg-amber-100 text-amber-800">
                                Follow up {a.follow_up_date}
                              </Badge>
                              <button onClick={() => handleCompleteFollowup(a.id)} className="text-[11px] text-blue-600 hover:underline">
                                Mark complete
                              </button>
                            </div>
                          )}
                        </div>
                        <span className="text-xs text-gray-400 flex-shrink-0">
                          {a.created_at ? new Date(a.created_at).toLocaleDateString() : ""}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {activityTotal > 20 && (
                <div className="flex justify-center gap-2">
                  <Button variant="outline" size="sm" disabled={activityPage <= 1} onClick={() => setActivityPage(activityPage - 1)}>Previous</Button>
                  <Button variant="outline" size="sm" disabled={activityPage >= Math.ceil(activityTotal / 20)} onClick={() => setActivityPage(activityPage + 1)}>Next</Button>
                </div>
              )}
            </div>
          )}

          {/* ── Orders Tab ─────────────────────────────────────────── */}
          {tab === "orders" && company.is_customer && (
            <div className="space-y-4">
              {company.linked_customer_id ? (
                <div className="text-center py-8 space-y-2">
                  <p className="text-sm text-gray-500">View full order history in the AR system</p>
                  <Button variant="outline" onClick={() => navigate(`/customers/${company.linked_customer_id}`)}>
                    <ExternalLink className="h-4 w-4 mr-1" /> Open customer record
                  </Button>
                </div>
              ) : (
                <p className="text-sm text-gray-400 text-center py-8">No linked customer record</p>
              )}
            </div>
          )}

          {/* ── Invoices Tab ─────────────────────────────────────── */}
          {tab === "invoices" && company.is_customer && (
            <CompanyInvoicesTab entityId={id!} />
          )}

          {/* ── Bills Tab ─────────────────────────────────────────── */}
          {tab === "bills" && company.is_vendor && (
            <CompanyBillsTab entityId={id!} />
          )}

          {/* ── Legacy Tab ────────────────────────────────────────── */}
          {tab === "legacy" && company.is_customer && (
            <CompanyLegacyTab entityId={id!} />
          )}

          {/* ── Contacts Tab ───────────────────────────────────────── */}
          {tab === "contacts" && (
            <ContactList
              masterCompanyId={id!}
              companyName={company.name}
              allowEdit
            />
          )}
        </div>

        {/* Right — Sidebar */}
        <div className="w-full lg:w-80 space-y-4 flex-shrink-0">
          {/* Identity */}
          <Card className="p-4 space-y-3">
            <h3 className="font-semibold text-sm">Identity</h3>
            <div className="flex flex-wrap gap-1.5">
              {company.roles.map((r) => {
                const b = ROLE_BADGES[r]
                return b ? <Badge key={r} className={`text-[10px] ${b.className}`}>{b.label}</Badge> : null
              })}
            </div>
            {missingRoles.length > 0 && (
              <div className="relative">
                <details className="group">
                  <summary className="text-xs text-blue-600 cursor-pointer hover:underline">+ Add role</summary>
                  <div className="absolute left-0 top-6 bg-white border rounded-lg shadow-lg py-1 z-10 w-48">
                    {missingRoles.map((r) => (
                      <button
                        key={r}
                        onClick={() => handleAddRole(r)}
                        className="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50"
                      >
                        Mark as {r.replace("_", " ")}
                      </button>
                    ))}
                  </div>
                </details>
              </div>
            )}
          </Card>

          {/* Billing group context */}
          {company.is_billing_group && (
            <Card className="p-4 space-y-2">
              <div className="flex items-center gap-2">
                <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">Billing Group</span>
              </div>
              <div className="text-xs text-muted-foreground">
                {groupLocations.length} location{groupLocations.length !== 1 ? "s" : ""}
              </div>
              {groupLocations.map(l => (
                <Link key={l.company_entity_id} to={`/vault/crm/companies/${l.company_entity_id}`} className="block text-sm text-blue-600 hover:underline">
                  {l.name}
                </Link>
              ))}
              <Link to={`/vault/crm/billing-groups/${company.id}`} className="mt-2 block text-xs text-blue-600 hover:underline">
                Manage group
              </Link>
            </Card>
          )}
          {parentGroup && (
            <Card className="p-4 space-y-2">
              <div className="text-xs text-muted-foreground">Part of</div>
              <Link to={`/vault/crm/billing-groups/${parentGroup.id}`} className="text-sm font-medium text-blue-600 hover:underline">
                {parentGroup.name}
              </Link>
              <div className="text-xs text-muted-foreground">
                Billing: {parentGroup.billing_preference === "separate" ? "Independent" : parentGroup.billing_preference === "consolidated_single_payer" ? "Consolidated to group" : "Split payment"}
              </div>
            </Card>
          )}

          {/* Contacts (compact) */}
          <Card className="p-4">
            <ContactList
              masterCompanyId={id!}
              companyName={company.name}
              allowEdit
              compact
            />
          </Card>

          {/* Linked records */}
          <Card className="p-4 space-y-2">
            <h3 className="font-semibold text-sm">System Records</h3>
            {company.linked_customer_id && (
              <Link to={`/customers/${company.linked_customer_id}`} className="flex items-center gap-1.5 text-sm text-blue-600 hover:underline">
                <ExternalLink className="h-3.5 w-3.5" /> Customer record
              </Link>
            )}
            {company.linked_vendor_id && (
              <Link to={`/ap/vendors/${company.linked_vendor_id}`} className="flex items-center gap-1.5 text-sm text-blue-600 hover:underline">
                <ExternalLink className="h-3.5 w-3.5" /> Vendor record
              </Link>
            )}
            {company.linked_cemetery_id && (
              <Link to={`/settings/cemeteries/${company.linked_cemetery_id}`} className="flex items-center gap-1.5 text-sm text-blue-600 hover:underline">
                <ExternalLink className="h-3.5 w-3.5" /> Cemetery profile
              </Link>
            )}
            {!company.linked_customer_id && !company.linked_vendor_id && !company.linked_cemetery_id && (
              <p className="text-xs text-gray-400">No linked records</p>
            )}
          </Card>

          {/* Status */}
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Status</span>
              <Badge className={company.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}>
                {company.is_active ? "Active" : "Inactive"}
              </Badge>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}


// ── Inline tab components ──────────────────────────────────────────────────

function CompanyInvoicesTab({ entityId }: { entityId: string }) {
  const [data, setData] = useState<{ items: any[]; total: number; total_outstanding?: string } | null>(null)
  const [page, setPage] = useState(1)
  useEffect(() => {
    apiClient.get(`/companies/${entityId}/invoices?page=${page}&per_page=20`).then(r => setData(r.data)).catch(() => {})
  }, [entityId, page])
  if (!data) return <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin text-gray-400" /></div>
  if (data.total === 0) return <p className="text-sm text-gray-400 text-center py-8">No invoices found</p>
  return (
    <div className="space-y-3">
      {data.total_outstanding && parseFloat(data.total_outstanding) > 0 && (
        <div className="text-sm text-gray-600">Outstanding: <span className="font-medium">${parseFloat(data.total_outstanding).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span></div>
      )}
      <div className="divide-y rounded-md border">
        {data.items.map((inv: any) => (
          <div key={inv.id} className="flex items-center justify-between px-3 py-2 text-sm">
            <div>
              <span className="font-medium">#{inv.number}</span>
              {inv.deceased_name && <span className="ml-2 text-gray-500">{inv.deceased_name}</span>}
            </div>
            <div className="flex items-center gap-3">
              <span className="text-gray-500">${parseFloat(inv.total).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
              <Badge className="text-xs" variant="outline">{inv.status}</Badge>
            </div>
          </div>
        ))}
      </div>
      {data.total > 20 && (
        <div className="flex justify-center gap-2 pt-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</Button>
          <span className="text-sm text-gray-500 self-center">Page {page}</span>
          <Button variant="outline" size="sm" disabled={page * 20 >= data.total} onClick={() => setPage(p => p + 1)}>Next</Button>
        </div>
      )}
    </div>
  )
}

function CompanyBillsTab({ entityId }: { entityId: string }) {
  const [data, setData] = useState<{ items: any[]; total: number } | null>(null)
  useEffect(() => {
    apiClient.get(`/companies/${entityId}/bills?per_page=20`).then(r => setData(r.data)).catch(() => {})
  }, [entityId])
  if (!data) return <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin text-gray-400" /></div>
  if (data.total === 0) return <p className="text-sm text-gray-400 text-center py-8">No bills found</p>
  return (
    <div className="divide-y rounded-md border">
      {data.items.map((b: any) => (
        <div key={b.id} className="flex items-center justify-between px-3 py-2 text-sm">
          <span className="font-medium">#{b.number}</span>
          <div className="flex items-center gap-3">
            <span className="text-gray-500">${parseFloat(b.total).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
            <Badge className="text-xs" variant="outline">{b.status}</Badge>
          </div>
        </div>
      ))}
    </div>
  )
}

function CompanyLegacyTab({ entityId }: { entityId: string }) {
  const [data, setData] = useState<{ items: any[]; total: number } | null>(null)
  useEffect(() => {
    apiClient.get(`/companies/${entityId}/legacy-proofs?per_page=20`).then(r => setData(r.data)).catch(() => {})
  }, [entityId])
  if (!data) return <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin text-gray-400" /></div>
  if (data.total === 0) return <p className="text-sm text-gray-400 text-center py-8">No legacy proofs found</p>
  return (
    <div className="divide-y rounded-md border">
      {data.items.map((p: any) => (
        <div key={p.id} className="flex items-center gap-3 px-3 py-2 text-sm">
          {p.proof_url && <img src={p.proof_url} alt="" className="h-10 w-10 rounded object-cover bg-gray-100" />}
          <div className="flex-1 min-w-0">
            <p className="font-medium truncate">{p.print_name}</p>
            <p className="text-xs text-gray-500">{p.inscription_name || p.deceased_name}</p>
          </div>
          <Badge className="text-xs" variant="outline">{p.status}</Badge>
        </div>
      ))}
    </div>
  )
}
