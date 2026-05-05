/**
 * Settings → Calendar Drafts — Phase W-4b Layer 1 Calendar Step 3.
 *
 * Per §3.26.16.18 + §3.26.14.14.5 drafted-not-auto-sent discipline:
 * state-change-generated calendar events with status="tentative" land
 * in this review queue. Operators review + commit (Send) or discard
 * (Cancel) before iTIP propagation.
 *
 * Auto-confirmed events (internal-only per §3.26.16.18 auto-confirmation
 * rules) bypass this surface and ship directly to status="confirmed".
 *
 * Send → POST /calendar-events/{id}/send: provider propagates iTIP
 *   REQUEST + status flips tentative → confirmed.
 * Cancel → POST /calendar-events/{id}/cancel: provider propagates iTIP
 *   CANCEL + status flips to cancelled (event row preserved for audit).
 */

import { useEffect, useState } from "react";
import {
  CalendarClock,
  Send,
  X,
  RefreshCw,
  AlertCircle,
} from "lucide-react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusPill } from "@/components/ui/status-pill";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  cancelCalendarEvent,
  listStateChangeDrafts,
  sendCalendarEvent,
} from "@/services/calendar-account-service";
import type { CalendarEvent } from "@/types/calendar-account";

/**
 * Format a generation_entity_type into a friendly label. Falls back to
 * the raw string when not in the canonical 7-mapping registry.
 */
function formatGenerationSource(
  entityType: string | null | undefined,
): string {
  if (!entityType) return "—";
  const canonical: Record<string, string> = {
    sales_order: "Sales order",
    fh_case: "FH case",
    quote: "Quote",
    work_order: "Work order",
    equipment: "Equipment maintenance",
    compliance_requirement: "Compliance renewal",
    disinterment: "Disinterment",
  };
  return canonical[entityType] ?? entityType;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

interface PendingAction {
  type: "send" | "cancel";
  event: CalendarEvent;
}

export default function CalendarDraftsPage() {
  const [drafts, setDrafts] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [actionInFlight, setActionInFlight] = useState(false);

  async function loadDrafts(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const data = await listStateChangeDrafts(100);
      setDrafts(data);
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ??
          "Failed to load drafted events. Try refreshing the page.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDrafts();
  }, []);

  async function handleConfirm(): Promise<void> {
    if (!pending) return;
    setActionInFlight(true);
    try {
      if (pending.type === "send") {
        const result = await sendCalendarEvent(pending.event.id);
        toast.success(
          `Invitation sent to ${result.recipient_count} ${
            result.recipient_count === 1 ? "attendee" : "attendees"
          }`,
        );
      } else {
        await cancelCalendarEvent(pending.event.id);
        toast.success("Event cancelled");
      }
      setPending(null);
      await loadDrafts();
    } catch (err: any) {
      toast.error(
        err?.response?.data?.detail ??
          (pending.type === "send"
            ? "Send failed. Operator may need to reconnect the calendar account."
            : "Cancel failed. Try again."),
      );
    } finally {
      setActionInFlight(false);
    }
  }

  return (
    <div className="container mx-auto max-w-5xl space-y-6 p-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-h2 font-plex-serif font-medium text-content-strong">
            Calendar drafts
          </h1>
          <p className="mt-1 text-body-sm text-content-muted">
            Tentative events generated from operational state changes. Review
            + commit (Send) or discard (Cancel) before invitations propagate.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={loadDrafts}
            disabled={loading}
          >
            <RefreshCw
              className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}
              aria-hidden="true"
            />
            <span className="ml-2">Refresh</span>
          </Button>
        </div>
      </div>

      {error ? (
        <Alert variant="error">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Couldn't load drafts</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="space-y-2 p-4">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : drafts.length === 0 ? (
            <EmptyState
              icon={CalendarClock}
              title="No drafted events"
              description="State-change-generated events appear here when they need explicit operator review. Auto-confirmed events ship directly without surfacing in this queue."
              size="sm"
              tone="neutral"
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Subject</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Starts</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {drafts.map((event) => (
                  <TableRow key={event.id}>
                    <TableCell className="font-medium text-content-strong">
                      {event.subject || "(no subject)"}
                      {event.is_cross_tenant ? (
                        <span className="ml-2 text-micro uppercase tracking-wider text-content-muted">
                          Cross-tenant
                        </span>
                      ) : null}
                    </TableCell>
                    <TableCell className="text-body-sm text-content-base">
                      {formatGenerationSource(event.generation_entity_type)}
                    </TableCell>
                    <TableCell className="text-body-sm text-content-base">
                      {formatDate(event.start_at)}
                    </TableCell>
                    <TableCell>
                      <StatusPill status={event.status} />
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          size="sm"
                          onClick={() =>
                            setPending({ type: "send", event })
                          }
                        >
                          <Send className="h-3.5 w-3.5" aria-hidden="true" />
                          <span className="ml-1.5">Send</span>
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            setPending({ type: "cancel", event })
                          }
                        >
                          <X className="h-3.5 w-3.5" aria-hidden="true" />
                          <span className="ml-1.5">Cancel</span>
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog
        open={pending !== null}
        onOpenChange={(open) => {
          if (!open) setPending(null);
        }}
      >
        <DialogContent>
          {pending ? (
            <>
              <DialogHeader>
                <DialogTitle>
                  {pending.type === "send"
                    ? "Send invitations?"
                    : "Cancel this event?"}
                </DialogTitle>
                <DialogDescription>
                  {pending.type === "send"
                    ? "This propagates an iTIP REQUEST to all attendees and flips the event status from tentative to confirmed."
                    : "This propagates an iTIP CANCEL to all attendees and flips the event status to cancelled. The event row is preserved for audit."}
                </DialogDescription>
              </DialogHeader>
              <div className="rounded border border-border-subtle bg-surface-sunken p-3 text-body-sm">
                <div className="font-medium text-content-strong">
                  {pending.event.subject || "(no subject)"}
                </div>
                <div className="text-content-muted">
                  {formatGenerationSource(
                    pending.event.generation_entity_type,
                  )}{" "}
                  · Starts {formatDate(pending.event.start_at)}
                </div>
              </div>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setPending(null)}
                  disabled={actionInFlight}
                >
                  Keep drafted
                </Button>
                <Button
                  variant={
                    pending.type === "cancel" ? "destructive" : "default"
                  }
                  onClick={handleConfirm}
                  disabled={actionInFlight}
                >
                  {pending.type === "send" ? "Send invitations" : "Cancel event"}
                </Button>
              </DialogFooter>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
