/**
 * "You haven't logged 11 Aug." — the nil-claim pattern's arrival half. CR-2 A-3.
 *
 * ⚠️ PROMPTED, NOT REMEMBERED. A quiet day produces no reason to open anything,
 * which is exactly how the gap forms. A "nothing to log today" control that
 * lives ONLY on the log page is satisfied by precisely the people who were
 * going to satisfy it anyway — everyone except the ones the review exists to
 * catch. So this component is designed to be mounted where the person already
 * is, not where the obligation is filed.
 *
 * ⚠️ IT IS THE PATTERN, NOT ONE SURFACE. Three obligations need this and each
 * belongs to a different person in a different place: production log
 * (production, terminal), deliveries (driver, phone), toolbox talk
 * (safety_trainer, weekly). Nothing here names production — it renders whatever
 * the caller's role owes, so the driver's and safety trainer's versions are a
 * mount point, not a new component.
 *
 * ⚠️ ABUSE IS VISIBLE, NOT HARD. Filing "nothing happened" is deliberately one
 * click and no friction — friction would be paying in the wrong currency, and
 * an affordance slower than skipping it does not get used. The safeguards are
 * structural instead: the claim is signed with the claimant's name and role,
 * it renders as its own verdict rather than as work, and a run of them shows up
 * on the accountant's review as a finding.
 */
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Check, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { getApiErrorMessage } from "@/lib/api-error";
import {
  completenessService,
  type CompletenessRun,
} from "@/services/completeness-service";
import { toast } from "sonner";

interface Props {
  /** Render only this obligation. Omit to show everything the role owes. */
  expectationKey?: string;
  /** Called after a successful claim so the host can refresh its own data. */
  onFiled?: () => void;
}

export function MyObligationsPrompt({ expectationKey, onFiled }: Props) {
  const [runs, setRuns] = useState<CompletenessRun[] | null>(null);
  const [filing, setFiling] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await completenessService.getMyObligations();
      setRuns(
        res.rows.filter(
          (r) => r.actionable && (!expectationKey || r.key === expectationKey),
        ),
      );
    } catch {
      // Deliberately silent: this is an unasked-for prompt on someone else's
      // page. A failed fetch must not put an error banner over the work they
      // actually came to do. It reappears on next load.
      setRuns([]);
    }
  }, [expectationKey]);

  useEffect(() => {
    void load();
  }, [load]);

  async function fileNothing(run: CompletenessRun) {
    setFiling(run.key + run.first);
    try {
      await completenessService.fileNilClaim({
        expectation_key: run.key,
        // The OLDEST open period, one at a time. Clearing a six-day run with a
        // single click would let one assertion stand for six separate days
        // nobody looked at — the claim is per-period because the obligation is.
        period_start: run.first,
        period_end: run.first,
      });
      toast.success(`Recorded: nothing to report for ${fmtDay(run.first)}.`);
      await load();
      onFiled?.();
    } catch (e) {
      toast.error(getApiErrorMessage(e, "Could not record that."));
    } finally {
      setFiling(null);
    }
  }

  if (!runs || runs.length === 0) return null;

  return (
    <div className="space-y-2">
      {runs.map((run) => {
        const busy = filing === run.key + run.first;
        return (
          <div
            key={run.key + run.first}
            className="flex flex-wrap items-center gap-3 rounded-lg border border-status-warning/30 bg-status-warning-muted px-4 py-3"
          >
            <AlertTriangle className="h-4 w-4 shrink-0 text-status-warning" />
            <div className="min-w-0 flex-1">
              <p className="text-body-sm font-medium text-content-strong">
                {run.label} — nothing recorded for {fmtDay(run.first)}
              </p>
              <p className="text-caption text-content-muted">
                {run.periods > 1
                  ? `${run.periods} days open, oldest first.`
                  : run.detail}
              </p>
            </div>
            {/* Both choices sit side by side and cost the same. Making the
                honest answer harder than the convenient one is how the
                convenient one becomes the default. */}
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => void fileNothing(run)}
            >
              {busy ? (
                <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
              ) : (
                <Check className="mr-1 h-3.5 w-3.5" />
              )}
              Nothing to log
            </Button>
          </div>
        );
      })}
    </div>
  );
}

/** Parsed by split, not `new Date(iso)` — a bare date parses as UTC midnight
 *  and renders the previous day at any negative offset. */
function fmtDay(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}
