/**
 * `/triage` — lists every queue available to the current user.
 *
 * Each card shows queue name + description + pending count +
 * "Open" button that routes to `/triage/:queueId`. Pending count
 * is fetched lazily for each queue; a slow count endpoint shouldn't
 * block the list from rendering.
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { InlineError } from "@/components/ui/inline-error";
import { SkeletonCard } from "@/components/ui/skeleton";
import { PinStar } from "@/components/spaces/PinStar";
import { ListChecks } from "lucide-react";
import {
  getQueueCount,
  listQueues,
  type TriageQueueSummary,
} from "@/services/triage-service";

export default function TriageIndex() {
  const [queues, setQueues] = useState<TriageQueueSummary[] | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const qs = await listQueues();
        if (cancelled) return;
        setQueues(qs);
        // Fire-and-forget count fetches — each independently.
        for (const q of qs) {
          void getQueueCount(q.queue_id)
            .then((c) => {
              if (cancelled) return;
              setCounts((prev) => ({ ...prev, [q.queue_id]: c.count }));
            })
            .catch(() => undefined);
        }
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load queues");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <InlineError
          message="Couldn't load triage queues."
          hint={error}
          onRetry={() => {
            setError(null);
            setQueues(null);
            void listQueues().then(setQueues).catch((e) =>
              setError(e instanceof Error ? e.message : "Failed"),
            );
          }}
        />
      </div>
    );
  }

  if (queues === null) {
    return (
      <div
        className="mx-auto max-w-5xl space-y-4 p-6"
        data-testid="triage-index-loading"
      >
        <h1 className="text-xl font-semibold">Triage Workspace</h1>
        <div className="grid gap-4 sm:grid-cols-2">
          <SkeletonCard lines={3} />
          <SkeletonCard lines={3} />
        </div>
      </div>
    );
  }

  if (queues.length === 0) {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <EmptyState
          icon={ListChecks}
          title="No triage queues for your role yet"
          description={
            <>
              Triage queues surface decisions you can act on. Your role
              doesn't have any queues available today, but admins can add
              per-tenant queues from{" "}
              <Link to="/settings" className="text-primary hover:underline">
                settings
              </Link>
              .
            </>
          }
          data-testid="triage-index-empty"
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <header>
        <h1 className="flex items-center gap-2 text-xl font-semibold">
          <ListChecks className="h-5 w-5" />
          Triage Workspace
        </h1>
        <p className="text-sm text-muted-foreground">
          Process pending items one at a time. Keyboard-driven —
          start a queue below, then use the shortcut hints on each
          decision button.
        </p>
      </header>
      <div className="grid gap-4 sm:grid-cols-2">
        {queues
          .sort((a, b) => a.display_order - b.display_order)
          .map((q) => (
            <Card key={q.queue_id}>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-base">{q.queue_name}</CardTitle>
                <div className="flex items-center gap-1.5">
                  <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                    {counts[q.queue_id] ?? "…"} pending
                  </span>
                  <PinStar
                    pinType="triage_queue"
                    targetId={q.queue_id}
                    labelOverride={q.queue_name}
                  />
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <p className="text-muted-foreground">{q.description}</p>
                <Button
                  render={
                    <Link to={`/triage/${encodeURIComponent(q.queue_id)}`} />
                  }
                >
                  Open
                </Button>
              </CardContent>
            </Card>
          ))}
      </div>
    </div>
  );
}
