/**
 * "We don't do that" — the authoring surface. CR-3 D-2.
 *
 * ⚠️ THE PLACEMENT IS THE DESIGN, NOT THE STYLING. Declining is reachable from
 * the review because a control only reachable from settings is safe and never
 * found — and four surfaces were built-and-unreachable in the fortnight before
 * this, one of them in this arc. But it attaches to the OBLIGATION LIST, not to
 * a `missing` row:
 *
 *   a control sitting on a red row is answered in the mood of clearing that row;
 *   the same control one section down is answered in the mood of describing the
 *   business.
 *
 * Same surface, same discoverability, different question. So this section renders
 * BELOW the review, under its own heading, over the FULL declared set — the
 * quiet obligations included. That is also why it cannot be derived from
 * `/review`: the review is exception-shaped, and a control built from its rows
 * could only ever decline things that were already red, which is precisely the
 * mood the ruling rejects.
 *
 * ⚠️ AND IT IS NOT A DELETE. Revoking keeps the episode and its dates, so the
 * months the tenant was not doing the thing still read as `declined` rather than
 * turning back into gaps the moment they resume.
 */
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Loader2, Undo2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { getApiErrorMessage } from "@/lib/api-error";
import {
  completenessService,
  type Obligation,
  type ObligationList,
} from "@/services/completeness-service";

interface Props {
  /** Called after a successful write so the review above re-reads. The two
   *  surfaces show the same facts; leaving the review stale would let the page
   *  contradict itself. */
  onChanged?: () => void;
}

export default function DeclaredObligations({ onChanged }: Props) {
  const [data, setData] = useState<ObligationList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await completenessService.getObligations());
    } catch (e) {
      // Cleared, like the review's own failure path: a stale list beside a
      // fresh review is the page being confidently wrong about which
      // obligations exist.
      setData(null);
      setError(getApiErrorMessage(e, "Could not load the declared obligations."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const afterWrite = useCallback(async () => {
    await load();
    onChanged?.();
  }, [load, onChanged]);

  return (
    <section
      aria-labelledby="declared-obligations-heading"
      data-testid="declared-obligations"
      // Separated from the review above by a rule and a full section gap. The
      // adjacency is what the placement ruling turns on — a decline control that
      // ends up beside a `missing` row has collapsed the distinction regardless
      // of which component owns it.
      className="mt-10 border-t border-border-subtle pt-8"
    >
      <h3
        id="declared-obligations-heading"
        className="text-h4 font-semibold text-content-strong"
      >
        Declared obligations
      </h3>
      <p className="mt-1 max-w-reading text-body-sm text-content-muted">
        Everything this tenant is expected to produce, whether or not it is
        currently outstanding. If one of these is not something you do, say so
        here — it stays on the review as an answer rather than becoming a gap.
      </p>

      {error ? (
        <div className="mt-4 flex items-center gap-3 rounded-lg border border-status-error/30 bg-status-error-muted px-4 py-3">
          <AlertTriangle className="h-4 w-4 shrink-0 text-status-error" />
          <p className="flex-1 text-body-sm text-content-base">{error}</p>
          <Button variant="outline" size="sm" onClick={() => void load()}>
            Try again
          </Button>
        </div>
      ) : loading && !data ? (
        <p className="mt-4 flex items-center gap-2 text-body-sm text-content-muted">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading obligations…
        </p>
      ) : data ? (
        <ul className="mt-4 divide-y divide-border-subtle overflow-hidden rounded-lg border border-border-subtle bg-surface-elevated">
          {data.obligations.map((o) => (
            <ObligationRow
              key={o.key}
              obligation={o}
              mayDecline={data.may_decline}
              onChanged={afterWrite}
            />
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function ObligationRow({
  obligation,
  mayDecline,
  onChanged,
}: {
  obligation: Obligation;
  mayDecline: boolean;
  onChanged: () => void | Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);

  const declined = obligation.declination;

  async function submit() {
    setBusy(true);
    setFailed(null);
    try {
      if (declined) {
        await completenessService.revokeDeclination(declined.id, reason);
      } else {
        await completenessService.decline({
          expectation_key: obligation.key,
          reason,
        });
      }
      setOpen(false);
      setReason("");
      await onChanged();
    } catch (e) {
      setFailed(getApiErrorMessage(e, "That did not save."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="px-4 py-3" data-testid={`obligation-${obligation.key}`}>
      <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
        <div className="min-w-0 flex-1">
          <p className="text-body-sm font-medium text-content-strong">
            {obligation.label}
          </p>
          <p className="mt-0.5 text-caption text-content-muted">
            {obligation.matters_because}
          </p>
          {declined && (
            // Attribution at the point of use. A declination silences this
            // obligation until somebody revokes it, and the cheapest thing that
            // keeps it honest is the row saying who answered.
            <p className="mt-1 text-caption text-content-base">
              <span className="font-medium">Declined</span>{" "}
              {fmtDay(declined.declined_on)} by {declined.declined_by_name} (
              {declined.declined_by_role_slug}): {declined.reason}
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span className="text-micro uppercase tracking-wide text-content-subtle">
            {obligation.cadence} · {obligation.role_slug}
          </span>
          {/* Rendered only when the server says this user may write. A button
              that exists and 403s is built-and-unreachable inverted — it invites
              the click rather than merely permitting it. */}
          {mayDecline && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setOpen((v) => !v);
                setFailed(null);
              }}
            >
              {declined ? (
                <>
                  <Undo2 className="mr-1.5 h-3.5 w-3.5" />
                  Resume
                </>
              ) : (
                "We don't do this"
              )}
            </Button>
          )}
        </div>
      </div>

      {open && mayDecline && (
        <div className="mt-3 rounded-base border border-border-base bg-surface-sunken p-3">
          <label
            className="block text-caption text-content-muted"
            htmlFor={`reason-${obligation.key}`}
          >
            {declined
              ? "Why are you resuming this?"
              : "Why does this not apply?"}
          </label>
          {/* Required, and the server agrees rather than trusting this. "We
              don't do that" with no reason is the weak assertion this arc
              rejected everywhere else, and it stands until someone revokes it —
              a future reader has only this sentence. */}
          <textarea
            id={`reason-${obligation.key}`}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={2}
            className="mt-1 w-full rounded-base border border-border-base bg-surface-raised px-3 py-2 text-body-sm text-content-base focus-visible:border-accent focus-visible:outline-none"
            placeholder={
              declined ? "We took deliveries back in house" : "We don't run a delivery fleet"
            }
          />
          {failed && (
            <p className="mt-2 text-caption text-status-error">{failed}</p>
          )}
          <div className="mt-2 flex items-center gap-2">
            <Button
              size="sm"
              disabled={busy || !reason.trim()}
              onClick={() => void submit()}
            >
              {busy && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
              {declined ? "Resume this obligation" : "Record declination"}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={busy}
              onClick={() => {
                setOpen(false);
                setReason("");
                setFailed(null);
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}
    </li>
  );
}

/** Parsed by split, NOT `new Date(iso)` — a bare date parses as UTC midnight and
 *  renders the previous day at any negative UTC offset. Same reason as the
 *  review tab's own formatter next door. */
function fmtDay(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
