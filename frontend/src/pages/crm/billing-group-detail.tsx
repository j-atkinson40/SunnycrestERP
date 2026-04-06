/**
 * Billing Group Detail — /crm/billing-groups/:id
 *
 * View and manage a multi-location funeral home billing group.
 */

import { useCallback, useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { toast } from "sonner"
import { ArrowLeft, ExternalLink, Plus, Trash2, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import apiClient from "@/lib/api-client"
import { getApiErrorMessage } from "@/lib/api-error"

interface LocationDetail {
  company_entity_id: string
  name: string
  customer_id: string | null
  customer_name: string
  open_ar_balance: number
  last_order_date: string | null
  order_count_12mo: number
  revenue_12mo: number
}

interface BillingGroup {
  id: string
  name: string
  billing_preference: string
  location_count: number
  locations: LocationDetail[]
  totals: {
    open_ar_balance: number
    order_count_12mo: number
    revenue_12mo: number
  }
}

interface UngroupedLocation {
  company_entity_id: string
  name: string
  city: string | null
  state: string | null
  customer_id: string | null
}

const PREF_OPTIONS = [
  { value: "separate", label: "Separate billing" },
  { value: "consolidated_single_payer", label: "Consolidated \u2014 Single payer" },
  { value: "consolidated_split_payment", label: "Consolidated \u2014 Split payment" },
]

function fmt(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

export default function BillingGroupDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [group, setGroup] = useState<BillingGroup | null>(null)
  const [loading, setLoading] = useState(true)
  const [editingName, setEditingName] = useState(false)
  const [nameVal, setNameVal] = useState("")
  const [showAddLoc, setShowAddLoc] = useState(false)
  const [locSearch, setLocSearch] = useState("")
  const [locResults, setLocResults] = useState<UngroupedLocation[]>([])
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const r = await apiClient.get(`/billing-groups/${id}`)
      setGroup(r.data)
      setNameVal(r.data.name)
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to load billing group"))
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { load() }, [load])

  const saveName = async () => {
    if (!nameVal.trim() || nameVal === group?.name) { setEditingName(false); return }
    try {
      await apiClient.patch(`/billing-groups/${id}`, { name: nameVal })
      toast.success("Name updated")
      load()
    } catch (err) { toast.error(getApiErrorMessage(err, "Failed to update name")) }
    setEditingName(false)
  }

  const changePref = async (pref: string) => {
    try {
      await apiClient.patch(`/billing-groups/${id}`, { billing_preference: pref })
      toast.success("Billing preference updated")
      load()
    } catch (err) { toast.error(getApiErrorMessage(err, "Failed to update preference")) }
  }

  const searchLocations = useCallback(async (q: string) => {
    if (q.length < 2) { setLocResults([]); return }
    try {
      const r = await apiClient.get("/billing-groups/ungrouped-locations", { params: { search: q } })
      setLocResults(r.data)
    } catch { setLocResults([]) }
  }, [])

  useEffect(() => {
    const t = setTimeout(() => searchLocations(locSearch), 300)
    return () => clearTimeout(t)
  }, [locSearch, searchLocations])

  const addLocation = async (ceId: string) => {
    try {
      await apiClient.post(`/billing-groups/${id}/locations`, { company_entity_id: ceId })
      toast.success("Location added")
      setShowAddLoc(false)
      setLocSearch("")
      load()
    } catch (err) { toast.error(getApiErrorMessage(err, "Failed to add location")) }
  }

  const removeLocation = async (ceId: string) => {
    try {
      await apiClient.delete(`/billing-groups/${id}/locations/${ceId}`)
      toast.success("Location removed")
      setConfirmRemove(null)
      load()
    } catch (err) { toast.error(getApiErrorMessage(err, "Failed to remove location")) }
  }

  const deleteGroup = async () => {
    try {
      await apiClient.delete(`/billing-groups/${id}`)
      toast.success("Billing group deleted")
      navigate("/crm/billing-groups")
    } catch (err) { toast.error(getApiErrorMessage(err, "Failed to delete group")) }
  }

  if (loading) return <div className="p-6 text-muted-foreground">Loading...</div>
  if (!group) return <div className="p-6 text-destructive">Group not found</div>

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Link to="/crm/billing-groups" className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" /> Billing Groups
          </Link>
          <div className="flex items-center gap-3">
            {editingName ? (
              <div className="flex items-center gap-2">
                <input
                  className="rounded-md border px-3 py-1.5 text-xl font-bold"
                  value={nameVal}
                  onChange={e => setNameVal(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && saveName()}
                  autoFocus
                />
                <Button size="sm" onClick={saveName}>Save</Button>
                <Button size="sm" variant="outline" onClick={() => { setEditingName(false); setNameVal(group.name) }}>Cancel</Button>
              </div>
            ) : (
              <h1 className="text-2xl font-bold cursor-pointer hover:underline" onClick={() => setEditingName(true)}>
                {group.name}
              </h1>
            )}
            <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">Billing Group</span>
          </div>
        </div>
      </div>

      {/* Billing preference */}
      <Card className="p-4">
        <label className="mb-1 block text-sm font-medium">Billing preference</label>
        <select
          className="rounded-md border px-3 py-2 text-sm"
          value={group.billing_preference}
          onChange={e => changePref(e.target.value)}
        >
          {PREF_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </Card>

      {/* Combined stats */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold">{fmt(group.totals.open_ar_balance)}</div>
          <div className="text-xs text-muted-foreground">Open AR (combined)</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold">{group.totals.order_count_12mo}</div>
          <div className="text-xs text-muted-foreground">Orders (12mo)</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold">{fmt(group.totals.revenue_12mo)}</div>
          <div className="text-xs text-muted-foreground">Revenue (12mo)</div>
        </Card>
      </div>

      {/* Locations */}
      <Card className="p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-semibold">Locations ({group.location_count})</h2>
          <Button size="sm" variant="outline" onClick={() => setShowAddLoc(!showAddLoc)}>
            <Plus className="mr-1 h-4 w-4" /> Add location
          </Button>
        </div>

        {showAddLoc && (
          <div className="mb-4 rounded-md border p-3">
            <input
              className="w-full rounded-md border px-3 py-2 text-sm"
              placeholder="Search funeral homes..."
              value={locSearch}
              onChange={e => setLocSearch(e.target.value)}
              autoFocus
            />
            {locResults.length > 0 && (
              <div className="mt-2 max-h-32 overflow-y-auto">
                {locResults.map(r => (
                  <button
                    key={r.company_entity_id}
                    className="w-full px-3 py-1.5 text-left text-sm hover:bg-muted rounded"
                    onClick={() => addLocation(r.company_entity_id)}
                  >
                    {r.name}
                    {r.city && <span className="ml-2 text-xs text-muted-foreground">{r.city}, {r.state}</span>}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="divide-y">
          {group.locations.map(loc => (
            <div key={loc.company_entity_id} className="flex items-center justify-between py-3">
              <div>
                <div className="text-sm font-medium">{loc.name}</div>
                <div className="flex gap-4 text-xs text-muted-foreground">
                  <span>AR: {fmt(loc.open_ar_balance)}</span>
                  <span>Orders: {loc.order_count_12mo}</span>
                  <span>Revenue: {fmt(loc.revenue_12mo)}</span>
                  {loc.last_order_date && <span>Last order: {new Date(loc.last_order_date).toLocaleDateString()}</span>}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {loc.company_entity_id && (
                  <Link to={`/crm/companies/${loc.company_entity_id}`} className="text-muted-foreground hover:text-foreground">
                    <ExternalLink className="h-4 w-4" />
                  </Link>
                )}
                {confirmRemove === loc.company_entity_id ? (
                  <div className="flex items-center gap-1">
                    <Button size="sm" variant="destructive" onClick={() => removeLocation(loc.company_entity_id)}>Remove</Button>
                    <Button size="sm" variant="outline" onClick={() => setConfirmRemove(null)}>Cancel</Button>
                  </div>
                ) : (
                  <button
                    className="text-muted-foreground hover:text-destructive"
                    onClick={() => setConfirmRemove(loc.company_entity_id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Delete group */}
      <div className="pt-4 border-t">
        {confirmDelete ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4">
            <p className="text-sm">Delete <strong>{group.name}</strong>? All locations will revert to individual billing. No order or invoice history is deleted.</p>
            <div className="mt-3 flex gap-2">
              <Button variant="destructive" onClick={deleteGroup}>Delete group</Button>
              <Button variant="outline" onClick={() => setConfirmDelete(false)}>Cancel</Button>
            </div>
          </div>
        ) : (
          <button className="text-sm text-muted-foreground hover:text-destructive" onClick={() => setConfirmDelete(true)}>
            Delete this billing group
          </button>
        )}
      </div>
    </div>
  )
}
