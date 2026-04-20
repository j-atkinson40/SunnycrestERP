// duplicates.tsx — Review potential duplicate company records
// Route: /vault/vault/crm/companies/duplicates

import { useState, useEffect, useCallback } from "react"
import { Link } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Check, X, Loader2, ChevronLeft, ExternalLink, Undo2 } from "lucide-react"

interface CompanySide {
  id: string
  name: string
  city: string | null
  state: string | null
  customer_type: string | null
  roles: string[]
}

interface DuplicateReview {
  id: string
  company_a: CompanySide
  company_b: CompanySide
  similarity_score: number | null
  status: string
}

const TYPE_LABELS: Record<string, string> = {
  funeral_home: "Funeral Home", contractor: "Contractor", cemetery: "Cemetery",
  licensee: "Licensee", church: "Church", government: "Government",
  school: "School", fire_department: "Fire Dept", individual: "Individual",
}

interface UndoItem {
  reviewId: string
  action: string
  review: DuplicateReview
}

export default function DuplicateReviewPage() {
  const [reviews, setReviews] = useState<DuplicateReview[]>([])
  const [loading, setLoading] = useState(true)
  const [lastAction, setLastAction] = useState<UndoItem | null>(null)

  const load = useCallback(async () => {
    try {
      const res = await apiClient.get("/ai/duplicates")
      setReviews(res.data || [])
    } catch {
      setReviews([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  async function handleResolve(review: DuplicateReview, action: "merge" | "not_duplicate") {
    try {
      await apiClient.post(`/ai/duplicates/${review.id}/resolve`, { action })
      toast.success(action === "merge" ? "Merged" : "Marked as not duplicate")
      setReviews((prev) => prev.filter((r) => r.id !== review.id))
      setLastAction({ reviewId: review.id, action, review })
    } catch {
      toast.error("Failed")
    }
  }

  async function handleUndo() {
    if (!lastAction) return
    try {
      await apiClient.post(`/ai/duplicates/${lastAction.reviewId}/resolve`, { action: "undo" })
      setReviews((prev) => [lastAction.review, ...prev])
      setLastAction(null)
      toast.success("Undone")
    } catch {
      toast.error("Could not undo")
    }
  }

  if (loading) return <div className="flex justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-gray-400" /></div>

  return (
    <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link to="/vault/crm/companies" className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-2">
            <ChevronLeft className="h-4 w-4" /> Back to companies
          </Link>
          <h1 className="text-2xl font-bold">Duplicate Review</h1>
          <p className="text-sm text-gray-500 mt-1">
            {reviews.length > 0 ? `${reviews.length} potential duplicate${reviews.length !== 1 ? "s" : ""} to review` : "Potential duplicate companies detected by AI"}
          </p>
        </div>
        {lastAction && (
          <Button variant="outline" size="sm" onClick={handleUndo}>
            <Undo2 className="h-3.5 w-3.5 mr-1" /> Undo last
          </Button>
        )}
      </div>

      {reviews.length === 0 ? (
        <div className="text-center py-16 space-y-3">
          <div className="inline-flex items-center gap-2 bg-green-50 text-green-700 px-4 py-2 rounded-full text-sm font-medium">
            <Check className="h-4 w-4" /> No duplicates to review
          </div>
          <p className="text-sm text-gray-400">The AI agent will check for new duplicates nightly.</p>
          <Link to="/vault/crm/companies" className="text-sm text-blue-600 hover:underline">← Back to companies</Link>
        </div>
      ) : (
        <div className="space-y-4">
          {reviews.map((r) => (
            <Card key={r.id} className="p-4 space-y-3">
              <p className="text-sm font-medium text-gray-700">Are these the same company?</p>
              <div className="grid grid-cols-2 gap-4">
                {[{ side: r.company_a, bg: "bg-gray-50" }, { side: r.company_b, bg: "bg-blue-50" }].map(({ side, bg }) => (
                  <div key={side.id} className={`${bg} rounded-lg p-3`}>
                    <p className="font-semibold text-sm">{side.name}</p>
                    {side.city && <p className="text-xs text-gray-500">{side.city}, {side.state}</p>}
                    <div className="flex flex-wrap gap-1 mt-1">
                      {side.customer_type && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-white border text-gray-600">
                          {TYPE_LABELS[side.customer_type] || side.customer_type}
                        </span>
                      )}
                      {(side.roles || []).map((role) => (
                        <span key={role} className="text-[10px] px-1.5 py-0.5 rounded-full bg-white border text-gray-500">{role}</span>
                      ))}
                    </div>
                    <a href={`/vault/crm/companies/${side.id}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-0.5 text-xs text-blue-600 hover:underline mt-1.5">
                      View <ExternalLink className="h-2.5 w-2.5" />
                    </a>
                  </div>
                ))}
              </div>
              {r.similarity_score && (
                <p className="text-xs text-gray-400">Name similarity: {Math.round(r.similarity_score * 100)}%</p>
              )}
              <div className="flex gap-2">
                <Button size="sm" className="bg-green-600 hover:bg-green-700" onClick={() => handleResolve(r, "merge")}>
                  <Check className="h-3.5 w-3.5 mr-1" /> Same — merge
                </Button>
                <Button size="sm" variant="outline" onClick={() => handleResolve(r, "not_duplicate")}>
                  <X className="h-3.5 w-3.5 mr-1" /> Different
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
