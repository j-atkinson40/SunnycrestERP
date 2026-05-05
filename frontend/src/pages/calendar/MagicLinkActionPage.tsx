/**
 * Calendar magic-link contextual surface — Phase W-4b Layer 1 Step 4.
 *
 * Public, token-authenticated route at `/calendar/actions/:token`.
 *
 * Per BRIDGEABLE_MASTER §3.26.16.17 + §14.10.5 — kill-the-portal
 * canonical: a non-Bridgeable funeral home director (or external
 * partner) clicks the magic-link in a calendar invite, sees a
 * tenant-branded mobile-first contextual surface displaying ONLY the
 * single action they were emailed about, and commits the outcome
 * (Accept / Decline / Propose alternative time) without ever entering
 * a Bridgeable login flow.
 *
 * Token = single-action authorization (§3.26.11.9): cannot navigate
 * beyond this surface. No app shell, no sidebar, no nav, no inbox.
 * Auth derives from the token in the URL alone.
 *
 * Visual canon per §14.10.5 verbatim:
 *   - Tenant-branded h-12 header (brand color inline-styled)
 *   - Mobile-first max-w-md container
 *   - Action title text-h3 font-plex-serif text-content-strong
 *   - Proposed details rendered as Pattern 2 card
 *   - Three-button action stack: primary Accept (brass) + outline
 *     Propose alternative + ghost Decline
 *   - Counter-proposal flow: counter-time picker + optional note
 *   - Decline flow: optional decline reason
 *   - Reschedule flow: cascade impact disclosure
 *   - Footer: expiry indicator + privacy assurance copy
 */

import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  AlertCircle,
  Check,
  CheckCircle2,
  Clock,
  Loader2,
  Repeat,
  X,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  CalendarMagicLinkError,
  commitMagicLinkAction,
  getMagicLinkAction,
} from "@/services/calendar-actions-service";
import type {
  CalendarActionStatus,
  CalendarActionType,
  MagicLinkActionDetails,
} from "@/types/calendar-actions";

type Phase =
  | "loading"
  | "error_invalid"
  | "error_expired"
  | "error_other"
  | "ready"
  | "submitting"
  | "done";


function _formatRange(startIso: string, endIso: string): string {
  try {
    const start = new Date(startIso);
    const end = new Date(endIso);
    const sameDay =
      start.getFullYear() === end.getFullYear() &&
      start.getMonth() === end.getMonth() &&
      start.getDate() === end.getDate();
    const dateFmt: Intl.DateTimeFormatOptions = {
      weekday: "long",
      month: "long",
      day: "numeric",
      year: "numeric",
    };
    const timeFmt: Intl.DateTimeFormatOptions = {
      hour: "numeric",
      minute: "2-digit",
    };
    if (sameDay) {
      return `${start.toLocaleDateString(undefined, dateFmt)} · ${start.toLocaleTimeString(undefined, timeFmt)} – ${end.toLocaleTimeString(undefined, timeFmt)}`;
    }
    return `${start.toLocaleString(undefined, { ...dateFmt, ...timeFmt })} – ${end.toLocaleString(undefined, { ...dateFmt, ...timeFmt })}`;
  } catch {
    return `${startIso} – ${endIso}`;
  }
}


function _expiresInDays(expiresIso: string): number {
  try {
    const expires = new Date(expiresIso).getTime();
    const now = Date.now();
    const diffMs = expires - now;
    return Math.max(0, Math.ceil(diffMs / (24 * 60 * 60 * 1000)));
  } catch {
    return 0;
  }
}


function _actionTitle(actionType: CalendarActionType): string {
  switch (actionType) {
    case "service_date_acceptance":
      return "Service date proposal";
    case "delivery_date_acceptance":
      return "Delivery date proposal";
    case "joint_event_acceptance":
      return "Joint event proposal";
    case "recurring_meeting_proposal":
      return "Recurring meeting proposal";
    case "event_reschedule_proposal":
      return "Reschedule proposal";
  }
}


function _terminalCopy(status: CalendarActionStatus): {
  icon: typeof CheckCircle2;
  title: string;
  body: string;
} {
  switch (status) {
    case "accepted":
      return {
        icon: CheckCircle2,
        title: "You accepted",
        body: "The organizer has been notified. You can close this window.",
      };
    case "rejected":
      return {
        icon: XCircle,
        title: "You declined",
        body: "The organizer has been notified.",
      };
    case "counter_proposed":
      return {
        icon: Repeat,
        title: "Counter-proposal sent",
        body: "The organizer will review your proposed time.",
      };
    default:
      return {
        icon: AlertCircle,
        title: "Already responded",
        body: "This invitation has already been responded to.",
      };
  }
}


export default function CalendarMagicLinkActionPage() {
  const { token = "" } = useParams<{ token: string }>();
  const [phase, setPhase] = useState<Phase>("loading");
  const [details, setDetails] = useState<MagicLinkActionDetails | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [counterOpen, setCounterOpen] = useState(false);
  const [counterStart, setCounterStart] = useState("");
  const [counterEnd, setCounterEnd] = useState("");
  const [declineOpen, setDeclineOpen] = useState(false);
  const [note, setNote] = useState("");
  const [terminalStatus, setTerminalStatus] = useState<CalendarActionStatus | null>(
    null,
  );

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const d = await getMagicLinkAction(token);
        if (cancelled) return;
        setDetails(d);
        if (d.consumed) {
          setPhase("done");
          setTerminalStatus(d.action_status);
        } else {
          setPhase("ready");
        }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof CalendarMagicLinkError) {
          if (err.status === 401) {
            setPhase("error_invalid");
          } else if (err.status === 410) {
            setPhase("error_expired");
          } else {
            setPhase("error_other");
            setError(err.detail);
          }
        } else {
          setPhase("error_other");
          setError("Failed to load action details.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const expiresInDays = useMemo(
    () => (details ? _expiresInDays(details.expires_at) : 0),
    [details],
  );

  const isReschedule = details?.action_type === "event_reschedule_proposal";

  // Apply tenant brand color to header (per §14.10.5 inline-style).
  const headerStyle = useMemo<React.CSSProperties>(() => {
    if (!details?.tenant_brand_color) return {};
    return {
      backgroundColor: details.tenant_brand_color,
      color: "#fff",
    };
  }, [details]);

  async function handleAccept() {
    if (!details) return;
    setPhase("submitting");
    try {
      const r = await commitMagicLinkAction(token, { outcome: "accept" });
      setTerminalStatus(r.action_status);
      setPhase("done");
    } catch (err) {
      const msg =
        err instanceof CalendarMagicLinkError
          ? err.detail
          : "Failed to submit response.";
      setError(msg);
      setPhase("ready");
    }
  }

  async function handleDecline() {
    if (!details) return;
    setPhase("submitting");
    try {
      const r = await commitMagicLinkAction(token, {
        outcome: "reject",
        completion_note: note.trim() || undefined,
      });
      setTerminalStatus(r.action_status);
      setPhase("done");
    } catch (err) {
      const msg =
        err instanceof CalendarMagicLinkError
          ? err.detail
          : "Failed to submit response.";
      setError(msg);
      setPhase("ready");
    }
  }

  async function handleCounterPropose() {
    if (!details) return;
    if (!counterStart || !counterEnd) {
      setError("Please pick a counter-time start and end.");
      return;
    }
    setPhase("submitting");
    try {
      const r = await commitMagicLinkAction(token, {
        outcome: "counter_propose",
        completion_note: note.trim() || undefined,
        counter_proposed_start_at: new Date(counterStart).toISOString(),
        counter_proposed_end_at: new Date(counterEnd).toISOString(),
      });
      setTerminalStatus(r.action_status);
      setPhase("done");
    } catch (err) {
      const msg =
        err instanceof CalendarMagicLinkError
          ? err.detail
          : "Failed to submit counter-proposal.";
      setError(msg);
      setPhase("ready");
    }
  }

  // ── Phase: loading ────────────────────────────────────────────
  if (phase === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-base">
        <Loader2 className="h-8 w-8 animate-spin text-content-muted" />
      </div>
    );
  }

  // ── Phase: error_invalid ──────────────────────────────────────
  if (phase === "error_invalid") {
    return (
      <ErrorScreen
        title="Invitation link not found"
        body="This link may have been mistyped or the invitation may have been cancelled."
      />
    );
  }

  if (phase === "error_expired") {
    return (
      <ErrorScreen
        title="Invitation expired"
        body="This invitation link has expired. Please contact the organizer for a new one."
      />
    );
  }

  if (phase === "error_other" || !details) {
    return (
      <ErrorScreen
        title="Couldn't load invitation"
        body={error ?? "An unknown error occurred."}
      />
    );
  }

  // ── Phase: done (terminal) ────────────────────────────────────
  if (phase === "done" && terminalStatus) {
    const copy = _terminalCopy(terminalStatus);
    return (
      <div className="flex min-h-screen flex-col bg-surface-base">
        <header
          className="flex h-12 items-center px-4 text-h4 font-medium"
          style={headerStyle}
        >
          {details.tenant_name}
        </header>
        <main className="mx-auto w-full max-w-md p-6">
          <div className="rounded border border-border-subtle bg-surface-elevated p-6 shadow-level-1">
            <copy.icon className="mb-3 h-10 w-10 text-status-success" />
            <h1 className="text-h3 font-plex-serif text-content-strong">
              {copy.title}
            </h1>
            <p className="mt-2 text-body-sm text-content-muted">
              {copy.body}
            </p>
          </div>
        </main>
      </div>
    );
  }

  // ── Phase: ready (or submitting) ──────────────────────────────
  const proposedStart =
    (details.action_metadata?.proposed_start_at as string) ??
    details.event_start_at;
  const proposedEnd =
    (details.action_metadata?.proposed_end_at as string) ??
    details.event_end_at;
  const proposedLocation =
    (details.action_metadata?.proposed_location as string | undefined) ??
    details.event_location ??
    null;
  const submitting = phase === "submitting";

  return (
    <div className="flex min-h-screen flex-col bg-surface-base">
      {/* Tenant-branded h-12 header per §14.10.5 */}
      <header
        className="flex h-12 items-center px-4 text-h4 font-medium"
        style={headerStyle}
      >
        {details.tenant_name}
      </header>

      <main className="mx-auto w-full max-w-md flex-1 p-6">
        {/* Action title + proposed details — Pattern 2 card */}
        <div className="rounded border border-border-subtle bg-surface-elevated p-6 shadow-level-1">
          <h1 className="text-h3 font-plex-serif text-content-strong">
            {_actionTitle(details.action_type)}
          </h1>
          {details.event_subject ? (
            <p className="mt-1 text-body-sm text-content-muted">
              {details.event_subject}
            </p>
          ) : null}

          <div className="mt-4 space-y-2">
            <div className="text-body-sm text-content-base">
              <Clock className="mr-1.5 inline h-4 w-4 text-content-muted" />
              {_formatRange(proposedStart, proposedEnd)}
            </div>
            {proposedLocation ? (
              <div className="text-body-sm text-content-base">
                {proposedLocation}
              </div>
            ) : null}
            {details.organizer_name ? (
              <div className="text-caption text-content-muted">
                Proposed by {details.organizer_name}
              </div>
            ) : null}
            {details.action_metadata?.deceased_name ? (
              <div className="text-caption text-content-muted">
                {String(details.action_metadata.deceased_name)} family
              </div>
            ) : null}
            {details.action_metadata?.recurrence_rule ? (
              <div className="text-caption text-content-muted">
                Recurring: {String(details.action_metadata.recurrence_rule)}
              </div>
            ) : null}
          </div>

          {/* §14.10.5 reschedule flow cascade impact disclosure */}
          {isReschedule && details.cascade_impact ? (
            <div className="mt-4 rounded border border-status-warning bg-status-warning-muted p-3 text-body-sm">
              <strong>Rescheduling this event will affect:</strong>
              <ul className="mt-1 list-inside list-disc text-content-base">
                <li>
                  {details.cascade_impact.linked_entity_count} linked{" "}
                  {details.cascade_impact.linked_entity_count === 1
                    ? "entity"
                    : "entities"}
                </li>
                {details.cascade_impact.paired_cross_tenant_count > 0 ? (
                  <li>
                    {details.cascade_impact.paired_cross_tenant_count}{" "}
                    paired cross-tenant{" "}
                    {details.cascade_impact.paired_cross_tenant_count === 1
                      ? "event"
                      : "events"}
                  </li>
                ) : null}
              </ul>
            </div>
          ) : null}
        </div>

        {/* Three-button action stack per §14.10.5 */}
        {!counterOpen && !declineOpen ? (
          <div className="mt-6 space-y-3">
            <Button
              size="lg"
              className="w-full"
              onClick={handleAccept}
              disabled={submitting}
            >
              {submitting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Check className="h-4 w-4" />
              )}
              <span className="ml-2">
                {isReschedule ? "Accept reschedule" : "Accept this date"}
              </span>
            </Button>
            <Button
              variant="outline"
              size="lg"
              className="w-full"
              onClick={() => {
                setCounterOpen(true);
                setError(null);
              }}
              disabled={submitting}
            >
              <Repeat className="h-4 w-4" />
              <span className="ml-2">Propose alternative time</span>
            </Button>
            <Button
              variant="ghost"
              size="lg"
              className="w-full"
              onClick={() => {
                setDeclineOpen(true);
                setError(null);
              }}
              disabled={submitting}
            >
              <X className="h-4 w-4" />
              <span className="ml-2">Decline</span>
            </Button>
          </div>
        ) : null}

        {/* Counter-propose flow per §14.10.5 */}
        {counterOpen ? (
          <div className="mt-6 rounded border border-border-subtle bg-surface-elevated p-4 shadow-level-1">
            <h2 className="text-body font-medium text-content-strong">
              Propose an alternative time
            </h2>
            <div className="mt-3 space-y-3">
              <label className="block text-body-sm">
                <span className="text-content-base">Start</span>
                <input
                  type="datetime-local"
                  className="mt-1 block w-full rounded border border-border-base bg-surface-raised p-2 font-plex-mono text-body-sm"
                  value={counterStart}
                  onChange={(e) => setCounterStart(e.target.value)}
                />
              </label>
              <label className="block text-body-sm">
                <span className="text-content-base">End</span>
                <input
                  type="datetime-local"
                  className="mt-1 block w-full rounded border border-border-base bg-surface-raised p-2 font-plex-mono text-body-sm"
                  value={counterEnd}
                  onChange={(e) => setCounterEnd(e.target.value)}
                />
              </label>
              <label className="block text-body-sm">
                <span className="text-content-base">Note (optional)</span>
                <textarea
                  className="mt-1 block w-full rounded border border-border-base bg-surface-raised p-2 text-body-sm"
                  rows={3}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  maxLength={2000}
                  placeholder="How about Friday morning instead?"
                />
              </label>
              {error ? (
                <p className="text-caption text-status-error">{error}</p>
              ) : null}
              <div className="flex gap-2">
                <Button
                  size="default"
                  className="flex-1"
                  onClick={handleCounterPropose}
                  disabled={submitting || !counterStart || !counterEnd}
                >
                  {submitting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : null}
                  Send counter-proposal
                </Button>
                <Button
                  variant="ghost"
                  size="default"
                  onClick={() => {
                    setCounterOpen(false);
                    setError(null);
                  }}
                  disabled={submitting}
                >
                  Back
                </Button>
              </div>
            </div>
          </div>
        ) : null}

        {/* Decline flow per §14.10.5 */}
        {declineOpen ? (
          <div className="mt-6 rounded border border-border-subtle bg-surface-elevated p-4 shadow-level-1">
            <h2 className="text-body font-medium text-content-strong">
              Decline this invitation
            </h2>
            <label className="mt-3 block text-body-sm">
              <span className="text-content-base">Reason (optional)</span>
              <textarea
                className="mt-1 block w-full rounded border border-border-base bg-surface-raised p-2 text-body-sm"
                rows={3}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                maxLength={2000}
                placeholder="Travel conflict; not available that week"
              />
            </label>
            {error ? (
              <p className="mt-2 text-caption text-status-error">{error}</p>
            ) : null}
            <div className="mt-3 flex gap-2">
              <Button
                variant="destructive"
                size="default"
                className="flex-1"
                onClick={handleDecline}
                disabled={submitting}
              >
                {submitting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : null}
                Confirm decline
              </Button>
              <Button
                variant="ghost"
                size="default"
                onClick={() => {
                  setDeclineOpen(false);
                  setError(null);
                }}
                disabled={submitting}
              >
                Back
              </Button>
            </div>
          </div>
        ) : null}
      </main>

      {/* Footer per §14.10.5: expiry indicator + privacy assurance */}
      <footer className="mx-auto w-full max-w-md px-6 pb-6 text-caption text-content-muted">
        <p>
          This link expires in {expiresInDays}{" "}
          {expiresInDays === 1 ? "day" : "days"}.
        </p>
        <p className="mt-1">
          Your response is private to {details.tenant_name}.
        </p>
      </footer>
    </div>
  );
}


function ErrorScreen({ title, body }: { title: string; body: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-base p-6">
      <div className="w-full max-w-md rounded border border-border-subtle bg-surface-elevated p-6 text-center shadow-level-1">
        <AlertCircle className="mx-auto mb-3 h-10 w-10 text-status-error" />
        <h1 className="text-h3 font-plex-serif text-content-strong">
          {title}
        </h1>
        <p className="mt-2 text-body-sm text-content-muted">{body}</p>
      </div>
    </div>
  );
}
