import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import apiClient from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Info,
  Clock,
  ChevronDown,
  ChevronRight,
  ArrowLeft,
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
  run_log: RunLogEntry[];
  report_payload: Record<string, any> | null;
  started_at: string | null;
  completed_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
  rejection_reason: string | null;
  error_message: string | null;
  created_at: string;
}

interface RunLogEntry {
  step_number: number;
  step_name: string;
  status: string;
  duration_ms: number | null;
  message: string;
  anomaly_count: number;
}

interface Anomaly {
  id: string;
  severity: string;
  anomaly_type: string;
  entity_type: string | null;
  entity_id: string | null;
  description: string;
  amount: number | null;
  resolved: boolean;
  resolution_note: string | null;
}

const JOB_LABELS: Record<string, string> = {
  month_end_close: "Month-End Close",
  ar_collections: "AR Collections Review",
  unbilled_orders: "Unbilled Orders Audit",
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

function severityIcon(severity: string) {
  if (severity === "critical")
    return <AlertTriangle className="h-4 w-4 text-red-600" />;
  if (severity === "warning")
    return <AlertTriangle className="h-4 w-4 text-amber-500" />;
  return <Info className="h-4 w-4 text-blue-500" />;
}

function severityBadge(severity: string) {
  const colors: Record<string, string> = {
    critical: "bg-red-100 text-red-700",
    warning: "bg-amber-100 text-amber-700",
    info: "bg-blue-100 text-blue-700",
  };
  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-medium ${colors[severity] || "bg-gray-100 text-gray-700"}`}
    >
      {severity}
    </span>
  );
}

function statusBadge(status: string) {
  const colors: Record<string, string> = {
    pending: "bg-blue-100 text-blue-700",
    running: "bg-blue-100 text-blue-700",
    awaiting_approval: "bg-amber-100 text-amber-700",
    approved: "bg-green-100 text-green-700",
    complete: "bg-green-100 text-green-700",
    rejected: "bg-red-100 text-red-700",
    failed: "bg-red-100 text-red-700",
  };
  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-medium ${colors[status] || "bg-gray-100 text-gray-700"}`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ApprovalReview() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<AgentJob | null>(null);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [loading, setLoading] = useState(true);
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [resolveNote, setResolveNote] = useState<Record<string, string>>({});
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set());
  const [showRunLog, setShowRunLog] = useState(false);

  const fetchData = useCallback(async () => {
    if (!jobId) return;
    try {
      const [jobRes, anomRes] = await Promise.all([
        apiClient.get(`/api/v1/agents/accounting/${jobId}`),
        apiClient.get(`/api/v1/agents/accounting/${jobId}/anomalies`),
      ]);
      setJob(jobRes.data);
      setAnomalies(anomRes.data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function handleApprove() {
    if (
      !confirm(
        `This will lock ${job?.period_start} – ${job?.period_end} and cannot be undone without admin access. Continue?`,
      )
    )
      return;
    setApproving(true);
    try {
      await apiClient.post(`/api/v1/agents/accounting/${jobId}`, {
        // Use the authenticated endpoint
      });
      // If there's an approval token in URL, use that
      // Otherwise the backend processes via authenticated user
      fetchData();
    } catch {
      // fallback
    }
    setApproving(false);
  }

  async function handleReject() {
    if (!rejectReason.trim()) {
      alert("Rejection reason is required");
      return;
    }
    setRejecting(true);
    try {
      // Note: approval is done via token from email, but in-app we'd need
      // the token or a separate authenticated endpoint
      fetchData();
    } catch {
      // ignore
    }
    setRejecting(false);
  }

  async function handleResolveAnomaly(anomalyId: string) {
    const note = resolveNote[anomalyId];
    if (!note?.trim()) return;
    try {
      await apiClient.post(
        `/api/v1/agents/accounting/${jobId}/anomalies/${anomalyId}/resolve`,
        { resolution_note: note },
      );
      setAnomalies((prev) =>
        prev.map((a) =>
          a.id === anomalyId ? { ...a, resolved: true, resolution_note: note } : a,
        ),
      );
    } catch {
      alert("Failed to resolve anomaly");
    }
  }

  function toggleStep(step: number) {
    setExpandedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(step)) next.delete(step);
      else next.add(step);
      return next;
    });
  }

  if (loading) {
    return (
      <div className="p-6 text-center text-muted-foreground">Loading...</div>
    );
  }

  if (!job) {
    return <div className="p-6 text-center">Job not found</div>;
  }

  const label = JOB_LABELS[job.job_type] || job.job_type;
  const period = `${job.period_start} – ${job.period_end}`;
  const criticalCount = anomalies.filter((a) => a.severity === "critical").length;
  const warningCount = anomalies.filter((a) => a.severity === "warning").length;
  const infoCount = anomalies.filter((a) => a.severity === "info").length;
  const steps = job.report_payload?.steps || {};
  const canAct = job.status === "awaiting_approval";

  return (
    <div className="space-y-6 p-6 max-w-4xl mx-auto">
      {/* Back button */}
      <button
        onClick={() => navigate("/agents")}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Agent Dashboard
      </button>

      {/* Top bar */}
      <div className="rounded-lg border bg-white p-6">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-bold">{label}</h1>
          {statusBadge(job.status)}
          {job.dry_run && <Badge variant="outline">Dry Run</Badge>}
        </div>
        <div className="flex flex-wrap gap-4 mt-2 text-sm text-muted-foreground">
          <span>Period: {period}</span>
          {job.started_at && (
            <span>
              Started: {new Date(job.started_at).toLocaleString()}
            </span>
          )}
          {job.started_at && job.completed_at && (
            <span>
              Duration:{" "}
              {Math.round(
                (new Date(job.completed_at).getTime() -
                  new Date(job.started_at).getTime()) /
                  1000,
              )}
              s
            </span>
          )}
        </div>
        {job.error_message && (
          <div className="mt-3 p-3 bg-red-50 rounded text-sm text-red-700">
            {job.error_message}
          </div>
        )}
        {job.rejection_reason && (
          <div className="mt-3 p-3 bg-red-50 rounded text-sm text-red-700">
            Rejected: {job.rejection_reason}
          </div>
        )}
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="rounded-lg border bg-white p-4 text-center">
          <div className="text-2xl font-bold">{job.anomaly_count}</div>
          <div className="text-xs text-muted-foreground mt-1">
            Total Anomalies
          </div>
        </div>
        <div className="rounded-lg border bg-white p-4 text-center">
          <div className="text-2xl font-bold text-red-600">{criticalCount}</div>
          <div className="text-xs text-muted-foreground mt-1">Critical</div>
        </div>
        <div className="rounded-lg border bg-white p-4 text-center">
          <div className="text-2xl font-bold text-amber-600">
            {warningCount}
          </div>
          <div className="text-xs text-muted-foreground mt-1">Warnings</div>
        </div>
        <div className="rounded-lg border bg-white p-4 text-center">
          <div className="text-2xl font-bold text-blue-600">{infoCount}</div>
          <div className="text-xs text-muted-foreground mt-1">Info</div>
        </div>
      </div>

      {/* Anomalies */}
      <div className="rounded-lg border bg-white">
        <div className="px-6 py-4 border-b">
          <h2 className="text-lg font-semibold">Anomalies</h2>
        </div>
        {anomalies.length === 0 ? (
          <div className="p-6 text-center">
            <CheckCircle2 className="h-8 w-8 text-green-500 mx-auto mb-2" />
            <p className="text-green-700 font-medium">No issues found</p>
          </div>
        ) : (
          <div className="divide-y">
            {["critical", "warning", "info"].map((sev) => {
              const items = anomalies.filter((a) => a.severity === sev);
              if (items.length === 0) return null;
              return (
                <div key={sev}>
                  <div className="px-6 py-2 bg-muted/30 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    {sev} ({items.length})
                  </div>
                  {items.map((a) => (
                    <div key={a.id} className="px-6 py-3 border-b last:border-0">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex items-start gap-3">
                          {severityIcon(a.severity)}
                          <div>
                            <div className="flex items-center gap-2">
                              {severityBadge(a.severity)}
                              <span className="font-medium text-sm">
                                {a.anomaly_type.replace(/_/g, " ")}
                              </span>
                              {a.resolved && (
                                <span className="text-xs text-green-600">
                                  Resolved
                                </span>
                              )}
                            </div>
                            <p className="text-sm text-muted-foreground mt-1">
                              {a.description}
                            </p>
                            {a.entity_type && a.entity_id && (
                              <p className="text-xs text-blue-600 mt-1">
                                {a.entity_type}: {a.entity_id}
                              </p>
                            )}
                          </div>
                        </div>
                        <div className="text-right shrink-0">
                          {a.amount != null && (
                            <span className="font-medium">
                              ${Number(a.amount).toLocaleString()}
                            </span>
                          )}
                          {!a.resolved && canAct && (
                            <div className="mt-2 flex items-center gap-1">
                              <input
                                type="text"
                                placeholder="Note..."
                                value={resolveNote[a.id] || ""}
                                onChange={(e) =>
                                  setResolveNote((p) => ({
                                    ...p,
                                    [a.id]: e.target.value,
                                  }))
                                }
                                className="border rounded px-2 py-1 text-xs w-32"
                              />
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleResolveAnomaly(a.id)}
                              >
                                Resolve
                              </Button>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Step detail accordion */}
      <div className="rounded-lg border bg-white">
        <div className="px-6 py-4 border-b">
          <h2 className="text-lg font-semibold">Step Detail</h2>
        </div>
        {Object.keys(steps).length === 0 ? (
          <div className="p-6 text-center text-muted-foreground">
            No step data available
          </div>
        ) : (
          <div className="divide-y">
            {Object.entries(steps).map(([name, data], i) => (
              <div key={name}>
                <button
                  className="w-full px-6 py-3 flex items-center justify-between hover:bg-muted/30 text-left"
                  onClick={() => toggleStep(i)}
                >
                  <span className="font-medium text-sm">{name}</span>
                  {expandedSteps.has(i) ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                </button>
                {expandedSteps.has(i) && (
                  <div className="px-6 pb-3 text-sm text-muted-foreground">
                    <pre className="whitespace-pre-wrap bg-muted/30 rounded p-3 text-xs">
                      {JSON.stringify(data, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Run log */}
      <div className="rounded-lg border bg-white">
        <button
          className="w-full px-6 py-4 flex items-center justify-between"
          onClick={() => setShowRunLog(!showRunLog)}
        >
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Run Log
          </h2>
          {showRunLog ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </button>
        {showRunLog && (
          <div className="border-t">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-4 py-2 text-left font-medium">#</th>
                  <th className="px-4 py-2 text-left font-medium">Step</th>
                  <th className="px-4 py-2 text-left font-medium">Status</th>
                  <th className="px-4 py-2 text-left font-medium">Duration</th>
                  <th className="px-4 py-2 text-left font-medium">Message</th>
                </tr>
              </thead>
              <tbody>
                {(job.run_log || []).map((entry, i) => (
                  <tr key={i} className="border-b">
                    <td className="px-4 py-2">{entry.step_number}</td>
                    <td className="px-4 py-2">{entry.step_name}</td>
                    <td className="px-4 py-2">
                      <span
                        className={
                          entry.status === "complete"
                            ? "text-green-600"
                            : "text-red-600"
                        }
                      >
                        {entry.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-muted-foreground">
                      {entry.duration_ms != null ? `${entry.duration_ms}ms` : "—"}
                    </td>
                    <td className="px-4 py-2 text-muted-foreground">
                      {entry.message}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Action bar */}
      {canAct && (
        <div className="sticky bottom-0 bg-white border-t p-4 flex items-center justify-end gap-3 rounded-lg shadow-lg">
          {!showRejectForm ? (
            <>
              <Button
                variant="outline"
                className="border-red-300 text-red-600 hover:bg-red-50"
                onClick={() => setShowRejectForm(true)}
              >
                <XCircle className="h-4 w-4 mr-1" />
                Reject
              </Button>
              <Button
                className="bg-green-600 hover:bg-green-700"
                onClick={handleApprove}
                disabled={approving}
              >
                <CheckCircle2 className="h-4 w-4 mr-1" />
                {approving ? "Approving..." : "Approve & Lock Period"}
              </Button>
            </>
          ) : (
            <div className="flex items-end gap-3 w-full">
              <div className="flex-1">
                <label className="block text-sm font-medium mb-1">
                  Rejection Reason (required)
                </label>
                <textarea
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  rows={2}
                  className="w-full border rounded-md p-2 text-sm"
                  placeholder="Explain why this job is being rejected..."
                />
              </div>
              <Button
                variant="outline"
                onClick={() => setShowRejectForm(false)}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleReject}
                disabled={rejecting || !rejectReason.trim()}
              >
                {rejecting ? "Rejecting..." : "Confirm Rejection"}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
