/**
 * Tax Settings — /settings/tax
 * Three tabs: Tax Rates, Jurisdictions, Exemptions
 */

import { useState, useEffect, useCallback } from "react"
import { toast } from "sonner"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Plus, Percent, MapPin, ShieldAlert, RefreshCw, Trash2, Star } from "lucide-react"
import { cn } from "@/lib/utils"
import apiClient from "@/lib/api-client"

interface TaxRate {
  id: string; rate_name: string; rate_percentage: number; description: string | null
  is_default: boolean; is_active: boolean; gl_account_id: string | null; jurisdiction_count: number
}

interface Jurisdiction {
  id: string; jurisdiction_name: string; state: string; county: string
  zip_codes: string[]; tax_rate_id: string; rate_name: string | null; rate_percentage: number | null; is_active: boolean
}

interface Exemption {
  customer_id: string; customer_name: string; tax_status: string
  exemption_certificate: string | null; exemption_expiry: string | null
  exemption_verified: boolean; is_expired: boolean; is_expiring: boolean; missing_cert: boolean
}

export default function TaxSettingsPage() {
  const [activeTab, setActiveTab] = useState("rates")
  const tabs = [
    { key: "rates", label: "Tax Rates", icon: Percent },
    { key: "jurisdictions", label: "Jurisdictions", icon: MapPin },
    { key: "exemptions", label: "Exemptions", icon: ShieldAlert },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Tax Configuration</h1>
        <p className="text-sm text-gray-500 mt-1">Manage tax rates, county jurisdictions, and customer exemptions</p>
      </div>
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex gap-6">
          {tabs.map((t) => (
            <button key={t.key} onClick={() => setActiveTab(t.key)} className={cn(
              "pb-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5",
              activeTab === t.key ? "border-gray-900 text-gray-900" : "border-transparent text-gray-500 hover:text-gray-700"
            )}>
              <t.icon className="h-3.5 w-3.5" /> {t.label}
            </button>
          ))}
        </nav>
      </div>
      {activeTab === "rates" && <RatesTab />}
      {activeTab === "jurisdictions" && <JurisdictionsTab />}
      {activeTab === "exemptions" && <ExemptionsTab />}
    </div>
  )
}

// ── Rates Tab ──

function RatesTab() {
  const [rates, setRates] = useState<TaxRate[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [formName, setFormName] = useState("")
  const [formPct, setFormPct] = useState("")
  const [formDesc, setFormDesc] = useState("")
  const [formDefault, setFormDefault] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const fetch = useCallback(() => {
    apiClient.get("/tax/rates").then((r) => setRates(r.data)).catch(() => {}).finally(() => setLoading(false))
  }, [])
  useEffect(() => { fetch() }, [fetch])

  const handleCreate = async () => {
    if (!formName || !formPct) { toast.error("Name and rate required"); return }
    setSubmitting(true)
    try {
      await apiClient.post("/tax/rates", { rate_name: formName, rate_percentage: parseFloat(formPct), description: formDesc || null, is_default: formDefault })
      toast.success("Rate created")
      setShowForm(false); setFormName(""); setFormPct(""); setFormDesc(""); setFormDefault(false)
      fetch()
    } catch { toast.error("Failed") } finally { setSubmitting(false) }
  }

  const handleSetDefault = async (id: string) => {
    await apiClient.post(`/tax/rates/${id}/set-default`).catch(() => {})
    fetch()
  }

  const handleDelete = async (id: string) => {
    try { await apiClient.delete(`/tax/rates/${id}`); fetch() }
    catch (e: unknown) { toast.error((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Cannot delete") }
  }

  if (loading) return <div className="flex justify-center py-12"><RefreshCw className="h-6 w-6 animate-spin text-gray-300" /></div>

  return (
    <div className="space-y-4">
      <Button size="sm" onClick={() => setShowForm(!showForm)} className="gap-1"><Plus className="h-3.5 w-3.5" /> Add Tax Rate</Button>

      {showForm && (
        <Card><CardContent className="p-4 space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <div><label className="text-[10px] font-medium text-gray-500">Rate Name</label><input value={formName} onChange={(e) => setFormName(e.target.value)} className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs mt-0.5" placeholder="e.g. Cayuga County" /></div>
            <div><label className="text-[10px] font-medium text-gray-500">Percentage</label><input type="number" step="0.0001" value={formPct} onChange={(e) => setFormPct(e.target.value)} className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs mt-0.5" placeholder="8.0000" /></div>
            <div><label className="text-[10px] font-medium text-gray-500">Description</label><input value={formDesc} onChange={(e) => setFormDesc(e.target.value)} className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs mt-0.5" /></div>
          </div>
          {formPct && <p className="text-xs text-gray-500">{formPct}% of $100.00 = ${(parseFloat(formPct) || 0).toFixed(2)}</p>}
          <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={formDefault} onChange={(e) => setFormDefault(e.target.checked)} className="h-3.5 w-3.5 rounded" /> Set as default rate</label>
          <div className="flex gap-2"><Button size="sm" onClick={handleCreate} disabled={submitting}>{submitting ? "Saving..." : "Save Rate"}</Button><Button size="sm" variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button></div>
        </CardContent></Card>
      )}

      {rates.length === 0 && !showForm ? (
        <Card><CardContent className="p-8 text-center"><p className="text-sm text-gray-400">Add your tax rates first, then assign them to counties.</p></CardContent></Card>
      ) : (
        <div className="space-y-2">
          {rates.map((r) => (
            <Card key={r.id}><CardContent className="p-3 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-900">{r.rate_name}</span>
                  {r.is_default && <span className="text-[10px] bg-blue-100 text-blue-700 rounded px-1.5 py-0.5">DEFAULT</span>}
                </div>
                <span className="text-xs text-gray-500">{r.rate_percentage}% · {r.jurisdiction_count} jurisdictions</span>
              </div>
              <div className="flex items-center gap-1">
                {!r.is_default && <Button size="sm" variant="ghost" className="h-6 text-[10px]" onClick={() => handleSetDefault(r.id)}><Star className="h-3 w-3" /></Button>}
                <Button size="sm" variant="ghost" className="h-6 text-[10px] text-red-500" onClick={() => handleDelete(r.id)}><Trash2 className="h-3 w-3" /></Button>
              </div>
            </CardContent></Card>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Jurisdictions Tab ──

function JurisdictionsTab() {
  const [jurisdictions, setJurisdictions] = useState<Jurisdiction[]>([])
  const [rates, setRates] = useState<TaxRate[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [formState, setFormState] = useState("")
  const [formCounty, setFormCounty] = useState("")
  const [formRateId, setFormRateId] = useState("")
  const [formZips, setFormZips] = useState("")
  const [submitting, setSubmitting] = useState(false)

  const fetch = useCallback(() => {
    Promise.all([
      apiClient.get("/tax/jurisdictions").then((r) => setJurisdictions(r.data)),
      apiClient.get("/tax/rates").then((r) => setRates(r.data)),
    ]).catch(() => {}).finally(() => setLoading(false))
  }, [])
  useEffect(() => { fetch() }, [fetch])

  const handleCreate = async () => {
    if (!formState || !formCounty || !formRateId) { toast.error("State, county, and rate required"); return }
    setSubmitting(true)
    try {
      const zips = formZips.split(",").map((z) => z.trim()).filter(Boolean)
      await apiClient.post("/tax/jurisdictions", { state: formState, county: formCounty, tax_rate_id: formRateId, zip_codes: zips.length ? zips : null })
      toast.success("Jurisdiction added")
      setShowForm(false); setFormState(""); setFormCounty(""); setFormRateId(""); setFormZips("")
      fetch()
    } catch { toast.error("Failed") } finally { setSubmitting(false) }
  }

  const handleDelete = async (id: string) => {
    await apiClient.delete(`/tax/jurisdictions/${id}`).catch(() => {})
    fetch()
  }

  const states = [...new Set(jurisdictions.map((j) => j.state))].sort()

  if (loading) return <div className="flex justify-center py-12"><RefreshCw className="h-6 w-6 animate-spin text-gray-300" /></div>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-500">{jurisdictions.length} counties · {states.length} states</p>
        <Button size="sm" onClick={() => setShowForm(!showForm)} className="gap-1"><Plus className="h-3.5 w-3.5" /> Add County</Button>
      </div>

      {showForm && (
        <Card><CardContent className="p-4 space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <div><label className="text-[10px] font-medium text-gray-500">State</label><input value={formState} onChange={(e) => setFormState(e.target.value.toUpperCase())} maxLength={2} className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs mt-0.5" placeholder="NY" /></div>
            <div><label className="text-[10px] font-medium text-gray-500">County</label><input value={formCounty} onChange={(e) => setFormCounty(e.target.value)} className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs mt-0.5" placeholder="Cayuga" /></div>
            <div><label className="text-[10px] font-medium text-gray-500">Tax Rate</label>
              <select value={formRateId} onChange={(e) => setFormRateId(e.target.value)} className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs mt-0.5">
                <option value="">Select rate...</option>
                {rates.map((r) => <option key={r.id} value={r.id}>{r.rate_name} ({r.rate_percentage}%)</option>)}
              </select>
            </div>
          </div>
          <div><label className="text-[10px] font-medium text-gray-500">Zip Codes (optional, comma-separated)</label><input value={formZips} onChange={(e) => setFormZips(e.target.value)} className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs mt-0.5" placeholder="13021, 13026, 13034" /></div>
          {formCounty && formState && <p className="text-xs text-gray-500">Deliveries to {formCounty}, {formState} will be taxed at {rates.find((r) => r.id === formRateId)?.rate_percentage || "?"}%</p>}
          <div className="flex gap-2"><Button size="sm" onClick={handleCreate} disabled={submitting}>{submitting ? "Saving..." : "Save"}</Button><Button size="sm" variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button></div>
        </CardContent></Card>
      )}

      {jurisdictions.length === 0 && !showForm ? (
        <Card><CardContent className="p-8 text-center"><p className="text-sm text-gray-400">No counties configured. Add a county to start collecting tax.</p></CardContent></Card>
      ) : (
        <div className="space-y-1.5">
          {jurisdictions.map((j) => (
            <Card key={j.id}><CardContent className="p-3 flex items-center justify-between">
              <div>
                <span className="text-sm font-medium">{j.county}, {j.state}</span>
                <span className="text-xs text-gray-500 ml-2">{j.rate_percentage}% ({j.rate_name})</span>
                {j.zip_codes?.length > 0 && <span className="text-xs text-gray-400 ml-2">{j.zip_codes.length} zips</span>}
              </div>
              <Button size="sm" variant="ghost" className="h-6 text-[10px] text-red-500" onClick={() => handleDelete(j.id)}><Trash2 className="h-3 w-3" /></Button>
            </CardContent></Card>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Exemptions Tab ──

function ExemptionsTab() {
  const [exemptions, setExemptions] = useState<Exemption[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiClient.get("/tax/exemptions").then((r) => setExemptions(r.data)).catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="flex justify-center py-12"><RefreshCw className="h-6 w-6 animate-spin text-gray-300" /></div>

  const expired = exemptions.filter((e) => e.is_expired)
  const expiring = exemptions.filter((e) => e.is_expiring)
  // missingCert count shown via summary card below

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <Card><CardContent className="p-3 text-center"><p className="text-2xl font-bold text-gray-900">{exemptions.length}</p><p className="text-xs text-gray-500">Exempt customers</p></CardContent></Card>
        <Card className={expiring.length > 0 ? "border-amber-200" : ""}><CardContent className="p-3 text-center"><p className="text-2xl font-bold text-amber-600">{expiring.length}</p><p className="text-xs text-gray-500">Expiring in 30 days</p></CardContent></Card>
        <Card className={expired.length > 0 ? "border-red-200" : ""}><CardContent className="p-3 text-center"><p className="text-2xl font-bold text-red-600">{expired.length}</p><p className="text-xs text-gray-500">Expired</p></CardContent></Card>
      </div>

      {exemptions.length === 0 ? (
        <Card><CardContent className="p-8 text-center"><p className="text-sm text-gray-400">No tax-exempt customers</p></CardContent></Card>
      ) : (
        <div className="space-y-1.5">
          {[...expired, ...expiring, ...exemptions.filter((e) => !e.is_expired && !e.is_expiring)].map((e) => (
            <Card key={e.customer_id} className={cn(e.is_expired ? "border-red-200" : e.is_expiring ? "border-amber-200" : "")}>
              <CardContent className="p-3 flex items-center justify-between">
                <div>
                  <span className="text-sm font-medium">{e.customer_name}</span>
                  <span className="text-xs text-gray-500 ml-2">
                    {e.exemption_certificate ? `Cert #${e.exemption_certificate}` : "No certificate"}
                    {e.exemption_expiry && ` · Expires ${e.exemption_expiry}`}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  {e.is_expired && <span className="text-[10px] bg-red-100 text-red-700 rounded px-1.5 py-0.5">Expired</span>}
                  {e.is_expiring && <span className="text-[10px] bg-amber-100 text-amber-700 rounded px-1.5 py-0.5">Expiring</span>}
                  {e.missing_cert && <span className="text-[10px] bg-gray-100 text-gray-600 rounded px-1.5 py-0.5">No cert</span>}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
