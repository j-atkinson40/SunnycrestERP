/**
 * TriageQueueCore — the Decide-primitive-as-Focus (3a.1-B).
 *
 * Renders a REAL triage queue inside the Focus shell by mounting the existing
 * Phase 5 triage workspace (TriageSessionProvider + the shared
 * `TriageWorkspace`), scoped to the queue named by `config.queueId`. Not a
 * reimplementation — the decision logic + the workflow_review approve wiring
 * (approve → commitWorkflowReviewDecision → the run advances) live inside the
 * mounted Phase 5 components and come along for free.
 *
 * Binding is DATA: a triageQueue Focus declares its queue via
 * `FocusConfig.queueId`. `decision-triage` binds to `workflow_review_triage`
 * (where the Legacy Order workflow stages its proof). The next triage Focus
 * (cash receipts, month-end) sets its own queueId — same core renders it.
 *
 * A triageQueue Focus with no queueId renders a deliberate "not bound" state
 * (§18 graceful empty) rather than the old hardcoded placeholder rows.
 */

import { TriageSessionProvider } from "@/contexts/triage-session-context"
import { TriageWorkspace } from "@/components/triage/TriageWorkspace"
import { CoreHeader, EscToDismissHint, type CoreProps } from "./_shared"


export function TriageQueueCore({ config }: CoreProps) {
  if (!config.queueId) {
    return (
      <div className="flex h-full flex-col gap-4">
        <CoreHeader modeLabel="triageQueue" title={config.displayName} />
        <div className="flex flex-1 items-center justify-center rounded-md border border-border-subtle bg-surface-sunken/40 p-8">
          <p className="max-w-sm text-center text-body-sm text-content-muted">
            This triage Focus isn&rsquo;t bound to a queue. Register it with a{" "}
            <code className="font-mono text-micro">queueId</code> to render a
            live decision queue.
          </p>
        </div>
        <EscToDismissHint />
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col gap-4">
      <CoreHeader modeLabel="triageQueue" title={config.displayName} />
      <div className="min-h-0 flex-1 overflow-auto">
        <TriageSessionProvider queueId={config.queueId}>
          <TriageWorkspace variant="focus" />
        </TriageSessionProvider>
      </div>
      <EscToDismissHint />
    </div>
  )
}
