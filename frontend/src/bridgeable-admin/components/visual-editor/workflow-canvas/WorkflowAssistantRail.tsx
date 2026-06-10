/**
 * WorkflowAssistantRail — Builder AI Assistant Phase 1b (the docked rail).
 *
 * The author describes a workflow in natural language → the editor calls the
 * proven 1a generation path → a validated candidate is held → this rail offers
 * Accept (candidate becomes the draft, rides the existing autosave pipeline) or
 * Reject (candidate discarded, draft untouched). From-scratch only;
 * edit/incremental is the filed follow-on.
 *
 * State ownership:
 *   - The EDITOR owns `candidate` / `generating` / `error` (it performs the
 *     async call; `candidate` also drives the canvas "Proposed" preview).
 *   - The RAIL owns only its `input` text + `collapsed` toggle. Because the
 *     shell renders this rail at a stable JSX slot position with a stable
 *     component type, prop updates reconcile (no remount) → the input text
 *     survives editor re-renders (see StudioAssistantSlotContext).
 *
 * This is the per-builder binding of the {grounding, emit, validate,
 * applyProposal} contract: `onGenerate` = emit (the editor calls 1a, which
 * grounds + validates server-side); Accept = applyProposal. Designed as the
 * extraction seam; NOT generalized (consumer #2 does that).
 *
 * Visual shape borrows the command-bar "Ask Bridgeable AI" panel: a prompt
 * input, a "generating" spinner, a graceful error message (never a crash — the
 * 1a service returns valid=false gracefully), and the result/actions zone.
 */
import { useCallback, useState } from "react"
import { AlertCircle, Bot, ChevronRight, Loader2, Sparkles } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert"
// Builder Craft 1a — shared chrome adoption: PanelHeader/PanelTitle/PanelBody
// (the rail's bespoke header/body matched the Panel defaults verbatim),
// Tooltip replaces title=, Icon lands the §7 stroke rule.
import { Icon } from "@/components/ui/icon"
import { PanelHeader, PanelTitle, PanelBody } from "@/components/ui/panel"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { summarizeCanvas } from "@/lib/visual-editor/workflows/canvas-validator"
import type { CanvasState } from "@/bridgeable-admin/services/workflow-templates-service"

export interface WorkflowAssistantRailProps {
  vertical: string
  workflowType: string
  /** True when the working draft has unsaved changes — accept warns it'll be replaced. */
  isDraftDirty: boolean
  /** Generation in flight (editor-owned — drives the rail spinner). */
  generating: boolean
  /** Friendly error message when generation failed/was unconfigured (never a crash). */
  error: string | null
  /** The validated candidate awaiting accept/reject (null = none). Drives the
      canvas Proposed preview AND the rail's accept/reject zone. */
  candidate: CanvasState | null
  /** Emit: the editor performs the 1a call with this NL spec. */
  onGenerate: (nl: string) => void
  /** applyProposal: candidate → draft (replaces; rides the autosave pipeline). */
  onAccept: () => void
  /** Discard the candidate; the draft is untouched. */
  onReject: () => void
}

export function WorkflowAssistantRail({
  vertical,
  workflowType,
  isDraftDirty,
  generating,
  error,
  candidate,
  onGenerate,
  onAccept,
  onReject,
}: WorkflowAssistantRailProps) {
  const [input, setInput] = useState("")
  const [collapsed, setCollapsed] = useState(false)

  const canGenerate = input.trim().length > 0 && !generating

  const handleGenerate = useCallback(() => {
    const nl = input.trim()
    if (nl.length > 0 && !generating) onGenerate(nl)
  }, [input, generating, onGenerate])

  // Collapsed → a narrow strip with an expand button (matches StudioRail's
  // collapse affordance). The slot is still occupied (the editor keeps pushing
  // the rail) — only the rail's own width/content collapses.
  if (collapsed) {
    return (
      <aside
        className="flex w-12 flex-col items-center border-l border-border-subtle bg-surface-sunken py-3"
        data-testid="workflow-assistant-rail"
        data-collapsed="true"
      >
        <Tooltip>
          <TooltipTrigger
            render={
              <button
                type="button"
                onClick={() => setCollapsed(false)}
                className="rounded-sm p-1.5 text-content-muted hover:bg-accent-subtle hover:text-content-strong"
                data-testid="workflow-assistant-rail-expand"
                aria-label="Expand AI assistant"
              >
                <Icon icon={Bot} size={18} />
              </button>
            }
          />
          <TooltipContent side="left">Expand AI assistant</TooltipContent>
        </Tooltip>
      </aside>
    )
  }

  return (
    <aside
      className="flex w-80 flex-col overflow-y-auto border-l border-border-subtle bg-surface-sunken"
      data-testid="workflow-assistant-rail"
      data-collapsed="false"
    >
      {/* Header — shared PanelHeader/PanelTitle (defaults match the prior
          bespoke classes verbatim: border-b border-border-subtle px-4 py-3 +
          body-sm/medium/content-strong title). */}
      <PanelHeader>
        <PanelTitle className="flex items-center gap-2">
          <Icon icon={Sparkles} size={14} className="text-accent" />
          Bridgeable AI
        </PanelTitle>
        <Tooltip>
          <TooltipTrigger
            render={
              <button
                type="button"
                onClick={() => setCollapsed(true)}
                className="rounded-sm p-1 text-content-muted hover:bg-accent-subtle hover:text-content-strong"
                data-testid="workflow-assistant-rail-collapse"
                aria-label="Collapse AI assistant"
              >
                <Icon icon={ChevronRight} size={16} />
              </button>
            }
          />
          <TooltipContent side="left">Collapse</TooltipContent>
        </Tooltip>
      </PanelHeader>

      {/* Body — three states: candidate (review) > generating > prompt input */}
      <PanelBody className="flex flex-col gap-3">
        {candidate ? (
          // ── Candidate review zone ──────────────────────────────
          <div
            className="flex flex-col gap-3"
            data-testid="workflow-assistant-candidate"
          >
            <div className="rounded-md border border-dashed border-accent bg-accent-subtle/20 p-3">
              <p className="flex items-center gap-1.5 text-body-sm font-medium text-content-strong">
                <Icon icon={Sparkles} size={13} className="text-accent" />
                Proposed workflow
              </p>
              <p className="mt-1 text-caption text-content-muted">
                {(() => {
                  const s = summarizeCanvas(candidate)
                  return `${s.nodes} node${s.nodes === 1 ? "" : "s"} · ${s.edges} edge${s.edges === 1 ? "" : "s"} · ${s.branchingNodes} branch${s.branchingNodes === 1 ? "" : "es"}`
                })()}
              </p>
              <p className="mt-2 text-caption text-content-muted">
                Previewing on the canvas. Accept to make it your working draft,
                or reject to keep your current canvas.
              </p>
              {isDraftDirty && (
                <p
                  className="mt-2 text-caption text-status-warning"
                  data-testid="workflow-assistant-dirty-warning"
                >
                  Accepting replaces your current unsaved draft. (You can still
                  Discard afterward to revert to the last saved version.)
                </p>
              )}
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={onAccept}
                data-testid="workflow-assistant-accept"
                className="flex-1"
              >
                Accept
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={onReject}
                data-testid="workflow-assistant-reject"
                className="flex-1"
              >
                Reject
              </Button>
            </div>
          </div>
        ) : generating ? (
          // ── Generating ─────────────────────────────────────────
          <div
            className="flex items-center gap-2 text-body-sm text-content-muted"
            data-testid="workflow-assistant-generating"
          >
            <Icon icon={Loader2} size={14} className="animate-spin" />
            Generating a workflow…
          </div>
        ) : (
          // ── Prompt input ───────────────────────────────────────
          <>
            <p className="text-caption text-content-muted">
              Describe a workflow in plain language. The assistant proposes a
              full canvas you can review before it touches your draft.
            </p>
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                // ⌘/Ctrl+Enter generates (Enter alone inserts a newline).
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                  e.preventDefault()
                  handleGenerate()
                }
              }}
              placeholder={`e.g. When a ${vertical === "manufacturing" ? "production order is committed, check inventory then schedule the pour" : "case is committed, generate the case file then branch on disposition"}…`}
              rows={5}
              data-testid="workflow-assistant-input"
            />
            {error && (
              <Alert variant="warning" data-testid="workflow-assistant-error">
                <Icon icon={AlertCircle} size={14} />
                <AlertTitle>Couldn't generate that</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <Button
              size="sm"
              onClick={handleGenerate}
              disabled={!canGenerate}
              data-testid="workflow-assistant-generate"
            >
              <Icon icon={Sparkles} size={14} className="mr-1" />
              Generate
            </Button>
            {!workflowType && (
              <p className="text-caption text-content-muted">
                Tip: pick or name a workflow type on the left for better-grounded
                results.
              </p>
            )}
          </>
        )}
      </PanelBody>
    </aside>
  )
}
