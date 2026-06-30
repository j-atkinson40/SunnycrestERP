/**
 * AuthoringAssistantBar — the omnipresent, page-aware authoring entry point
 * (Shell-1 mount + Shell-2 workflow-draft routing).
 *
 * Shell-1 mounted it above the top-level <Routes> (omnipresent, survives
 * navigation) and gave it route-derived page context. Shell-2 wires the
 * workflow-draft hand-off: on a workflow-armed surface, typing a request routes
 * it to the existing brain + WorkflowAssistantRail (navigate-to-rail).
 *
 *   - MoC vertical page → navigate into that vertical's Studio workflow editor,
 *     carrying the NL in route state; the rail auto-runs generation there.
 *   - Already in the Studio workflow editor → re-navigate in-place (new history
 *     key) so the rail receives the new request without leaving the editor.
 *   - Everywhere else (operational, MoC home, NON-workflow Studio editors) → the
 *     existing generic command overlay (Shell-1 behavior). Scope guard: only the
 *     workflow brain/rail ship, so only workflow drafting routes; focus/widget/
 *     document editors stay generic until their brains exist.
 *
 * Non-intrusive: pointer-events-none wrapper (only the pill/input is clickable);
 * z-40 below the command dialog. The actual review surface is the rail — this
 * bar delivers the request TO it.
 */
import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { Sparkles } from "lucide-react"

import { useAdminPageContext } from "../hooks/useAdminPageContext"
import { useAuthoringRequest } from "../contexts/AuthoringRequestContext"
import { useCommandBar } from "./AdminCommandBar"
import { adminPath } from "../lib/admin-routes"
import { studioPath } from "../lib/studio-routes"

export function AuthoringAssistantBar() {
  const ctx = useAdminPageContext()
  const { setOpen } = useCommandBar()
  const { submit } = useAuthoringRequest()
  const navigate = useNavigate()
  const [expanded, setExpanded] = useState(false)
  const [nl, setNl] = useState("")

  // Login / unauthenticated → no bar.
  if (ctx.surface === "none") return null

  // Workflows-only routing (Shell-2 scope guard).
  const inWorkflowEditor =
    ctx.surface === "studio" && ctx.editorKind === "workflows"
  const canDraftWorkflow =
    (ctx.surface === "moc" && !!ctx.vertical) || inWorkflowEditor

  function submitDraft() {
    const text = nl.trim()
    if (!text) return
    // The request rides the shared context (survives navigation, no same-path
    // useLocation re-fire dependency). From MoC, also route INTO the editor; in
    // the editor already, just set the context — the rail re-reads + delivers.
    submit(text)
    if (!inWorkflowEditor) {
      navigate(
        adminPath(studioPath({ vertical: ctx.vertical, editor: "workflows" })),
      )
    }
    setNl("")
    setExpanded(false)
  }

  const verb = canDraftWorkflow ? "Author" : "Assistant"

  return (
    <div
      className="pointer-events-none fixed inset-x-0 bottom-5 z-40 flex justify-center"
      data-testid="authoring-assistant-bar"
    >
      {expanded && canDraftWorkflow ? (
        <form
          className="pointer-events-auto flex items-center gap-2 rounded-full border border-slate-700 bg-slate-900/95 px-3 py-2 shadow-lg backdrop-blur"
          data-testid="authoring-assistant-input-form"
          onSubmit={(e) => {
            e.preventDefault()
            submitDraft()
          }}
        >
          <Sparkles className="h-4 w-4 flex-none text-amber-300" aria-hidden />
          <input
            autoFocus
            value={nl}
            onChange={(e) => setNl(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                setExpanded(false)
                setNl("")
              }
            }}
            placeholder="Describe a workflow to draft…"
            aria-label="Describe a workflow to draft"
            data-testid="authoring-assistant-input"
            className="w-80 bg-transparent text-sm text-slate-100 placeholder:text-slate-400 focus:outline-none"
          />
          <button
            type="submit"
            disabled={!nl.trim()}
            className="flex-none rounded-full bg-amber-300 px-3 py-1 text-xs font-medium text-slate-900 transition-opacity disabled:opacity-40"
          >
            Draft →
          </button>
        </form>
      ) : (
        <button
          type="button"
          onClick={() => (canDraftWorkflow ? setExpanded(true) : setOpen(true))}
          aria-label={
            canDraftWorkflow
              ? `Draft a workflow — ${ctx.label}`
              : `Open assistant — ${ctx.label || "command bar"}`
          }
          className="pointer-events-auto flex items-center gap-2.5 rounded-full border border-slate-700 bg-slate-900/95 px-4 py-2 text-sm text-slate-100 shadow-lg backdrop-blur transition-colors hover:border-slate-500 hover:bg-slate-900"
        >
          <Sparkles className="h-4 w-4 text-amber-300" aria-hidden />
          <span className="font-medium">{verb}</span>
          {ctx.label ? (
            <>
              <span className="h-3.5 w-px bg-slate-600" aria-hidden />
              <span className="text-slate-300" data-testid="authoring-assistant-context">
                {ctx.label}
              </span>
            </>
          ) : null}
          <kbd className="ml-1 rounded border border-slate-600 bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] text-slate-300">
            {canDraftWorkflow ? "↵" : "⌘K"}
          </kbd>
        </button>
      )}
    </div>
  )
}
