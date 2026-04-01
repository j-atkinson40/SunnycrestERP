// vault-order-lifecycle.tsx
// Route: /training/vault-order-lifecycle
// Interactive 7-stage lifecycle training with per-user progress tracking.

import { useState, useEffect, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "@/contexts/auth-context"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import {
  ChevronLeft,
  ChevronRight,
  CheckCircle,
  ExternalLink,
  Award,
  Loader2,
} from "lucide-react"

// ── Stage definitions ────────────────────────────────────────────────────────

interface Stage {
  key: string
  pill: string
  title: string
  description: string
  details: [string, string][] // [text, "ai" | ""]
  tryItLabel: string
  tryItUrl: string
}

const ALL_STAGES: Stage[] = [
  {
    key: "entry",
    pill: "1. Order Entry",
    title: "Order entry in under 30 seconds",
    description:
      "When a funeral home calls to order a vault, your staff opens the order station and taps a template. A pop-up asks which funeral home — recent ones appear for one-tap selection. The slide-over fills in with the cemetery shortlist, service location, time, and ETA. Save, and the order is in the system before the call ends.",
    details: [
      ["Template-first flow — tap the right vault and equipment combo", ""],
      ["Funeral home pop-up with recent history for repeat callers", "ai"],
      ["Cemetery shortlist with city labels prevents wrong-cemetery mistakes", "ai"],
      ["Equipment auto-prefill from cemetery settings", "ai"],
      ["ETA field for procession arrival — Church, Funeral Home, or Graveside", ""],
      ["Soft inventory check flags low stock without blocking", "ai"],
      ["Credit hold banner shows the situation without blocking the order", ""],
    ],
    tryItLabel: "Open order station",
    tryItUrl: "/order-station",
  },
  {
    key: "scheduling",
    pill: "2. Scheduling",
    title: "Scheduling and delivery — connected",
    description:
      "Orders appear on the scheduling board automatically. Your dispatcher drags them to driver lanes. Drivers see their route on their phone with all the details — vault type, equipment, service location, time, and ETA. When they arrive and complete the delivery, the order status updates in real time.",
    details: [
      ["Drag-and-drop scheduling board with driver lanes", ""],
      ["Driver portal on any phone — today's route and stop details", ""],
      ["Cards show vault, equipment, service location, time, and ETA", ""],
      ["Exception reporting at delivery completion", ""],
      ["Auto-confirm at 6 PM for tenants without driver updates", "ai"],
    ],
    tryItLabel: "Open scheduling board",
    tryItUrl: "/scheduling",
  },
  {
    key: "invoicing",
    pill: "3. Invoicing",
    title: "Invoices that create themselves",
    description:
      "At 6 PM every day, Bridgeable generates draft invoices for all completed funeral orders. The next morning, your office reviews them — clean deliveries can be bulk-approved in one click. Exceptions are flagged for individual review. No one creates an invoice manually.",
    details: [
      ["6 PM batch job creates draft invoices automatically", "ai"],
      ["Morning briefing shows draft count, total, and exceptions", "ai"],
      ["Review queue with driver exception flags", ""],
      ["Bulk approve clean deliveries — one-by-one for exceptions", ""],
      ["Never sent without human approval", ""],
    ],
    tryItLabel: "Open invoice review",
    tryItUrl: "/ar/invoices/review",
  },
  {
    key: "billing",
    pill: "4. Billing",
    title: "Bills go out automatically",
    description:
      "Some funeral homes want an invoice per order. Others want a monthly statement. Bridgeable handles both — the billing preference is set once per customer and invoices route automatically. PDFs include the deceased name, cemetery, and service date.",
    details: [
      ["Per-order invoicing — PDF emailed immediately after approval", ""],
      ["Monthly statement billing — invoices accumulate until statement run", ""],
      ["PDF includes deceased name, cemetery, and service date", ""],
      ["Early payment discount shown — discounted vs. full amount", "ai"],
      ["Statements auto-generate at month end", "ai"],
    ],
    tryItLabel: "View a customer",
    tryItUrl: "/customers",
  },
  {
    key: "collections",
    pill: "5. Collections",
    title: "Collections that run themselves",
    description:
      "Every night, Bridgeable checks for overdue invoices and triggers collection sequences. AI drafts reminder emails for staff review. When payment is received, collections pause automatically. Credit holds apply when balances exceed limits.",
    details: [
      ["Nightly overdue detection triggers collection sequences", "ai"],
      ["AI drafts reminder emails in your tone", "ai"],
      ["Escalation from friendly reminder to firm final notice", ""],
      ["Auto-pause collections when payment is received", "ai"],
      ["Credit hold applied when balance exceeds limit", ""],
      ["Morning briefing shows collection status and risk", "ai"],
    ],
    tryItLabel: "View AR aging",
    tryItUrl: "/ar/aging",
  },
  {
    key: "payment",
    pill: "6. Payment",
    title: "Payment processing in seconds",
    description:
      "When a check arrives, scan it. Claude reads the payer, amount, and check number. The system matches it to the right customer and suggests which invoices to apply it to — oldest first. Confirm and the payment is recorded.",
    details: [
      ["Check scanning with Claude Vision — extracts payer, amount, check number", "ai"],
      ["Smart customer matching from check payer name", "ai"],
      ["FIFO payment suggestion — oldest invoices first", "ai"],
      ["Early payment discount auto-applied within window", "ai"],
      ["Short-pay detection with honor-discount option", "ai"],
    ],
    tryItLabel: "Record a payment",
    tryItUrl: "/ar/payments",
  },
  {
    key: "completion",
    pill: "7. Completion",
    title: "The platform gets smarter with every order",
    description:
      "When an invoice is fully paid, the order auto-completes. The cemetery shortlist updates. Payment timing patterns are tracked. Vault preferences are learned. After 90 days, every part of this lifecycle runs faster because Bridgeable knows your funeral homes.",
    details: [
      ["Invoice fully paid — order auto-completes", "ai"],
      ["Cemetery shortlist updates from completed orders", "ai"],
      ["Payment timing patterns tracked per funeral home", "ai"],
      ["Vault preference and equipment patterns learned", "ai"],
      ["Collections auto-pause and credit hold auto-release", "ai"],
    ],
    tryItLabel: "View completed orders",
    tryItUrl: "/orders?status=completed",
  },
]

// Role-based stage filtering
const ROLE_STAGES: Record<string, string[]> = {
  driver: ["scheduling", "billing"],
  production: ["scheduling"],
}

function getVisibleStages(roleSlug: string | undefined): Stage[] {
  if (!roleSlug) return ALL_STAGES
  const allowed = ROLE_STAGES[roleSlug]
  if (!allowed) return ALL_STAGES
  return ALL_STAGES.filter((s) => allowed.includes(s.key))
}

// ── Component ────────────────────────────────────────────────────────────────

export default function VaultOrderLifecyclePage() {
  const navigate = useNavigate()
  const { user } = useAuth()

  const stages = getVisibleStages(user?.role_slug)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [completedStages, setCompletedStages] = useState<Set<string>>(new Set())
  const [allComplete, setAllComplete] = useState(false)
  const [loading, setLoading] = useState(true)
  const [completing, setCompleting] = useState(false)

  const currentStage = stages[currentIndex]

  // Fetch progress
  const fetchProgress = useCallback(async () => {
    try {
      const { data } = await apiClient.get("/training/vault-order-lifecycle/progress")
      setCompletedStages(new Set(data.stages_completed))
      setAllComplete(data.all_complete)
    } catch {
      // Silently fail
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchProgress()
  }, [fetchProgress])

  // Complete stage
  async function handleComplete() {
    if (!currentStage || completedStages.has(currentStage.key)) return
    setCompleting(true)
    try {
      const { data } = await apiClient.post(
        `/training/vault-order-lifecycle/stages/${currentStage.key}/complete`
      )
      setCompletedStages((prev) => new Set([...prev, currentStage.key]))
      if (data.all_complete) {
        setAllComplete(true)
        toast.success("Vault order lifecycle training complete!")
      } else {
        toast.success(`Stage ${currentIndex + 1} complete`)
      }
    } catch {
      toast.error("Failed to save progress")
    } finally {
      setCompleting(false)
    }
  }

  function goTo(idx: number) {
    setCurrentIndex(idx)
  }

  function prev() {
    if (currentIndex > 0) setCurrentIndex(currentIndex - 1)
  }

  function next() {
    if (currentIndex < stages.length - 1) setCurrentIndex(currentIndex + 1)
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  const completedCount = stages.filter((s) => completedStages.has(s.key)).length

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          Vault order lifecycle
        </h1>
        <p className="text-gray-500 mt-1">
          Learn how an order moves through Bridgeable from first call to closed account
        </p>
        {completedCount > 0 && !allComplete && (
          <div className="mt-4">
            <div className="flex items-center justify-between text-sm mb-1">
              <span className="text-gray-600">
                {completedCount} of {stages.length} stages complete
              </span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-teal-500 rounded-full transition-all"
                style={{ width: `${(completedCount / stages.length) * 100}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* All complete banner */}
      {allComplete && (
        <div className="bg-teal-50 border border-teal-200 rounded-xl p-6 flex items-start gap-4">
          <Award className="h-8 w-8 text-teal-600 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-semibold text-teal-900 text-lg">
              Vault order lifecycle complete
            </h3>
            <p className="text-teal-700 mt-1">
              You know how an order moves through Bridgeable end to end.
            </p>
          </div>
        </div>
      )}

      {/* Stage pills */}
      <div className="flex flex-wrap gap-2 pb-4 border-b border-gray-200">
        {stages.map((stage, idx) => {
          const isCompleted = completedStages.has(stage.key)
          const isCurrent = idx === currentIndex
          return (
            <button
              key={stage.key}
              onClick={() => goTo(idx)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium border transition-colors ${
                isCurrent
                  ? "bg-teal-600 text-white border-teal-600"
                  : isCompleted
                    ? "bg-teal-50 text-teal-700 border-teal-200"
                    : "bg-white text-gray-500 border-gray-200 hover:border-teal-300"
              }`}
            >
              {isCompleted && !isCurrent && (
                <CheckCircle className="h-3.5 w-3.5" />
              )}
              {stage.pill}
            </button>
          )
        })}
      </div>

      {/* Current stage content */}
      {currentStage && (
        <div className="space-y-6">
          <h2 className="text-2xl font-bold text-gray-900">
            {currentStage.title}
          </h2>
          <p className="text-gray-600 text-base leading-relaxed">
            {currentStage.description}
          </p>

          {/* Details */}
          <ul className="space-y-3">
            {currentStage.details.map(([text, badge], idx) => (
              <li key={idx} className="flex items-start gap-3 text-sm">
                <span className="text-teal-500 mt-0.5 flex-shrink-0">&#10003;</span>
                <span>
                  <span dangerouslySetInnerHTML={{ __html: text }} />
                  {badge === "ai" && (
                    <span className="inline-block ml-1.5 bg-teal-50 text-teal-700 text-[11px] font-medium px-2 py-0.5 rounded-full">
                      Bridgeable intelligence
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ul>

          {/* Try it now */}
          <button
            onClick={() => navigate(currentStage.tryItUrl)}
            className="flex items-center gap-2 text-sm font-medium text-teal-600 hover:text-teal-800 transition-colors"
          >
            {currentStage.tryItLabel}
            <ExternalLink className="h-3.5 w-3.5" />
          </button>

          {/* Mark complete */}
          {!completedStages.has(currentStage.key) ? (
            <button
              onClick={handleComplete}
              disabled={completing}
              className="w-full py-3 bg-teal-600 text-white rounded-xl font-semibold text-sm hover:bg-teal-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {completing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <CheckCircle className="h-4 w-4" />
              )}
              Mark as complete
            </button>
          ) : (
            <div className="text-center text-sm text-teal-600 font-medium flex items-center justify-center gap-1.5">
              <CheckCircle className="h-4 w-4" />
              Stage complete
            </div>
          )}
        </div>
      )}

      {/* Navigation */}
      <div className="flex items-center justify-between pt-4 border-t border-gray-200">
        <button
          onClick={prev}
          disabled={currentIndex === 0}
          className="flex items-center gap-1 text-sm font-medium text-gray-500 hover:text-gray-700 disabled:invisible"
        >
          <ChevronLeft className="h-4 w-4" />
          Previous
        </button>
        <div className="flex gap-1.5">
          {stages.map((_, idx) => (
            <span
              key={idx}
              className={`w-2 h-2 rounded-full transition-colors ${
                idx === currentIndex ? "bg-teal-500" : "bg-gray-200"
              }`}
            />
          ))}
        </div>
        {currentIndex < stages.length - 1 ? (
          <button
            onClick={next}
            className="flex items-center gap-1 text-sm font-medium text-teal-600 hover:text-teal-800"
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </button>
        ) : (
          <div className="w-20" /> // spacer
        )}
      </div>
    </div>
  )
}
