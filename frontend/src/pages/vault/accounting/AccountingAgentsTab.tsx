/**
 * Agent Schedules sub-tab — Phase V-1e.
 *
 * CONFIGURATION, not trigger. This tab edits when each of the 12
 * accounting agents runs on its own schedule. The tenant-facing
 * Agents Hub (/agents) is where humans actually kick off runs
 * and approve results — that stays untouched. This surface is the
 * platform admin saying "run month-end-close on the 3rd at 3am".
 */

import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  accountingAdminService,
  type AgentScheduleRow,
  type AgentJobListItem,
} from "@/services/accounting-admin-service";

const AGENT_LABELS: Record<string, string> = {
  month_end_close: "Month-End Close",
  ar_collections: "AR Collections",
  unbilled_orders: "Unbilled Orders",
  cash_receipts_matching: "Cash Receipts Matching",
  expense_categorization: "Expense Categorization",
  estimated_tax_prep: "Estimated Tax Prep",
  inventory_reconciliation: "Inventory Reconciliation",
  budget_vs_actual: "Budget vs. Actual",
  "1099_prep": "1099 Prep",
  year_end_close: "Year-End Close",
  tax_package: "Tax Package",
  annual_budget: "Annual Budget",
};

function labelFor(jobType: string): string {
  return AGENT_LABELS[jobType] ?? jobType;
}

function humanize(sched: AgentScheduleRow): string {
  if (!sched.is_enabled) return "Disabled";
  if (sched.cron_expression) return sched.cron_expression;
  const parts: string[] = [];
  if (sched.run_day_of_month !== null) {
    parts.push(`day ${sched.run_day_of_month} of month`);
  }
  if (sched.run_hour !== null) {
    const h = sched.run_hour;
    parts.push(`at ${h < 10 ? "0" + h : h}:00 ${sched.timezone}`);
  }
  return parts.length ? parts.join(", ") : "Enabled (no schedule set)";
}

function formatRelativeAge(iso: string | null): string {
  if (!iso) return "never";
  const then = new Date(iso).getTime();
  const mins = Math.max(0, Math.floor((Date.now() - then) / 60_000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function statusTone(status: string): string {
  if (["complete", "approved"].includes(status))
    return "bg-green-100 text-green-800";
  if (["failed", "rejected"].includes(status))
    return "bg-red-100 text-red-800";
  if (["running", "awaiting_approval"].includes(status))
    return "bg-yellow-100 text-yellow-800";
  return "bg-gray-100 text-gray-700";
}

export default function AccountingAgentsTab() {
  const [schedules, setSchedules] = useState<AgentScheduleRow[] | null>(null);
  const [jobs, setJobs] = useState<AgentJobListItem[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, j] = await Promise.all([
        accountingAdminService.listAgentSchedules(),
        accountingAdminService.listRecentJobs(20),
      ]);
      setSchedules(s);
      setJobs(j);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleToggle(jobType: string) {
    setToggling(jobType);
    try {
      await accountingAdminService.toggleAgentSchedule(jobType);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Toggle failed");
    } finally {
      setToggling(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-600">
          Configure when each accounting agent runs on a recurring
          schedule. Manual runs + approvals happen in the Agents Hub.
        </p>
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
        <div className="border-b p-4">
          <h2 className="text-sm font-semibold text-gray-700">
            Agent schedules
          </h2>
        </div>
        {loading && !schedules && (
          <div className="p-4 text-sm text-gray-500">Loading…</div>
        )}
        {schedules && schedules.length === 0 && (
          <div className="p-4 text-sm text-gray-500">
            No schedules configured. Schedules are created on first
            admin configuration — or an admin can run an agent manually
            to seed one via the Agents Hub.
          </div>
        )}
        {schedules && schedules.length > 0 && (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-2 font-medium">Agent</th>
                <th className="px-4 py-2 font-medium">Schedule</th>
                <th className="px-4 py-2 font-medium">Last run</th>
                <th className="px-4 py-2 font-medium text-right">Enabled</th>
              </tr>
            </thead>
            <tbody>
              {schedules.map((s) => (
                <tr key={s.id} className="border-t">
                  <td className="px-4 py-2 font-medium text-gray-900">
                    {labelFor(s.job_type)}
                  </td>
                  <td className="px-4 py-2 text-gray-600">{humanize(s)}</td>
                  <td className="px-4 py-2 text-gray-600">
                    {formatRelativeAge(s.last_run_at)}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <Button
                      size="sm"
                      variant={s.is_enabled ? "default" : "outline"}
                      disabled={toggling === s.job_type}
                      onClick={() => handleToggle(s.job_type)}
                    >
                      {s.is_enabled ? "Enabled" : "Disabled"}
                    </Button>
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
            Recent jobs
          </h2>
        </div>
        {jobs && jobs.length === 0 && (
          <div className="p-4 text-sm text-gray-500">
            No recent agent activity.
          </div>
        )}
        {jobs && jobs.length > 0 && (
          <ul className="divide-y">
            {jobs.map((j) => (
              <li
                key={j.id}
                className="flex items-center gap-3 px-4 py-2 text-sm"
              >
                <span className="flex-1 font-medium text-gray-900">
                  {labelFor(j.job_type)}
                </span>
                <Badge variant="secondary" className={statusTone(j.status)}>
                  {j.status}
                </Badge>
                <span className="w-24 text-right text-xs text-gray-500">
                  {formatRelativeAge(j.started_at ?? j.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
