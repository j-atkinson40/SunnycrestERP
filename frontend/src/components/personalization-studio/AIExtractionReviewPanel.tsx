/**
 * AIExtractionReviewPanel — canonical Pattern 2 sub-cards container per
 * DESIGN_LANGUAGE §14.14.3 visual canon.
 *
 * **Canonical AI-extraction-review surface composition** per §14.14.3:
 * - Vision-AI extraction surface: `bg-surface-elevated` panel with
 *   extracted line items rendered as Pattern 2 sub-cards
 * - Per-line-item composition via canonical SuggestionLineItem chrome
 * - Confidence indicators canonical per §14.14.3 thresholds
 * - Action affordances canonical per canonical operator agency
 *
 * **Canonical batch operations** per §14.14.3:
 * - "Confirm all high-confidence" canonical button confirms all canonical
 *   line items with ≥0.85 canonical confidence in single canonical
 *   action; preserves canonical operator agency per §3.26.14.14.5
 *   (operator clicks button; not auto-applied)
 * - "Reject all" canonical button rejects all canonical line items in
 *   single canonical action
 *
 * **Canonical anti-pattern guards explicit at chrome substrate**:
 * - §3.26.11.12.16 Anti-pattern 1 (auto-commit on extraction confidence
 *   rejected): canonical batch "Confirm all high-confidence" requires
 *   canonical operator click; canonical confidence threshold does NOT
 *   trigger canonical auto-commit; canonical operator agency canonical
 *   at canonical batch + per-line-item action substrate
 */

import { useCallback, useMemo } from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type {
  LineItemDecisionRecord,
  UseAIExtractionReviewValue,
} from "./useAIExtractionReview"
import { SuggestionLineItem } from "./SuggestionLineItem"


export interface AIExtractionReviewPanelProps {
  /** Canonical AI-extraction-review hook value. */
  review: UseAIExtractionReviewValue
  /** Optional canonical operator-facing title override. */
  title?: string
}


export function AIExtractionReviewPanel({
  review,
  title,
}: AIExtractionReviewPanelProps) {
  const {
    activeSuggestionType,
    payload,
    isLoading,
    error,
    decisions,
    confirm,
    edit,
    reject,
    skip,
  } = review

  // Canonical decision lookup per canonical line_item_key.
  const decisionByKey = useMemo(() => {
    const map = new Map<string | null, LineItemDecisionRecord>()
    for (const record of decisions) {
      map.set(record.line_item_key, record)
    }
    return map
  }, [decisions])

  // Canonical batch "Confirm all high-confidence" — canonical operator
  // agency canonical at canonical batch substrate per §3.26.11.12.16
  // Anti-pattern 1.
  const handleConfirmAllHighConfidence = useCallback(() => {
    if (!payload) return
    for (const lineItem of payload.line_items) {
      if (
        lineItem.confidence_tier === "high" &&
        decisionByKey.get(lineItem.line_item_key) === undefined
      ) {
        confirm(lineItem)
      }
    }
  }, [payload, decisionByKey, confirm])

  // Canonical batch "Reject all" — canonical operator agency canonical.
  const handleRejectAll = useCallback(() => {
    if (!payload) return
    for (const lineItem of payload.line_items) {
      if (decisionByKey.get(lineItem.line_item_key) === undefined) {
        reject(lineItem)
      }
    }
  }, [payload, decisionByKey, reject])

  // Canonical empty-state chrome — no canonical suggestion requested.
  if (!isLoading && !payload && !error) {
    return null
  }

  const highConfidenceCount = payload
    ? payload.line_items.filter((li) => li.confidence_tier === "high").length
    : 0

  return (
    <div
      data-slot="ai-extraction-review-panel"
      data-active-suggestion-type={activeSuggestionType ?? "none"}
      className={cn(
        // Canonical Pattern 2 panel chrome per §14.14.3.
        "rounded-md border border-border-subtle bg-surface-elevated p-4 shadow-level-1",
        "flex flex-col gap-3",
      )}
    >
      {/* Canonical header */}
      <div className="flex items-center justify-between">
        <div
          data-slot="ai-extraction-review-title"
          className="text-caption font-medium uppercase tracking-wider text-content-muted"
        >
          {title ??
            (activeSuggestionType === "suggest_layout"
              ? "Layout suggestions"
              : activeSuggestionType === "suggest_text_style"
                ? "Text style suggestions"
                : activeSuggestionType === "extract_decedent_info"
                  ? "Decedent info — extracted from source materials"
                  : "AI extraction review")}
        </div>
        {payload && payload.line_items.length > 0 && (
          <div
            data-slot="ai-extraction-review-count"
            className="text-caption font-plex-mono text-content-muted"
          >
            {payload.line_items.length} line item
            {payload.line_items.length === 1 ? "" : "s"}
          </div>
        )}
      </div>

      {/* Canonical loading state */}
      {isLoading && (
        <div
          data-slot="ai-extraction-review-loading"
          className="flex items-center gap-2 text-body-sm text-content-muted"
        >
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-accent" />
          Working on canonical suggestions…
        </div>
      )}

      {/* Canonical error state */}
      {error && (
        <div
          data-slot="ai-extraction-review-error"
          className="rounded-sm bg-status-error-muted px-3 py-2 text-body-sm text-status-error"
        >
          {error}
        </div>
      )}

      {/* Canonical Pattern 2 sub-cards — per-line-item canonical
          SuggestionLineItem chrome per §14.14.3. */}
      {payload && payload.line_items.length > 0 && (
        <>
          {/* Canonical batch operations — canonical operator agency
              canonical per §3.26.11.12.16 Anti-pattern 1. */}
          {highConfidenceCount > 0 && (
            <div
              data-slot="ai-extraction-review-batch-actions"
              className="flex items-center gap-2 border-b border-border-subtle pb-2"
            >
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={handleConfirmAllHighConfidence}
                data-slot="batch-confirm-all-high-confidence"
              >
                Confirm all high-confidence ({highConfidenceCount})
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={handleRejectAll}
                data-slot="batch-reject-all"
              >
                Reject all
              </Button>
            </div>
          )}
          <div
            data-slot="ai-extraction-review-line-items"
            className="flex flex-col gap-2"
          >
            {payload.line_items.map((lineItem, idx) => (
              <SuggestionLineItem
                key={`${lineItem.line_item_key ?? "unkeyed"}-${idx}`}
                lineItem={lineItem}
                decision={
                  decisionByKey.get(lineItem.line_item_key)?.decision
                }
                onConfirm={confirm}
                onEdit={edit}
                onReject={reject}
                onSkip={skip}
              />
            ))}
          </div>
        </>
      )}

      {/* Canonical empty-payload state */}
      {payload && payload.line_items.length === 0 && (
        <div
          data-slot="ai-extraction-review-empty"
          className="text-body-sm italic text-content-subtle"
        >
          No canonical suggestions returned. Provide more context or try a
          different source material.
        </div>
      )}
    </div>
  )
}
