/**
 * `/triage/:queueId` — the keyboard-driven triage workspace.
 *
 * Composes the five Phase-5 surfaces: item display (center),
 * action palette (bottom), flow controls (below actions), and the
 * context panel rail (right). Session state + action dispatch live
 * in `TriageSessionProvider`.
 */

import { Link, useNavigate, useParams } from "react-router-dom";
import { CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { SkeletonCard } from "@/components/ui/skeleton";
import { toast } from "sonner";
import {
  TriageSessionProvider,
  useTriageSession,
} from "@/contexts/triage-session-context";
import { TriageItemDisplay } from "@/components/triage/TriageItemDisplay";
import { TriageActionPalette } from "@/components/triage/TriageActionPalette";
import { TriageContextPanel } from "@/components/triage/TriageContextPanel";
import { TriageFlowControls } from "@/components/triage/TriageFlowControls";
import { OnboardingTouch } from "@/components/onboarding/OnboardingTouch";
import type { TriageActionConfig } from "@/types/triage";

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
      <TriageInner />
    </TriageSessionProvider>
  );
}

function TriageInner() {
  const navigate = useNavigate();
  const { status, error, config, session, item, act, snooze } =
    useTriageSession();

  if (status === "loading") {
    return (
      <div
        className="mx-auto max-w-6xl space-y-4 p-6"
        data-testid="triage-loading"
      >
        <SkeletonCard lines={4} />
        <div className="flex gap-2">
          <SkeletonCard lines={0} showHeader className="h-10 w-28" />
          <SkeletonCard lines={0} showHeader className="h-10 w-28" />
          <SkeletonCard lines={0} showHeader className="h-10 w-28" />
        </div>
      </div>
    );
  }
  if (status === "error") {
    return (
      <div className="space-y-2 p-6">
        <p className="text-destructive">Triage error: {error ?? "unknown"}</p>
        <Button variant="outline" onClick={() => navigate("/triage")}>
          Back to queues
        </Button>
      </div>
    );
  }
  if (!config) {
    return (
      <div className="p-6">
        <p>Queue config unavailable.</p>
      </div>
    );
  }

  if (status === "empty" || !item) {
    const processed = session?.items_processed_count ?? 0;
    return (
      <div className="mx-auto max-w-2xl space-y-4 p-6">
        <Link
          to="/triage"
          className="text-xs text-muted-foreground hover:underline"
        >
          ← All queues
        </Link>
        <EmptyState
          icon={CheckCircle2}
          title={
            processed > 0
              ? `You're all caught up on ${config.queue_name}`
              : `${config.queue_name} is already clear`
          }
          description={
            session && processed > 0 ? (
              <span>
                Processed {processed} this session ·{" "}
                {session.items_approved_count} approved ·{" "}
                {session.items_rejected_count} rejected ·{" "}
                {session.items_snoozed_count} deferred.
              </span>
            ) : (
              "Nothing pending right now. Take a break or try another queue."
            )
          }
          tone="positive"
          action={
            <Button render={<Link to="/triage" />}>Back to queues</Button>
          }
          data-testid="triage-caught-up"
        />
      </div>
    );
  }

  const handleAct = async (action: TriageActionConfig, reason?: string) => {
    try {
      await act({
        action_id: action.action_id,
        reason: reason ?? null,
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Action failed");
    }
  };

  const handleSnooze = async (offset_hours: number, label: string) => {
    try {
      await snooze({ offset_hours, reason: label });
      toast.success(`Deferred · ${label}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Snooze failed");
    }
  };

  const working = status === "working";

  return (
    <div className="relative mx-auto flex max-w-6xl flex-col gap-6 p-6 lg:flex-row">
      <OnboardingTouch
        touchKey="triage_intro"
        title="Process items one at a time."
        body="Press Enter to accept, or use the keyboard shortcuts shown on each action button. Defer to come back later."
        position="bottom"
        className="right-6 top-2 w-72"
      />
      <section
        className="min-w-0 flex-1 space-y-4"
        role="region"
        aria-label="Current triage item"
        aria-live="polite"
        aria-busy={working}
      >
        <header className="flex items-center justify-between">
          <div>
            <Link to="/triage" className="text-xs text-muted-foreground hover:underline">
              ← All queues
            </Link>
            <h1 className="text-xl font-semibold">{config.queue_name}</h1>
            {config.description ? (
              <p className="text-sm text-muted-foreground">{config.description}</p>
            ) : null}
          </div>
          {session ? (
            <div className="text-right text-xs text-muted-foreground">
              <div>Processed · {session.items_processed_count}</div>
              <div>
                {session.items_approved_count} approved ·{" "}
                {session.items_rejected_count} rejected ·{" "}
                {session.items_snoozed_count} deferred
              </div>
            </div>
          ) : null}
        </header>

        {/* Phase 7 — `key` forces remount on item change, triggering
            the motion-safe fade-in animation on the wrapper below. */}
        <div
          key={item.entity_id}
          className="motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-1 motion-safe:duration-200"
        >
          <TriageItemDisplay item={item} display={config.item_display} />
        </div>

        <TriageFlowControls
          flow={config.flow_controls}
          onSnooze={handleSnooze}
          disabled={working}
        />

        <TriageActionPalette
          actions={config.action_palette}
          onAct={handleAct}
          disabled={working}
        />
      </section>

      <TriageContextPanel panels={config.context_panels} item={item} />
    </div>
  );
}
