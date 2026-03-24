/**
 * Tax Jurisdictions Onboarding — /onboarding/tax-jurisdictions
 * Geographic county suggestions with pre-filled tax rates.
 */

import { useState, useEffect, useCallback, useMemo } from "react"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { ChevronLeft, ChevronRight, MapPin, Info, Plus, Search, Users } from "lucide-react"
import apiClient from "@/lib/api-client"

interface CountySuggestion {
  county: string
  state: string
  combined_rate: number | null
  state_rate: number | null
  county_rate: number | null
  is_state_rate_only: boolean
  source: "service_territory" | "radius_lookup" | "customer_addresses"
  distance_miles: number | null
  already_configured: boolean
  rate_found: boolean
}

interface SuggestionResponse {
  suggestions: CountySuggestion[]
  tenant_state: string | null
  tenant_zip: string | null
  has_service_territory: boolean
  existing_count: number
}

const SOURCE_LABELS: Record<string, string> = {
  service_territory: "From your service territory",
  radius_lookup: "Nearby county",
  customer_addresses: "From your imported customers",
}

const SOURCE_ICONS: Record<string, typeof MapPin> = {
  service_territory: MapPin,
  radius_lookup: Search,
  customer_addresses: Users,
}

export default function TaxJurisdictionsOnboarding() {
  const navigate = useNavigate()
  const [data, setData] = useState<SuggestionResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [radiusMiles, setRadiusMiles] = useState(100)

  // Per-county selection and rate state
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [rates, setRates] = useState<Record<string, string>>({})

  // Manual add form
  const [showManualAdd, setShowManualAdd] = useState(false)
  const [manualCounty, setManualCounty] = useState("")
  const [manualState, setManualState] = useState("")
  const [manualRate, setManualRate] = useState("")

  // Bulk rate tool
  const [useBulkRate, setUseBulkRate] = useState(false)
  const [bulkRate, setBulkRate] = useState("")

  const fetchSuggestions = useCallback(async (radius: number) => {
    setLoading(true)
    try {
      const res = await apiClient.get(`/tax/jurisdictions/county-suggestions?radius_miles=${radius}`)
      setData(res.data)
      // Auto-select service territory counties and pre-fill rates
      const autoSelect = new Set<string>()
      const autoRates: Record<string, string> = {}
      for (const s of res.data.suggestions) {
        const key = `${s.state}|${s.county}`
        if (s.source === "service_territory" && !s.already_configured) {
          autoSelect.add(key)
        }
        if (s.combined_rate !== null) {
          autoRates[key] = String(s.combined_rate)
        }
      }
      setSelected((prev) => new Set([...prev, ...autoSelect]))
      setRates((prev) => ({ ...autoRates, ...prev }))
    } catch {
      toast.error("Failed to load county suggestions")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSuggestions(radiusMiles)
  }, [fetchSuggestions, radiusMiles])

  const toggleCounty = (key: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const selectAll = () => {
    if (!data) return
    const all = new Set<string>()
    for (const s of data.suggestions) {
      if (!s.already_configured) all.add(`${s.state}|${s.county}`)
    }
    setSelected(all)
  }

  const deselectAll = () => setSelected(new Set())

  const setRate = (key: string, value: string) => {
    setRates((prev) => ({ ...prev, [key]: value }))
  }

  const applyBulkRate = () => {
    if (!bulkRate) return
    const updated = { ...rates }
    for (const key of selected) {
      updated[key] = bulkRate
    }
    setRates(updated)
  }

  // Group suggestions by source
  const grouped = useMemo(() => {
    if (!data) return { service_territory: [], radius_lookup: [], customer_addresses: [] }
    const groups: Record<string, CountySuggestion[]> = {
      service_territory: [],
      radius_lookup: [],
      customer_addresses: [],
    }
    for (const s of data.suggestions) {
      groups[s.source]?.push(s)
    }
    return groups
  }, [data])

  // Customer coverage calculation
  const coveragePercent = useMemo(() => {
    if (!data) return null
    const customerCounties = data.suggestions.filter((s) => s.source === "customer_addresses")
    if (customerCounties.length === 0) return null
    const covered = customerCounties.filter((s) => selected.has(`${s.state}|${s.county}`))
    return Math.round((covered.length / customerCounties.length) * 100)
  }, [data, selected])

  // Validation
  const allSelectedHaveRates = useMemo(() => {
    for (const key of selected) {
      const r = rates[key]
      if (!r || isNaN(parseFloat(r))) return false
    }
    return true
  }, [selected, rates])

  const canContinue = selected.size > 0 && allSelectedHaveRates

  const handleAddManual = () => {
    if (!manualCounty.trim() || !manualState.trim()) {
      toast.error("County and state are required")
      return
    }
    const key = `${manualState.toUpperCase()}|${manualCounty.trim()}`
    setSelected((prev) => new Set([...prev, key]))
    if (manualRate) setRates((prev) => ({ ...prev, [key]: manualRate }))
    // Add to data suggestions for rendering
    if (data) {
      setData({
        ...data,
        suggestions: [
          ...data.suggestions,
          {
            county: manualCounty.trim(),
            state: manualState.toUpperCase(),
            combined_rate: manualRate ? parseFloat(manualRate) : null,
            state_rate: null,
            county_rate: null,
            is_state_rate_only: false,
            source: "customer_addresses",
            distance_miles: null,
            already_configured: false,
            rate_found: !!manualRate,
          },
        ],
      })
    }
    setManualCounty("")
    setManualState(data?.tenant_state || "")
    setManualRate("")
    setShowManualAdd(false)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const jurisdictions = Array.from(selected).map((key) => {
        const [state, county] = key.split("|")
        return {
          state,
          county,
          rate_percentage: parseFloat(rates[key] || "0"),
        }
      })
      await apiClient.post("/tax/jurisdictions/bulk-onboarding", { jurisdictions })
      toast.success(`${jurisdictions.length} counties configured`)
      navigate("/onboarding")
    } catch {
      toast.error("Failed to save jurisdictions")
    } finally {
      setSaving(false)
    }
  }

  const handleSkip = () => {
    navigate("/onboarding")
  }

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-64" />
          <div className="h-4 bg-gray-200 rounded w-96" />
          <div className="h-48 bg-gray-200 rounded" />
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 pb-32">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Map your delivery counties</h1>
        <p className="text-sm text-gray-600 mt-1">
          {data?.has_service_territory
            ? "We loaded your service territory counties and pre-filled their tax rates. Select the counties you deliver to."
            : "We found counties near your location and pre-filled their tax rates. Select the ones you deliver to."}
        </p>
      </div>

      {/* Data freshness notice */}
      <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg p-3 mb-6 text-sm text-amber-800">
        <Info className="h-4 w-4 mt-0.5 shrink-0" />
        <span>
          Tax rates shown are from our database and may not reflect recent changes.
          Edit any rate that doesn't match your current records. Verify with your accountant.
        </span>
      </div>

      {/* Bulk rate tool */}
      <div className="flex items-center gap-3 mb-4">
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={useBulkRate}
            onChange={(e) => setUseBulkRate(e.target.checked)}
            className="h-4 w-4 rounded border-gray-300"
          />
          All my counties have the same rate
        </label>
        {useBulkRate && (
          <div className="flex items-center gap-2">
            <input
              type="number"
              step="0.01"
              value={bulkRate}
              onChange={(e) => setBulkRate(e.target.value)}
              placeholder="8.00"
              className="w-24 rounded-md border border-gray-300 px-2 py-1 text-sm"
            />
            <span className="text-sm text-gray-500">%</span>
            <Button size="sm" variant="outline" onClick={applyBulkRate} disabled={!bulkRate}>
              Apply to all
            </Button>
          </div>
        )}
      </div>

      {/* Select all / deselect */}
      <div className="flex items-center gap-3 mb-4 text-sm">
        <button onClick={selectAll} className="text-blue-600 hover:text-blue-700 underline">
          Select all
        </button>
        <button onClick={deselectAll} className="text-gray-500 hover:text-gray-700 underline">
          Deselect all
        </button>
        <span className="text-gray-400">
          {selected.size} selected
        </span>
      </div>

      {/* Suggestion groups */}
      {(["service_territory", "radius_lookup", "customer_addresses"] as const).map((source) => {
        const counties = grouped[source]
        if (!counties || counties.length === 0) return null
        const Icon = SOURCE_ICONS[source] || MapPin

        return (
          <div key={source} className="mb-6">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Icon className="h-3.5 w-3.5" />
              {source === "service_territory" && "Your service territory"}
              {source === "radius_lookup" && `Counties within ${radiusMiles} miles`}
              {source === "customer_addresses" && "From your imported customers"}
            </h3>
            <div className="space-y-2">
              {counties.map((s) => {
                const key = `${s.state}|${s.county}`
                const isSelected = selected.has(key)
                const rateValue = rates[key] || ""

                return (
                  <Card
                    key={key}
                    className={`transition-colors ${
                      s.already_configured
                        ? "bg-gray-50 opacity-60"
                        : isSelected
                          ? "border-blue-300 bg-blue-50/30"
                          : ""
                    }`}
                  >
                    <CardContent className="p-3">
                      <div className="flex items-start gap-3">
                        <input
                          type="checkbox"
                          checked={isSelected || s.already_configured}
                          disabled={s.already_configured}
                          onChange={() => toggleCounty(key)}
                          className="h-4 w-4 rounded border-gray-300 mt-1"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-gray-900">
                              {s.county} County, {s.state}
                            </span>
                            {s.already_configured && (
                              <span className="text-xs bg-gray-200 text-gray-600 px-1.5 py-0.5 rounded">
                                Already added
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-gray-500 mt-0.5">
                            {s.distance_miles !== null && `${s.distance_miles} miles · `}
                            {SOURCE_LABELS[s.source]}
                          </p>
                        </div>
                        {!s.already_configured && (
                          <div className="text-right shrink-0">
                            <label className="text-xs text-gray-500 block mb-0.5">Combined rate</label>
                            <div className="flex items-center gap-1">
                              <input
                                type="number"
                                step="0.01"
                                value={rateValue}
                                onChange={(e) => setRate(key, e.target.value)}
                                placeholder={s.combined_rate !== null ? String(s.combined_rate) : ""}
                                className="w-20 rounded-md border border-gray-300 px-2 py-1 text-sm text-right"
                              />
                              <span className="text-xs text-gray-500">%</span>
                            </div>
                            {s.state_rate !== null && s.county_rate !== null && !s.is_state_rate_only && (
                              <p className="text-xs text-gray-400 mt-0.5">
                                State: {s.state_rate}% + County: {s.county_rate}%
                              </p>
                            )}
                            {s.is_state_rate_only && s.rate_found && (
                              <p className="text-xs text-amber-600 mt-0.5">
                                State rate only — enter county rate if different
                              </p>
                            )}
                            {!s.rate_found && (
                              <p className="text-xs text-amber-600 mt-0.5">
                                Rate not found — enter manually
                              </p>
                            )}
                            {rateValue && !isNaN(parseFloat(rateValue)) && (
                              <p className="text-xs text-gray-400 mt-0.5">
                                {parseFloat(rateValue)}% of $100 = ${(parseFloat(rateValue)).toFixed(2)}
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          </div>
        )
      })}

      {/* Expand radius / manual add */}
      <div className="flex flex-wrap items-center gap-3 mb-6 text-sm">
        {radiusMiles < 300 && (
          <button
            onClick={() => setRadiusMiles(Math.min(radiusMiles + 50, 300))}
            className="text-blue-600 hover:text-blue-700 underline"
          >
            Expand search to {radiusMiles + 50} miles
          </button>
        )}
        <button
          onClick={() => setShowManualAdd(true)}
          className="flex items-center gap-1 text-blue-600 hover:text-blue-700 underline"
        >
          <Plus className="h-3.5 w-3.5" /> Add a county not listed
        </button>
      </div>

      {/* Manual add form */}
      {showManualAdd && (
        <Card className="mb-6">
          <CardContent className="p-4 space-y-3">
            <h4 className="text-sm font-medium">Add a county manually</h4>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-xs text-gray-500">State</label>
                <input
                  type="text"
                  maxLength={2}
                  value={manualState}
                  onChange={(e) => setManualState(e.target.value.toUpperCase())}
                  placeholder="NY"
                  className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500">County</label>
                <input
                  type="text"
                  value={manualCounty}
                  onChange={(e) => setManualCounty(e.target.value)}
                  placeholder="Cayuga"
                  className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500">Rate %</label>
                <input
                  type="number"
                  step="0.01"
                  value={manualRate}
                  onChange={(e) => setManualRate(e.target.value)}
                  placeholder="8.00"
                  className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={handleAddManual}>Add County</Button>
              <Button size="sm" variant="ghost" onClick={() => setShowManualAdd(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Skip option */}
      <div className="text-center text-sm text-gray-500 mb-8">
        <button onClick={handleSkip} className="underline hover:text-gray-700">
          I'll configure counties later
        </button>
        <p className="text-xs text-gray-400 mt-1">
          Without county configuration, the default tax rate will apply to all invoices.
        </p>
      </div>

      {/* Sticky footer */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t shadow-lg z-10">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="text-sm">
            <span className="font-medium">{selected.size} counties selected</span>
            {coveragePercent !== null && (
              <span className="text-gray-500 ml-2">
                · Covers ~{coveragePercent}% of your customers
              </span>
            )}
            {!allSelectedHaveRates && selected.size > 0 && (
              <span className="text-red-500 ml-2">· Some counties missing rates</span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <Button variant="ghost" onClick={() => navigate("/onboarding")}>
              <ChevronLeft className="h-4 w-4 mr-1" /> Back
            </Button>
            <Button onClick={handleSave} disabled={!canContinue || saving}>
              {saving ? "Saving..." : "Save & Continue"}
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
