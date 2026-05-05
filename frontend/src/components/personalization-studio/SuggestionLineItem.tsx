/**
 * SuggestionLineItem — canonical confidence-scored line item chrome
 * per DESIGN_LANGUAGE §14.14.3 visual canon.
 *
 * **Canonical Pattern 2 sub-card composition** per §14.14.3:
 * - Line item body: extracted content rendering
 * - Confidence section: confidence bar + numeric score
 * - Action affordances: Confirm + Edit + Reject + Skip buttons
 * - Default-selected state: ≥0.70 confidence canonical default-selected
 *   for confirm; <0.70 confidence canonical requires explicit operator
 *   confirmation per §3.26.11.12.16 Anti-pattern 1
 *
 * **Canonical confidence indicator chrome** per §14.14.3:
 * - High (≥0.85): `bg-status-success` chrome
 * - Medium (0.70-0.85): `bg-status-warning` chrome
 * - Low (<0.70): `bg-status-error` chrome
 * - Numeric score: `text-caption font-plex-mono text-content-muted`
 *
 * **Canonical anti-pattern guards explicit at chrome substrate**:
 * - §3.26.11.12.16 Anti-pattern 1 (auto-commit on extraction confidence
 *   rejected): canonical Confirm action canonical at chrome substrate
 *   requires canonical operator click; canonical confidence threshold
 *   does NOT trigger canonical auto-commit
 * - §3.26.11.12.16 Anti-pattern 11 (UI-coupled Generation Focus design
 *   rejected): canonical line item shape canonical at canonical service
 *   substrate; chrome substrate consumes canonical line items via
 *   canonical Pattern 2 sub-cards
 */

import { Check, Edit3, SkipForward, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type {
  ConfidenceTier,
  LineItemDecision,
  SuggestionLineItem as SuggestionLineItemType,
} from "@/types/personalization-studio"


export interface SuggestionLineItemProps {
  lineItem: SuggestionLineItemType
  /** Canonical operator-decision record (when canonical decision recorded). */
  decision?: LineItemDecision
  onConfirm: (lineItem: SuggestionLineItemType) => void
  onEdit: (lineItem: SuggestionLineItemType) => void
  onReject: (lineItem: SuggestionLineItemType) => void
  onSkip: (lineItem: SuggestionLineItemType) => void
}


export function SuggestionLineItem({
  lineItem,
  decision,
  onConfirm,
  onEdit,
  onReject,
  onSkip,
}: SuggestionLineItemProps) {
  const tier = lineItem.confidence_tier
  const formattedValue = formatLineItemValue(lineItem.value)
  const formattedConfidence = lineItem.confidence.toFixed(2)
  const isDecided = decision !== undefined

  return (
    <div
      data-slot="ai-extraction-suggestion-line-item"
      data-line-item-key={lineItem.line_item_key ?? ""}
      data-confidence-tier={tier}
      data-decision={decision ?? "pending"}
      className={cn(
        // Canonical Pattern 2 sub-card chrome per §11 Pattern 2.
        "rounded-md border bg-surface-elevated p-3 shadow-level-1",
        "flex flex-col gap-2",
        // Canonical decision-state visual treatment per §14.14.3.
        decision === "confirm" && "border-status-success",
        decision === "reject" && "border-status-error opacity-60",
        decision === "skip" && "border-border-base opacity-70",
        decision === "edit" && "border-accent",
        !decision && "border-border-subtle",
      )}
    >
      {/* Canonical line item header — line_item_key + confidence */}
      <div className="flex items-center justify-between gap-3">
        <div
          data-slot="ai-extraction-line-item-key"
          className="text-caption font-medium uppercase tracking-wider text-content-muted"
        >
          {lineItem.line_item_key ?? "(canonical key missing)"}
        </div>
        <ConfidenceIndicator
          confidence={lineItem.confidence}
          tier={tier}
          formattedConfidence={formattedConfidence}
        />
      </div>

      {/* Canonical line item value */}
      <div
        data-slot="ai-extraction-line-item-value"
        className="text-body font-plex-sans text-content-strong"
      >
        {formattedValue}
      </div>

      {/* Canonical rationale (when canonical present) */}
      {lineItem.rationale && (
        <div
          data-slot="ai-extraction-line-item-rationale"
          className="text-caption text-content-muted"
        >
          {lineItem.rationale}
        </div>
      )}

      {/* Canonical action affordances — Confirm + Edit + Reject + Skip
          per §14.14.3 visual canon */}
      <div
        data-slot="ai-extraction-line-item-actions"
        className="flex items-center gap-2 pt-1"
      >
        <Button
          type="button"
          size="sm"
          variant={decision === "confirm" ? "default" : "outline"}
          onClick={() => onConfirm(lineItem)}
          disabled={isDecided && decision !== "confirm"}
          data-slot="suggestion-confirm"
        >
          <Check className="mr-1 h-3 w-3" />
          Confirm
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => onEdit(lineItem)}
          disabled={isDecided && decision !== "edit"}
          data-slot="suggestion-edit"
        >
          <Edit3 className="mr-1 h-3 w-3" />
          Edit
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => onReject(lineItem)}
          disabled={isDecided && decision !== "reject"}
          data-slot="suggestion-reject"
        >
          <X className="mr-1 h-3 w-3" />
          Reject
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => onSkip(lineItem)}
          disabled={isDecided && decision !== "skip"}
          data-slot="suggestion-skip"
        >
          <SkipForward className="mr-1 h-3 w-3" />
          Skip
        </Button>
      </div>
    </div>
  )
}


function ConfidenceIndicator({
  confidence,
  tier,
  formattedConfidence,
}: {
  confidence: number
  tier: ConfidenceTier
  formattedConfidence: string
}) {
  const percent = Math.round(confidence * 100)
  return (
    <div
      data-slot="ai-extraction-confidence-indicator"
      data-confidence-tier={tier}
      className="flex items-center gap-2"
    >
      {/* Canonical confidence bar per §14.14.3 visual canon. */}
      <div
        className="h-1.5 w-16 overflow-hidden rounded-full bg-surface-sunken"
        aria-label={`Confidence ${formattedConfidence}`}
      >
        <div
          className={cn(
            "h-full transition-all",
            tier === "high" && "bg-status-success",
            tier === "medium" && "bg-status-warning",
            tier === "low" && "bg-status-error",
          )}
          style={{ width: `${percent}%` }}
        />
      </div>
      {/* Canonical numeric score per §14.14.3 visual canon. */}
      <span
        className={cn(
          "text-caption font-plex-mono",
          tier === "high" && "text-status-success",
          tier === "medium" && "text-status-warning",
          tier === "low" && "text-status-error",
        )}
      >
        {formattedConfidence}
      </span>
    </div>
  )
}


/** Canonical line item value formatter per §14.14.3 visual canon.
 *
 *  Canonical canvas position objects render as canonical x/y readout;
 *  canonical text style objects render as canonical font + size + color
 *  readout; canonical strings render verbatim; canonical null renders
 *  as canonical placeholder. */
function formatLineItemValue(value: unknown): string {
  if (value === null || value === undefined) return "(canonically empty)"
  if (typeof value === "string") return value
  if (typeof value === "number") return value.toString()
  if (typeof value === "object") {
    const v = value as Record<string, unknown>
    if (typeof v.x === "number" && typeof v.y === "number") {
      // Canonical canvas position object.
      const parts = [`x ${v.x}`, `y ${v.y}`]
      if (typeof v.width === "number") parts.push(`w ${v.width}`)
      if (typeof v.height === "number") parts.push(`h ${v.height}`)
      return parts.join(" · ")
    }
    if (typeof v.font === "string" || typeof v.size === "number" || typeof v.color === "string") {
      // Canonical text style object.
      const parts: string[] = []
      if (v.font) parts.push(`${v.font}`)
      if (v.size !== undefined) parts.push(`${v.size}px`)
      if (v.color) parts.push(`${v.color}`)
      return parts.join(" · ") || JSON.stringify(value)
    }
  }
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}
