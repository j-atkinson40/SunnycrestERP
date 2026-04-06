/**
 * Charge Account Terms Onboarding — /onboarding/charge-terms
 *
 * Two-tier layout:
 *   Tier 1 — Default terms applied to all funeral homes
 *   Tier 2 — Individual exceptions (collapsed by default)
 *
 * TODO: Also mount this component in Settings > Billing once that page exists.
 */

import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { Check, ChevronDown, ChevronUp, Edit2, Plus, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import apiClient from "@/lib/api-client"
import { getApiErrorMessage } from "@/lib/api-error"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DefaultTerms {
  net_days: number
  finance_charge_rate: number
  finance_charge_after_days: number
  no_finance_charge: boolean
  credit_limit: number | null
  applied: boolean
}

interface TermsException {
  id: string
  customer_id: string
  customer_name: string
  net_days: number
  finance_charge_rate: number
  finance_charge_after_days: number
  no_finance_charge: boolean
  credit_limit: number | null
}

interface ChargeTermsData {
  default: DefaultTerms
  exceptions: TermsException[]
  funeral_home_count: number
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const NET_OPTIONS = [
  { value: 0, label: "Due on receipt" },
  { value: 15, label: "Net 15" },
  { value: 30, label: "Net 30" },
  { value: 45, label: "Net 45" },
  { value: 60, label: "Net 60" },
  { value: -1, label: "Custom..." },
]

// ---------------------------------------------------------------------------
// Subcomponents
// ---------------------------------------------------------------------------

function TermsForm({
  netDays,
  setNetDays,
  fcRate,
  setFcRate,
  fcAfterDays,
  setFcAfterDays,
  noFc,
  setNoFc,
  creditLimit,
  setCreditLimit,
  noLimit,
  setNoLimit,
}: {
  netDays: number
  setNetDays: (v: number) => void
  fcRate: string
  setFcRate: (v: string) => void
  fcAfterDays: string
  setFcAfterDays: (v: string) => void
  noFc: boolean
  setNoFc: (v: boolean) => void
  creditLimit: string
  setCreditLimit: (v: string) => void
  noLimit: boolean
  setNoLimit: (v: boolean) => void
}) {
  const isCustom = !NET_OPTIONS.some((o) => o.value === netDays && o.value !== -1)
  const [showCustom, setShowCustom] = useState(isCustom)

  return (
    <div className="space-y-4">
      {/* Net days */}
      <div className="space-y-1.5">
        <label className="text-sm font-medium">Net days</label>
        <select
          className="w-full rounded-md border bg-background px-3 py-2 text-sm"
          value={showCustom ? -1 : netDays}
          onChange={(e) => {
            const v = parseInt(e.target.value)
            if (v === -1) {
              setShowCustom(true)
            } else {
              setShowCustom(false)
              setNetDays(v)
            }
          }}
        >
          {NET_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        {showCustom && (
          <input
            type="number"
            min={1}
            className="w-full rounded-md border bg-background px-3 py-2 text-sm mt-1"
            placeholder="Enter number of days..."
            value={netDays}
            onChange={(e) => setNetDays(parseInt(e.target.value) || 30)}
          />
        )}
      </div>

      {/* Finance charge */}
      <div className="space-y-1.5">
        <label className="text-sm font-medium">Finance charge</label>
        <label className="flex items-center gap-2 cursor-pointer text-sm">
          <input
            type="checkbox"
            checked={noFc}
            onChange={(e) => setNoFc(e.target.checked)}
            className="size-4 rounded"
          />
          No finance charge
        </label>
        {!noFc && (
          <div className="flex items-center gap-2 text-sm">
            <input
              type="number"
              step="0.1"
              min={0}
              className="w-20 rounded-md border bg-background px-2 py-1.5 text-sm"
              value={fcRate}
              onChange={(e) => setFcRate(e.target.value)}
            />
            <span className="text-muted-foreground">% per month after</span>
            <input
              type="number"
              min={0}
              className="w-16 rounded-md border bg-background px-2 py-1.5 text-sm"
              value={fcAfterDays}
              onChange={(e) => setFcAfterDays(e.target.value)}
            />
            <span className="text-muted-foreground">days past due</span>
          </div>
        )}
      </div>

      {/* Credit limit */}
      <div className="space-y-1.5">
        <label className="text-sm font-medium">Credit limit</label>
        <div className="space-y-1">
          <label className="flex items-center gap-2 cursor-pointer text-sm">
            <input
              type="radio"
              name="credit_limit_mode"
              checked={noLimit}
              onChange={() => {
                setNoLimit(true)
                setCreditLimit("")
              }}
              className="size-4"
            />
            No limit
          </label>
          <label className="flex items-center gap-2 cursor-pointer text-sm">
            <input
              type="radio"
              name="credit_limit_mode"
              checked={!noLimit}
              onChange={() => setNoLimit(false)}
              className="size-4"
            />
            Set limit:
            {!noLimit && (
              <div className="relative">
                <span className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">
                  $
                </span>
                <input
                  type="number"
                  min={0}
                  step={100}
                  className="w-32 rounded-md border bg-background pl-6 pr-2 py-1.5 text-sm"
                  value={creditLimit}
                  onChange={(e) => setCreditLimit(e.target.value)}
                />
              </div>
            )}
          </label>
        </div>
      </div>
    </div>
  )
}

function ExceptionRow({
  ex,
  onEdit,
  onRemove,
}: {
  ex: TermsException
  onEdit: () => void
  onRemove: () => void
}) {
  const parts: string[] = []
  parts.push(ex.net_days === 0 ? "Due on receipt" : `Net ${ex.net_days}`)
  if (ex.no_finance_charge) {
    parts.push("No finance charge")
  } else {
    parts.push(`${ex.finance_charge_rate}%/mo after ${ex.finance_charge_after_days} days`)
  }
  parts.push(ex.credit_limit !== null ? `$${ex.credit_limit.toLocaleString()} limit` : "No limit")

  return (
    <div className="flex items-center justify-between py-2.5 px-3 rounded-md border bg-white">
      <div>
        <div className="font-medium text-sm">{ex.customer_name}</div>
        <div className="text-xs text-muted-foreground">{parts.join(" · ")}</div>
      </div>
      <div className="flex gap-1.5">
        <Button variant="outline" size="sm" onClick={onEdit}>
          <Edit2 className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="text-red-600 hover:text-red-700"
          onClick={onRemove}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ChargeTermsOnboardingPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<ChargeTermsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  // Default form state
  const [netDays, setNetDays] = useState(30)
  const [fcRate, setFcRate] = useState("1.5")
  const [fcAfterDays, setFcAfterDays] = useState("30")
  const [noFc, setNoFc] = useState(false)
  const [creditLimit, setCreditLimit] = useState("")
  const [noLimit, setNoLimit] = useState(true)
  const [applied, setApplied] = useState(false)

  // Exceptions
  const [exceptionsOpen, setExceptionsOpen] = useState(false)
  const [showAddException, setShowAddException] = useState(false)
  const [editingExceptionId, setEditingExceptionId] = useState<string | null>(null)
  const [exSaving, setExSaving] = useState(false)

  // Exception form
  const [exCustomerId, setExCustomerId] = useState("")
  const [exCustomerSearch, setExCustomerSearch] = useState("")
  const [exSearchResults, setExSearchResults] = useState<Array<{ id: string; name: string }>>([])
  const [exNetDays, setExNetDays] = useState(30)
  const [exFcRate, setExFcRate] = useState("1.5")
  const [exFcAfterDays, setExFcAfterDays] = useState("30")
  const [exNoFc, setExNoFc] = useState(false)
  const [exCreditLimit, setExCreditLimit] = useState("")
  const [exNoLimit, setExNoLimit] = useState(true)

  // Remove confirmation
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    try {
      const res = await apiClient.get("/onboarding/charge-terms")
      const d: ChargeTermsData = res.data
      setData(d)

      // Populate defaults
      setNetDays(d.default.net_days)
      setFcRate(String(d.default.finance_charge_rate))
      setFcAfterDays(String(d.default.finance_charge_after_days))
      setNoFc(d.default.no_finance_charge)
      if (d.default.credit_limit !== null) {
        setCreditLimit(String(d.default.credit_limit))
        setNoLimit(false)
      } else {
        setCreditLimit("")
        setNoLimit(true)
      }
      setApplied(d.default.applied)
      if (d.exceptions.length > 0) setExceptionsOpen(true)
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to load charge terms"))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleApplyDefaults = async () => {
    setSaving(true)
    try {
      await apiClient.post("/onboarding/charge-terms/default", {
        net_days: netDays,
        finance_charge_rate: parseFloat(fcRate) || 1.5,
        finance_charge_after_days: parseInt(fcAfterDays) || 30,
        no_finance_charge: noFc,
        credit_limit: noLimit ? null : parseFloat(creditLimit) || null,
      })
      setApplied(true)
      toast.success(`Applied to ${data?.funeral_home_count ?? 0} funeral homes`)
      loadData()
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to save defaults"))
    } finally {
      setSaving(false)
    }
  }

  const prefillExceptionForm = () => {
    setExNetDays(netDays)
    setExFcRate(fcRate)
    setExFcAfterDays(fcAfterDays)
    setExNoFc(noFc)
    setExCreditLimit(creditLimit)
    setExNoLimit(noLimit)
    setExCustomerId("")
    setExCustomerSearch("")
    setExSearchResults([])
  }

  const searchFuneralHomes = async (q: string) => {
    setExCustomerSearch(q)
    if (q.length < 2) {
      setExSearchResults([])
      return
    }
    try {
      const r = await apiClient.get(
        `/customers?search=${encodeURIComponent(q)}&per_page=8&include_hidden=false`
      )
      const items = (r.data?.items || []).filter(
        (c: { customer_type: string | null }) =>
          c.customer_type === "funeral_home" || c.customer_type === null
      )
      setExSearchResults(
        items.map((c: { id: string; display_name?: string; name: string }) => ({
          id: c.id,
          name: c.display_name ?? c.name,
        }))
      )
    } catch {
      setExSearchResults([])
    }
  }

  const handleSaveException = async () => {
    if (!exCustomerId && !editingExceptionId) {
      toast.error("Select a funeral home")
      return
    }
    setExSaving(true)
    try {
      const body = {
        customer_id: exCustomerId || editingExceptionId,
        net_days: exNetDays,
        finance_charge_rate: parseFloat(exFcRate) || 1.5,
        finance_charge_after_days: parseInt(exFcAfterDays) || 30,
        no_finance_charge: exNoFc,
        credit_limit: exNoLimit ? null : parseFloat(exCreditLimit) || null,
      }

      if (editingExceptionId) {
        await apiClient.patch(
          `/onboarding/charge-terms/exceptions/${editingExceptionId}`,
          body
        )
      } else {
        await apiClient.post("/onboarding/charge-terms/exceptions", body)
      }

      setShowAddException(false)
      setEditingExceptionId(null)
      toast.success(editingExceptionId ? "Exception updated" : "Exception added")
      loadData()
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to save exception"))
    } finally {
      setExSaving(false)
    }
  }

  const handleRemoveException = async (customerId: string) => {
    try {
      await apiClient.delete(`/onboarding/charge-terms/exceptions/${customerId}`)
      setConfirmRemove(null)
      toast.success("Exception removed")
      loadData()
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to remove exception"))
    }
  }

  const handleSkip = async () => {
    try {
      // Just mark step complete without changing anything
      await apiClient.post("/onboarding/charge-terms/default", {
        net_days: 30,
        finance_charge_rate: 1.5,
        finance_charge_after_days: 30,
        no_finance_charge: false,
        credit_limit: null,
      })
    } catch {
      // Even if save fails, navigate away
    }
    navigate("/onboarding")
  }

  const startEditException = (ex: TermsException) => {
    setEditingExceptionId(ex.customer_id)
    setExCustomerId(ex.customer_id)
    setExCustomerSearch(ex.customer_name)
    setExNetDays(ex.net_days)
    setExFcRate(String(ex.finance_charge_rate))
    setExFcAfterDays(String(ex.finance_charge_after_days))
    setExNoFc(ex.no_finance_charge)
    if (ex.credit_limit !== null) {
      setExCreditLimit(String(ex.credit_limit))
      setExNoLimit(false)
    } else {
      setExCreditLimit("")
      setExNoLimit(true)
    }
    setShowAddException(true)
    setExceptionsOpen(true)
  }

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto p-6 flex justify-center py-16">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-gray-900" />
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Set up charge account terms</h1>
        <p className="text-muted-foreground mt-1">
          Configure billing terms for your funeral home customers.
          {(data?.funeral_home_count ?? 0) > 0 && (
            <span className="font-medium text-foreground">
              {" "}
              {data?.funeral_home_count} funeral home
              {data?.funeral_home_count !== 1 ? "s" : ""} found.
            </span>
          )}
        </p>
      </div>

      {/* ── TIER 1: Default Terms ─────────────────────────────── */}
      <Card className="p-5 space-y-4">
        <h2 className="text-base font-semibold">
          Default terms for all funeral homes
        </h2>

        <TermsForm
          netDays={netDays}
          setNetDays={setNetDays}
          fcRate={fcRate}
          setFcRate={setFcRate}
          fcAfterDays={fcAfterDays}
          setFcAfterDays={setFcAfterDays}
          noFc={noFc}
          setNoFc={setNoFc}
          creditLimit={creditLimit}
          setCreditLimit={setCreditLimit}
          noLimit={noLimit}
          setNoLimit={setNoLimit}
        />

        {applied ? (
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 text-sm text-green-700">
              <Check className="h-4 w-4" />
              Applied to {data?.funeral_home_count ?? 0} funeral homes
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setApplied(false)}
            >
              Edit defaults
            </Button>
          </div>
        ) : (
          <Button onClick={handleApplyDefaults} disabled={saving}>
            {saving
              ? "Applying..."
              : `Apply to all ${data?.funeral_home_count ?? 0} funeral homes`}
          </Button>
        )}
      </Card>

      {/* ── TIER 2: Exceptions ────────────────────────────────── */}
      <Card className="p-5 space-y-3">
        <button
          type="button"
          className="flex items-center justify-between w-full text-left"
          onClick={() => setExceptionsOpen(!exceptionsOpen)}
        >
          <div>
            <h2 className="text-base font-semibold">Exceptions</h2>
            <p className="text-sm text-muted-foreground">
              Override terms for specific funeral homes
            </p>
          </div>
          {exceptionsOpen ? (
            <ChevronUp className="h-5 w-5 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-5 w-5 text-muted-foreground" />
          )}
        </button>

        {exceptionsOpen && (
          <div className="space-y-3 pt-2 border-t">
            {/* Existing exceptions */}
            {(data?.exceptions ?? []).length === 0 && !showAddException && (
              <p className="text-sm text-muted-foreground py-2">
                No exceptions — all funeral homes use the default terms.
              </p>
            )}

            {(data?.exceptions ?? []).map((ex) =>
              confirmRemove === ex.customer_id ? (
                <div
                  key={ex.customer_id}
                  className="rounded-md border border-red-200 bg-red-50 p-3 space-y-2"
                >
                  <p className="text-sm text-red-800">
                    Remove exception for {ex.customer_name}? They will use the
                    default{" "}
                    {netDays === 0 ? "Due on receipt" : `Net ${netDays}`} terms.
                  </p>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => handleRemoveException(ex.customer_id)}
                    >
                      Confirm
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setConfirmRemove(null)}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <ExceptionRow
                  key={ex.customer_id}
                  ex={ex}

                  onEdit={() => startEditException(ex)}
                  onRemove={() => setConfirmRemove(ex.customer_id)}
                />
              )
            )}

            {/* Add/edit exception form */}
            {showAddException ? (
              <div className="border rounded-lg p-4 space-y-3 bg-gray-50">
                <h3 className="text-sm font-semibold">
                  {editingExceptionId ? "Edit exception" : "Add exception"}
                </h3>

                {!editingExceptionId && (
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">Funeral home</label>
                    <input
                      type="text"
                      className="w-full rounded-md border bg-white px-3 py-2 text-sm"
                      placeholder="Search funeral homes..."
                      value={exCustomerSearch}
                      onChange={(e) => searchFuneralHomes(e.target.value)}
                    />
                    {exSearchResults.length > 0 && (
                      <div className="border rounded-md bg-white shadow-sm max-h-36 overflow-y-auto">
                        {exSearchResults.map((v) => (
                          <button
                            key={v.id}
                            type="button"
                            className="w-full text-left px-3 py-2 text-sm hover:bg-muted"
                            onClick={() => {
                              setExCustomerId(v.id)
                              setExCustomerSearch(v.name)
                              setExSearchResults([])
                            }}
                          >
                            {v.name}
                          </button>
                        ))}
                      </div>
                    )}
                    {exCustomerId && (
                      <p className="text-xs text-green-600">
                        Selected: {exCustomerSearch}
                      </p>
                    )}
                  </div>
                )}

                <TermsForm
                  netDays={exNetDays}
                  setNetDays={setExNetDays}
                  fcRate={exFcRate}
                  setFcRate={setExFcRate}
                  fcAfterDays={exFcAfterDays}
                  setFcAfterDays={setExFcAfterDays}
                  noFc={exNoFc}
                  setNoFc={setExNoFc}
                  creditLimit={exCreditLimit}
                  setCreditLimit={setExCreditLimit}
                  noLimit={exNoLimit}
                  setNoLimit={setExNoLimit}
                />

                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setShowAddException(false)
                      setEditingExceptionId(null)
                    }}
                  >
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleSaveException}
                    disabled={exSaving}
                  >
                    {exSaving
                      ? "Saving..."
                      : editingExceptionId
                        ? "Save changes"
                        : "Save exception"}
                  </Button>
                </div>
              </div>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  prefillExceptionForm()
                  setShowAddException(true)
                  setEditingExceptionId(null)
                }}
              >
                <Plus className="h-3.5 w-3.5 mr-1" />
                Add exception
              </Button>
            )}
          </div>
        )}
      </Card>

      {/* ── Footer ────────────────────────────────────────────── */}
      <div className="flex items-center justify-between pt-2">
        <Button onClick={() => navigate("/onboarding")}>
          {applied ? "Back to Onboarding" : "Save & Continue"}
        </Button>

        <button
          type="button"
          className="text-sm text-muted-foreground hover:text-foreground underline underline-offset-2"
          onClick={handleSkip}
        >
          Skip for now
        </button>
      </div>

      <p className="text-xs text-muted-foreground">
        Default terms: Net 30, 1.5% finance charge after 30 days. You can update
        these anytime in Settings.
      </p>
    </div>
  )
}
