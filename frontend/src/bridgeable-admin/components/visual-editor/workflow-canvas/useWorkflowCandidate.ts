/**
 * useWorkflowCandidate — Builder AI Assistant Phase 1b candidate slot.
 *
 * The cohesive "candidate-slot state + transitions" unit, extracted so the
 * generate → candidate → accept/reject logic is jsdom-testable without the
 * polished editor UI (de-risk order item 1).
 *
 * The candidate is held NEXT TO the editor's working draft — never written
 * into it directly (non-destructive). Transitions:
 *   - generateWorkflow(nl): call the proven 1a path → a VALID candidate fills
 *     the slot, or a friendly error is surfaced (never a throw — the 1a service
 *     returns a structured verdict; a transport error is caught too).
 *   - acceptCandidate(): hand the candidate to the editor's `onAccept`
 *     (candidate → draft, replaces; the existing autosave/validate pipeline
 *     takes over) and CLEAR the slot.
 *   - rejectCandidate(): CLEAR the slot; `onAccept` is NOT called, so the
 *     draft is untouched.
 *
 * `generate` is injected (defaults to the platform-realm service) so tests can
 * drive valid / invalid / errored / rejected responses.
 */
import { useCallback, useState } from "react"

import {
  workflowAuthoringService,
  type GenerateWorkflowResponse,
} from "@/bridgeable-admin/services/workflow-authoring-service"
import type { CanvasState } from "@/bridgeable-admin/services/workflow-templates-service"

const ERR_UNAVAILABLE =
  "The assistant isn't available right now — please try again in a moment."
const ERR_REPHRASE =
  "Couldn't turn that into a valid workflow — try rephrasing or adding a bit more detail."
const ERR_TRANSPORT =
  "Couldn't reach the workflow assistant — check your connection and try again."

/**
 * Pure interpretation of a generation verdict → the next slot state. Exported
 * for direct unit testing of the graceful-handling branches.
 *   - valid + canvas_state → { candidate }
 *   - model didn't run (ai_status not success/fallback) → unavailable error
 *   - model ran but invalid structure → rephrase error
 */
export function interpretGenerateResult(res: GenerateWorkflowResponse): {
  candidate: CanvasState | null
  error: string | null
} {
  if (res.valid && res.canvas_state) {
    return { candidate: res.canvas_state, error: null }
  }
  if (res.ai_status !== "success" && res.ai_status !== "fallback_used") {
    return { candidate: null, error: ERR_UNAVAILABLE }
  }
  return { candidate: null, error: ERR_REPHRASE }
}

export interface UseWorkflowCandidateOptions {
  vertical: string
  workflowType: string
  /** Apply the accepted candidate to the editor's draft (replaces it). */
  onAccept: (candidate: CanvasState) => void
  /** Injected for tests; defaults to the platform-realm 1a service. */
  generate?: (req: {
    nl: string
    vertical: string
    workflow_type: string
  }) => Promise<GenerateWorkflowResponse>
}

export interface UseWorkflowCandidate {
  candidate: CanvasState | null
  generating: boolean
  error: string | null
  generateWorkflow: (nl: string) => Promise<void>
  acceptCandidate: () => void
  rejectCandidate: () => void
}

export function useWorkflowCandidate(
  opts: UseWorkflowCandidateOptions,
): UseWorkflowCandidate {
  const { vertical, workflowType, onAccept } = opts
  const generate = opts.generate ?? workflowAuthoringService.generate

  const [candidate, setCandidate] = useState<CanvasState | null>(null)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const generateWorkflow = useCallback(
    async (nl: string) => {
      setGenerating(true)
      setError(null)
      setCandidate(null)
      try {
        const res = await generate({ nl, vertical, workflow_type: workflowType })
        const next = interpretGenerateResult(res)
        setCandidate(next.candidate)
        setError(next.error)
      } catch {
        setError(ERR_TRANSPORT)
      } finally {
        setGenerating(false)
      }
    },
    [generate, vertical, workflowType],
  )

  const acceptCandidate = useCallback(() => {
    setCandidate((cur) => {
      if (cur) {
        onAccept(cur)
        setError(null)
      }
      return null
    })
  }, [onAccept])

  const rejectCandidate = useCallback(() => {
    setCandidate(null)
    setError(null)
  }, [])

  return {
    candidate,
    generating,
    error,
    generateWorkflow,
    acceptCandidate,
    rejectCandidate,
  }
}
