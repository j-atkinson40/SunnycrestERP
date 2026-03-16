import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  getRecentJobs,
  getRecentSyncs,
  getSystemHealth,
} from "@/services/platform-service";
import type { SystemHealth } from "@/types/platform";

export default function SystemHealthPage() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [jobs, setJobs] = useState<any[]>([]);
  const [syncs, setSyncs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getSystemHealth(),
      getRecentJobs({ limit: 20 }),
      getRecentSyncs({ limit: 20 }),
    ])
      .then(([h, j, s]) => {
        setHealth(h);
        setJobs(j);
        setSyncs(s);
      })
      .catch(() => toast.error("Failed to load system data"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <p className="text-muted-foreground">Loading system health...</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">System Health</h1>
        <p className="text-muted-foreground">
          Infrastructure and background job monitoring
        </p>
      </div>

      {health && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card className="p-4">
            <div className="text-sm text-muted-foreground">Database</div>
            <div className="mt-1 flex items-center gap-2">
              <span
                className={`h-2.5 w-2.5 rounded-full ${health.db_connected ? "bg-green-500" : "bg-red-500"}`}
              />
              <span className="font-semibold">
                {health.db_connected ? "Connected" : "Down"}
              </span>
            </div>
          </Card>
          <Card className="p-4">
            <div className="text-sm text-muted-foreground">Redis</div>
            <div className="mt-1 flex items-center gap-2">
              <span
                className={`h-2.5 w-2.5 rounded-full ${health.redis_connected ? "bg-green-500" : "bg-yellow-500"}`}
              />
              <span className="font-semibold">
                {health.redis_connected ? "Connected" : "Not configured"}
              </span>
            </div>
          </Card>
          <Card className="p-4">
            <div className="text-sm text-muted-foreground">Jobs (24h)</div>
            <div className="mt-1 text-2xl font-bold">
              {health.total_jobs_24h}
            </div>
          </Card>
          <Card className="p-4">
            <div className="text-sm text-muted-foreground">
              Failed Jobs (24h)
            </div>
            <div
              className={`mt-1 text-2xl font-bold ${health.failed_jobs_24h > 0 ? "text-red-600" : ""}`}
            >
              {health.failed_jobs_24h}
            </div>
          </Card>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Recent Jobs */}
        <Card className="p-4">
          <h3 className="mb-3 font-semibold">Recent Jobs</h3>
          <div className="max-h-96 space-y-2 overflow-y-auto">
            {jobs.map((j: any) => (
              <div
                key={j.id}
                className="flex items-center justify-between rounded border p-2 text-sm"
              >
                <div>
                  <span className="font-medium">{j.job_type}</span>
                  <span className="ml-2 text-xs text-muted-foreground">
                    {new Date(j.created_at).toLocaleString()}
                  </span>
                </div>
                <Badge
                  variant="outline"
                  className={`text-xs ${
                    j.status === "completed"
                      ? "border-green-300 text-green-700"
                      : j.status === "failed" || j.status === "dead"
                        ? "border-red-300 text-red-700"
                        : j.status === "processing"
                          ? "border-blue-300 text-blue-700"
                          : ""
                  }`}
                >
                  {j.status}
                </Badge>
              </div>
            ))}
            {jobs.length === 0 && (
              <p className="text-sm text-muted-foreground">No recent jobs</p>
            )}
          </div>
        </Card>

        {/* Recent Syncs */}
        <Card className="p-4">
          <h3 className="mb-3 font-semibold">Recent Syncs</h3>
          <div className="max-h-96 space-y-2 overflow-y-auto">
            {syncs.map((s: any) => (
              <div
                key={s.id}
                className="flex items-center justify-between rounded border p-2 text-sm"
              >
                <div>
                  <span className="font-medium">{s.entity_type}</span>
                  <span className="ml-2 text-xs text-muted-foreground">
                    {s.direction} |{" "}
                    {new Date(s.created_at).toLocaleString()}
                  </span>
                </div>
                <Badge
                  variant="outline"
                  className={`text-xs ${
                    s.status === "success"
                      ? "border-green-300 text-green-700"
                      : s.status === "error"
                        ? "border-red-300 text-red-700"
                        : ""
                  }`}
                >
                  {s.status} ({s.records_synced})
                </Badge>
              </div>
            ))}
            {syncs.length === 0 && (
              <p className="text-sm text-muted-foreground">No sync history</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
