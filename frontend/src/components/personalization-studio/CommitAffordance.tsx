/**
 * CommitAffordance — canonical canvas commit affordance per
 * DESIGN_LANGUAGE §14.14.5 + Phase 1B canvas implementation.
 *
 * **Per-authoring-context canonical button labels** per §14.14.5:
 *   - `funeral_home_with_family`: "Add to case" (commits to FH case
 *     via `fh_case_field_update` event)
 *   - `manufacturer_without_family`: "Add to order" (commits to order
 *     line item via `order_line_item_personalization_spec_update` event)
 *   - `manufacturer_from_fh_share`: "Mark reviewed" (read-only consume;
 *     no commit affordance per canonical Document read-only state —
 *     button label canonically signals review-complete intent rather
 *     than commit-output intent)
 *
 * **Canonical anti-pattern guards explicit**:
 * - §3.26.11.12.16 Anti-pattern 1 (auto-commit on extraction confidence
 *   rejected): commit happens canonical at canonical operator-decision
 *   button click; button is explicit operator-action affordance per
 *   canonical operator agency
 * - §3.26.14.14.5 operator agency discipline preserved
 *
 * **Canonical commit flow**:
 * 1. Canvas state mutations accumulate at canonical canvas-state-context
 *    ephemeral state via canonical applyDragEnd + applyElementUpdate
 *    helpers
 * 2. Canonical Save Draft button → POST /commit-canvas-state →
 *    canonical DocumentVersion canonical at canonical Document
 *    substrate (canvas state preserved; lifecycle stays `active`)
 * 3. Canonical Commit button → POST /commit-canvas-state followed by
 *    POST /commit → canonical DocumentVersion + canonical lifecycle
 *    transition `active` → `committed` per §3.26.11.12.4 closure
 *    semantics
 */

import { useCallback, useState } from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  commitCanvasState,
  commitInstance,
} from "@/services/personalization-studio-service"
import type {
  AuthoringContext,
  GenerationFocusInstance,
} from "@/types/personalization-studio"

import { usePersonalizationCanvasState } from "./canvas-state-context"

interface CommitAffordanceProps {
  instance: GenerationFocusInstance
  /** Called after canonical commit completes successfully — parent
   *  refetches instance metadata + closes Focus chrome per
   *  §14.14.1 commit-affordance discipline. */
  onCommitted?: (next: GenerationFocusInstance) => void
  /** Called after canonical save-draft completes — parent updates
   *  canonical instance metadata for "Draft saved {relative time}"
   *  chrome per §14.14.5. */
  onSavedDraft?: (versionNumber: number) => void
}

export function CommitAffordance({
  instance,
  onCommitted,
  onSavedDraft,
}: CommitAffordanceProps) {
  const { canvasState, isCommitting, setIsCommitting } =
    usePersonalizationCanvasState()
  const [error, setError] = useState<string | null>(null)

  const isReadOnly = instance.authoring_context === "manufacturer_from_fh_share"
  const isTerminal =
    instance.lifecycle_state === "committed" ||
    instance.lifecycle_state === "abandoned"

  const handleSaveDraft = useCallback(async () => {
    setError(null)
    setIsCommitting(true)
    try {
      const res = await commitCanvasState(instance.id, canvasState)
      onSavedDraft?.(res.version_number)
    } catch (err) {
      setError(extractErrorMessage(err) || "Failed to save draft")
    } finally {
      setIsCommitting(false)
    }
  }, [canvasState, instance.id, onSavedDraft, setIsCommitting])

  const handleCommit = useCallback(async () => {
    setError(null)
    setIsCommitting(true)
    try {
      // Canonical canvas commit first (canonical Document substrate
      // versioning), then canonical instance commit (canonical
      // lifecycle transition).
      await commitCanvasState(instance.id, canvasState)
      const next = await commitInstance(instance.id)
      onCommitted?.(next)
    } catch (err) {
      setError(extractErrorMessage(err) || "Failed to commit")
    } finally {
      setIsCommitting(false)
    }
  }, [canvasState, instance.id, onCommitted, setIsCommitting])

  // Canonical read-only consume chrome per `manufacturer_from_fh_share`.
  // Per §14.14.5: "Mark reviewed" canonical button label.
  if (isReadOnly) {
    return (
      <div
        data-slot="commit-affordance"
        data-mode="read-only-consume"
        className="flex items-center justify-end gap-3 border-t border-border-subtle px-4 py-3"
      >
        <Button
          type="button"
          variant="default"
          disabled={isCommitting || isTerminal}
          onClick={handleCommit}
        >
          Mark reviewed
        </Button>
      </div>
    )
  }

  // Canonical per-authoring-context button labels per §14.14.5.
  const commitLabel = commitButtonLabel(instance.authoring_context)

  return (
    <div
      data-slot="commit-affordance"
      data-mode="author"
      className={cn(
        "flex items-center justify-end gap-3",
        "border-t border-border-subtle px-4 py-3",
      )}
    >
      {error && (
        <div
          data-slot="commit-affordance-error"
          className="mr-auto text-caption text-status-error"
        >
          {error}
        </div>
      )}
      <Button
        type="button"
        variant="outline"
        disabled={isCommitting || isTerminal}
        onClick={handleSaveDraft}
      >
        {isCommitting ? "Saving…" : "Save draft"}
      </Button>
      <Button
        type="button"
        variant="default"
        disabled={isCommitting || isTerminal}
        onClick={handleCommit}
      >
        {commitLabel}
      </Button>
    </div>
  )
}

function commitButtonLabel(authoringContext: AuthoringContext): string {
  switch (authoringContext) {
    case "funeral_home_with_family":
      return "Add to case"
    case "manufacturer_without_family":
      return "Add to order"
    case "manufacturer_from_fh_share":
      return "Mark reviewed"
  }
}

function extractErrorMessage(err: unknown): string | null {
  if (typeof err === "object" && err !== null) {
    const e = err as { response?: { data?: { detail?: string } }; message?: string }
    return e.response?.data?.detail ?? e.message ?? null
  }
  return null
}
