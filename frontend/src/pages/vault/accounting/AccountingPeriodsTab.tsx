/**
 * Periods & Locks sub-tab — Phase V-1e.
 *
 * Asymmetric destructive/non-destructive UX:
 *   - Locking a period requires typing the exact period name
 *     ("March 2026") to confirm. Locking blocks writes to that
 *     period, so the friction matches the stakes.
 *   - Unlocking is a simple confirm — it restores the prior write
 *     capability, and if it was a mistake to lock, unlocking is
 *     cheap.
 */

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Lock, Unlock, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  accountingAdminService,
  type PeriodRow,
  type PeriodAuditRow,
} from "@/services/accounting-admin-service";

function formatRelativeAge(iso: string | null): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  const mins = Math.max(0, Math.floor((Date.now() - then) / 60_000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export default function AccountingPeriodsTab() {
  const [year, setYear] = useState<number>(new Date().getFullYear());
  const [periods, setPeriods] = useState<PeriodRow[] | null>(null);
  const [audit, setAudit] = useState<PeriodAuditRow[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Lock / unlock modal state
  const [lockTarget, setLockTarget] = useState<PeriodRow | null>(null);
  const [typedConfirm, setTypedConfirm] = useState("");
  const [unlockTarget, setUnlockTarget] = useState<PeriodRow | null>(null);
  const [mutating, setMutating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [p, a] = await Promise.all([
        accountingAdminService.listPeriods(year),
        accountingAdminService.listPeriodAudit(10),
      ]);
      setPeriods(p.periods);
      setAudit(a.events);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load periods";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [year]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleLock() {
    if (!lockTarget) return;
    if (typedConfirm !== lockTarget.display_name) return;
    setMutating(true);
    try {
      await accountingAdminService.lockPeriod(lockTarget.id);
      setLockTarget(null);
      setTypedConfirm("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Lock failed");
    } finally {
      setMutating(false);
    }
  }

  async function handleUnlock() {
    if (!unlockTarget) return;
    setMutating(true);
    try {
      await accountingAdminService.unlockPeriod(unlockTarget.id);
      setUnlockTarget(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unlock failed");
    } finally {
      setMutating(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <label htmlFor="year" className="text-sm font-medium text-gray-700">
            Year
          </label>
          <select
            id="year"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm"
          >
            {Array.from({ length: 6 }, (_, i) => new Date().getFullYear() - i + 1).map(
              (y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ),
            )}
          </select>
        </div>
        <Button variant="outline" size="sm" onClick={() => void load()}>
          <RefreshCw className="mr-1 h-3.5 w-3.5" /> Refresh
        </Button>
      </div>

      {error && (
        <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      <section className="rounded border bg-white">
        <div className="flex items-center justify-between border-b p-4">
          <h2 className="text-sm font-semibold text-gray-700">
            Accounting periods
          </h2>
          <p className="text-xs text-gray-500">
            Lock = block writes dated in this month. Unlock = restore
            write capability.
          </p>
        </div>
        {loading && <div className="p-4 text-sm text-gray-500">Loading…</div>}
        {periods && periods.length === 0 && (
          <div className="p-4 text-sm text-gray-500">
            No periods yet for {year}.
          </div>
        )}
        {periods && periods.length > 0 && (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-2 font-medium">Period</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Closed at</th>
                <th className="px-4 py-2 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {periods.map((p) => (
                <tr key={p.id} className="border-t">
                  <td className="px-4 py-2 font-medium text-gray-900">
                    {p.display_name}
                  </td>
                  <td className="px-4 py-2">
                    {p.status === "closed" ? (
                      <Badge variant="secondary" className="bg-red-100 text-red-800">
                        <Lock className="mr-1 h-3 w-3" /> Closed
                      </Badge>
                    ) : (
                      <Badge variant="secondary" className="bg-green-100 text-green-800">
                        Open
                      </Badge>
                    )}
                  </td>
                  <td className="px-4 py-2 text-gray-600">
                    {p.closed_at ? formatRelativeAge(p.closed_at) : "—"}
                  </td>
                  <td className="px-4 py-2 text-right">
                    {p.status === "closed" ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setUnlockTarget(p)}
                      >
                        <Unlock className="mr-1 h-3.5 w-3.5" /> Unlock
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setLockTarget(p);
                          setTypedConfirm("");
                        }}
                      >
                        <Lock className="mr-1 h-3.5 w-3.5" /> Close period
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="rounded border bg-white">
        <div className="border-b p-4">
          <h2 className="text-sm font-semibold text-gray-700">
            Recent activity
          </h2>
        </div>
        {audit && audit.length === 0 && (
          <div className="p-4 text-sm text-gray-500">
            No period-lock activity yet.
          </div>
        )}
        {audit && audit.length > 0 && (
          <ul className="divide-y">
            {audit.map((e) => (
              <li key={e.id} className="flex items-center gap-3 px-4 py-2 text-sm">
                {e.action === "period_locked" ? (
                  <Lock className="h-4 w-4 text-red-600" />
                ) : (
                  <Unlock className="h-4 w-4 text-green-600" />
                )}
                <span className="flex-1">
                  {e.changes?.display_name ?? "Unknown period"} {" "}
                  <span className="text-gray-500">
                    {e.action === "period_locked" ? "closed" : "reopened"}
                  </span>
                </span>
                <span className="text-xs text-gray-500">
                  {formatRelativeAge(e.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Type-to-confirm modal for locking */}
      {lockTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="max-w-md rounded bg-white p-6">
            <div className="mb-4 flex items-center gap-2 text-amber-700">
              <AlertTriangle className="h-5 w-5" />
              <h2 className="text-base font-semibold">
                Close period: {lockTarget.display_name}
              </h2>
            </div>
            <p className="mb-4 text-sm text-gray-700">
              This will prevent any writes to this period. Invoices,
              bills, journal entries, and payments dated in{" "}
              {lockTarget.display_name} will be rejected until this
              period is unlocked.
            </p>
            <p className="mb-2 text-sm text-gray-700">
              Type <strong>{lockTarget.display_name}</strong> to confirm.
            </p>
            <input
              type="text"
              value={typedConfirm}
              onChange={(e) => setTypedConfirm(e.target.value)}
              className="mb-4 w-full rounded border border-gray-300 px-3 py-2 text-sm"
              placeholder={lockTarget.display_name}
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => {
                  setLockTarget(null);
                  setTypedConfirm("");
                }}
                disabled={mutating}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                disabled={
                  typedConfirm !== lockTarget.display_name || mutating
                }
                onClick={handleLock}
              >
                Close period
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Simple-confirm modal for unlocking */}
      {unlockTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="max-w-md rounded bg-white p-6">
            <h2 className="mb-4 text-base font-semibold">
              Unlock period: {unlockTarget.display_name}?
            </h2>
            <p className="mb-4 text-sm text-gray-700">
              This will allow writes to this period again.
            </p>
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setUnlockTarget(null)}
                disabled={mutating}
              >
                Cancel
              </Button>
              <Button onClick={handleUnlock} disabled={mutating}>
                Unlock
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
