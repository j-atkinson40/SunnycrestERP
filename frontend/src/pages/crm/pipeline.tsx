// pipeline.tsx — CRM sales pipeline (kanban-style)
// Route: /vault/crm/pipeline (only when pipeline_enabled=true)

import { useState, useEffect, useCallback } from "react"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Plus, Loader2, X } from "lucide-react"

interface Opportunity {
  id: string
  title: string
  company_name: string | null
  master_company_id: string | null
  city: string | null
  state: string | null
  stage: string
  estimated_annual_value: number | null
  assigned_to: string | null
  expected_close_date: string | null
  notes: string | null
  created_at: string | null
}

const STAGES = [
  { key: "prospect", label: "Prospect" },
  { key: "contacted", label: "Contacted" },
  { key: "meeting_scheduled", label: "Meeting" },
  { key: "proposal_sent", label: "Proposal" },
  { key: "negotiating", label: "Negotiating" },
  { key: "won", label: "Won" },
  { key: "lost", label: "Lost" },
]

export default function PipelinePage() {
  const [stages, setStages] = useState<Record<string, Opportunity[]>>({})
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [formTitle, setFormTitle] = useState("")
  const [formName, setFormName] = useState("")
  const [formCity, setFormCity] = useState("")
  const [formState, setFormState] = useState("")
  const [formValue, setFormValue] = useState("")
  const [creating, setCreating] = useState(false)

  const loadData = useCallback(async () => {
    try {
      const res = await apiClient.get("/companies/opportunities")
      setStages(res.data.stages || {})
    } catch {
      toast.error("Could not load pipeline")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  async function handleCreate() {
    if (!formTitle.trim()) return
    setCreating(true)
    try {
      await apiClient.post("/companies/opportunities", {
        title: formTitle,
        prospect_name: formName || null,
        prospect_city: formCity || null,
        prospect_state: formState || null,
        estimated_annual_value: formValue ? parseFloat(formValue) : null,
      })
      toast.success("Opportunity created")
      setShowCreate(false); setFormTitle(""); setFormName(""); setFormCity(""); setFormState(""); setFormValue("")
      loadData()
    } catch {
      toast.error("Failed")
    } finally {
      setCreating(false)
    }
  }

  async function handleMoveStage(oppId: string, newStage: string) {
    try {
      await apiClient.patch(`/companies/opportunities/${oppId}`, { stage: newStage })
      loadData()
    } catch {
      toast.error("Failed")
    }
  }

  async function handleDelete(oppId: string) {
    if (!window.confirm("Delete this opportunity?")) return
    try {
      await apiClient.delete(`/companies/opportunities/${oppId}`)
      loadData()
    } catch {
      toast.error("Failed")
    }
  }

  function fmtCurrency(n: number) { return `$${n.toLocaleString()}` }

  if (loading) return <div className="flex justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-gray-400" /></div>

  return (
    <div className="max-w-full mx-auto px-6 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Sales Pipeline</h1>
          <p className="text-sm text-gray-500 mt-1">Track prospective funeral homes and sales opportunities</p>
        </div>
        <Button onClick={() => setShowCreate(true)}><Plus className="h-4 w-4 mr-1" /> New opportunity</Button>
      </div>

      {/* Create form */}
      {showCreate && (
        <Card className="p-4 space-y-3 border-blue-200 max-w-md">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-sm">New Opportunity</h3>
            <button onClick={() => setShowCreate(false)}><X className="h-4 w-4 text-gray-400" /></button>
          </div>
          <div><Label className="text-xs">Title *</Label><Input value={formTitle} onChange={(e) => setFormTitle(e.target.value)} className="mt-0.5" /></div>
          <div><Label className="text-xs">Prospect name</Label><Input value={formName} onChange={(e) => setFormName(e.target.value)} className="mt-0.5" /></div>
          <div className="grid grid-cols-2 gap-2">
            <div><Label className="text-xs">City</Label><Input value={formCity} onChange={(e) => setFormCity(e.target.value)} className="mt-0.5" /></div>
            <div><Label className="text-xs">State</Label><Input value={formState} onChange={(e) => setFormState(e.target.value)} className="mt-0.5" /></div>
          </div>
          <div><Label className="text-xs">Est. annual value</Label><Input type="number" value={formValue} onChange={(e) => setFormValue(e.target.value)} className="mt-0.5" placeholder="$" /></div>
          <Button onClick={handleCreate} disabled={creating || !formTitle.trim()} className="w-full">{creating ? "Creating..." : "Create"}</Button>
        </Card>
      )}

      {/* Kanban columns */}
      <div className="flex gap-4 overflow-x-auto pb-4">
        {STAGES.map((stage) => {
          const items = stages[stage.key] || []
          return (
            <div key={stage.key} className="min-w-[240px] max-w-[280px] flex-shrink-0">
              <div className="flex items-center justify-between mb-2 px-1">
                <span className="text-sm font-semibold text-gray-700">{stage.label}</span>
                <Badge variant="secondary" className="text-[10px]">{items.length}</Badge>
              </div>
              <div className="space-y-2">
                {items.map((opp) => (
                  <Card key={opp.id} className="p-3 space-y-1.5">
                    <p className="font-medium text-sm">{opp.title}</p>
                    {opp.company_name && <p className="text-xs text-gray-600">{opp.company_name}</p>}
                    {opp.city && <p className="text-xs text-gray-400">{opp.city}{opp.state ? `, ${opp.state}` : ""}</p>}
                    {opp.estimated_annual_value != null && <p className="text-xs text-green-600 font-medium">{fmtCurrency(opp.estimated_annual_value)}/yr</p>}
                    {opp.expected_close_date && <p className="text-[10px] text-gray-400">Close: {opp.expected_close_date}</p>}
                    <div className="flex gap-1 pt-1">
                      <select
                        value={opp.stage}
                        onChange={(e) => handleMoveStage(opp.id, e.target.value)}
                        className="text-[11px] border rounded px-1 py-0.5 bg-background flex-1"
                      >
                        {STAGES.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
                      </select>
                      <button onClick={() => handleDelete(opp.id)} className="text-[11px] text-red-500 hover:underline px-1">Del</button>
                    </div>
                  </Card>
                ))}
                {items.length === 0 && <p className="text-xs text-gray-300 text-center py-4">Empty</p>}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
