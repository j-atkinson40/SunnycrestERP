/**
 * ContextualExplanation — inline expandable "Why does this matter?" panel.
 * Renders nothing if explanation not found or user has disabled explanations.
 */

import { useState, useEffect } from "react"
import { ChevronDown, ChevronUp, Lightbulb, Check } from "lucide-react"
import apiClient from "@/lib/api-client"

interface ExplanationData {
  exists: boolean
  explanation_key?: string
  headline?: string
  explanation?: string
  trigger_context?: string
}

export function ContextualExplanation({ explanationKey }: { explanationKey: string }) {
  const [data, setData] = useState<ExplanationData | null>(null)
  const [expanded, setExpanded] = useState(false)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    // Check session storage for previously dismissed explanations
    const dismissedKeys = JSON.parse(sessionStorage.getItem("dismissed_explanations") || "[]")
    if (dismissedKeys.includes(explanationKey)) {
      setDismissed(true)
      return
    }

    apiClient
      .get(`/training/explanations/${explanationKey}`)
      .then((res) => setData(res.data))
      .catch(() => setData({ exists: false }))
  }, [explanationKey])

  if (!data || !data.exists || dismissed) return null

  const handleDismiss = () => {
    setDismissed(true)
    setExpanded(false)
    // Store in session so it stays dismissed for this session
    const dismissedKeys = JSON.parse(sessionStorage.getItem("dismissed_explanations") || "[]")
    if (!dismissedKeys.includes(explanationKey)) {
      dismissedKeys.push(explanationKey)
      sessionStorage.setItem("dismissed_explanations", JSON.stringify(dismissedKeys))
    }
    // Record as viewed (fire-and-forget)
    apiClient.post("/training/profile", { training_role: "accounting" }).catch(() => {})
  }

  return (
    <div className="mt-2 mb-3">
      {!expanded ? (
        <button
          onClick={() => setExpanded(true)}
          className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 transition-colors"
        >
          <Lightbulb className="h-3.5 w-3.5" />
          <span>{data.headline || "Why does this matter?"}</span>
          <ChevronDown className="h-3 w-3" />
        </button>
      ) : (
        <div className="rounded-lg border border-blue-200 bg-blue-50/50 p-3">
          <div className="flex items-start justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <Lightbulb className="h-4 w-4 text-blue-600 shrink-0" />
              <span className="text-sm font-medium text-blue-900">
                {data.headline}
              </span>
            </div>
            <button
              onClick={() => setExpanded(false)}
              className="text-blue-400 hover:text-blue-600"
            >
              <ChevronUp className="h-4 w-4" />
            </button>
          </div>
          <div className="text-sm text-blue-800 leading-relaxed whitespace-pre-line pl-6">
            {data.explanation}
          </div>
          <div className="mt-3 pl-6">
            <button
              onClick={handleDismiss}
              className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
            >
              <Check className="h-3 w-3" />
              Got it
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
