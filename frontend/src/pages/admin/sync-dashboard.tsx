import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { jobQueueService } from "@/services/job-queue-service";
import type { Job, SyncDashboard, SyncHealthTenant } from "@/types/job-queue";

type Tab = "health" | "queue" | "dead-letter";

export default function SyncDashboardPage() {
  const [tab, setTab] = useState<Tab>("health");

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">Sync & Job Monitoring</h1>
        <p className="text-muted-foreground text-sm">
          Monitor sync health across tenants, manage the job queue, and handle
          dead-lettered jobs.
        </p>
      </div>

      <div className="flex gap-2 border-b pb-2">
        {(["health", "queue", "dead-letter"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              tab === t
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted"
            }`}
          >
            {t === "health"
              ? "Sync Health"
              : t === "queue"
                ? "Job Queue"
                : "Dead Letter"}
          </button>
        ))}
      </div>

      {tab === "health" && <SyncHealthView />}
      {tab === "queue" && <QueueView />}
      {tab === "dead-letter" && <DeadLetterView />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sync Health View
// ---------------------------------------------------------------------------

const STATUS_COLORS: Record<string, string> = {
  green: "bg-green-500",
  yellow: "bg-yellow-500",
  red: "bg-red-500",
};

function SyncHealthView() {
  const [dashboard, setDashboard] = useState<SyncDashboard | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await jobQueueService.getSyncDashboard();
      setDashboard(data);
    } catch {
      toast.error("Failed to load sync dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 30000); // Auto-refresh every 30s
    return () => clearInterval(interval);
  }, [load]);

  if (loading || !dashboard) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="border-primary h-8 w-8 animate-spin rounded-full border-b-2" />
      </div>
    );
  }

  const { tenants, queue_stats } = dashboard;

  return (
    <div className="space-y-6">
      {/* Queue summary cards */}
      <div className="grid gap-4 md:grid-cols-5">
        <StatCard label="Pending" value={queue_stats.pending} />
        <StatCard label="Running" value={queue_stats.running} color="text-blue-600" />
        <StatCard label="Completed" value={queue_stats.completed} color="text-green-600" />
        <StatCard label="Failed" value={queue_stats.failed} color="text-yellow-600" />
        <StatCard
          label="Dead Letter"
          value={queue_stats.dead}
          color={queue_stats.dead > 0 ? "text-red-600" : undefined}
        />
      </div>

      <div className="flex items-center gap-2">
        <div
          className={`h-2.5 w-2.5 rounded-full ${
            queue_stats.redis_connected ? "bg-green-500" : "bg-red-500"
          }`}
        />
        <span className="text-muted-foreground text-xs">
          Redis {queue_stats.redis_connected ? "connected" : "disconnected (using DB polling)"}
          {queue_stats.redis_connected && ` — ${queue_stats.redis_queue_depth} queued`}
        </span>
        <Button variant="outline" size="sm" className="ml-auto" onClick={load}>
          Refresh
        </Button>
      </div>

      {/* Tenant health table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Tenant Sync Health</CardTitle>
          <CardDescription>
            Status based on last sync result and recency. Auto-refreshes every
            30 seconds.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {tenants.length === 0 ? (
            <p className="text-muted-foreground text-sm">No tenants found.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-muted-foreground border-b text-left text-xs">
                    <th className="pb-2">Status</th>
                    <th className="pb-2">Tenant</th>
                    <th className="pb-2">Last Sync</th>
                    <th className="pb-2">Type</th>
                    <th className="pb-2">Result</th>
                    <th className="pb-2">24h Total</th>
                    <th className="pb-2">24h Failed</th>
                  </tr>
                </thead>
                <tbody>
                  {tenants.map((t) => (
                    <TenantRow key={t.company_id} tenant={t} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function TenantRow({ tenant }: { tenant: SyncHealthTenant }) {
  const [showError, setShowError] = useState(false);

  return (
    <>
      <tr className="border-b last:border-0">
        <td className="py-2">
          <div className={`h-3 w-3 rounded-full ${STATUS_COLORS[tenant.status]}`} />
        </td>
        <td className="py-2 font-medium">{tenant.company_name}</td>
        <td className="py-2 text-xs">
          {tenant.last_sync_at
            ? new Date(tenant.last_sync_at).toLocaleString()
            : "Never"}
        </td>
        <td className="py-2 text-xs">{tenant.last_sync_type || "-"}</td>
        <td className="py-2">
          {tenant.last_sync_status ? (
            <span
              className={`cursor-pointer rounded-full px-2 py-0.5 text-xs font-medium ${
                tenant.last_sync_status === "completed"
                  ? "bg-green-100 text-green-700"
                  : tenant.last_sync_status === "failed"
                    ? "bg-red-100 text-red-700"
                    : "bg-yellow-100 text-yellow-700"
              }`}
              onClick={() => tenant.error_message && setShowError(!showError)}
            >
              {tenant.last_sync_status}
            </span>
          ) : (
            "-"
          )}
        </td>
        <td className="py-2 text-center text-xs">{tenant.total_syncs_24h}</td>
        <td className="py-2 text-center text-xs">
          {tenant.failed_syncs_24h > 0 ? (
            <span className="font-medium text-red-600">{tenant.failed_syncs_24h}</span>
          ) : (
            "0"
          )}
        </td>
      </tr>
      {showError && tenant.error_message && (
        <tr>
          <td colSpan={7} className="bg-red-50 px-4 py-2">
            <pre className="max-h-32 overflow-y-auto whitespace-pre-wrap text-xs text-red-800">
              {tenant.error_message}
            </pre>
          </td>
        </tr>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Queue View
// ---------------------------------------------------------------------------

function QueueView() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await jobQueueService.listJobs({
        status: statusFilter || undefined,
        page,
        per_page: 20,
      });
      setJobs(data.items);
      setTotal(data.total);
    } catch {
      toast.error("Failed to load jobs");
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <select
          className="border-input rounded-md border px-3 py-1.5 text-sm"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="dead">Dead</option>
        </select>
        <span className="text-muted-foreground text-xs">{total} jobs</span>
        <Button variant="outline" size="sm" className="ml-auto" onClick={load}>
          Refresh
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center p-12">
          <div className="border-primary h-8 w-8 animate-spin rounded-full border-b-2" />
        </div>
      ) : jobs.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center">
            <p className="text-muted-foreground">No jobs found.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} />
          ))}
        </div>
      )}

      {total > 20 && (
        <div className="flex justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          <span className="px-3 py-1.5 text-sm">
            Page {page} of {Math.ceil(total / 20)}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= Math.ceil(total / 20)}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}

function JobCard({ job }: { job: Job }) {
  const statusColors: Record<string, string> = {
    pending: "bg-gray-100 text-gray-700",
    running: "bg-blue-100 text-blue-700",
    completed: "bg-green-100 text-green-700",
    failed: "bg-yellow-100 text-yellow-700",
    dead: "bg-red-100 text-red-700",
  };

  return (
    <Card>
      <CardContent className="flex items-center gap-4 py-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{job.job_type}</span>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                statusColors[job.status] || ""
              }`}
            >
              {job.status}
            </span>
            {job.retry_count > 0 && (
              <span className="text-muted-foreground text-xs">
                (attempt {job.retry_count + 1}/{job.max_retries})
              </span>
            )}
          </div>
          <div className="text-muted-foreground mt-0.5 flex gap-3 text-xs">
            <span>Created: {new Date(job.created_at).toLocaleString()}</span>
            {job.started_at && (
              <span>Started: {new Date(job.started_at).toLocaleString()}</span>
            )}
            {job.completed_at && (
              <span>Done: {new Date(job.completed_at).toLocaleString()}</span>
            )}
          </div>
          {job.error_message && (
            <p className="mt-1 max-h-16 overflow-hidden text-xs text-red-600">
              {job.error_message.slice(0, 200)}
            </p>
          )}
        </div>
        <span className="bg-muted rounded px-2 py-0.5 text-xs">P{job.priority}</span>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Dead Letter View
// ---------------------------------------------------------------------------

function DeadLetterView() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await jobQueueService.listDeadLetter();
      setJobs(data.items);
      setTotal(data.total);
    } catch {
      toast.error("Failed to load dead letter jobs");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleRetry = async (jobId: string) => {
    try {
      await jobQueueService.retryDeadLetter(jobId);
      toast.success("Job re-queued");
      load();
    } catch {
      toast.error("Failed to retry job");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="border-primary h-8 w-8 animate-spin rounded-full border-b-2" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-muted-foreground text-sm">
          {total} dead-lettered job{total !== 1 ? "s" : ""} — failed after max
          retries.
        </p>
        <Button variant="outline" size="sm" onClick={load}>
          Refresh
        </Button>
      </div>

      {jobs.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center">
            <p className="text-muted-foreground">
              No dead-lettered jobs. All clear!
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {jobs.map((job) => (
            <Card key={job.id}>
              <CardContent className="flex items-center gap-4 py-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{job.job_type}</span>
                    <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                      Dead ({job.retry_count} attempts)
                    </span>
                  </div>
                  <p className="text-muted-foreground mt-0.5 text-xs">
                    Failed: {new Date(job.completed_at || job.created_at).toLocaleString()}
                  </p>
                  {job.error_message && (
                    <pre className="mt-1 max-h-24 overflow-y-auto whitespace-pre-wrap rounded bg-red-50 p-2 text-xs text-red-800">
                      {job.error_message}
                    </pre>
                  )}
                </div>
                <Button size="sm" onClick={() => handleRetry(job.id)}>
                  Retry
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color?: string;
}) {
  return (
    <Card>
      <CardContent className="py-3 text-center">
        <p className="text-muted-foreground text-xs">{label}</p>
        <p className={`text-2xl font-bold ${color || ""}`}>{value}</p>
      </CardContent>
    </Card>
  );
}
