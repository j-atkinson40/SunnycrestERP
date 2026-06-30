/**
 * AuthoringAssistantBar — the omnipresent, page-aware authoring entry point
 * (Authoring Assistant Shell-1).
 *
 * Mounted ABOVE the top-level <Routes> in BridgeableAdminApp (a sibling of the
 * swapping layout branches), so it is present on EVERY admin surface — MoC,
 * Studio, operational — and SURVIVES navigation between them (the thing the
 * AdminLayout-scoped AdminCommandBar cannot do). It reads its page context from
 * the route (useAdminPageContext) and shows it; clicking opens the existing
 * command-bar overlay. Shell-2 wires the actual draft→brain routing; this phase
 * establishes the omnipresent, context-aware shell.
 *
 * Non-intrusive by construction: the wrapper is `pointer-events-none` (only the
 * pill itself is clickable, so it never blocks the layout beneath), and z-40 sits
 * BELOW the command-bar dialog (z-50) + existing modals — no clobbering.
 *
 * Context-appropriate: on authoring surfaces (MoC/Studio with an editor open) it
 * reads "Author"; elsewhere "Assistant" — present everywhere, never pretending to
 * author where there's no target (Shell-2 gates the real routing on `canAuthor`).
 */
import { Sparkles } from "lucide-react"

import { useAdminPageContext } from "../hooks/useAdminPageContext"
import { useCommandBar } from "./AdminCommandBar"

export function AuthoringAssistantBar() {
  const ctx = useAdminPageContext()
  const { setOpen } = useCommandBar()

  // Login / unauthenticated → no bar.
  if (ctx.surface === "none") return null

  return (
    <div
      className="pointer-events-none fixed inset-x-0 bottom-5 z-40 flex justify-center"
      data-testid="authoring-assistant-bar"
    >
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={`Open assistant — ${ctx.label || "command bar"}`}
        className="pointer-events-auto flex items-center gap-2.5 rounded-full border border-slate-700 bg-slate-900/95 px-4 py-2 text-sm text-slate-100 shadow-lg backdrop-blur transition-colors hover:border-slate-500 hover:bg-slate-900"
      >
        <Sparkles className="h-4 w-4 text-amber-300" aria-hidden />
        <span className="font-medium">{ctx.canAuthor ? "Author" : "Assistant"}</span>
        {ctx.label ? (
          <>
            <span className="h-3.5 w-px bg-slate-600" aria-hidden />
            <span className="text-slate-300" data-testid="authoring-assistant-context">
              {ctx.label}
            </span>
          </>
        ) : null}
        <kbd className="ml-1 rounded border border-slate-600 bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] text-slate-300">
          ⌘K
        </kbd>
      </button>
    </div>
  )
}
