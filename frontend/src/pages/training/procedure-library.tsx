/**
 * Procedure Library — /training/procedures
 * Step-by-step guides for common business processes.
 */

import { useState, useEffect, useCallback } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { toast } from "sonner"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { BookOpen, Search, ChevronRight, ArrowLeft, Lightbulb, AlertTriangle } from "lucide-react"
import { cn } from "@/lib/utils"
import apiClient from "@/lib/api-client"

interface Procedure {
  procedure_key: string
  title: string
  category: string
  applicable_roles: string[]
  overview: string | null
  steps: ProcedureStep[]
  related_procedure_keys: string[] | null
  content_generated: boolean
}

interface ProcedureStep {
  step_number: number
  title: string
  instruction: string
  platform_path?: string
  why_this_matters?: string
  common_mistakes?: string[]
}

const CATEGORIES = [
  { key: "all", label: "All Procedures" },
  { key: "accounting", label: "Accounting" },
  { key: "month_end", label: "Month-End" },
  { key: "sales", label: "Sales" },
  { key: "operations", label: "Operations" },
  { key: "transfers", label: "Transfers" },
  { key: "compliance", label: "Compliance" },
]

const ROLE_LABELS: Record<string, string> = {
  accounting: "Accounting",
  inside_sales: "Inside Sales",
  operations: "Operations",
  manager: "Manager",
  owner: "Owner",
}

const CATEGORY_COLORS: Record<string, string> = {
  accounting: "bg-blue-100 text-blue-700",
  month_end: "bg-purple-100 text-purple-700",
  sales: "bg-green-100 text-green-700",
  operations: "bg-amber-100 text-amber-700",
  transfers: "bg-cyan-100 text-cyan-700",
  compliance: "bg-red-100 text-red-700",
}

export default function ProcedureLibraryPage() {
  const [procedures, setProcedures] = useState<Procedure[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedCategory, setSelectedCategory] = useState("all")
  const [searchQuery, setSearchQuery] = useState("")

  const fetchProcedures = useCallback(async () => {
    setLoading(true)
    try {
      const params = selectedCategory !== "all" ? `?category=${selectedCategory}` : ""
      const res = await apiClient.get(`/training/procedures${params}`)
      setProcedures(res.data)
    } catch {
      toast.error("Failed to load procedures")
    } finally {
      setLoading(false)
    }
  }, [selectedCategory])

  useEffect(() => {
    fetchProcedures()
  }, [fetchProcedures])

  const filtered = procedures.filter((p) =>
    searchQuery
      ? p.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (p.overview && p.overview.toLowerCase().includes(searchQuery.toLowerCase()))
      : true
  )

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Procedure Library</h1>
        <p className="text-sm text-gray-500 mt-1">
          Step-by-step guides for common business processes
        </p>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search procedures..."
          className="w-full pl-9 pr-4 py-2 rounded-lg border border-gray-200 text-sm"
        />
      </div>

      {/* Category filter */}
      <div className="flex flex-wrap gap-2">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.key}
            onClick={() => setSelectedCategory(cat.key)}
            className={cn(
              "px-3 py-1.5 rounded-full text-xs font-medium transition-colors",
              selectedCategory === cat.key
                ? "bg-gray-900 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            )}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Procedure list */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-24 bg-gray-100 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <BookOpen className="mx-auto h-10 w-10 text-gray-300 mb-3" />
            <p className="text-sm text-gray-500">
              {searchQuery
                ? "No procedures match your search."
                : "No procedures available yet. Content will be generated when training is set up."}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {filtered.map((proc) => (
            <ProcedureCard key={proc.procedure_key} procedure={proc} />
          ))}
        </div>
      )}
    </div>
  )
}

function ProcedureCard({ procedure }: { procedure: Procedure }) {
  const navigate = useNavigate()

  return (
    <Card
      className="hover:border-gray-300 transition-colors cursor-pointer"
      onClick={() => navigate(`/training/procedures/${procedure.procedure_key}`)}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-gray-900">{procedure.title}</h3>
            <div className="flex items-center gap-2 mt-1">
              <span
                className={cn(
                  "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                  CATEGORY_COLORS[procedure.category] || "bg-gray-100 text-gray-600"
                )}
              >
                {procedure.category.replace("_", " ")}
              </span>
              {procedure.applicable_roles?.map((role) => (
                <span key={role} className="text-xs text-gray-400">
                  {ROLE_LABELS[role] || role}
                </span>
              ))}
            </div>
            {procedure.overview && (
              <p className="text-xs text-gray-500 mt-1.5 line-clamp-2">{procedure.overview}</p>
            )}
          </div>
          <ChevronRight className="h-4 w-4 text-gray-400 shrink-0 mt-1" />
        </div>
      </CardContent>
    </Card>
  )
}

// Detail page component
export function ProcedureDetailPage() {
  const { key } = useParams<{ key: string }>()
  const navigate = useNavigate()
  const [procedure, setProcedure] = useState<Procedure | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!key) return
    apiClient
      .get(`/training/procedures/${key}`)
      .then((res) => setProcedure(res.data))
      .catch(() => toast.error("Procedure not found"))
      .finally(() => setLoading(false))
  }, [key])

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

  if (!procedure) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-8 text-center">
        <p className="text-gray-500">Procedure not found.</p>
        <Button variant="ghost" onClick={() => navigate("/training/procedures")} className="mt-4">
          ← Back to procedures
        </Button>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Back link */}
      <button
        onClick={() => navigate("/training/procedures")}
        className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Procedure Library
      </button>

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{procedure.title}</h1>
        <div className="flex items-center gap-2 mt-2">
          <span
            className={cn(
              "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
              CATEGORY_COLORS[procedure.category] || "bg-gray-100 text-gray-600"
            )}
          >
            {procedure.category.replace("_", " ")}
          </span>
          {procedure.applicable_roles?.map((role) => (
            <span key={role} className="text-xs text-gray-400 bg-gray-100 rounded-full px-2 py-0.5">
              {ROLE_LABELS[role] || role}
            </span>
          ))}
        </div>
      </div>

      {/* Overview */}
      {procedure.overview && (
        <Card className="border-blue-200 bg-blue-50/30">
          <CardContent className="p-4">
            <h3 className="text-xs font-semibold text-blue-800 uppercase tracking-wider mb-2">
              Overview
            </h3>
            <p className="text-sm text-blue-900 leading-relaxed whitespace-pre-line">
              {procedure.overview}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Steps */}
      {procedure.steps && procedure.steps.length > 0 && (
        <div className="space-y-4">
          {procedure.steps.map((step, i) => (
            <Card key={i}>
              <CardContent className="p-4">
                <h3 className="text-sm font-semibold text-gray-900 mb-2">
                  Step {step.step_number}: {step.title}
                </h3>

                {step.platform_path && (
                  <p className="text-xs text-gray-500 mb-2 font-mono bg-gray-50 rounded px-2 py-1 inline-block">
                    Navigate to: {step.platform_path}
                  </p>
                )}

                <p className="text-sm text-gray-700 leading-relaxed">{step.instruction}</p>

                {step.why_this_matters && (
                  <div className="mt-3 flex items-start gap-2 bg-amber-50 rounded-lg p-3">
                    <Lightbulb className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs font-semibold text-amber-800 mb-0.5">Why this matters</p>
                      <p className="text-xs text-amber-700">{step.why_this_matters}</p>
                    </div>
                  </div>
                )}

                {step.common_mistakes && step.common_mistakes.length > 0 && (
                  <div className="mt-3 flex items-start gap-2 bg-red-50 rounded-lg p-3">
                    <AlertTriangle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs font-semibold text-red-800 mb-0.5">Common mistakes</p>
                      <ul className="text-xs text-red-700 list-disc list-inside">
                        {step.common_mistakes.map((m, j) => (
                          <li key={j}>{m}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Related procedures */}
      {procedure.related_procedure_keys && procedure.related_procedure_keys.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            Related Procedures
          </h3>
          <div className="flex flex-wrap gap-2">
            {procedure.related_procedure_keys.map((rk) => (
              <Button
                key={rk}
                variant="outline"
                size="sm"
                onClick={() => navigate(`/training/procedures/${rk}`)}
                className="text-xs"
              >
                {rk.replace(/_/g, " ")}
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
