import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import apiClient from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StatusPill } from "@/components/ui/status-pill";
import { Textarea } from "@/components/ui/textarea";
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

// Phase II Batch 1a — severity icon + badge + status pill now route
// through DESIGN_LANGUAGE warm status palette + StatusPill primitive.
function severityIcon(severity: string) {
  if (severity === "critical")
    return <AlertTriangle className="h-4 w-4 text-status-error" />;
  if (severity === "warning")
    return <AlertTriangle className="h-4 w-4 text-status-warning" />;
  return <Info className="h-4 w-4 text-status-info" />;
}

function severityBadge(severity: string) {
  const SEVERITY_TO_PILL: Record<string, string> = {
    critical: "failed",
    warning: "pending_review",
    info: "draft",
  };
  return (
    <StatusPill status={SEVERITY_TO_PILL[severity] ?? severity}>
      {severity}
    </StatusPill>
  );
}

function statusBadge(status: string) {
  const STATUS_TO_PILL: Record<string, { statusKey: string; pulse?: boolean }> = {
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
    <StatusPill
      status={m.statusKey}
      className={m.pulse ? "animate-pulse" : undefined}
    >
      {status.replace(/_/g, " ")}
    </StatusPill>
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
      <div className="p-6 text-center text-content-muted">Loading...</div>
    );
  }

  if (!job) {
    return (
      <div className="p-6 text-center text-content-base">Job not found</div>
    );
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
        className="flex items-center gap-1 text-body-sm text-content-muted hover:text-content-strong focus-ring-accent rounded-sm"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Agent Dashboard
      </button>

      {/* Top bar */}
      <Card>
        <CardContent className="p-6">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-h2 font-display font-medium text-content-strong">
              {label}
            </h1>
            {statusBadge(job.status)}
            {job.dry_run && <Badge variant="outline">Dry Run</Badge>}
          </div>
          <div className="flex flex-wrap gap-4 mt-2 text-body-sm text-content-muted">
            <span>Period: {period}</span>
            {job.started_at && (
              <span>Started: {new Date(job.started_at).toLocaleString()}</span>
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
            <div className="mt-3 p-3 bg-status-error-muted rounded-sm text-body-sm text-status-error">
              {job.error_message}
            </div>
          )}
          {job.rejection_reason && (
            <div className="mt-3 p-3 bg-status-error-muted rounded-sm text-body-sm text-status-error">
              Rejected: {job.rejection_reason}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-h2 font-display font-medium text-content-strong">
              {job.anomaly_count}
            </div>
            <div className="text-caption text-content-muted mt-1">
              Total Anomalies
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-h2 font-display font-medium text-status-error">
              {criticalCount}
            </div>
            <div className="text-caption text-content-muted mt-1">Critical</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-h2 font-display font-medium text-status-warning">
              {warningCount}
            </div>
            <div className="text-caption text-content-muted mt-1">Warnings</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-h2 font-display font-medium text-status-info">
              {infoCount}
            </div>
            <div className="text-caption text-content-muted mt-1">Info</div>
          </CardContent>
        </Card>
      </div>

      {/* Anomalies */}
      <Card>
        <CardHeader>
          <CardTitle>Anomalies</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {anomalies.length === 0 ? (
            <div className="p-6 text-center">
              <CheckCircle2 className="h-8 w-8 text-status-success mx-auto mb-2" />
              <p className="text-status-success font-medium">No issues found</p>
            </div>
          ) : (
            <div className="divide-y divide-border-subtle">
              {["critical", "warning", "info"].map((sev) => {
                const items = anomalies.filter((a) => a.severity === sev);
                if (items.length === 0) return null;
                return (
                  <div key={sev}>
                    <div className="px-6 py-2 bg-surface-sunken/60 text-caption font-semibold uppercase tracking-wider text-content-muted">
                      {sev} ({items.length})
                    </div>
                    {items.map((a) => (
                      <div
                        key={a.id}
                        className="px-6 py-3 border-b border-border-subtle last:border-0"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex items-start gap-3">
                            {severityIcon(a.severity)}
                            <div>
                              <div className="flex items-center gap-2">
                                {severityBadge(a.severity)}
                                <span className="font-medium text-body-sm text-content-base">
                                  {a.anomaly_type.replace(/_/g, " ")}
                                </span>
                                {a.resolved && (
                                  <span className="text-caption text-status-success">
                                    Resolved
                                  </span>
                                )}
                              </div>
                              <p className="text-body-sm text-content-muted mt-1">
                                {a.description}
                              </p>
                              {a.entity_type && a.entity_id && (
                                <p className="text-caption text-accent mt-1">
                                  {a.entity_type}: {a.entity_id}
                                </p>
                              )}
                            </div>
                          </div>
                          <div className="text-right shrink-0">
                            {a.amount != null && (
                              <span className="font-medium text-content-base">
                                ${Number(a.amount).toLocaleString()}
                              </span>
                            )}
                            {!a.resolved && canAct && (
                              <div className="mt-2 flex items-center gap-1">
                                <Input
                                  type="text"
                                  placeholder="Note..."
                                  value={resolveNote[a.id] || ""}
                                  onChange={(e) =>
                                    setResolveNote((p) => ({
                                      ...p,
                                      [a.id]: e.target.value,
                                    }))
                                  }
                                  className="h-7 w-32 px-2 text-caption"
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
        </CardContent>
      </Card>

      {/* Step detail accordion */}
      <Card>
        <CardHeader>
          <CardTitle>Step Detail</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {Object.keys(steps).length === 0 ? (
            <div className="p-6 text-center text-content-muted">
              No step data available
            </div>
          ) : (
            <div className="divide-y divide-border-subtle">
              {Object.entries(steps).map(([name, data], i) => (
                <div key={name}>
                  <button
                    className="w-full px-6 py-3 flex items-center justify-between hover:bg-accent-subtle/40 text-left focus-ring-accent"
                    onClick={() => toggleStep(i)}
                  >
                    <span className="font-medium text-body-sm text-content-base">
                      {name}
                    </span>
                    {expandedSteps.has(i) ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4" />
                    )}
                  </button>
                  {expandedSteps.has(i) && (
                    <div className="px-6 pb-3 text-body-sm text-content-muted">
                      <pre className="whitespace-pre-wrap bg-surface-sunken rounded-sm p-3 text-caption font-mono">
                        {JSON.stringify(data, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Run log */}
      <Card>
        <button
          className="w-full px-6 py-4 flex items-center justify-between focus-ring-accent"
          onClick={() => setShowRunLog(!showRunLog)}
        >
          <h2 className="text-h4 font-medium text-content-strong flex items-center gap-2">
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
          <div className="border-t border-border-subtle">
            <table className="w-full text-body-sm">
              <thead>
                <tr className="border-b border-border-subtle bg-surface-sunken/60">
                  <th className="px-4 py-2 text-left font-medium text-content-muted">
                    #
                  </th>
                  <th className="px-4 py-2 text-left font-medium text-content-muted">
                    Step
                  </th>
                  <th className="px-4 py-2 text-left font-medium text-content-muted">
                    Status
                  </th>
                  <th className="px-4 py-2 text-left font-medium text-content-muted">
                    Duration
                  </th>
                  <th className="px-4 py-2 text-left font-medium text-content-muted">
                    Message
                  </th>
                </tr>
              </thead>
              <tbody>
                {(job.run_log || []).map((entry, i) => (
                  <tr
                    key={i}
                    className="border-b border-border-subtle"
                  >
                    <td className="px-4 py-2 text-content-base">
                      {entry.step_number}
                    </td>
                    <td className="px-4 py-2 text-content-base">
                      {entry.step_name}
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={
                          entry.status === "complete"
                            ? "text-status-success"
                            : "text-status-error"
                        }
                      >
                        {entry.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-content-muted">
                      {entry.duration_ms != null
                        ? `${entry.duration_ms}ms`
                        : "—"}
                    </td>
                    <td className="px-4 py-2 text-content-muted">
                      {entry.message}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Action bar */}
      {canAct && (
        <div className="sticky bottom-0 bg-surface-raised border-t border-border-subtle p-4 flex items-center justify-end gap-3 rounded-md shadow-level-3">
          {!showRejectForm ? (
            <>
              <Button
                variant="destructive"
                onClick={() => setShowRejectForm(true)}
              >
                <XCircle className="h-4 w-4 mr-1" />
                Reject
              </Button>
              <Button
                onClick={handleApprove}
                disabled={approving}
              >
                <CheckCircle2 className="h-4 w-4 mr-1" />
                {approving ? "Approving..." : "Approve & Lock Period"}
              </Button>
            </>
          ) : (
            <div className="flex items-end gap-3 w-full">
              <div className="flex-1 space-y-1">
                <Label htmlFor="rejectReason">Rejection Reason (required)</Label>
                <Textarea
                  id="rejectReason"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  rows={2}
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
