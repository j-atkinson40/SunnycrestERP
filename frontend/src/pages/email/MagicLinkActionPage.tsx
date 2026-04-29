/**
 * MagicLinkActionPage — Phase W-4b Layer 1 Step 4c.
 *
 * Public, token-authenticated route at `/email/actions/:token`.
 *
 * Per BRIDGEABLE_MASTER §3.26.15.17 + §14.9.5 — kill-the-portal
 * canonical: a non-Bridgeable funeral home director who receives a
 * quote_approval email clicks the magic-link, sees a tenant-branded
 * mobile-first contextual surface displaying ONLY the action they
 * were emailed about, and commits the outcome (approve / reject /
 * request changes) without ever entering a Bridgeable login flow.
 *
 * Token = single-action authorization (§3.26.15.17): cannot navigate
 * beyond this surface. No app shell, no sidebar, no nav, no inbox.
 * Auth derives from the token in the URL alone.
 *
 * State machine:
 *   loading       → fetching action details
 *   error_invalid → 401 invalid token
 *   error_expired → 410 expired
 *   ready_pending → render action chrome + commit affordances
 *   submitting    → user pressed a commit button
 *   ready_done    → terminal state (just committed OR consumed=true)
 */

import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  AlertCircle,
  Check,
  CheckCircle2,
  Clock,
  Loader2,
  MessageSquare,
  X,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import * as inboxService from "@/services/email-inbox-service";
import { MagicLinkError } from "@/services/email-inbox-service";
import type {
  EmailActionStatus,
  MagicLinkActionDetails,
} from "@/types/email-inbox";


type Phase =
  | "loading"
  | "error_invalid"
  | "error_expired"
  | "ready"
  | "submitting"
  | "done";


export default function MagicLinkActionPage() {
  const { token = "" } = useParams<{ token: string }>();
  const [phase, setPhase] = useState<Phase>("loading");
  const [details, setDetails] = useState<MagicLinkActionDetails | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [requestChangesOpen, setRequestChangesOpen] = useState(false);
  const [note, setNote] = useState("");
  const [terminalStatus, setTerminalStatus] = useState<EmailActionStatus | null>(
    null,
  );

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const d = await inboxService.getMagicLinkAction(token);
        if (cancelled) return;
        setDetails(d);
        if (d.consumed) {
          setPhase("done");
          setTerminalStatus(d.action_status);
        } else {
          setPhase("ready");
        }
      } catch (e) {
        if (cancelled) return;
        if (e instanceof MagicLinkError) {
          if (e.status === 410) {
            setPhase("error_expired");
            setError(e.message);
            return;
          }
          if (e.status === 401 || e.status === 404) {
            setPhase("error_invalid");
            setError(e.message);
            return;
          }
        }
        setPhase("error_invalid");
        setError("Could not load this action.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  // Apply tenant brand color via CSS var on the page root if present.
  // We re-use the portal pattern (PortalBrandProvider sets --portal-brand)
  // without requiring the full provider — magic-link is a one-shot
  // surface, no need for the provider lifecycle.
  useEffect(() => {
    if (!details?.tenant_brand_color) return;
    const root = document.documentElement;
    const prev = root.style.getPropertyValue("--portal-brand");
    root.style.setProperty("--portal-brand", details.tenant_brand_color);
    return () => {
      if (prev) root.style.setProperty("--portal-brand", prev);
      else root.style.removeProperty("--portal-brand");
    };
  }, [details?.tenant_brand_color]);

  const commit = async (
    outcome: "approve" | "reject" | "request_changes",
    completionNote?: string,
  ) => {
    setPhase("submitting");
    try {
      const result = await inboxService.commitMagicLinkAction(token, {
        outcome,
        completion_note: completionNote || null,
      });
      setTerminalStatus(result.action_status);
      setPhase("done");
    } catch (e) {
      if (e instanceof MagicLinkError && e.status === 409) {
        // Already committed (e.g., user opened multiple tabs). Re-fetch.
        try {
          const d = await inboxService.getMagicLinkAction(token);
          setDetails(d);
          setTerminalStatus(d.action_status);
          setPhase("done");
          return;
        } catch {
          /* fall through to error */
        }
      }
      setError(
        e instanceof Error ? e.message : "Could not submit your response.",
      );
      setPhase("ready");
    }
  };

  if (phase === "loading") {
    return (
      <PageShell tenantName="Loading…">
        <div className="flex flex-col items-center justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-content-muted" />
        </div>
      </PageShell>
    );
  }

  if (phase === "error_invalid" || phase === "error_expired") {
    const expired = phase === "error_expired";
    return (
      <PageShell tenantName="Bridgeable">
        <div
          className="flex flex-col items-center text-center py-12"
          data-testid="magic-link-error"
        >
          {expired ? (
            <Clock className="h-10 w-10 text-status-warning mb-3" />
          ) : (
            <AlertCircle className="h-10 w-10 text-status-error mb-3" />
          )}
          <h2 className="font-plex-serif text-h3 font-medium text-content-strong mb-2">
            {expired ? "This link has expired" : "This link is no longer valid"}
          </h2>
          <p className="font-plex-sans text-body-sm text-content-muted max-w-sm">
            {expired
              ? "Magic-link approvals are valid for 7 days. Please reach out to the sender for a new link."
              : error || "The link may have been revoked."}
          </p>
        </div>
      </PageShell>
    );
  }

  if (!details) return null;

  // Terminal state — done branch
  if (phase === "done" && terminalStatus) {
    return (
      <PageShell
        tenantName={details.tenant_name}
        brandColor={details.tenant_brand_color}
      >
        <DoneSurface details={details} status={terminalStatus} />
      </PageShell>
    );
  }

  // Pending — ready / submitting
  return (
    <PageShell
      tenantName={details.tenant_name}
      brandColor={details.tenant_brand_color}
    >
      <ActionDetailsCard details={details} />

      {error && (
        <div
          className="rounded-[2px] border border-status-error/30 bg-status-error-muted text-status-error p-3 mb-4 font-plex-sans text-body-sm"
          data-testid="magic-link-error"
        >
          {error}
        </div>
      )}

      {!requestChangesOpen ? (
        <div
          className="space-y-2"
          data-testid="magic-link-action-buttons"
        >
          <Button
            className="w-full h-11"
            disabled={phase === "submitting"}
            onClick={() => commit("approve")}
            data-testid="magic-approve-btn"
          >
            {phase === "submitting" ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Check className="h-4 w-4 mr-2" />
            )}
            Approve quote
          </Button>
          <Button
            variant="outline"
            className="w-full h-11"
            disabled={phase === "submitting"}
            onClick={() => setRequestChangesOpen(true)}
            data-testid="magic-request-changes-btn"
          >
            <MessageSquare className="h-4 w-4 mr-2" />
            Request changes
          </Button>
          <Button
            variant="ghost"
            className="w-full h-11"
            disabled={phase === "submitting"}
            onClick={() => commit("reject")}
            data-testid="magic-reject-btn"
          >
            <X className="h-4 w-4 mr-2" />
            Reject
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          <label className="block">
            <span className="font-plex-sans text-body-sm font-medium text-content-strong">
              What changes are needed?
            </span>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Reduce price by …"
              rows={4}
              maxLength={2000}
              className="mt-1 w-full font-plex-sans text-body-sm bg-surface-elevated border border-border-subtle rounded-[2px] p-2 focus-ring-accent"
              data-testid="magic-changes-note"
            />
          </label>
          <div className="flex gap-2 justify-end">
            <Button
              variant="ghost"
              disabled={phase === "submitting"}
              onClick={() => {
                setRequestChangesOpen(false);
                setNote("");
              }}
            >
              Cancel
            </Button>
            <Button
              disabled={!note.trim() || phase === "submitting"}
              onClick={() => commit("request_changes", note)}
              data-testid="magic-submit-changes-btn"
            >
              {phase === "submitting" ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <MessageSquare className="h-4 w-4 mr-2" />
              )}
              Send request
            </Button>
          </div>
        </div>
      )}

      <p className="font-plex-sans text-caption text-content-muted text-center mt-6">
        This link is for {details.recipient_email}. Expires{" "}
        {new Date(details.expires_at).toLocaleDateString()}.
      </p>
    </PageShell>
  );
}


// ─────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────


function PageShell({
  tenantName,
  brandColor,
  children,
}: {
  tenantName: string;
  brandColor?: string | null;
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-surface-base flex flex-col">
      <header
        className="h-12 border-b border-border-subtle flex items-center px-4"
        style={
          brandColor ? { backgroundColor: brandColor, color: "white" } : undefined
        }
        data-testid="magic-link-header"
      >
        <span className="font-plex-serif text-body font-medium">
          {tenantName}
        </span>
      </header>
      <main className="flex-1 max-w-md mx-auto w-full px-4 py-6">
        {children}
      </main>
    </div>
  );
}


function ActionDetailsCard({
  details,
}: {
  details: MagicLinkActionDetails;
}) {
  const meta = details.action_metadata || {};
  const amount = meta.quote_amount as string | undefined;
  const quoteNumber = meta.quote_number as string | undefined;
  const customerName = meta.customer_name as string | undefined;
  const lineItems = (meta.quote_line_items as
    | { description: string; quantity: string; unit_price: string; line_total: string }[]
    | undefined) || [];

  return (
    <div
      className="rounded-[2px] bg-surface-elevated border border-border-subtle shadow-level-1 p-5 mb-4"
      data-testid="magic-link-details"
    >
      <div className="font-plex-sans text-caption text-content-muted mb-2">
        From{" "}
        {details.sender_name
          ? `${details.sender_name} <${details.sender_email}>`
          : details.sender_email}
      </div>
      <h2 className="font-plex-serif text-h3 font-medium text-content-strong mb-3">
        Approve quote{quoteNumber ? ` ${quoteNumber}` : ""}
      </h2>
      {customerName && (
        <p className="font-plex-sans text-body-sm text-content-muted mb-3">
          For {customerName}
        </p>
      )}
      {amount && (
        <div className="mb-4 flex items-baseline gap-2">
          <span className="font-plex-mono text-h2 text-content-strong">
            ${amount}
          </span>
        </div>
      )}
      {lineItems.length > 0 && (
        <div className="border-t border-border-subtle pt-3 space-y-2">
          {lineItems.map((li, i) => (
            <div
              key={i}
              className="flex justify-between gap-2 font-plex-sans text-body-sm"
            >
              <span className="text-content-base flex-1">
                {li.description}
              </span>
              <span className="font-plex-mono text-content-muted shrink-0">
                {li.quantity} × ${li.unit_price}
              </span>
              <span className="font-plex-mono text-content-strong shrink-0">
                ${li.line_total}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


function DoneSurface({
  details,
  status,
}: {
  details: MagicLinkActionDetails;
  status: EmailActionStatus;
}) {
  const icon =
    status === "approved" ? (
      <CheckCircle2 className="h-12 w-12 text-status-success" />
    ) : status === "rejected" ? (
      <XCircle className="h-12 w-12 text-status-error" />
    ) : (
      <Clock className="h-12 w-12 text-status-warning" />
    );

  const heading =
    status === "approved"
      ? "Approved"
      : status === "rejected"
      ? "Declined"
      : "Changes requested";

  const body =
    status === "approved"
      ? `Thanks — your approval has been recorded. ${details.sender_name || "The sender"} will follow up.`
      : status === "rejected"
      ? `Got it. Your decline has been recorded. ${details.sender_name || "The sender"} will follow up.`
      : `Your message has been sent. ${details.sender_name || "The sender"} will reach out with revisions.`;

  return (
    <div
      className="text-center py-8"
      data-testid="magic-link-done"
      data-status={status}
    >
      <div className="flex justify-center mb-4">{icon}</div>
      <h2 className="font-plex-serif text-h3 font-medium text-content-strong mb-2">
        {heading}
      </h2>
      <p className="font-plex-sans text-body text-content-muted max-w-sm mx-auto">
        {body}
      </p>
    </div>
  );
}
