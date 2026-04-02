// ContactList.tsx — Reusable CRM contact list component.
// Modes: full view (default), compact, picker (onContactSelect).

import { useState, useEffect, useCallback } from "react"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { Plus, Check, X, Phone, Mail, MoreHorizontal, Star } from "lucide-react"

interface Contact {
  id: string
  name: string
  title: string | null
  phone: string | null
  phone_ext: string | null
  mobile: string | null
  email: string | null
  role: string | null
  is_primary: boolean
  is_active: boolean
  receives_invoices: boolean
  receives_legacy_proofs: boolean
  linked_user_id: string | null
  linked_auto: boolean
  notes: string | null
}

interface ContactListProps {
  masterCompanyId: string
  companyName: string
  allowEdit?: boolean
  compact?: boolean
  onContactSelect?: (contact: Contact) => void
}

const ROLE_OPTIONS = [
  { value: "owner", label: "Owner" },
  { value: "director", label: "Director" },
  { value: "manager", label: "Manager" },
  { value: "billing", label: "Billing" },
  { value: "arranger", label: "Arranger" },
  { value: "on_call", label: "On-call" },
  { value: "other", label: "Other" },
]

export default function ContactList({
  masterCompanyId,
  companyName,
  allowEdit = true,
  compact = false,
  onContactSelect,
}: ContactListProps) {
  const [confirmed, setConfirmed] = useState<Contact[]>([])
  const [suggested, setSuggested] = useState<Contact[]>([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [menuId, setMenuId] = useState<string | null>(null)

  // Form state
  const [formName, setFormName] = useState("")
  const [formTitle, setFormTitle] = useState("")
  const [formPhone, setFormPhone] = useState("")
  const [formMobile, setFormMobile] = useState("")
  const [formEmail, setFormEmail] = useState("")
  const [formRole, setFormRole] = useState("")
  const [formPrimary, setFormPrimary] = useState(false)
  const [formInvoices, setFormInvoices] = useState(false)
  const [formProofs, setFormProofs] = useState(false)
  const [formNotes, setFormNotes] = useState("")

  const fetchContacts = useCallback(async () => {
    try {
      const res = await apiClient.get(`/companies/${masterCompanyId}/contacts`)
      setConfirmed(res.data.confirmed || [])
      setSuggested(res.data.suggested || [])
    } catch {
      // Silent — component may be shown before entity is linked
    } finally {
      setLoading(false)
    }
  }, [masterCompanyId])

  useEffect(() => { fetchContacts() }, [fetchContacts])

  function resetForm() {
    setFormName(""); setFormTitle(""); setFormPhone(""); setFormMobile("")
    setFormEmail(""); setFormRole(""); setFormPrimary(false)
    setFormInvoices(false); setFormProofs(false); setFormNotes("")
  }

  function loadIntoForm(c: Contact) {
    setFormName(c.name); setFormTitle(c.title || ""); setFormPhone(c.phone || "")
    setFormMobile(c.mobile || ""); setFormEmail(c.email || ""); setFormRole(c.role || "")
    setFormPrimary(c.is_primary); setFormInvoices(c.receives_invoices)
    setFormProofs(c.receives_legacy_proofs); setFormNotes(c.notes || "")
  }

  async function handleSave() {
    if (!formName.trim()) { toast.error("Name is required"); return }
    try {
      if (editId) {
        await apiClient.patch(`/companies/${masterCompanyId}/contacts/${editId}`, {
          name: formName, title: formTitle || null, phone: formPhone || null,
          mobile: formMobile || null, email: formEmail || null, role: formRole || null,
          is_primary: formPrimary, receives_invoices: formInvoices,
          receives_legacy_proofs: formProofs, notes: formNotes || null,
        })
        toast.success("Contact updated")
      } else {
        await apiClient.post(`/companies/${masterCompanyId}/contacts`, {
          name: formName, title: formTitle || null, phone: formPhone || null,
          mobile: formMobile || null, email: formEmail || null, role: formRole || null,
          is_primary: formPrimary, receives_invoices: formInvoices,
          receives_legacy_proofs: formProofs, notes: formNotes || null,
        })
        toast.success("Contact added")
      }
      resetForm(); setShowAdd(false); setEditId(null); fetchContacts()
    } catch {
      toast.error("Failed to save contact")
    }
  }

  async function handleConfirm(id: string) {
    try {
      await apiClient.post(`/companies/${masterCompanyId}/contacts/${id}/confirm`)
      toast.success("Contact confirmed")
      fetchContacts()
    } catch { toast.error("Failed") }
  }

  async function handleDismiss(id: string) {
    try {
      await apiClient.post(`/companies/${masterCompanyId}/contacts/${id}/dismiss`)
      fetchContacts()
    } catch { toast.error("Failed") }
  }

  async function handleDelete(id: string) {
    try {
      await apiClient.delete(`/companies/${masterCompanyId}/contacts/${id}`)
      toast.success("Contact removed")
      fetchContacts()
    } catch { toast.error("Failed") }
  }

  async function handleSetPrimary(id: string) {
    try {
      await apiClient.patch(`/companies/${masterCompanyId}/contacts/${id}`, { is_primary: true })
      fetchContacts()
    } catch { toast.error("Failed") }
  }

  async function handleToggle(id: string, field: string, value: boolean) {
    try {
      await apiClient.patch(`/companies/${masterCompanyId}/contacts/${id}`, { [field]: value })
      fetchContacts()
    } catch { toast.error("Failed") }
  }

  if (loading) return null

  // ── Picker mode ────────────────────────────────────────────────────────
  if (onContactSelect) {
    return (
      <div className="space-y-1">
        {confirmed.map((c) => (
          <button
            key={c.id}
            onClick={() => onContactSelect(c)}
            className="w-full text-left px-3 py-2 rounded-md hover:bg-gray-50 text-sm flex items-center justify-between"
          >
            <div>
              <span className="font-medium">{c.name}</span>
              {c.title && <span className="text-gray-500 ml-1">· {c.title}</span>}
            </div>
            {c.email && <span className="text-xs text-gray-400">{c.email}</span>}
          </button>
        ))}
        {confirmed.length === 0 && <p className="text-xs text-gray-400 px-3 py-2">No contacts</p>}
      </div>
    )
  }

  // ── Compact mode ───────────────────────────────────────────────────────
  if (compact) {
    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Contacts</p>
          {allowEdit && (
            <button onClick={() => setShowAdd(true)} className="text-xs text-blue-600 font-medium">+ Add</button>
          )}
        </div>
        {confirmed.length === 0 && !showAdd && (
          <p className="text-xs text-gray-400">No contacts yet</p>
        )}
        {confirmed.map((c) => (
          <div key={c.id} className="text-sm">
            <div className="flex items-center gap-1.5">
              {c.is_primary && <Star className="h-3 w-3 text-amber-500 fill-amber-500" />}
              <span className="font-medium">{c.name}</span>
              {c.title && <span className="text-gray-500 text-xs">· {c.title}</span>}
            </div>
            <div className="text-xs text-gray-500 flex items-center gap-2 mt-0.5">
              {c.phone && <span className="flex items-center gap-0.5"><Phone className="h-3 w-3" />{c.phone}</span>}
              {c.email && <span className="flex items-center gap-0.5"><Mail className="h-3 w-3" />{c.email}</span>}
            </div>
          </div>
        ))}
        {showAdd && renderForm()}
      </div>
    )
  }

  // ── Full mode ──────────────────────────────────────────────────────────

  function renderForm() {
    return (
      <Card className="p-4 space-y-3 border-blue-200">
        <div className="grid grid-cols-2 gap-3">
          <div><Label className="text-xs">Name *</Label><Input value={formName} onChange={(e) => setFormName(e.target.value)} className="mt-0.5" /></div>
          <div><Label className="text-xs">Title</Label><Input value={formTitle} onChange={(e) => setFormTitle(e.target.value)} className="mt-0.5" placeholder="e.g. Funeral Director" /></div>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div><Label className="text-xs">Phone</Label><Input value={formPhone} onChange={(e) => setFormPhone(e.target.value)} className="mt-0.5" /></div>
          <div><Label className="text-xs">Mobile</Label><Input value={formMobile} onChange={(e) => setFormMobile(e.target.value)} className="mt-0.5" /></div>
          <div><Label className="text-xs">Email</Label><Input value={formEmail} onChange={(e) => setFormEmail(e.target.value)} className="mt-0.5" /></div>
        </div>
        <div>
          <Label className="text-xs">Role</Label>
          <select value={formRole} onChange={(e) => setFormRole(e.target.value)} className="mt-0.5 w-full rounded-md border px-3 py-1.5 text-sm bg-background">
            <option value="">Select...</option>
            {ROLE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div className="flex flex-wrap gap-4 text-sm">
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={formPrimary} onChange={(e) => setFormPrimary(e.target.checked)} className="rounded" /> Primary contact</label>
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={formInvoices} onChange={(e) => setFormInvoices(e.target.checked)} className="rounded" /> Receives invoices</label>
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={formProofs} onChange={(e) => setFormProofs(e.target.checked)} className="rounded" /> Receives legacy proofs</label>
        </div>
        <div><Label className="text-xs">Notes</Label><Input value={formNotes} onChange={(e) => setFormNotes(e.target.value)} className="mt-0.5" /></div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => { resetForm(); setShowAdd(false); setEditId(null) }}>Cancel</Button>
          <Button size="sm" onClick={handleSave}>{editId ? "Save changes" : "Add contact"}</Button>
        </div>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm">Contacts</h3>
        {allowEdit && !showAdd && (
          <Button variant="outline" size="sm" onClick={() => { resetForm(); setShowAdd(true) }}>
            <Plus className="h-3.5 w-3.5 mr-1" /> Add contact
          </Button>
        )}
      </div>

      {/* Suggested contacts (auto-populated) */}
      {suggested.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 space-y-2">
          <p className="text-xs text-amber-800 font-medium">
            {suggested.length} contact{suggested.length > 1 ? "s" : ""} auto-populated from Bridgeable. Confirm or dismiss.
          </p>
          {suggested.map((c) => (
            <div key={c.id} className="flex items-center justify-between bg-white rounded-md p-2">
              <div>
                <p className="text-sm font-medium">{c.name}</p>
                {c.email && <p className="text-xs text-gray-500">{c.email}</p>}
                {c.linked_user_id && <Badge variant="outline" className="text-[10px] mt-0.5">Bridgeable user</Badge>}
              </div>
              <div className="flex gap-1.5">
                <Button size="sm" variant="outline" onClick={() => handleConfirm(c.id)}>
                  <Check className="h-3.5 w-3.5 mr-0.5" /> Add
                </Button>
                <Button size="sm" variant="ghost" onClick={() => handleDismiss(c.id)}>
                  <X className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add form */}
      {showAdd && renderForm()}

      {/* Confirmed contacts */}
      {confirmed.length === 0 && !showAdd && (
        <div className="text-center py-4">
          <p className="text-sm text-gray-500">No contacts yet</p>
          <p className="text-xs text-gray-400 mt-0.5">Add contacts to track who to call and who receives invoices and proofs.</p>
        </div>
      )}

      {confirmed.map((c) => (
        <div key={c.id} className="flex items-start justify-between py-2 border-b border-gray-100 last:border-0">
          {editId === c.id ? (
            <div className="w-full">{renderForm()}</div>
          ) : (
            <>
              <div className="space-y-0.5">
                <div className="flex items-center gap-1.5">
                  {c.is_primary && <Badge className="text-[10px] bg-amber-100 text-amber-800">Primary</Badge>}
                  <span className="font-medium text-sm">{c.name}</span>
                  {c.title && <span className="text-xs text-gray-500">· {c.title}</span>}
                </div>
                <div className="flex items-center gap-3 text-xs text-gray-500">
                  {c.phone && <span className="flex items-center gap-0.5"><Phone className="h-3 w-3" />{c.phone}</span>}
                  {c.email && <span className="flex items-center gap-0.5"><Mail className="h-3 w-3" />{c.email}</span>}
                </div>
                <div className="flex gap-1.5 mt-0.5">
                  {c.receives_invoices && <Badge variant="outline" className="text-[10px]">Invoices</Badge>}
                  {c.receives_legacy_proofs && <Badge variant="outline" className="text-[10px]">Proofs</Badge>}
                </div>
              </div>
              {allowEdit && (
                <div className="relative">
                  <button onClick={() => setMenuId(menuId === c.id ? null : c.id)} className="p-1 hover:bg-gray-100 rounded">
                    <MoreHorizontal className="h-4 w-4 text-gray-400" />
                  </button>
                  {menuId === c.id && (
                    <div className="absolute right-0 top-8 bg-white border rounded-lg shadow-lg py-1 z-10 w-48">
                      {!c.is_primary && (
                        <button onClick={() => { handleSetPrimary(c.id); setMenuId(null) }} className="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50">Set as primary</button>
                      )}
                      <button onClick={() => { handleToggle(c.id, "receives_invoices", !c.receives_invoices); setMenuId(null) }} className="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50">
                        {c.receives_invoices ? "Stop" : "Start"} receiving invoices
                      </button>
                      <button onClick={() => { handleToggle(c.id, "receives_legacy_proofs", !c.receives_legacy_proofs); setMenuId(null) }} className="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50">
                        {c.receives_legacy_proofs ? "Stop" : "Start"} receiving proofs
                      </button>
                      <button onClick={() => { loadIntoForm(c); setEditId(c.id); setMenuId(null) }} className="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50">Edit details</button>
                      <button onClick={() => { handleDelete(c.id); setMenuId(null) }} className="w-full text-left px-3 py-1.5 text-sm text-red-600 hover:bg-red-50">Deactivate</button>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      ))}
    </div>
  )
}
