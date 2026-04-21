import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StatusPill } from "@/components/ui/status-pill";
import { cn } from "@/lib/utils";
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

// Phase II Batch 1a — status pill replaced with StatusPill primitive.
// StatusPill's STATUS_MAP already covers pending/running/approved/complete/
// rejected/failed. awaiting_approval is a custom state — map to warning.
function statusBadge(status: string) {
  const STATUS_TO_PILL: Record<
    string,
    { statusKey: string; pulse?: boolean }
  > = {
    pending: { statusKey: "pending", pulse: true },
    running: { statusKey: "pending", pulse: true },
    awaiting_approval: { statusKey: "pending_review" },
    approved: { statusKey: "approved" },
    complete: { statusKey: "completed" },
    rejected: { statusKey: "rejected" },
    failed: { statusKey: "failed" },
  };
  const m = STATUS_TO_PILL[status] ?? { statusKey: status };
  return (
    <StatusPill status={m.statusKey} className={m.pulse ? "animate-pulse" : undefined}>
      {status.replace(/_/g, " ")}
    </StatusPill>
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
// Component — Aesthetic Arc Phase II Batch 1a refresh
// ---------------------------------------------------------------------------
//
// Migrated from 3 hardcoded `bg-white` section cards + native form elements +
// Tailwind color status pill map to:
//   - <Card> primitive (Session 2) for the 3 sections
//   - <Input> primitive (Session 2) for date inputs (handles type="date"
//     natively with DL chrome; works in both modes)
//   - <Label> primitive (Session 2) for form labels
//   - <StatusPill> primitive (Session 3) for status pills
//   - Page title uses DL typography scale
//   - Anomaly warning uses text-status-warning token
//
// Native <select> kept (browser dropdown renders per-OS; DL tokens style
// the closed-state chrome). Full Select primitive migration deferred —
// would require 12-option mapping to SelectItem children, disproportionate
// scope for a settings-tier page.

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
      <h1 className="text-h2 font-plex-serif font-medium text-content-strong">
        Accounting Agents
      </h1>

      {/* Section A — Run an Agent */}
      <Card>
        <CardHeader>
          <CardTitle>Run an Agent</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={handleSubmit}
            className="flex flex-wrap items-end gap-4"
          >
            <div className="space-y-1">
              <Label htmlFor="jobType">Job Type</Label>
              <select
                id="jobType"
                value={jobType}
                onChange={(e) => setJobType(e.target.value)}
                className="h-10 min-w-[220px] rounded-sm border border-border-base bg-surface-raised px-3 text-body-sm text-content-base focus-visible:outline-none focus-visible:border-brass focus-visible:ring-2 focus-visible:ring-brass/30 transition-colors duration-quick ease-settle"
              >
                {JOB_TYPE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="periodStart">Period Start</Label>
              <Input
                id="periodStart"
                type="date"
                value={periodStart}
                onChange={(e) => setPeriodStart(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="periodEnd">Period End</Label>
              <Input
                id="periodEnd"
                type="date"
                value={periodEnd}
                onChange={(e) => setPeriodEnd(e.target.value)}
              />
            </div>
            <div className="flex items-center gap-2 pb-2">
              <input
                type="checkbox"
                id="dryRun"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
                className="h-4 w-4 accent-brass"
              />
              <Label
                htmlFor="dryRun"
                className="cursor-pointer"
                title="Read-only mode: generates report but commits nothing"
              >
                Dry run
              </Label>
            </div>
            <Button type="submit" disabled={submitting}>
              <Play className="h-4 w-4 mr-1" />
              {submitting ? "Starting..." : "Run Agent"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Section B — Recent Runs */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle>Recent Runs</CardTitle>
          <Button variant="outline" size="sm" onClick={fetchData}>
            <RefreshCw className="h-4 w-4 mr-1" />
            Refresh
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-6 text-center text-content-muted">Loading...</div>
          ) : jobs.length === 0 ? (
            <div className="p-6 text-center text-content-muted">
              No agent runs yet. Run your first agent above.
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-body-sm">
                  <thead>
                    <tr className="border-b border-border-subtle bg-surface-sunken/60">
                      <th className="px-4 py-3 text-left font-medium text-content-muted">
                        Type
                      </th>
                      <th className="px-4 py-3 text-left font-medium text-content-muted">
                        Period
                      </th>
                      <th className="px-4 py-3 text-left font-medium text-content-muted">
                        Status
                      </th>
                      <th className="px-4 py-3 text-center font-medium text-content-muted">
                        Anomalies
                      </th>
                      <th className="px-4 py-3 text-center font-medium text-content-muted">
                        Dry Run
                      </th>
                      <th className="px-4 py-3 text-left font-medium text-content-muted">
                        Started
                      </th>
                      <th className="px-4 py-3 text-left font-medium text-content-muted">
                        Duration
                      </th>
                      <th className="px-4 py-3 text-left font-medium text-content-muted">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.map((job) => (
                      <tr
                        key={job.id}
                        className="border-b border-border-subtle hover:bg-brass-subtle/40"
                      >
                        <td className="px-4 py-3 font-medium text-content-base">
                          {getJobLabel(job.job_type)}
                        </td>
                        <td className="px-4 py-3 text-content-muted">
                          {job.period_start} – {job.period_end}
                        </td>
                        <td className="px-4 py-3">{statusBadge(job.status)}</td>
                        <td className="px-4 py-3 text-center">
                          {job.anomaly_count > 0 ? (
                            <span
                              className={cn(
                                "inline-flex items-center gap-1 font-medium",
                                "text-status-warning",
                              )}
                            >
                              <AlertTriangle className="h-3 w-3" />
                              {job.anomaly_count}
                            </span>
                          ) : (
                            <span className="text-content-muted">0</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {job.dry_run ? (
                            <Badge variant="outline">Yes</Badge>
                          ) : (
                            <span className="text-content-muted">No</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-content-muted text-caption">
                          {job.started_at
                            ? new Date(job.started_at).toLocaleString()
                            : "—"}
                        </td>
                        <td className="px-4 py-3 text-content-muted text-caption">
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
              <div className="flex items-center justify-between px-4 py-3 border-t border-border-subtle">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 0}
                  onClick={() => setPage((p) => p - 1)}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="text-body-sm text-content-muted">
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
        </CardContent>
      </Card>

      {/* Section C — Period Locks */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lock className="h-5 w-5" />
            Period Locks
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {locks.length === 0 ? (
            <div className="p-6 text-center text-content-muted">
              No locked periods
            </div>
          ) : (
            <div className="divide-y divide-border-subtle">
              {locks.map((lock) => (
                <div
                  key={lock.id}
                  className="flex items-center justify-between px-6 py-3"
                >
                  <div>
                    <span className="font-medium text-content-base">
                      {lock.period_start} – {lock.period_end}
                    </span>
                    <span className="text-body-sm text-content-muted ml-3">
                      Locked {new Date(lock.locked_at).toLocaleDateString()}
                    </span>
                    {lock.lock_reason && (
                      <span className="text-body-sm text-content-muted ml-2">
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
        </CardContent>
      </Card>
    </div>
  );
}
