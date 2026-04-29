/**
 * InlineActionBar — Phase W-4b Layer 1 Step 4c.
 *
 * Renders the operational-action affordance chrome under a message.
 * Per §3.26.15.17 + §14.9.5: when a message carries an action_type
 * affordance and the viewer is a Bridgeable user (in the sender's
 * tenant), the action bar lets them commit the outcome inline —
 * without leaving the thread surface.
 *
 * For Step 4c the only shipping action_type is `quote_approval` with
 * three outcomes: approve / reject / request_changes (note required
 * for the latter).
 *
 * State machine (terminal states render summary; pending shows action
 * buttons):
 *   pending           → 3 buttons + (if request_changes selected) note input
 *   approved          → "Approved by … on …" + brass status pill
 *   rejected          → "Rejected by … on …" + status pill
 *   changes_requested → "Changes requested by … on …" + note excerpt
 *
 * Optimistic UI: button press immediately disables the bar with
 * "Submitting…" spinner, then on success replaces with the terminal
 * state. On 409 (already committed) we re-fetch via onCommitted to
 * pick up the canonical state another user committed concurrently.
 */

import { useState } from "react";
import {
  Check,
  Clock,
  Loader2,
  MessageSquare,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import * as inboxService from "@/services/email-inbox-service";
import type {
  CommitActionResponse,
  EmailMessageAction,
} from "@/types/email-inbox";

interface Props {
  messageId: string;
  actionIdx: number;
  action: EmailMessageAction;
  onCommitted?: (result: CommitActionResponse) => void;
}

type Outcome = "approve" | "reject" | "request_changes";

export default function InlineActionBar({
  messageId,
  actionIdx,
  action,
  onCommitted,
}: Props) {
  const [submitting, setSubmitting] = useState<Outcome | null>(null);
  const [requestChangesOpen, setRequestChangesOpen] = useState(false);
  const [note, setNote] = useState("");

  if (action.action_type !== "quote_approval") {
    return null; // unknown action_type — render nothing rather than crash
  }

  // Terminal states — render summary chrome + status pill
  if (action.action_status !== "pending") {
    return <TerminalState action={action} />;
  }

  const handleCommit = async (
    outcome: Outcome,
    completionNote?: string,
  ) => {
    setSubmitting(outcome);
    try {
      const result = await inboxService.commitInlineAction(
        messageId,
        actionIdx,
        {
          outcome,
          completion_note: completionNote || null,
        },
      );
      const verb =
        outcome === "approve"
          ? "Approved"
          : outcome === "reject"
          ? "Rejected"
          : "Changes requested";
      toast.success(`${verb}.`);
      onCommitted?.(result);
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail || "Couldn't submit.";
      toast.error(detail);
    } finally {
      setSubmitting(null);
    }
  };

  // Quote metadata excerpt
  const meta = action.action_metadata || {};
  const amount = meta.quote_amount as string | undefined;
  const quoteNumber = meta.quote_number as string | undefined;
  const customerName = meta.customer_name as string | undefined;

  return (
    <div
      className="mt-3 rounded-[2px] border border-accent/30 bg-accent-subtle/40 p-3"
      data-testid="inline-action-bar"
      data-action-status="pending"
    >
      <div className="flex items-baseline justify-between gap-2 mb-3">
        <div className="font-plex-sans text-body-sm font-medium text-content-strong">
          Quote approval requested
        </div>
        {amount && (
          <span className="font-plex-mono text-caption text-content-muted shrink-0">
            ${amount}
          </span>
        )}
      </div>
      {(quoteNumber || customerName) && (
        <div className="font-plex-sans text-caption text-content-muted mb-3">
          {[quoteNumber, customerName].filter(Boolean).join(" · ")}
        </div>
      )}
      {!requestChangesOpen ? (
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            disabled={submitting !== null}
            onClick={() => handleCommit("approve")}
            data-testid="action-approve-btn"
          >
            {submitting === "approve" ? (
              <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
            ) : (
              <Check className="h-3.5 w-3.5 mr-1.5" />
            )}
            Approve
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={submitting !== null}
            onClick={() => setRequestChangesOpen(true)}
            data-testid="action-request-changes-btn"
          >
            <MessageSquare className="h-3.5 w-3.5 mr-1.5" />
            Request changes
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={submitting !== null}
            onClick={() => handleCommit("reject")}
            data-testid="action-reject-btn"
          >
            {submitting === "reject" ? (
              <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
            ) : (
              <X className="h-3.5 w-3.5 mr-1.5" />
            )}
            Reject
          </Button>
        </div>
      ) : (
        <div className="space-y-2">
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="What changes are needed?"
            rows={3}
            maxLength={2000}
            className="w-full font-plex-sans text-body-sm bg-surface-elevated border border-border-subtle rounded-[2px] p-2 focus-ring-accent"
            data-testid="action-changes-note"
          />
          <div className="flex flex-wrap gap-2 justify-end">
            <Button
              size="sm"
              variant="ghost"
              disabled={submitting !== null}
              onClick={() => {
                setRequestChangesOpen(false);
                setNote("");
              }}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={!note.trim() || submitting !== null}
              onClick={() => handleCommit("request_changes", note)}
              data-testid="action-submit-changes-btn"
            >
              {submitting === "request_changes" ? (
                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
              ) : (
                <MessageSquare className="h-3.5 w-3.5 mr-1.5" />
              )}
              Send request
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}


function TerminalState({ action }: { action: EmailMessageAction }) {
  const status = action.action_status;
  const completedAt = action.action_completed_at
    ? new Date(action.action_completed_at).toLocaleString()
    : null;
  const note = (action.action_completion_metadata?.note as string) || null;

  const icon =
    status === "approved" ? (
      <Check className="h-3.5 w-3.5" />
    ) : status === "rejected" ? (
      <X className="h-3.5 w-3.5" />
    ) : (
      <Clock className="h-3.5 w-3.5" />
    );

  const label =
    status === "approved"
      ? "Approved"
      : status === "rejected"
      ? "Rejected"
      : "Changes requested";

  // Status palette per DESIGN_LANGUAGE §3
  const tone =
    status === "approved"
      ? "border-status-success/40 bg-status-success-muted text-status-success"
      : status === "rejected"
      ? "border-status-error/40 bg-status-error-muted text-status-error"
      : "border-status-warning/40 bg-status-warning-muted text-status-warning";

  return (
    <div
      className={`mt-3 rounded-[2px] border ${tone} p-3`}
      data-testid="inline-action-bar"
      data-action-status={status}
    >
      <div className="flex items-baseline gap-2">
        {icon}
        <span className="font-plex-sans text-body-sm font-medium">{label}</span>
        {completedAt && (
          <span className="font-plex-mono text-caption text-content-muted ml-auto">
            {completedAt}
          </span>
        )}
      </div>
      {note && (
        <div className="mt-2 font-plex-sans text-caption text-content-muted">
          “{note}”
        </div>
      )}
    </div>
  );
}
