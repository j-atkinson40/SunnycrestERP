import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Play,
  RefreshCw,
  Lock,
  Unlock,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AgentJob {
  id: string;
  job_type: string;
  status: string;
  period_start: string | null;
  period_end: string | null;
  dry_run: boolean;
  anomaly_count: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

interface PeriodLock {
  id: string;
  period_start: string;
  period_end: string;
  locked_at: string;
  lock_reason: string | null;
  locked_by: string | null;
  is_active: boolean;
}

const JOB_TYPE_OPTIONS = [
  { value: "month_end_close", label: "Month-End Close" },
  { value: "ar_collections", label: "AR Collections Review" },
  { value: "unbilled_orders", label: "Unbilled Orders Audit" },
  { value: "cash_receipts_matching", label: "Cash Receipts Matching" },
  { value: "expense_categorization", label: "Expense Categorization" },
  { value: "estimated_tax_prep", label: "Estimated Tax Prep" },
  { value: "inventory_reconciliation", label: "Inventory Reconciliation" },
  { value: "budget_vs_actual", label: "Budget vs. Actual" },
  { value: "1099_prep", label: "1099 Prep" },
  { value: "year_end_close", label: "Year-End Close" },
  { value: "tax_package", label: "Tax Package" },
  { value: "annual_budget", label: "Annual Budget" },
];

function getJobLabel(type: string) {
  return JOB_TYPE_OPTIONS.find((o) => o.value === type)?.label || type;
}

function statusBadge(status: string) {
  const map: Record<string, { color: string; pulse?: boolean }> = {
    pending: { color: "bg-blue-100 text-blue-700" },
    running: { color: "bg-blue-100 text-blue-700", pulse: true },
    awaiting_approval: { color: "bg-amber-100 text-amber-700" },
    approved: { color: "bg-green-100 text-green-700" },
    complete: { color: "bg-green-100 text-green-700" },
    rejected: { color: "bg-red-100 text-red-700" },
    failed: { color: "bg-red-100 text-red-700" },
  };
  const s = map[status] || { color: "bg-gray-100 text-gray-700" };
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${s.color} ${s.pulse ? "animate-pulse" : ""}`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}

function defaultPeriod() {
  const now = new Date();
  const first = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const last = new Date(now.getFullYear(), now.getMonth(), 0);
  return {
    start: first.toISOString().slice(0, 10),
    end: last.toISOString().slice(0, 10),
  };
}

function formatDuration(started: string | null, completed: string | null) {
  if (!started) return "—";
  const s = new Date(started).getTime();
  const e = completed ? new Date(completed).getTime() : Date.now();
  const sec = Math.round((e - s) / 1000);
  if (sec < 60) return `${sec}s`;
  return `${Math.floor(sec / 60)}m ${sec % 60}s`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AgentDashboard() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<AgentJob[]>([]);
  const [locks, setLocks] = useState<PeriodLock[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [page, setPage] = useState(0);

  // Form state
  const period = defaultPeriod();
  const [jobType, setJobType] = useState("month_end_close");
  const [periodStart, setPeriodStart] = useState(period.start);
  const [periodEnd, setPeriodEnd] = useState(period.end);
  const [dryRun, setDryRun] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [jobsRes, locksRes] = await Promise.all([
        apiClient.get("/api/v1/agents/accounting", {
          params: { limit: 20, offset: page * 20 },
        }),
        apiClient.get("/api/v1/agents/periods/locked"),
      ]);
      setJobs(jobsRes.data);
      setLocks(locksRes.data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Poll running jobs
  useEffect(() => {
    const hasRunning = jobs.some(
      (j) => j.status === "pending" || j.status === "running",
    );
    if (!hasRunning) return;
    const id = setInterval(fetchData, 3000);
    return () => clearInterval(id);
  }, [jobs, fetchData]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await apiClient.post("/api/v1/agents/accounting", {
        job_type: jobType,
        period_start: periodStart,
        period_end: periodEnd,
        dry_run: dryRun,
      });
      fetchData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Failed to create job");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleUnlock(lockId: string) {
    if (!confirm("Are you sure you want to unlock this period? This allows financial writes to the period.")) return;
    try {
      await apiClient.post(`/api/v1/agents/periods/${lockId}/unlock`);
      fetchData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Failed to unlock");
    }
  }

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold">Accounting Agents</h1>

      {/* Section A — Run an Agent */}
      <div className="rounded-lg border bg-white p-6">
        <h2 className="text-lg font-semibold mb-4">Run an Agent</h2>
        <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Job Type</label>
            <select
              value={jobType}
              onChange={(e) => setJobType(e.target.value)}
              className="rounded-md border px-3 py-2 text-sm min-w-[220px]"
            >
              {JOB_TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              Period Start
            </label>
            <input
              type="date"
              value={periodStart}
              onChange={(e) => setPeriodStart(e.target.value)}
              className="rounded-md border px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              Period End
            </label>
            <input
              type="date"
              value={periodEnd}
              onChange={(e) => setPeriodEnd(e.target.value)}
              className="rounded-md border px-3 py-2 text-sm"
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="dryRun"
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
              className="h-4 w-4"
            />
            <label htmlFor="dryRun" className="text-sm" title="Read-only mode: generates report but commits nothing">
              Dry run
            </label>
          </div>
          <Button type="submit" disabled={submitting}>
            <Play className="h-4 w-4 mr-1" />
            {submitting ? "Starting..." : "Run Agent"}
          </Button>
        </form>
      </div>

      {/* Section B — Recent Runs */}
      <div className="rounded-lg border bg-white">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold">Recent Runs</h2>
          <Button variant="outline" size="sm" onClick={fetchData}>
            <RefreshCw className="h-4 w-4 mr-1" />
            Refresh
          </Button>
        </div>
        {loading ? (
          <div className="p-6 text-center text-muted-foreground">
            Loading...
          </div>
        ) : jobs.length === 0 ? (
          <div className="p-6 text-center text-muted-foreground">
            No agent runs yet. Run your first agent above.
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-4 py-3 text-left font-medium">Type</th>
                    <th className="px-4 py-3 text-left font-medium">Period</th>
                    <th className="px-4 py-3 text-left font-medium">Status</th>
                    <th className="px-4 py-3 text-center font-medium">
                      Anomalies
                    </th>
                    <th className="px-4 py-3 text-center font-medium">
                      Dry Run
                    </th>
                    <th className="px-4 py-3 text-left font-medium">
                      Started
                    </th>
                    <th className="px-4 py-3 text-left font-medium">
                      Duration
                    </th>
                    <th className="px-4 py-3 text-left font-medium">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job) => (
                    <tr key={job.id} className="border-b hover:bg-muted/30">
                      <td className="px-4 py-3 font-medium">
                        {getJobLabel(job.job_type)}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {job.period_start} – {job.period_end}
                      </td>
                      <td className="px-4 py-3">{statusBadge(job.status)}</td>
                      <td className="px-4 py-3 text-center">
                        {job.anomaly_count > 0 ? (
                          <span className="inline-flex items-center gap-1 text-amber-600 font-medium">
                            <AlertTriangle className="h-3 w-3" />
                            {job.anomaly_count}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">0</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {job.dry_run ? (
                          <Badge variant="outline">Yes</Badge>
                        ) : (
                          "No"
                        )}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground text-xs">
                        {job.started_at
                          ? new Date(job.started_at).toLocaleString()
                          : "—"}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground text-xs">
                        {formatDuration(job.started_at, job.completed_at)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() =>
                              navigate(`/agents/${job.id}/review`)
                            }
                          >
                            View
                          </Button>
                          {job.status === "awaiting_approval" && (
                            <Button
                              size="sm"
                              onClick={() =>
                                navigate(`/agents/${job.id}/review`)
                              }
                            >
                              Review
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between px-4 py-3 border-t">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {page + 1}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={jobs.length < 20}
                onClick={() => setPage((p) => p + 1)}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </>
        )}
      </div>

      {/* Section C — Period Locks */}
      <div className="rounded-lg border bg-white">
        <div className="px-6 py-4 border-b">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Lock className="h-5 w-5" />
            Period Locks
          </h2>
        </div>
        {locks.length === 0 ? (
          <div className="p-6 text-center text-muted-foreground">
            No locked periods
          </div>
        ) : (
          <div className="divide-y">
            {locks.map((lock) => (
              <div
                key={lock.id}
                className="flex items-center justify-between px-6 py-3"
              >
                <div>
                  <span className="font-medium">
                    {lock.period_start} – {lock.period_end}
                  </span>
                  <span className="text-sm text-muted-foreground ml-3">
                    Locked {new Date(lock.locked_at).toLocaleDateString()}
                  </span>
                  {lock.lock_reason && (
                    <span className="text-sm text-muted-foreground ml-2">
                      — {lock.lock_reason}
                    </span>
                  )}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleUnlock(lock.id)}
                >
                  <Unlock className="h-4 w-4 mr-1" />
                  Unlock
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
