import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { superAdminService } from "@/services/super-admin-service";
import type { SuperDashboard, TenantOverview } from "@/types/super-admin";
import { toast } from "sonner";

const SYNC_COLORS: Record<string, string> = {
  green: "bg-green-500",
  yellow: "bg-yellow-500",
  red: "bg-red-500",
};

const SUB_STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-800",
  trialing: "bg-blue-100 text-blue-800",
  past_due: "bg-red-100 text-red-800",
  canceled: "bg-gray-100 text-gray-800",
};

export default function SuperDashboardPage() {
  const [data, setData] = useState<SuperDashboard | null>(null);
  const [loading, setLoading] = useState(true);

  const loadDashboard = async () => {
    try {
      setLoading(true);
      const result = await superAdminService.getDashboard();
      setData(result);
    } catch {
      toast.error("Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
    const interval = setInterval(loadDashboard, 60000); // 60s refresh
    return () => clearInterval(interval);
  }, []);

  if (loading && !data) {
    return (
      <div className="p-6">
        <p className="text-muted-foreground">Loading super dashboard...</p>
      </div>
    );
  }

  if (!data) return null;

  const { system_health: h } = data;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Platform Overview</h1>
          <p className="text-muted-foreground">
            System-wide health, tenants, and billing
          </p>
        </div>
        <Button variant="outline" onClick={loadDashboard} disabled={loading}>
          Refresh
        </Button>
      </div>

      {/* System Health */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardHeader>
            <h3 className="text-sm font-medium text-muted-foreground">
              Infrastructure
            </h3>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm">Database</span>
                <div
                  className={`h-3 w-3 rounded-full ${h.db_connected ? "bg-green-500" : "bg-red-500"}`}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Redis</span>
                <div
                  className={`h-3 w-3 rounded-full ${h.redis_connected ? "bg-green-500" : "bg-red-500"}`}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Jobs (24h)</span>
                <span className="text-sm font-medium">
                  {h.total_jobs_24h}{" "}
                  {h.failed_jobs_24h > 0 && (
                    <span className="text-red-600">
                      ({h.failed_jobs_24h} failed)
                    </span>
                  )}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h3 className="text-sm font-medium text-muted-foreground">
              Tenants
            </h3>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm">Total</span>
                <span className="text-2xl font-bold">{h.total_tenants}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Active</span>
                <span className="text-sm font-medium text-green-600">
                  {h.active_tenants}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Inactive</span>
                <span className="text-sm font-medium text-gray-500">
                  {h.inactive_tenants}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h3 className="text-sm font-medium text-muted-foreground">
              Billing
            </h3>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm">MRR</span>
                <span className="text-2xl font-bold text-blue-600">
                  ${data.billing_mrr}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Active Subs</span>
                <span className="text-sm font-medium text-green-600">
                  {data.billing_active}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Past Due</span>
                <span className="text-sm font-medium text-red-600">
                  {data.billing_past_due}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Users summary */}
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{h.total_users}</div>
            <p className="text-xs text-muted-foreground">Total Users</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-green-600">
              {h.active_users}
            </div>
            <p className="text-xs text-muted-foreground">Active Users</p>
          </CardContent>
        </Card>
      </div>

      {/* Tenant List */}
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold">All Tenants</h2>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {data.tenants.map((tenant: TenantOverview) => (
              <div
                key={tenant.id}
                className="flex items-center justify-between rounded-md border p-3"
              >
                <div className="flex items-center gap-3">
                  {/* Sync indicator */}
                  <div
                    className={`h-3 w-3 rounded-full ${
                      tenant.sync_status
                        ? SYNC_COLORS[tenant.sync_status]
                        : "bg-gray-300"
                    }`}
                    title={
                      tenant.sync_status
                        ? `Sync: ${tenant.sync_status}`
                        : "No syncs"
                    }
                  />
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">
                        {tenant.name}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        ({tenant.slug})
                      </span>
                      {!tenant.is_active && (
                        <Badge variant="destructive">Inactive</Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span>{tenant.user_count} users</span>
                      {tenant.plan_name && <span>{tenant.plan_name}</span>}
                      {tenant.subscription_status && (
                        <Badge
                          variant="secondary"
                          className={
                            SUB_STATUS_COLORS[tenant.subscription_status] || ""
                          }
                        >
                          {tenant.subscription_status}
                        </Badge>
                      )}
                      <span>
                        Joined{" "}
                        {new Date(tenant.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>
                {tenant.last_sync_at && (
                  <span className="text-xs text-muted-foreground">
                    Last sync:{" "}
                    {new Date(tenant.last_sync_at).toLocaleString()}
                  </span>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
