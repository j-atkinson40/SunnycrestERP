// companies-list-mobile.tsx — Mobile card-based companies list
// Replaces the data table on mobile devices.

import { useState, useEffect, useCallback, useRef } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  Loader2, Search, Phone, StickyNote, ChevronRight, X, Filter, Plus,
} from "lucide-react"

// ── Types ───────────────────────────────────────────────────────────────────

interface CompanySummary {
  id: string
  name: string
  legal_name: string | null
  city: string | null
  state: string | null
  is_customer: boolean
  is_vendor: boolean
  is_cemetery: boolean
  is_funeral_home: boolean
  is_licensee: boolean
  primary_contact: { name: string; phone: string | null } | null
  linked_customer_id: string | null
  linked_vendor_id: string | null
  created_at: string | null
  last_activity_date: string | null
}

const ROLE_FILTERS = [
  { value: "", label: "All" },
  { value: "customer", label: "Customers" },
  { value: "vendor", label: "Vendors" },
  { value: "cemetery", label: "Cemeteries" },
  { value: "funeral_home", label: "Funeral Homes" },
  { value: "licensee", label: "Licensees" },
]

const ROLE_BADGES: Record<string, { label: string; className: string }> = {
  customer: { label: "Customer", className: "bg-blue-100 text-blue-700" },
  vendor: { label: "Vendor", className: "bg-purple-100 text-purple-700" },
  cemetery: { label: "Cemetery", className: "bg-green-100 text-green-700" },
  funeral_home: { label: "Funeral Home", className: "bg-teal-100 text-teal-700" },
  licensee: { label: "Licensee", className: "bg-amber-100 text-amber-700" },
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function getRoles(item: CompanySummary): string[] {
  const roles: string[] = []
  if (item.is_customer) roles.push("customer")
  if (item.is_vendor) roles.push("vendor")
  if (item.is_cemetery) roles.push("cemetery")
  if (item.is_funeral_home) roles.push("funeral_home")
  if (item.is_licensee) roles.push("licensee")
  return roles
}

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return ""
  const diff = Date.now() - new Date(dateStr).getTime()
  const days = Math.floor(diff / 86400000)
  if (days === 0) return "Today"
  if (days === 1) return "Yesterday"
  if (days < 30) return `${days}d ago`
  return `${Math.floor(days / 30)}mo ago`
}

function primaryRoleLabel(item: CompanySummary): string {
  if (item.is_funeral_home) return "Funeral Home"
  if (item.is_customer) return "Customer"
  if (item.is_vendor) return "Vendor"
  if (item.is_cemetery) return "Cemetery"
  if (item.is_licensee) return "Licensee"
  return ""
}

// ── Component ───────────────────────────────────────────────────────────────

export default function CompaniesListMobile() {
  const navigate = useNavigate()
  const [urlParams] = useSearchParams()
  const [items, setItems] = useState<CompanySummary[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [roleFilter, setRoleFilter] = useState(urlParams.get("role") || "")
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [showFilters, setShowFilters] = useState(false)

  // Quick note bottom sheet
  const [noteTarget, setNoteTarget] = useState<CompanySummary | null>(null)
  const [noteText, setNoteText] = useState("")
  const [noteSaving, setNoteSaving] = useState(false)
  const noteInputRef = useRef<HTMLTextAreaElement>(null)

  const fetchData = useCallback(async () => {
    try {
      const params = new URLSearchParams()
      if (search) params.set("q", search)
      if (roleFilter) params.set("role", roleFilter)
      params.set("page", String(page))
      params.set("per_page", "20")
      const res = await apiClient.get(`/companies?${params}`)
      setItems(res.data.items || [])
      setTotal(res.data.total || 0)
    } catch {
      toast.error("Could not load companies")
    } finally {
      setLoading(false)
    }
  }, [search, roleFilter, page])

  useEffect(() => { fetchData() }, [fetchData])

  useEffect(() => {
    const t = setTimeout(() => { setPage(1); fetchData() }, 300)
    return () => clearTimeout(t)
  }, [search])

  // Focus note input when sheet opens
  useEffect(() => {
    if (noteTarget) {
      setTimeout(() => noteInputRef.current?.focus(), 100)
    }
  }, [noteTarget])

  async function handleSaveNote() {
    if (!noteTarget || !noteText.trim()) return
    setNoteSaving(true)
    try {
      await apiClient.post(`/companies/${noteTarget.id}/activity`, {
        activity_type: "note",
        title: "Quick note",
        body: noteText,
      })
      toast.success("Note saved")
      setNoteTarget(null)
      setNoteText("")
    } catch {
      toast.error("Failed to save note")
    } finally {
      setNoteSaving(false)
    }
  }

  const activeFilterLabel = ROLE_FILTERS.find((f) => f.value === roleFilter)?.label || "All"

  return (
    <div className="fixed inset-0 z-40 bg-gray-50 flex flex-col">
      {/* Header */}
      <div className="bg-white border-b px-4 pt-3 pb-2 space-y-2">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-bold text-gray-900">Companies</h1>
          <Button size="sm" onClick={() => navigate("/vault/crm/companies/new")} className="h-8 px-3">
            <Plus className="h-3.5 w-3.5 mr-1" /> New
          </Button>
        </div>

        {/* Search bar */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search companies..."
            className="pl-9 h-10"
          />
        </div>

        {/* Filter button */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFilters(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border border-gray-200 bg-white"
          >
            <Filter className="h-3 w-3" />
            {activeFilterLabel}
          </button>
          {roleFilter && (
            <button
              onClick={() => { setRoleFilter(""); setPage(1) }}
              className="text-xs text-blue-600 font-medium"
            >
              Clear
            </button>
          )}
          <span className="text-xs text-gray-400 ml-auto">{total} companies</span>
        </div>
      </div>

      {/* Card list */}
      <div className="flex-1 overflow-auto px-4 py-3 space-y-2">
        {loading ? (
          <div className="flex justify-center py-16">
            <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-gray-500 text-sm">
              {search || roleFilter ? "No companies match your filters" : "No companies yet"}
            </p>
            {(search || roleFilter) && (
              <Button
                variant="outline"
                size="sm"
                className="mt-3"
                onClick={() => { setSearch(""); setRoleFilter("") }}
              >
                Clear filters
              </Button>
            )}
          </div>
        ) : (
          <>
            {items.map((item) => {
              const roles = getRoles(item)
              const location = item.city && item.state ? `${item.city}, ${item.state}` : item.city || item.state || ""
              const lastActivity = timeAgo(item.last_activity_date || item.created_at)
              const roleLabel = primaryRoleLabel(item)

              return (
                <div
                  key={item.id}
                  className="bg-white rounded-xl border border-gray-200 p-4 space-y-2.5"
                >
                  {/* Company name + role */}
                  <div>
                    <h3 className="font-semibold text-gray-900">{item.name}</h3>
                    <div className="flex items-center gap-2 mt-0.5">
                      {roleLabel && (
                        <span className="text-xs text-gray-500">{roleLabel}</span>
                      )}
                      {roleLabel && location && (
                        <span className="text-xs text-gray-300">&middot;</span>
                      )}
                      {location && (
                        <span className="text-xs text-gray-500">{location}</span>
                      )}
                    </div>
                    {roles.length > 1 && (
                      <div className="flex gap-1 mt-1">
                        {roles.map((r) => {
                          const b = ROLE_BADGES[r]
                          return b ? (
                            <Badge key={r} className={`text-[9px] px-1.5 py-0 ${b.className}`}>
                              {b.label}
                            </Badge>
                          ) : null
                        })}
                      </div>
                    )}
                  </div>

                  {/* Contact + activity info */}
                  <div className="space-y-1 text-xs text-gray-500">
                    {item.primary_contact && (
                      <div className="flex items-center gap-1.5">
                        <Phone className="h-3 w-3" />
                        <span>{item.primary_contact.name}</span>
                      </div>
                    )}
                    {lastActivity && (
                      <div>Last activity: {lastActivity}</div>
                    )}
                  </div>

                  {/* Action buttons */}
                  <div className="flex items-center gap-2 pt-1">
                    {item.primary_contact?.phone && (
                      <a
                        href={`tel:${item.primary_contact.phone}`}
                        onClick={(e) => e.stopPropagation()}
                        className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium border border-gray-200 bg-white text-gray-700 active:bg-gray-100"
                      >
                        <Phone className="h-3 w-3" /> Call
                      </a>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setNoteTarget(item)
                        setNoteText("")
                      }}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium border border-gray-200 bg-white text-gray-700 active:bg-gray-100"
                    >
                      <StickyNote className="h-3 w-3" /> Log note
                    </button>
                    <button
                      onClick={() => navigate(`/vault/crm/companies/${item.id}`)}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-900 text-white ml-auto active:bg-gray-700"
                    >
                      View <ChevronRight className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              )
            })}

            {/* Pagination */}
            {total > 20 && (
              <div className="flex items-center justify-between pt-2 pb-4">
                <span className="text-xs text-gray-500">
                  {(page - 1) * 20 + 1}&ndash;{Math.min(page * 20, total)} of {total}
                </span>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                    Prev
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= Math.ceil(total / 20)}
                    onClick={() => setPage(page + 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* ── Filter bottom sheet ──────────────────────────────────────── */}
      {showFilters && (
        <div className="fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/40" onClick={() => setShowFilters(false)} />
          <div className="absolute bottom-0 left-0 right-0 bg-white rounded-t-2xl animate-in slide-in-from-bottom duration-200">
            <div className="flex items-center justify-between px-4 py-3 border-b">
              <h3 className="font-semibold text-sm">Filter by role</h3>
              <button onClick={() => setShowFilters(false)}>
                <X className="h-5 w-5 text-gray-400" />
              </button>
            </div>
            <div className="px-4 py-3 space-y-1">
              {ROLE_FILTERS.map((f) => (
                <button
                  key={f.value}
                  onClick={() => {
                    setRoleFilter(f.value)
                    setPage(1)
                    setShowFilters(false)
                  }}
                  className={`w-full text-left px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                    roleFilter === f.value
                      ? "bg-blue-50 text-blue-700"
                      : "text-gray-700 active:bg-gray-100"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
            <div className="h-8" />
          </div>
        </div>
      )}

      {/* ── Quick note bottom sheet ──────────────────────────────────── */}
      {noteTarget && (
        <div className="fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/40" onClick={() => setNoteTarget(null)} />
          <div className="absolute bottom-0 left-0 right-0 bg-white rounded-t-2xl animate-in slide-in-from-bottom duration-200">
            <div className="flex items-center justify-between px-4 py-3 border-b">
              <div>
                <h3 className="font-semibold text-sm">Quick note</h3>
                <p className="text-xs text-gray-500">{noteTarget.name}</p>
              </div>
              <button onClick={() => setNoteTarget(null)}>
                <X className="h-5 w-5 text-gray-400" />
              </button>
            </div>
            <div className="px-4 py-3 space-y-3">
              <textarea
                ref={noteInputRef}
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                placeholder="Type a quick note..."
                rows={3}
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm resize-none"
              />
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => setNoteTarget(null)}
                >
                  Cancel
                </Button>
                <Button
                  className="flex-1"
                  disabled={!noteText.trim() || noteSaving}
                  onClick={handleSaveNote}
                >
                  {noteSaving ? "Saving..." : "Save note"}
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
