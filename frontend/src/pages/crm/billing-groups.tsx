/**
 * Billing Groups — /vault/crm/billing-groups
 *
 * Manage multi-location funeral home accounts with configurable billing preferences.
 */

import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { toast } from "sonner"
import { Building, ChevronRight, Plus, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import apiClient from "@/lib/api-client"
import { getApiErrorMessage } from "@/lib/api-error"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

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
  is_billing_group: boolean
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

const PREF_LABELS: Record<string, string> = {
  separate: "Separate billing",
  consolidated_single_payer: "Consolidated \u2014 Single payer",
  consolidated_split_payment: "Consolidated \u2014 Split payment",
}

function fmt(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

// ---------------------------------------------------------------------------
// Create Group Wizard
// ---------------------------------------------------------------------------

function CreateGroupWizard({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [step, setStep] = useState(1)
  const [name, setName] = useState("")
  const [pref, setPref] = useState("consolidated_single_payer")
  const [locations, setLocations] = useState<UngroupedLocation[]>([])
  const [search, setSearch] = useState("")
  const [results, setResults] = useState<UngroupedLocation[]>([])
  const [searching, setSearching] = useState(false)
  const [billingContactId, setBillingContactId] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const doSearch = useCallback(async (q: string) => {
    if (q.length < 2) { setResults([]); return }
    setSearching(true)
    try {
      const r = await apiClient.get("/billing-groups/ungrouped-locations", { params: { search: q } })
      const filtered = r.data.filter((l: UngroupedLocation) => !locations.some(s => s.company_entity_id === l.company_entity_id))
      setResults(filtered)
    } catch { setResults([]) }
    finally { setSearching(false) }
  }, [locations])

  useEffect(() => {
    const t = setTimeout(() => doSearch(search), 300)
    return () => clearTimeout(t)
  }, [search, doSearch])

  const addLocation = (loc: UngroupedLocation) => {
    setLocations(prev => [...prev, loc])
    setSearch("")
    setResults([])
  }

  const removeLocation = (ceId: string) => {
    setLocations(prev => prev.filter(l => l.company_entity_id !== ceId))
    if (billingContactId) {
      const removed = locations.find(l => l.company_entity_id === ceId)
      if (removed?.customer_id === billingContactId) setBillingContactId(null)
    }
  }

  const handleCreate = async () => {
    setCreating(true)
    try {
      await apiClient.post("/billing-groups", {
        name,
        billing_preference: pref,
        location_company_entity_ids: locations.map(l => l.company_entity_id),
        billing_contact_customer_id: billingContactId,
      })
      toast.success("Billing group created")
      onCreated()
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to create group"))
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <Card className="w-full max-w-lg p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">
            {step === 1 && "Group details"}
            {step === 2 && "Add locations"}
            {step === 3 && pref !== "separate" ? "Billing contact" : "Confirm"}
            {step === 4 && "Confirm"}
          </h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground"><X className="h-5 w-5" /></button>
        </div>

        {/* Step 1 — Name & preference */}
        {step === 1 && (
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium">Group name</label>
              <input
                className="w-full rounded-md border px-3 py-2 text-sm"
                placeholder="e.g. Johnson Funeral Group"
                value={name}
                onChange={e => setName(e.target.value)}
              />
              <p className="mt-1 text-xs text-muted-foreground">Usually the family or corporate name, not a specific location</p>
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium">Billing preference</label>
              <div className="space-y-2">
                {([
                  ["separate", "Separate billing", "Each location receives their own invoice and pays separately. Groups them for reporting only."],
                  ["consolidated_single_payer", "Consolidated \u2014 single payer", "One invoice for all locations. One payment covers everything. Best for corporate-owned groups."],
                  ["consolidated_split_payment", "Consolidated \u2014 split payment", "One invoice showing all locations but each location pays their own portion."],
                ] as const).map(([val, label, desc]) => (
                  <label key={val} className={`flex cursor-pointer gap-3 rounded-md border p-3 ${pref === val ? "border-primary bg-primary/5" : ""}`}>
                    <input type="radio" name="pref" value={val} checked={pref === val} onChange={() => setPref(val)} className="mt-0.5" />
                    <div>
                      <div className="text-sm font-medium">{label}</div>
                      <div className="text-xs text-muted-foreground">{desc}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>
            <div className="flex justify-end">
              <Button onClick={() => setStep(2)} disabled={!name.trim()}>Next</Button>
            </div>
          </div>
        )}

        {/* Step 2 — Add locations */}
        {step === 2 && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">Which funeral homes are part of this group?</p>
            <input
              className="w-full rounded-md border px-3 py-2 text-sm"
              placeholder="Search funeral homes..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
            {results.length > 0 && (
              <div className="max-h-40 overflow-y-auto rounded-md border">
                {results.map(r => (
                  <button
                    key={r.company_entity_id}
                    className="w-full px-3 py-2 text-left text-sm hover:bg-muted"
                    onClick={() => addLocation(r)}
                  >
                    {r.name}
                    {r.city && <span className="ml-2 text-xs text-muted-foreground">{r.city}, {r.state}</span>}
                  </button>
                ))}
              </div>
            )}
            {searching && <p className="text-xs text-muted-foreground">Searching...</p>}

            {locations.length > 0 && (
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">Selected ({locations.length})</label>
                {locations.map(l => (
                  <div key={l.company_entity_id} className="flex items-center justify-between rounded-md border px-3 py-1.5 text-sm">
                    <span>{l.name}</span>
                    <button onClick={() => removeLocation(l.company_entity_id)} className="text-muted-foreground hover:text-destructive"><X className="h-4 w-4" /></button>
                  </div>
                ))}
              </div>
            )}

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(1)}>Back</Button>
              <Button
                onClick={() => setStep(pref !== "separate" ? 3 : 4)}
                disabled={locations.length < 2}
              >
                Next
              </Button>
            </div>
          </div>
        )}

        {/* Step 3 — Billing contact (only for consolidated) */}
        {step === 3 && pref !== "separate" && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">Who receives the consolidated invoice?</p>
            <div className="space-y-2">
              {locations.filter(l => l.customer_id).map(l => (
                <label key={l.company_entity_id} className={`flex cursor-pointer items-center gap-3 rounded-md border p-3 ${billingContactId === l.customer_id ? "border-primary bg-primary/5" : ""}`}>
                  <input
                    type="radio"
                    name="billing_contact"
                    checked={billingContactId === l.customer_id}
                    onChange={() => setBillingContactId(l.customer_id)}
                  />
                  <span className="text-sm">{l.name}</span>
                </label>
              ))}
            </div>
            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(2)}>Back</Button>
              <Button onClick={() => setStep(4)}>Next</Button>
            </div>
          </div>
        )}

        {/* Step 4 — Confirm */}
        {step === 4 && (
          <div className="space-y-4">
            <div className="rounded-md border p-4 text-sm space-y-2">
              <div><span className="font-medium">Group:</span> {name}</div>
              <div><span className="font-medium">Billing:</span> {PREF_LABELS[pref]}</div>
              <div>
                <span className="font-medium">Locations:</span>
                <ul className="mt-1 ml-4 list-disc">
                  {locations.map(l => <li key={l.company_entity_id}>{l.name}</li>)}
                </ul>
              </div>
              {billingContactId && (
                <div><span className="font-medium">Billing contact:</span> {locations.find(l => l.customer_id === billingContactId)?.name}</div>
              )}
            </div>
            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(pref !== "separate" ? 3 : 2)}>Back</Button>
              <Button onClick={handleCreate} disabled={creating}>
                {creating ? "Creating..." : "Create group"}
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function BillingGroupsPage() {
  const [groups, setGroups] = useState<BillingGroup[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)

  const load = useCallback(async () => {
    try {
      const r = await apiClient.get("/billing-groups")
      setGroups(r.data)
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to load billing groups"))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  if (loading) return <div className="p-6 text-muted-foreground">Loading...</div>

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Billing Groups</h1>
          <p className="text-sm text-muted-foreground">Manage multi-location funeral home accounts</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New group
        </Button>
      </div>

      {groups.length === 0 ? (
        <Card className="p-8 text-center">
          <Building className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
          <h3 className="text-lg font-medium">No billing groups yet</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Group multi-location funeral homes to consolidate their billing.
          </p>
          <Button className="mt-4" onClick={() => setShowCreate(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Create first group
          </Button>
        </Card>
      ) : (
        <div className="grid gap-4">
          {groups.map(g => (
            <Link key={g.id} to={`/vault/crm/billing-groups/${g.id}`}>
              <Card className="p-5 hover:bg-muted/30 transition-colors">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-base font-semibold">{g.name}</h3>
                    <p className="text-sm text-muted-foreground">{PREF_LABELS[g.billing_preference] || g.billing_preference}</p>
                  </div>
                  <ChevronRight className="mt-1 h-5 w-5 text-muted-foreground" />
                </div>
                <div className="mt-3 text-sm">
                  <span className="font-medium">Locations:</span>{" "}
                  {g.locations.map(l => l.name).join(", ")}
                </div>
                <div className="mt-2 flex gap-6 text-sm text-muted-foreground">
                  <span>Open AR: {fmt(g.totals.open_ar_balance)}</span>
                  <span>Orders (12mo): {g.totals.order_count_12mo}</span>
                  <span>Revenue (12mo): {fmt(g.totals.revenue_12mo)}</span>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}

      {showCreate && (
        <CreateGroupWizard
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); load() }}
        />
      )}
    </div>
  )
}
