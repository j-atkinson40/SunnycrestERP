// company-migration-review.tsx — Review uncertain company merges from data migration.

import { useState, useEffect, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Check, X, Loader2 } from "lucide-react"

interface ReviewItem {
  id: string
  source_type: string
  source_id: string
  source_name: string
  suggested_company_id: string
  suggested_company_name: string
  similarity_score: number | null
  current_company_id: string
  status: string
}

export default function CompanyMigrationReviewPage() {
  const navigate = useNavigate()
  const [reviews, setReviews] = useState<ReviewItem[]>([])
  const [loading, setLoading] = useState(true)
  const [totalAll, setTotalAll] = useState(0)
  const [currentIdx, setCurrentIdx] = useState(0)
  const [acting, setActing] = useState(false)

  const load = useCallback(async () => {
    try {
      const res = await apiClient.get("/companies/migration-reviews")
      setReviews(res.data.items || [])
      setTotalAll(res.data.total || 0)
    } catch {
      toast.error("Could not load reviews")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  async function handleResolve(reviewId: string, action: "merge" | "separate") {
    setActing(true)
    try {
      await apiClient.post(`/companies/merge-review/${reviewId}`, { action })
      toast.success(action === "merge" ? "Merged" : "Kept separate")
      // Advance to next
      setReviews((prev) => prev.filter((r) => r.id !== reviewId))
      setCurrentIdx((prev) => Math.min(prev, reviews.length - 2))
    } catch {
      toast.error("Failed")
    } finally {
      setActing(false)
    }
  }

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto p-6 flex justify-center py-16">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  if (reviews.length === 0) {
    return (
      <div className="max-w-2xl mx-auto p-6 text-center py-16 space-y-4">
        <div className="inline-flex items-center gap-2 bg-green-50 text-green-700 px-4 py-2 rounded-full text-sm font-medium">
          <Check className="h-4 w-4" /> All company records have been reviewed
        </div>
        <p className="text-gray-500 text-sm">{totalAll} total records processed</p>
        <Button onClick={() => navigate("/companies")}>View all companies</Button>
      </div>
    )
  }

  const review = reviews[Math.min(currentIdx, reviews.length - 1)]
  const reviewed = totalAll - reviews.length
  const pct = totalAll > 0 ? Math.round((reviewed / totalAll) * 100) : 0

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Company record review</h1>
        <p className="text-sm text-gray-500 mt-1">
          We found possible duplicate companies during migration. Please confirm which records refer to the same real company.
        </p>
      </div>

      {/* Progress */}
      <div className="space-y-1">
        <div className="flex justify-between text-xs text-gray-500">
          <span>{reviewed} of {totalAll} reviewed</span>
          <span>{reviews.length} remaining</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div className="bg-blue-600 h-2 rounded-full transition-all" style={{ width: `${pct}%` }} />
        </div>
      </div>

      {/* Review card */}
      <Card className="p-5 space-y-4">
        <p className="font-medium text-gray-900">Is this the same company?</p>

        <div className="grid grid-cols-2 gap-4">
          {/* Source (vendor/cemetery) */}
          <div className="bg-gray-50 rounded-lg p-3 space-y-1">
            <Badge variant="outline" className="text-[10px] mb-1">
              {review.source_type === "vendor" ? "Vendor" : "Cemetery"} record
            </Badge>
            <p className="font-semibold text-sm">{review.source_name}</p>
          </div>

          {/* Suggested match (existing customer/entity) */}
          <div className="bg-blue-50 rounded-lg p-3 space-y-1">
            <Badge className="text-[10px] mb-1 bg-blue-100 text-blue-700">Existing company</Badge>
            <p className="font-semibold text-sm">{review.suggested_company_name}</p>
          </div>
        </div>

        {review.similarity_score && (
          <p className="text-xs text-gray-500">
            Name similarity: <span className="font-medium">{Math.round(review.similarity_score * 100)}%</span>
          </p>
        )}

        <div className="flex gap-3">
          <Button
            className="flex-1 bg-green-600 hover:bg-green-700"
            onClick={() => handleResolve(review.id, "merge")}
            disabled={acting}
          >
            <Check className="h-4 w-4 mr-1" /> Same company — merge
          </Button>
          <Button
            variant="outline"
            className="flex-1"
            onClick={() => handleResolve(review.id, "separate")}
            disabled={acting}
          >
            <X className="h-4 w-4 mr-1" /> Different — keep separate
          </Button>
        </div>
      </Card>
    </div>
  )
}
