// duplicates.tsx — Review potential duplicate company records
// Route: /crm/companies/duplicates

import { useState, useEffect, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Check, X, Loader2 } from "lucide-react"

interface DuplicateReview {
  id: string
  company_a: { id: string; name: string; city: string | null; state: string | null }
  company_b: { id: string; name: string; city: string | null; state: string | null }
  similarity_score: number | null
  status: string
}

export default function DuplicateReviewPage() {
  const navigate = useNavigate()
  const [reviews, setReviews] = useState<DuplicateReview[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const res = await apiClient.get("/ai/duplicates")
      setReviews(res.data || [])
    } catch {
      // Table may not exist yet
      setReviews([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  async function handleResolve(reviewId: string, action: "merge" | "not_duplicate") {
    try {
      await apiClient.post(`/ai/duplicates/${reviewId}/resolve`, { action })
      toast.success(action === "merge" ? "Merged" : "Marked as not duplicate")
      setReviews((prev) => prev.filter((r) => r.id !== reviewId))
    } catch {
      toast.error("Failed")
    }
  }

  if (loading) return <div className="flex justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-gray-400" /></div>

  return (
    <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Duplicate Review</h1>
        <p className="text-sm text-gray-500 mt-1">Potential duplicate companies detected by AI. Merge or dismiss each pair.</p>
      </div>

      {reviews.length === 0 ? (
        <div className="text-center py-16 space-y-2">
          <div className="inline-flex items-center gap-2 bg-green-50 text-green-700 px-4 py-2 rounded-full text-sm font-medium">
            <Check className="h-4 w-4" /> No duplicates to review
          </div>
          <p className="text-sm text-gray-400">The AI agent will check for new duplicates nightly.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {reviews.map((r) => (
            <Card key={r.id} className="p-4 space-y-3">
              <p className="text-sm font-medium text-gray-700">Are these the same company?</p>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="font-semibold text-sm">{r.company_a.name}</p>
                  {r.company_a.city && <p className="text-xs text-gray-500">{r.company_a.city}, {r.company_a.state}</p>}
                  <button onClick={() => navigate(`/crm/companies/${r.company_a.id}`)} className="text-xs text-blue-600 hover:underline mt-1">View →</button>
                </div>
                <div className="bg-blue-50 rounded-lg p-3">
                  <p className="font-semibold text-sm">{r.company_b.name}</p>
                  {r.company_b.city && <p className="text-xs text-gray-500">{r.company_b.city}, {r.company_b.state}</p>}
                  <button onClick={() => navigate(`/crm/companies/${r.company_b.id}`)} className="text-xs text-blue-600 hover:underline mt-1">View →</button>
                </div>
              </div>
              {r.similarity_score && (
                <p className="text-xs text-gray-400">Name similarity: {Math.round(r.similarity_score * 100)}%</p>
              )}
              <div className="flex gap-2">
                <Button size="sm" className="bg-green-600 hover:bg-green-700" onClick={() => handleResolve(r.id, "merge")}>
                  <Check className="h-3.5 w-3.5 mr-1" /> Same — merge
                </Button>
                <Button size="sm" variant="outline" onClick={() => handleResolve(r.id, "not_duplicate")}>
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
