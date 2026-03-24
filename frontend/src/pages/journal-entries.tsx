/**
 * Journal Entries page — /journal-entries
 * Three tabs: Entries, Templates, Periods
 * AI natural language input + traditional debit/credit form
 */

import { useState, useEffect, useCallback } from "react"
import { toast } from "sonner"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  Plus, Check, X, RefreshCw, Undo2, Lock, Unlock,
  FileText, Calendar, Sparkles,
} from "lucide-react"
import { cn } from "@/lib/utils"
import apiClient from "@/lib/api-client"

// ── Types ──

interface JEEntry {
  id: string; entry_number: string; entry_type: string; status: string
  entry_date: string; period_month: number; period_year: number
  description: string; total_debits: number; total_credits: number
  is_reversal: boolean; reversal_of_entry_id: string | null
  posted_at: string | null
}

interface GLAccount {
  id: string; account_number: string; account_name: string; category: string
}

interface Template {
  id: string; template_name: string; entry_type: string; frequency: string
  is_active: boolean; auto_post: boolean
  next_run_date: string | null; last_run_date: string | null
}

interface Period {
  id: string; period_month: number; period_year: number; status: string
  closed_at: string | null
}

const STATUS_BADGE: Record<string, { label: string; color: string }> = {
  draft: { label: "Draft", color: "bg-gray-100 text-gray-600" },
  pending_review: { label: "Pending Review", color: "bg-amber-100 text-amber-700" },
  posted: { label: "Posted", color: "bg-green-100 text-green-700" },
  reversed: { label: "Reversed", color: "bg-red-100 text-red-600" },
}

const ENTRY_TYPES = ["manual", "adjusting", "correcting", "recurring", "closing", "reversal"]
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

// ── Main Page ──

export default function JournalEntriesPage() {
  const [activeTab, setActiveTab] = useState("entries")

  const tabs = [
    { key: "entries", label: "Entries", icon: FileText },
    { key: "templates", label: "Templates", icon: RefreshCw },
    { key: "periods", label: "Periods", icon: Calendar },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Journal Entries</h1>
          <p className="text-sm text-gray-500 mt-1">Manual adjustments, recurring entries, and period management</p>
        </div>
      </div>

      <div className="border-b border-gray-200">
        <nav className="-mb-px flex gap-6">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                "pb-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5",
                activeTab === tab.key ? "border-gray-900 text-gray-900" : "border-transparent text-gray-500 hover:text-gray-700"
              )}
            >
              <tab.icon className="h-3.5 w-3.5" />
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {activeTab === "entries" && <EntriesTab />}
      {activeTab === "templates" && <TemplatesTab />}
      {activeTab === "periods" && <PeriodsTab />}
    </div>
  )
}

// ── Entries Tab ──

function EntriesTab() {
  const [entries, setEntries] = useState<JEEntry[]>([])
  const [glAccounts, setGLAccounts] = useState<GLAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [aiInput, setAIInput] = useState("")
  const [aiParsing, setAIParsing] = useState(false)

  // Form state
  const [formType, setFormType] = useState("manual")
  const [formDate, setFormDate] = useState(new Date().toISOString().split("T")[0])
  const [formDesc, setFormDesc] = useState("")
  const [formRef, setFormRef] = useState("")
  const [formLines, setFormLines] = useState<{ gl_account_id: string; description: string; debit: string; credit: string }[]>([
    { gl_account_id: "", description: "", debit: "", credit: "" },
    { gl_account_id: "", description: "", debit: "", credit: "" },
  ])
  const [submitting, setSubmitting] = useState(false)

  const fetchData = useCallback(() => {
    setLoading(true)
    Promise.all([
      apiClient.get("/journal-entries/entries").then((r) => setEntries(r.data)),
      apiClient.get("/journal-entries/gl-accounts").then((r) => setGLAccounts(r.data)),
    ]).catch(() => {}).finally(() => setLoading(false))
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  const handleAIParse = async () => {
    if (!aiInput.trim()) return
    setAIParsing(true)
    try {
      const res = await apiClient.post("/journal-entries/entries/parse", { input: aiInput.trim() })
      const data = res.data
      if (data.lines?.length) {
        setFormDesc(data.description || aiInput)
        setFormType(data.entry_type || "manual")
        if (data.entry_date) setFormDate(data.entry_date)
        setFormLines(data.lines.map((l: { gl_account_id?: string; side: string; amount: number; description?: string }) => ({
          gl_account_id: l.gl_account_id || "",
          description: l.description || "",
          debit: l.side === "debit" ? String(l.amount) : "",
          credit: l.side === "credit" ? String(l.amount) : "",
        })))
        setShowForm(true)
        setAIInput("")
        toast.success(`Parsed ${data.lines.length} lines — review and post`)
      } else {
        toast.error(data.clarification_needed || "Could not parse entry")
      }
    } catch {
      toast.error("Failed to parse entry")
    } finally {
      setAIParsing(false)
    }
  }

  const addLine = () => {
    setFormLines((prev) => [...prev, { gl_account_id: "", description: "", debit: "", credit: "" }])
  }

  const updateLine = (idx: number, field: string, value: string) => {
    setFormLines((prev) => prev.map((l, i) => {
      if (i !== idx) return l
      const updated = { ...l, [field]: value }
      if (field === "debit" && value) updated.credit = ""
      if (field === "credit" && value) updated.debit = ""
      return updated
    }))
  }

  const totalDebits = formLines.reduce((s, l) => s + (parseFloat(l.debit) || 0), 0)
  const totalCredits = formLines.reduce((s, l) => s + (parseFloat(l.credit) || 0), 0)
  const isBalanced = Math.abs(totalDebits - totalCredits) < 0.005 && totalDebits > 0

  const handleSubmit = async (post: boolean) => {
    if (!formDesc.trim()) { toast.error("Description required"); return }
    const lines = formLines.filter((l) => l.gl_account_id && (parseFloat(l.debit) || parseFloat(l.credit)))
    if (lines.length < 2) { toast.error("At least 2 lines required"); return }
    if (post && !isBalanced) { toast.error("Entry must be balanced to post"); return }

    setSubmitting(true)
    try {
      const res = await apiClient.post("/journal-entries/entries", {
        entry_type: formType,
        entry_date: formDate,
        description: formDesc.trim(),
        reference_number: formRef.trim() || null,
        lines: lines.map((l) => ({
          gl_account_id: l.gl_account_id,
          debit_amount: parseFloat(l.debit) || 0,
          credit_amount: parseFloat(l.credit) || 0,
          description: l.description || null,
        })),
      })
      if (post) {
        await apiClient.post(`/journal-entries/entries/${res.data.id}/post`)
        toast.success(`${res.data.entry_number} posted`)
      } else {
        toast.success(`${res.data.entry_number} saved as draft`)
      }
      setShowForm(false)
      setFormDesc("")
      setFormRef("")
      setFormLines([
        { gl_account_id: "", description: "", debit: "", credit: "" },
        { gl_account_id: "", description: "", debit: "", credit: "" },
      ])
      fetchData()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed"
      toast.error(msg)
    } finally {
      setSubmitting(false)
    }
  }

  const handlePost = async (entryId: string) => {
    try {
      await apiClient.post(`/journal-entries/entries/${entryId}/post`)
      toast.success("Entry posted")
      fetchData()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to post"
      toast.error(msg)
    }
  }

  const handleReverse = async (entryId: string) => {
    try {
      const res = await apiClient.post(`/journal-entries/entries/${entryId}/reverse`)
      toast.success(`Reversal ${res.data.entry_number} created and posted`)
      fetchData()
    } catch {
      toast.error("Failed to create reversal")
    }
  }

  return (
    <div className="space-y-4">
      {/* AI input bar */}
      <div className="flex gap-2">
        <div className="flex-1 relative">
          <Sparkles className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
          <input
            value={aiInput}
            onChange={(e) => setAIInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAIParse()}
            placeholder="Describe a journal entry... e.g. 'Record monthly depreciation $1,200'"
            className="w-full rounded-lg border border-gray-300 pl-9 pr-3 py-2 text-sm"
            disabled={aiParsing}
          />
        </div>
        <Button size="sm" onClick={handleAIParse} disabled={aiParsing || !aiInput.trim()} className="gap-1">
          {aiParsing ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
          Parse
        </Button>
        <Button size="sm" variant="outline" onClick={() => setShowForm(!showForm)} className="gap-1">
          <Plus className="h-3.5 w-3.5" /> Manual
        </Button>
      </div>

      {/* Entry form */}
      {showForm && (
        <Card>
          <CardContent className="p-5 space-y-4">
            <div className="grid grid-cols-4 gap-3">
              <div>
                <label className="text-[10px] font-medium text-gray-500">Type</label>
                <select value={formType} onChange={(e) => setFormType(e.target.value)} className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs mt-0.5">
                  {ENTRY_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[10px] font-medium text-gray-500">Date</label>
                <input type="date" value={formDate} onChange={(e) => setFormDate(e.target.value)} className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs mt-0.5" />
              </div>
              <div className="col-span-2">
                <label className="text-[10px] font-medium text-gray-500">Description</label>
                <input value={formDesc} onChange={(e) => setFormDesc(e.target.value)} className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs mt-0.5" placeholder="Entry description" />
              </div>
            </div>

            {/* Lines table */}
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-1.5 font-medium text-gray-500 w-1/3">Account</th>
                    <th className="text-left py-1.5 font-medium text-gray-500 w-1/4">Description</th>
                    <th className="text-right py-1.5 font-medium text-gray-500 w-1/6">Debit</th>
                    <th className="text-right py-1.5 font-medium text-gray-500 w-1/6">Credit</th>
                    <th className="w-8"></th>
                  </tr>
                </thead>
                <tbody>
                  {formLines.map((line, i) => (
                    <tr key={i} className="border-b border-gray-100">
                      <td className="py-1">
                        <select value={line.gl_account_id} onChange={(e) => updateLine(i, "gl_account_id", e.target.value)} className="w-full rounded border border-gray-200 px-1.5 py-1 text-xs">
                          <option value="">Select account...</option>
                          {glAccounts.map((a) => <option key={a.id} value={a.id}>{a.account_number} — {a.account_name}</option>)}
                        </select>
                      </td>
                      <td className="py-1">
                        <input value={line.description} onChange={(e) => updateLine(i, "description", e.target.value)} className="w-full rounded border border-gray-200 px-1.5 py-1 text-xs" />
                      </td>
                      <td className="py-1">
                        <input type="number" step="0.01" value={line.debit} onChange={(e) => updateLine(i, "debit", e.target.value)} className="w-full rounded border border-gray-200 px-1.5 py-1 text-xs text-right" placeholder="0.00" />
                      </td>
                      <td className="py-1">
                        <input type="number" step="0.01" value={line.credit} onChange={(e) => updateLine(i, "credit", e.target.value)} className="w-full rounded border border-gray-200 px-1.5 py-1 text-xs text-right" placeholder="0.00" />
                      </td>
                      <td>
                        {formLines.length > 2 && (
                          <button onClick={() => setFormLines((p) => p.filter((_, j) => j !== i))} className="text-gray-300 hover:text-gray-500"><X className="h-3.5 w-3.5" /></button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t border-gray-300">
                    <td colSpan={2} className="py-2">
                      <button onClick={addLine} className="text-xs text-blue-600 hover:text-blue-700">+ Add line</button>
                    </td>
                    <td className="py-2 text-right text-xs font-medium">${totalDebits.toFixed(2)}</td>
                    <td className="py-2 text-right text-xs font-medium">${totalCredits.toFixed(2)}</td>
                    <td></td>
                  </tr>
                </tfoot>
              </table>
            </div>

            {/* Balance indicator */}
            <div className={cn("text-xs font-medium flex items-center gap-1.5", isBalanced ? "text-green-600" : "text-red-600")}>
              {isBalanced ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
              {isBalanced ? "Balanced" : `Out of balance by $${Math.abs(totalDebits - totalCredits).toFixed(2)}`}
            </div>

            <div className="flex items-center gap-2">
              <Button size="sm" variant="outline" onClick={() => handleSubmit(false)} disabled={submitting}>Save Draft</Button>
              <Button size="sm" onClick={() => handleSubmit(true)} disabled={submitting || !isBalanced}>
                {submitting ? "Saving..." : "Post"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Entry list */}
      {loading ? (
        <div className="flex justify-center py-12"><RefreshCw className="h-6 w-6 animate-spin text-gray-300" /></div>
      ) : entries.length === 0 ? (
        <Card><CardContent className="p-8 text-center"><p className="text-sm text-gray-400">No journal entries yet</p></CardContent></Card>
      ) : (
        <div className="space-y-1.5">
          {entries.map((e) => {
            const badge = STATUS_BADGE[e.status] || STATUS_BADGE.draft
            return (
              <Card key={e.id}>
                <CardContent className="p-3 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-400 font-mono w-16">{e.entry_number}</span>
                    <span className="text-xs text-gray-400 w-20">{e.entry_date}</span>
                    <span className="text-sm text-gray-900 truncate max-w-xs">{e.description}</span>
                    {e.is_reversal && <span className="text-[10px] bg-red-50 text-red-600 rounded px-1 py-0.5">Reversal</span>}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-600">${e.total_debits.toFixed(2)}</span>
                    <span className={cn("text-[10px] px-1.5 py-0.5 rounded", badge.color)}>{badge.label}</span>
                    {e.status === "draft" && (
                      <Button size="sm" variant="ghost" className="h-6 text-[10px]" onClick={() => handlePost(e.id)}>Post</Button>
                    )}
                    {e.status === "posted" && (
                      <Button size="sm" variant="ghost" className="h-6 text-[10px]" onClick={() => handleReverse(e.id)}>
                        <Undo2 className="h-3 w-3 mr-0.5" /> Reverse
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Templates Tab ──

function TemplatesTab() {
  const [templates, setTemplates] = useState<Template[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiClient.get("/journal-entries/templates")
      .then((r) => setTemplates(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="flex justify-center py-12"><RefreshCw className="h-6 w-6 animate-spin text-gray-300" /></div>

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button size="sm" variant="outline" className="gap-1"><Plus className="h-3.5 w-3.5" /> New Template</Button>
      </div>
      {templates.length === 0 ? (
        <Card><CardContent className="p-8 text-center"><p className="text-sm text-gray-400">No templates yet. Create one to automate recurring entries.</p></CardContent></Card>
      ) : (
        <div className="space-y-2">
          {templates.map((t) => (
            <Card key={t.id}>
              <CardContent className="p-3 flex items-center justify-between">
                <div>
                  <span className="text-sm font-medium text-gray-900">{t.template_name}</span>
                  <span className="text-xs text-gray-400 ml-2">{t.frequency} · {t.entry_type}</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  {t.next_run_date && <span className="text-gray-500">Next: {t.next_run_date}</span>}
                  <span className={cn("px-1.5 py-0.5 rounded", t.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500")}>
                    {t.is_active ? "Active" : "Inactive"}
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Periods Tab ──

function PeriodsTab() {
  const [periods, setPeriods] = useState<Period[]>([])
  const [loading, setLoading] = useState(true)

  const fetchPeriods = useCallback(() => {
    setLoading(true)
    apiClient.get("/journal-entries/periods")
      .then((r) => setPeriods(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { fetchPeriods() }, [fetchPeriods])

  const handleClose = async (month: number, year: number) => {
    try {
      await apiClient.post("/journal-entries/periods/close", { period_month: month, period_year: year })
      toast.success(`${MONTHS[month - 1]} ${year} closed`)
      fetchPeriods()
    } catch { toast.error("Failed to close period") }
  }

  const handleOpen = async (month: number, year: number) => {
    try {
      await apiClient.post("/journal-entries/periods/open", { period_month: month, period_year: year })
      toast.success(`${MONTHS[month - 1]} ${year} reopened`)
      fetchPeriods()
    } catch { toast.error("Failed to open period") }
  }

  if (loading) return <div className="flex justify-center py-12"><RefreshCw className="h-6 w-6 animate-spin text-gray-300" /></div>

  const PERIOD_BADGE: Record<string, { label: string; color: string; icon: typeof Lock }> = {
    open: { label: "Open", color: "bg-green-100 text-green-700", icon: Unlock },
    review: { label: "Review", color: "bg-amber-100 text-amber-700", icon: Lock },
    closed: { label: "Closed", color: "bg-red-100 text-red-600", icon: Lock },
  }

  return (
    <div className="space-y-2">
      {periods.map((p) => {
        const badge = PERIOD_BADGE[p.status] || PERIOD_BADGE.open
        const Icon = badge.icon
        return (
          <Card key={p.id}>
            <CardContent className="p-3 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Icon className="h-4 w-4 text-gray-400" />
                <span className="text-sm font-medium text-gray-900">{MONTHS[p.period_month - 1]} {p.period_year}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className={cn("text-[10px] px-1.5 py-0.5 rounded", badge.color)}>{badge.label}</span>
                {p.status === "open" && (
                  <Button size="sm" variant="ghost" className="h-6 text-[10px]" onClick={() => handleClose(p.period_month, p.period_year)}>
                    <Lock className="h-3 w-3 mr-0.5" /> Close
                  </Button>
                )}
                {p.status === "closed" && (
                  <Button size="sm" variant="ghost" className="h-6 text-[10px]" onClick={() => handleOpen(p.period_month, p.period_year)}>
                    <Unlock className="h-3 w-3 mr-0.5" /> Reopen
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
