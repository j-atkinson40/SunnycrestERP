import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { getSystemHealth } from "@/services/platform-service";
import type { SystemHealth } from "@/types/platform";
import { toast } from "sonner";

export default function PlatformDashboard() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSystemHealth()
      .then(setHealth)
      .catch(() => toast.error("Failed to load system health"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <p className="text-muted-foreground">Loading dashboard...</p>;
  }

  if (!health) return null;

  const stats = [
    { label: "Active Tenants", value: health.active_tenants, total: health.total_tenants },
    { label: "Active Users", value: health.active_users, total: health.total_users },
    { label: "Jobs (24h)", value: health.total_jobs_24h, alert: health.failed_jobs_24h > 0 },
    { label: "Failed Jobs (24h)", value: health.failed_jobs_24h, alert: health.failed_jobs_24h > 0 },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Platform Dashboard</h1>
        <p className="text-muted-foreground">System-wide overview</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
          <Card key={s.label} className="p-4">
            <div className="text-sm font-medium text-muted-foreground">
              {s.label}
            </div>
            <div className={`mt-1 text-2xl font-bold ${s.alert ? "text-red-600" : ""}`}>
              {s.value}
              {s.total !== undefined && (
                <span className="text-sm font-normal text-muted-foreground">
                  {" "}/ {s.total}
                </span>
              )}
            </div>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card className="p-4">
          <h3 className="mb-2 font-semibold">Infrastructure</h3>
          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span>Database</span>
              <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${health.db_connected ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${health.db_connected ? "bg-green-500" : "bg-red-500"}`} />
                {health.db_connected ? "Connected" : "Unreachable"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span>Redis</span>
              <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${health.redis_connected ? "bg-green-100 text-green-800" : "bg-yellow-100 text-yellow-800"}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${health.redis_connected ? "bg-green-500" : "bg-yellow-500"}`} />
                {health.redis_connected ? "Connected" : "Not configured"}
              </span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
