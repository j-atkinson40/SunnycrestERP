/**
 * TriageWorkspace — the Phase 5 triage workspace BODY, shared between the
 * standalone page (`/triage/:queueId`, `variant="page"`) and the Decide-as-Focus
 * core (`TriageQueueCore`, `variant="focus"`). Must be rendered inside a
 * `TriageSessionProvider` (consumes `useTriageSession`).
 *
 * Reuse, not reinvention (3a.1-B): the decision logic + the five Phase-5
 * surfaces (item display, flow controls, action palette, context panel) are
 * the SAME in both surfaces — including the workflow_review approve wiring,
 * which lives inside TriageItemDisplay → WorkflowReviewItemDisplay. Only the
 * outer chrome differs: the page variant carries "← All queues" navigation +
 * page max-widths; the focus variant drops them (the Focus shell frames it).
 */

import { Link, useNavigate } from "react-router-dom";
import { CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { SkeletonCard } from "@/components/ui/skeleton";
import { useTriageSession } from "@/contexts/triage-session-context";
import { TriageItemDisplay } from "@/components/triage/TriageItemDisplay";
import { TriageActionPalette } from "@/components/triage/TriageActionPalette";
import { TriageContextPanel } from "@/components/triage/TriageContextPanel";
import { TriageFlowControls } from "@/components/triage/TriageFlowControls";
import { OnboardingTouch } from "@/components/onboarding/OnboardingTouch";
import type { TriageActionConfig } from "@/types/triage";

export type TriageWorkspaceVariant = "page" | "focus";

export function TriageWorkspace({
  variant = "page",
}: {
  variant?: TriageWorkspaceVariant;
}) {
  const isPage = variant === "page";
  const navigate = useNavigate();
  const { status, error, config, session, item, act, snooze, advance } =
    useTriageSession();

  if (status === "loading") {
    return (
      <div className="space-y-4" data-testid="triage-loading">
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
      <div className="space-y-2" data-testid="triage-error">
        <p className="text-destructive">Triage error: {error ?? "unknown"}</p>
        {isPage ? (
          <Button variant="outline" onClick={() => navigate("/triage")}>
            Back to queues
          </Button>
        ) : null}
      </div>
    );
  }
  if (!config) {
    return <p className="text-content-muted">Queue config unavailable.</p>;
  }

  if (status === "empty" || !item) {
    const processed = session?.items_processed_count ?? 0;
    return (
      <div className="space-y-4" data-testid="triage-caught-up">
        {isPage ? (
          <Link
            to="/triage"
            className="text-xs text-muted-foreground hover:underline"
          >
            ← All queues
          </Link>
        ) : null}
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
              "Nothing pending right now."
            )
          }
          tone="positive"
          action={
            isPage ? (
              <Button render={<Link to="/triage" />}>Back to queues</Button>
            ) : undefined
          }
        />
      </div>
    );
  }

  const handleAct = async (action: TriageActionConfig, reason?: string) => {
    try {
      await act({ action_id: action.action_id, reason: reason ?? null });
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
    <div
      className={
        isPage
          ? "relative flex flex-col gap-6 lg:flex-row"
          : "relative flex flex-col gap-6"
      }
    >
      {isPage ? (
        <OnboardingTouch
          touchKey="triage_intro"
          title="Process items one at a time."
          body="Press Enter to accept, or use the keyboard shortcuts shown on each action button. Defer to come back later."
          position="bottom"
          className="right-6 top-2 w-72"
        />
      ) : null}
      <section
        className="min-w-0 flex-1 space-y-4"
        role="region"
        aria-label="Current triage item"
        aria-live="polite"
        aria-busy={working}
      >
        <header className="flex items-center justify-between">
          <div>
            {isPage ? (
              <Link
                to="/triage"
                className="text-xs text-muted-foreground hover:underline"
              >
                ← All queues
              </Link>
            ) : null}
            {isPage ? (
              <h1 className="text-xl font-semibold">{config.queue_name}</h1>
            ) : null}
            {config.description ? (
              <p className="text-sm text-muted-foreground">
                {config.description}
              </p>
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

        {/* `key` forces remount on item change → motion-safe fade-in. */}
        <div
          key={item.entity_id}
          className="motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-1 motion-safe:duration-200"
        >
          <TriageItemDisplay
            item={item}
            display={config.item_display}
            onAdvance={advance}
          />
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

      {session ? (
        <TriageContextPanel
          panels={config.context_panels}
          item={item}
          sessionId={session.session_id}
        />
      ) : null}
    </div>
  );
}
