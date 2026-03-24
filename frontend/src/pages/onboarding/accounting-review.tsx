/**
 * AI Analysis Review Screen — /onboarding/accounting/review
 *
 * Shows AI-analyzed accounting data with auto-approved items collapsed
 * and flagged items surfaced for tenant review. The goal is "review, not configure."
 */

import { useState, useEffect, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  Check,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  Archive,
  RefreshCw,
  Users,
  Building2,
  Package,
} from "lucide-react"
import { cn } from "@/lib/utils"
import apiClient from "@/lib/api-client"

// ── Types ──

interface AnalysisItem {
  id: string
  source_id: string | null
  source_name: string
  platform_category: string | null
  confidence: number
  reasoning: string | null
  alternative: string | null
  status: string
  is_stale: boolean
}

interface AnalysisResults {
  gl_accounts: { auto_approved: AnalysisItem[]; needs_review: AnalysisItem[]; stale: AnalysisItem[] }
  customers: { auto_approved: AnalysisItem[]; needs_review: AnalysisItem[] }
  vendors: { auto_approved: AnalysisItem[]; needs_review: AnalysisItem[] }
  products: { auto_approved: AnalysisItem[]; needs_review: AnalysisItem[] }
}

interface AnalysisStatus {
  status: string
  auto_approved: number
  review_required: number
}

// ── Platform categories for dropdowns ──

const GL_CATEGORIES = [
  { group: "Revenue", items: ["vault_sales", "urn_sales", "equipment_sales", "delivery_revenue", "redi_rock_sales", "wastewater_sales", "rosetta_sales", "service_revenue", "other_revenue"] },
  { group: "AR", items: ["ar_funeral_homes", "ar_contractors", "ar_government", "ar_other"] },
  { group: "COGS", items: ["vault_materials", "direct_labor", "delivery_costs", "other_cogs"] },
  { group: "AP", items: ["accounts_payable"] },
  { group: "Expenses", items: ["rent", "utilities", "insurance", "payroll", "office_supplies", "vehicle_expense", "repairs_maintenance", "depreciation", "professional_fees", "advertising", "other_expense"] },
]

const CUSTOMER_TYPES = ["funeral_home", "cemetery", "contractor", "government", "retail", "unknown"]
const VENDOR_TYPES = ["materials_supplier", "equipment", "utilities", "professional_services", "unknown"]

// ── Component ──

export default function AccountingReviewPage() {
  const navigate = useNavigate()
  const [status, setStatus] = useState<AnalysisStatus | null>(null)
  const [results, setResults] = useState<AnalysisResults | null>(null)
  const [loading, setLoading] = useState(true)
  const [confirming, setConfirming] = useState(false)
  const [decisions, setDecisions] = useState<Record<string, { action: string; new_category?: string }>>({})

  // Collapsed sections
  const [showAutoGL, setShowAutoGL] = useState(false)
  const [showStale, setShowStale] = useState(false)
  const [showAutoCust, setShowAutoCust] = useState(false)
  const [showAutoVend, setShowAutoVend] = useState(false)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const [statusRes, resultsRes] = await Promise.all([
        apiClient.get("/accounting-connection/ai-analysis/status"),
        apiClient.get("/accounting-connection/ai-analysis/results"),
      ])
      setStatus(statusRes.data)
      setResults(resultsRes.data)

      // Pre-set all pending items to "confirm" as default
      const defaults: Record<string, { action: string }> = {}
      const allReview = [
        ...resultsRes.data.gl_accounts.needs_review,
        ...resultsRes.data.customers.needs_review,
        ...resultsRes.data.vendors.needs_review,
        ...resultsRes.data.products.needs_review,
      ]
      for (const item of allReview) {
        defaults[item.id] = { action: "confirm" }
      }
      setDecisions(defaults)
    } catch {
      toast.error("Failed to load analysis results")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const setDecision = (id: string, action: string, new_category?: string) => {
    setDecisions((prev) => ({
      ...prev,
      [id]: { action, ...(new_category ? { new_category } : {}) },
    }))
  }

  const handleConfirmAll = async () => {
    setConfirming(true)
    try {
      const confirmations = Object.entries(decisions).map(([id, dec]) => ({
        id,
        ...dec,
      }))
      await apiClient.post("/accounting-connection/ai-analysis/confirm", {
        confirmations,
      })
      toast.success("Analysis confirmed — accounts mapped and data imported")
      navigate("/onboarding")
    } catch {
      toast.error("Failed to confirm analysis")
    } finally {
      setConfirming(false)
    }
  }

  if (loading || !results || !status) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  if (status.status === "running") {
    return (
      <div className="max-w-2xl mx-auto py-16 text-center">
        <RefreshCw className="h-10 w-10 animate-spin text-blue-500 mx-auto mb-4" />
        <h2 className="text-lg font-semibold text-gray-900">Analyzing your accounting data...</h2>
        <p className="text-sm text-gray-500 mt-2">
          This usually takes 15-30 seconds. We're mapping your chart of accounts,
          categorizing customers and vendors, and matching products.
        </p>
      </div>
    )
  }

  if (status.status === "failed") {
    return (
      <div className="max-w-2xl mx-auto py-16 text-center">
        <AlertTriangle className="h-10 w-10 text-amber-500 mx-auto mb-4" />
        <h2 className="text-lg font-semibold text-gray-900">Analysis couldn't complete</h2>
        <p className="text-sm text-gray-500 mt-2 mb-6">
          We'll set up manual mapping instead. You can map your accounts step by step.
        </p>
        <Button onClick={() => navigate("/onboarding/accounting")}>
          Continue with manual setup
        </Button>
      </div>
    )
  }

  const totalAutoApproved =
    results.gl_accounts.auto_approved.length +
    results.customers.auto_approved.length +
    results.vendors.auto_approved.length +
    results.products.auto_approved.length

  const totalReview =
    results.gl_accounts.needs_review.length +
    results.customers.needs_review.length +
    results.vendors.needs_review.length +
    results.products.needs_review.length

  return (
    <div className="max-w-3xl mx-auto space-y-6 pb-24">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Review Your Accounting Data</h1>
        <p className="text-sm text-gray-500 mt-1">
          We analyzed your accounting system.{" "}
          <span className="text-green-600 font-medium">{totalAutoApproved} items mapped automatically.</span>{" "}
          {totalReview > 0 && (
            <span className="text-amber-600 font-medium">{totalReview} need your review.</span>
          )}
        </p>
      </div>

      {/* SECTION 1 — GL Account Mappings */}
      <Card>
        <CardContent className="p-5">
          <h2 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
            GL Account Mappings
            <span className="text-xs font-normal text-gray-400">
              {results.gl_accounts.auto_approved.length} auto ·{" "}
              {results.gl_accounts.needs_review.length} review
            </span>
          </h2>

          {/* Auto-approved (collapsed) */}
          {results.gl_accounts.auto_approved.length > 0 && (
            <button
              onClick={() => setShowAutoGL(!showAutoGL)}
              className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 mb-3"
            >
              {showAutoGL ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              <Check className="h-3.5 w-3.5 text-green-500" />
              {results.gl_accounts.auto_approved.length} accounts mapped automatically
            </button>
          )}
          {showAutoGL && (
            <div className="mb-4 space-y-1 pl-6">
              {results.gl_accounts.auto_approved.map((item) => (
                <div key={item.id} className="flex items-center justify-between text-xs text-gray-500 py-0.5">
                  <span>{item.source_id} — {item.source_name}</span>
                  <span className="text-green-600">{item.platform_category}</span>
                </div>
              ))}
            </div>
          )}

          {/* Needs review */}
          {results.gl_accounts.needs_review.length > 0 && (
            <div className="space-y-3">
              {results.gl_accounts.needs_review.map((item) => (
                <ReviewItem
                  key={item.id}
                  item={item}
                  categories={GL_CATEGORIES.flatMap((g) => g.items)}
                  decision={decisions[item.id]}
                  onDecision={(action, cat) => setDecision(item.id, action, cat)}
                />
              ))}
            </div>
          )}

          {results.gl_accounts.needs_review.length === 0 && !showAutoGL && (
            <p className="text-sm text-green-600 flex items-center gap-1.5">
              <Check className="h-4 w-4" /> All accounts mapped — no review needed
            </p>
          )}
        </CardContent>
      </Card>

      {/* SECTION 2 — Stale Data */}
      {results.gl_accounts.stale.length > 0 && (
        <Card className="border-gray-200">
          <CardContent className="p-5">
            <button
              onClick={() => setShowStale(!showStale)}
              className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700"
            >
              {showStale ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              <Archive className="h-3.5 w-3.5" />
              {results.gl_accounts.stale.length} accounts with no recent activity — archived
            </button>
            {showStale && (
              <div className="mt-3 space-y-1 pl-6">
                {results.gl_accounts.stale.map((item) => (
                  <div key={item.id} className="flex items-center justify-between text-xs text-gray-400 py-0.5">
                    <span>{item.source_id} — {item.source_name}</span>
                    <span>Archived</span>
                  </div>
                ))}
                <p className="text-xs text-gray-400 mt-2">
                  You can restore these anytime from Settings.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* SECTION 3 — Customer Import */}
      <Card>
        <CardContent className="p-5">
          <h2 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Users className="h-4 w-4" /> Customer Import
            <span className="text-xs font-normal text-gray-400">
              {results.customers.auto_approved.length} auto ·{" "}
              {results.customers.needs_review.length} review
            </span>
          </h2>

          {results.customers.auto_approved.length > 0 && (
            <button
              onClick={() => setShowAutoCust(!showAutoCust)}
              className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 mb-3"
            >
              {showAutoCust ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              <Check className="h-3.5 w-3.5 text-green-500" />
              {results.customers.auto_approved.length} customers matched automatically
            </button>
          )}
          {showAutoCust && (
            <div className="mb-4 space-y-1 pl-6">
              {results.customers.auto_approved.map((item) => (
                <div key={item.id} className="flex items-center justify-between text-xs text-gray-500 py-0.5">
                  <span>{item.source_name}</span>
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs">{item.platform_category}</span>
                </div>
              ))}
            </div>
          )}

          {results.customers.needs_review.map((item) => (
            <ReviewItem
              key={item.id}
              item={item}
              categories={CUSTOMER_TYPES}
              decision={decisions[item.id]}
              onDecision={(action, cat) => setDecision(item.id, action, cat)}
            />
          ))}

          {results.customers.needs_review.length === 0 && !showAutoCust && (
            <p className="text-sm text-green-600 flex items-center gap-1.5">
              <Check className="h-4 w-4" /> All customers categorized
            </p>
          )}
        </CardContent>
      </Card>

      {/* SECTION 4 — Vendor Import */}
      <Card>
        <CardContent className="p-5">
          <h2 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Building2 className="h-4 w-4" /> Vendor Import
            <span className="text-xs font-normal text-gray-400">
              {results.vendors.auto_approved.length} auto ·{" "}
              {results.vendors.needs_review.length} review
            </span>
          </h2>

          {results.vendors.auto_approved.length > 0 && (
            <button
              onClick={() => setShowAutoVend(!showAutoVend)}
              className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 mb-3"
            >
              {showAutoVend ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              <Check className="h-3.5 w-3.5 text-green-500" />
              {results.vendors.auto_approved.length} vendors categorized automatically
            </button>
          )}

          {results.vendors.needs_review.map((item) => (
            <ReviewItem
              key={item.id}
              item={item}
              categories={VENDOR_TYPES}
              decision={decisions[item.id]}
              onDecision={(action, cat) => setDecision(item.id, action, cat)}
            />
          ))}

          {results.vendors.needs_review.length === 0 && (
            <p className="text-sm text-green-600 flex items-center gap-1.5">
              <Check className="h-4 w-4" /> All vendors categorized
            </p>
          )}
        </CardContent>
      </Card>

      {/* SECTION 5 — Product Matching */}
      {(results.products.auto_approved.length > 0 || results.products.needs_review.length > 0) && (
        <Card>
          <CardContent className="p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Package className="h-4 w-4" /> Product Matching
            </h2>
            {results.products.needs_review.map((item) => (
              <ReviewItem
                key={item.id}
                item={item}
                categories={[]}
                decision={decisions[item.id]}
                onDecision={(action) => setDecision(item.id, action)}
              />
            ))}
            {results.products.needs_review.length === 0 && (
              <p className="text-sm text-green-600 flex items-center gap-1.5">
                <Check className="h-4 w-4" /> Products matched
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* SECTION 6 — Sync Validation Notice */}
      <Card className="border-blue-100 bg-blue-50/30">
        <CardContent className="p-4">
          <p className="text-sm text-blue-800">
            After your first sync runs, we'll monitor for any accounts posting to unexpected
            categories and flag them for your review. This catches any mapping gaps automatically.
          </p>
        </CardContent>
      </Card>

      {/* Sticky footer */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t p-4 flex items-center justify-between z-40">
        <Button variant="ghost" onClick={() => navigate("/onboarding/accounting")}>
          ← Back
        </Button>
        <Button onClick={handleConfirmAll} disabled={confirming} className="gap-2">
          {confirming ? (
            <RefreshCw className="h-4 w-4 animate-spin" />
          ) : (
            <Check className="h-4 w-4" />
          )}
          {confirming ? "Confirming..." : "Confirm & Continue"}
        </Button>
      </div>
    </div>
  )
}

// ── Review item component ──

function ReviewItem({
  item,
  categories,
  decision,
  onDecision,
}: {
  item: AnalysisItem
  categories: string[]
  decision?: { action: string; new_category?: string }
  onDecision: (action: string, new_category?: string) => void
}) {
  const isIgnored = decision?.action === "ignore"
  const confPct = Math.round(item.confidence * 100)
  const confColor =
    confPct >= 60 ? "text-amber-600" : "text-red-500"

  return (
    <div
      className={cn(
        "border rounded-lg p-3 mb-2",
        isIgnored ? "opacity-50 bg-gray-50" : "bg-white"
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            {item.source_id && (
              <span className="text-xs text-gray-400 font-mono">{item.source_id}</span>
            )}
            <span className="text-sm font-medium text-gray-900 truncate">{item.source_name}</span>
          </div>
          {item.reasoning && (
            <p className="text-xs text-gray-500 mt-0.5">{item.reasoning}</p>
          )}
        </div>
        <span className={cn("text-xs font-medium whitespace-nowrap", confColor)}>
          {confPct}% match
        </span>
      </div>

      <div className="mt-2 flex items-center gap-2 flex-wrap">
        {categories.length > 0 ? (
          <select
            value={decision?.new_category || item.platform_category || ""}
            onChange={(e) => onDecision("change", e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-xs"
            disabled={isIgnored}
          >
            <option value="">Select category...</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        ) : (
          <span className="text-xs text-gray-500">
            {item.platform_category || "No match found"}
          </span>
        )}

        {item.alternative && (
          <span className="text-xs text-gray-400">
            Alt: {item.alternative.replace(/_/g, " ")}
          </span>
        )}

        <button
          onClick={() => onDecision(isIgnored ? "confirm" : "ignore")}
          className="ml-auto text-xs text-gray-400 hover:text-gray-600"
        >
          {isIgnored ? "Restore" : "Ignore"}
        </button>
      </div>
    </div>
  )
}
