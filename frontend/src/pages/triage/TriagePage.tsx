/**
 * `/triage/:queueId` — the keyboard-driven triage workspace (page surface).
 *
 * Thin wrapper: mounts the shared `TriageWorkspace` (the five Phase-5 surfaces)
 * inside `TriageSessionProvider`, in the page `variant`. The same workspace is
 * mounted by `TriageQueueCore` in the `focus` variant (the Decide-as-Focus
 * surface) — see `components/triage/TriageWorkspace.tsx`.
 */

import { useParams } from "react-router-dom";
import { TriageSessionProvider } from "@/contexts/triage-session-context";
import { TriageWorkspace } from "@/components/triage/TriageWorkspace";

export default function TriagePage() {
  const { queueId = "" } = useParams<{ queueId: string }>();
  if (!queueId) {
    return (
      <div className="p-6">
        <p>Missing queue id.</p>
      </div>
    );
  }
  return (
    <TriageSessionProvider queueId={queueId}>
      <div className="mx-auto max-w-6xl p-6">
        <TriageWorkspace variant="page" />
      </div>
    </TriageSessionProvider>
  );
}
