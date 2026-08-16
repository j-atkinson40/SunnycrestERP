/**
 * "Did everything that was supposed to arrive, arrive?" — the accountant's half. CR-2 A-4.
 *
 * A-1 built the verdicts, A-2 the classifier, A-3 the producer-side prompt. The
 * review endpoint has existed since A-1 and NOTHING CONSUMED IT — `getReview`
 * was a service method with no caller. This is that surface.
 *
 * ⚠️ EXCEPTION-SHAPED, AND THAT IS THE BACKEND'S DECISION, NOT THIS FILE'S.
 * `summarise` already dropped `arrived` and `not_yet_due` from `rows` and left
 * their count in `quiet_summary`. So this component renders what it is given and
 * does NOT re-filter — a second filter here would be a second place the review's
 * shape is decided, which is the defect §8 of the design doc forbids.
 *
 * ⚠️ THE GRACEFUL PATH IS WHERE THE SIGNAL DIES — the design constraint the week
 * earned, and this page is where it would die most expensively. Three states
 * that a tolerant `if (!rows.length) return "All clear"` would collapse into one:
 *
 *   - fetch FAILED            → we do not know. Renders an error, never a tick.
 *   - no rows, quiet non-empty→ complete: everything declared is current.
 *   - no rows, quiet EMPTY    → nothing is DECLARED. An empty review is not a
 *                               clean one, and a tenant with no expectations is
 *                               the one case where a green page is a lie.
 *
 * ⚠️ IT MUST NOT FAIL QUIETLY, WHICH IS THE OPPOSITE OF ITS SIBLING.
 * `MyObligationsPrompt` swallows fetch errors on purpose — it is unasked-for
 * chrome on someone else's page. This page IS the thing the accountant opened;
 * silence here is the failure mode, not the courtesy.
 */
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Loader2, RefreshCw, ShieldQuestion } from "lucide-react";

import { Button } from "@/components/ui/button";
import { StatusPill, type StatusFamily } from "@/components/ui/status-pill";
import { getApiErrorMessage } from "@/lib/api-error";
import {
  completenessService,
  type CompletenessResult,
  type CompletenessRun,
  type Verdict,
} from "@/services/completeness-service";

/**
 * Verdict → how it reads. The status-key-keyed dict pattern (CLAUDE.md): the
 * verdict names a family, the family owns the tokens. Adding a verdict is one
 * row here and no raw colours anywhere.
 *
 * `unknown` is deliberately NOT neutral. It means the check could not run, which
 * is a thing to go and fix — rendering it the same grey as `declined` would file
 * a broken probe under "handled".
 */
const VERDICT_STYLE: Record<Verdict, { family: StatusFamily; label: string }> = {
  missing: { family: "error", label: "Missing" },
  partial: { family: "warning", label: "Partial" },
  unknown: { family: "warning", label: "Check failed" },
  reported_none: { family: "info", label: "Reported none" },
  declined: { family: "neutral", label: "Declined" },
  arrived: { family: "success", label: "Arrived" },
  not_yet_due: { family: "neutral", label: "Not yet due" },
};

export default function AccountingCompletenessTab() {
  const [asOf, setAsOf] = useState<string>(todayIso);
  const [result, setResult] = useState<CompletenessResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setResult(await completenessService.getReview(asOf));
    } catch (e) {
      // Clear the stale result. A previous period's verdicts rendered under a
      // failed refresh would be the worst outcome this page has: confidently
      // wrong about the date in the header.
      setResult(null);
      setError(getApiErrorMessage(e, "Could not load the completeness review."));
    } finally {
      setLoading(false);
    }
  }, [asOf]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-h3 font-semibold text-content-strong">
            Completeness
          </h2>
          <p className="mt-1 max-w-reading text-body-sm text-content-muted">
            What was owed for these periods, and whether it arrived. Obligations
            belong to roles, so they survive both the person and the mechanism.
          </p>
        </div>
        <div className="flex items-end gap-2">
          <label className="flex flex-col gap-1">
            <span className="text-caption text-content-muted">
              Complete through
            </span>
            <input
              type="date"
              value={asOf}
              max={todayIso()}
              onChange={(e) => setAsOf(e.target.value || todayIso())}
              className="rounded-base border border-border-base bg-surface-raised px-3 py-2 text-body-sm text-content-base focus-visible:border-accent focus-visible:outline-none"
            />
          </label>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void load()}
            disabled={loading}
          >
            <RefreshCw
              className={`mr-1.5 h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
        </div>
      </header>

      {error ? (
        <ReviewError message={error} onRetry={() => void load()} />
      ) : loading && !result ? (
        <div className="flex items-center gap-2 rounded-lg border border-border-subtle bg-surface-elevated px-4 py-6 text-body-sm text-content-muted">
          <Loader2 className="h-4 w-4 animate-spin" />
          Checking what was owed…
        </div>
      ) : result ? (
        <Review result={result} />
      ) : null}
    </div>
  );
}

function Review({ result }: { result: CompletenessResult }) {
  const { rows, quiet_summary, actionable_count } = result;

  // Nothing to show AND nothing counted quiet: no expectation resolved for this
  // tenant at all. Distinct from "complete", and said as such — a review with no
  // subject is the one state a green tick would misreport.
  if (rows.length === 0 && !quiet_summary) return <NothingDeclared />;

  return (
    <div className="space-y-4">
      <p className="text-body-sm text-content-base">
        {actionable_count > 0 ? (
          <>
            <span className="font-medium text-content-strong">
              {actionable_count}
            </span>{" "}
            {actionable_count === 1 ? "obligation needs" : "obligations need"}{" "}
            attention.
          </>
        ) : (
          "Nothing outstanding."
        )}
      </p>

      {rows.length > 0 && (
        <ul className="divide-y divide-border-subtle overflow-hidden rounded-lg border border-border-subtle bg-surface-elevated">
          {rows.map((run) => (
            <RunRow key={run.key + run.first} run={run} />
          ))}
        </ul>
      )}

      {/* Counted, never enumerated — a reader scanning for a problem should not
          walk past everything that is fine to find it. But the count is stated,
          because silence is what a reader fills in with an assumption. */}
      {quiet_summary && (
        <p className="text-caption text-content-muted">{quiet_summary}</p>
      )}
    </div>
  );
}

function RunRow({ run }: { run: CompletenessRun }) {
  const style = VERDICT_STYLE[run.verdict] ?? {
    family: "warning" as StatusFamily,
    label: run.verdict,
  };

  return (
    <li className="flex flex-wrap items-start gap-x-4 gap-y-2 px-4 py-3">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-body-sm font-medium text-content-strong">
            {run.label}
          </span>
          <StatusPill variant={style.family} label={style.label} />
        </div>
        <p className="mt-1 text-caption text-content-muted">{run.detail}</p>
      </div>
      <div className="shrink-0 text-right">
        <p className="text-caption text-content-base">{spanLabel(run)}</p>
        {/* WHOSE duty. Named on the row because "missing" without an owner is a
            complaint rather than something anyone can pick up. */}
        <p className="text-micro uppercase tracking-wide text-content-subtle">
          {run.role_slug}
        </p>
      </div>
    </li>
  );
}

function ReviewError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-status-error/30 bg-status-error-muted px-4 py-3">
      <AlertTriangle className="h-4 w-4 shrink-0 text-status-error" />
      <div className="min-w-0 flex-1">
        <p className="text-body-sm font-medium text-content-strong">
          The review did not run.
        </p>
        {/* Said outright: an unavailable review is not a clean one. This is the
            sentence that stops a failed fetch being read as a quiet month. */}
        <p className="text-caption text-content-muted">
          {message} No conclusion should be drawn about completeness from this
          screen until it loads.
        </p>
      </div>
      <Button variant="outline" size="sm" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}

function NothingDeclared() {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border-base bg-surface-sunken px-4 py-4">
      <ShieldQuestion className="h-4 w-4 shrink-0 text-content-muted" />
      <div className="min-w-0 flex-1">
        <p className="text-body-sm font-medium text-content-strong">
          No obligations are declared for this tenant.
        </p>
        <p className="text-caption text-content-muted">
          Nothing is being checked, so nothing can be found missing. This is not
          the same as a complete period.
        </p>
      </div>
    </div>
  );
}

/** "14 Aug" for one period, "8–14 Aug" for a run. The count is already in
 *  `detail`; repeating it here would say the same thing twice in one row. */
function spanLabel(run: CompletenessRun): string {
  const first = fmtDay(run.first);
  return run.periods === 1 && run.first === run.last
    ? first
    : `${first} – ${fmtDay(run.last)}`;
}

/** Parsed by split, NOT `new Date(iso)` — a bare date parses as UTC midnight and
 *  renders the previous day at any negative UTC offset, which would misdate
 *  every row for every US tenant. Same reason as `formatLockedDays` next door. */
function fmtDay(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

/** Local calendar day, not `toISOString()` — that converts to UTC first and
 *  hands back tomorrow's date for anyone east of Greenwich in the evening. */
function todayIso(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}
