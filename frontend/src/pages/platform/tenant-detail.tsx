import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  getTenant,
  impersonateTenant,
  updateTenant,
} from "@/services/platform-service";
import type { TenantDetail } from "@/types/platform";

export default function TenantDetailPage() {
  const { tenantId } = useParams<{ tenantId: string }>();
  const [tenant, setTenant] = useState<TenantDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!tenantId) return;
    getTenant(tenantId)
      .then(setTenant)
      .catch(() => toast.error("Failed to load tenant"))
      .finally(() => setLoading(false));
  }, [tenantId]);

  async function toggleActive() {
    if (!tenant || !tenantId) return;
    try {
      await updateTenant(tenantId, { is_active: !tenant.is_active });
      setTenant({ ...tenant, is_active: !tenant.is_active });
      toast.success(
        `Tenant ${!tenant.is_active ? "activated" : "deactivated"}`
      );
    } catch {
      toast.error("Failed to update tenant");
    }
  }

  async function handleImpersonate(userId?: string) {
    if (!tenantId || !tenant) return;
    try {
      const result = await impersonateTenant(tenantId, userId);
      localStorage.setItem(
        "impersonation_info",
        JSON.stringify({
          session_id: result.session_id,
          tenant_name: result.tenant_name,
          user_name: result.impersonated_user_name,
          expires_at: Date.now() + result.expires_in_minutes * 60 * 1000,
        })
      );
      localStorage.setItem("access_token", result.access_token);

      const hostname = window.location.hostname;
      const hasSubdomainSupport =
        hostname === "admin.localhost" ||
        hostname.endsWith(".localhost") ||
        (import.meta.env.VITE_APP_DOMAIN &&
          hostname.endsWith(`.${import.meta.env.VITE_APP_DOMAIN}`));

      if (hasSubdomainSupport) {
        // Subdomain-based routing: navigate to tenant subdomain
        const tenantUrl = hostname.endsWith(".localhost")
          ? `${window.location.protocol}//${result.tenant_slug}.localhost:${window.location.port}/dashboard`
          : `${window.location.protocol}//${result.tenant_slug}.${import.meta.env.VITE_APP_DOMAIN}/dashboard`;
        window.location.href = tenantUrl;
      } else {
        // Non-subdomain setup (Railway, single-origin): stay on same origin,
        // switch from platform mode to tenant mode via localStorage
        localStorage.setItem("company_slug", result.tenant_slug);
        localStorage.removeItem("platform_mode");
        window.location.href = "/dashboard";
      }
    } catch (err: unknown) {
      const detail =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string }; status?: number } })
              .response?.data?.detail ||
            `HTTP ${(err as { response?: { status?: number } }).response?.status}`
          : String(err);
      toast.error(`Impersonation failed: ${detail}`);
    }
  }

  if (loading) {
    return <p className="text-muted-foreground">Loading tenant...</p>;
  }
  if (!tenant) return <p>Tenant not found</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Link to="/tenants" className="text-muted-foreground hover:underline">
              Tenants
            </Link>
            <span className="text-muted-foreground">/</span>
            <h1 className="text-2xl font-bold">{tenant.name}</h1>
          </div>
          <p className="text-muted-foreground">
            Slug: {tenant.slug} | Created:{" "}
            {new Date(tenant.created_at).toLocaleDateString()}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => handleImpersonate()}
            className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            Impersonate Admin
          </button>
          <button
            onClick={toggleActive}
            className={`rounded-md px-4 py-2 text-sm font-medium ${
              tenant.is_active
                ? "border border-red-300 text-red-600 hover:bg-red-50"
                : "border border-green-300 text-green-600 hover:bg-green-50"
            }`}
          >
            {tenant.is_active ? "Deactivate" : "Activate"}
          </button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Subscription */}
        <Card className="p-4">
          <h3 className="mb-3 font-semibold">Subscription</h3>
          {tenant.subscription ? (
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Status</span>
                <Badge
                  className={
                    tenant.subscription.status === "active"
                      ? "bg-green-100 text-green-800"
                      : "bg-yellow-100 text-yellow-800"
                  }
                >
                  {tenant.subscription.status}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Plan</span>
                <span>{tenant.subscription.plan_name || "—"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Billing</span>
                <span>{tenant.subscription.billing_interval || "—"}</span>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No subscription</p>
          )}
        </Card>

        {/* Modules */}
        <Card className="p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-semibold">Modules</h3>
            <Link
              to={`/tenants/${tenantId}/modules`}
              className="text-xs text-indigo-600 hover:underline"
            >
              Manage Modules &rarr;
            </Link>
          </div>
          <div className="flex flex-wrap gap-2">
            {tenant.modules.map((m) => (
              <Badge
                key={m.module}
                variant={m.enabled ? "default" : "secondary"}
                className={m.enabled ? "bg-green-100 text-green-800" : ""}
              >
                {m.module}
              </Badge>
            ))}
            {tenant.modules.length === 0 && (
              <p className="text-sm text-muted-foreground">No modules configured</p>
            )}
          </div>
        </Card>

        {/* Users */}
        <Card className="p-4">
          <h3 className="mb-3 font-semibold">
            Users ({tenant.users.length})
          </h3>
          <div className="max-h-60 space-y-2 overflow-y-auto">
            {tenant.users.map((u) => (
              <div
                key={u.id}
                className="flex items-center justify-between text-sm"
              >
                <div>
                  <span className="font-medium">
                    {u.first_name} {u.last_name}
                  </span>
                  <span className="ml-2 text-muted-foreground">{u.email}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Badge
                    variant={u.is_active ? "default" : "secondary"}
                    className={`text-xs ${u.is_active ? "bg-green-100 text-green-800" : ""}`}
                  >
                    {u.is_active ? "Active" : "Inactive"}
                  </Badge>
                  <button
                    onClick={() => handleImpersonate(u.id)}
                    className="text-xs text-indigo-600 hover:underline"
                  >
                    Impersonate
                  </button>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Recent Syncs */}
        <Card className="p-4">
          <h3 className="mb-3 font-semibold">Recent Syncs</h3>
          {tenant.recent_syncs.length > 0 ? (
            <div className="max-h-60 space-y-2 overflow-y-auto">
              {tenant.recent_syncs.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center justify-between text-sm"
                >
                  <div>
                    <span className="font-medium">{s.entity_type}</span>
                    <span className="ml-2 text-muted-foreground">
                      {s.direction}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
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
                      {s.status}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      {new Date(s.created_at).toLocaleString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No sync history</p>
          )}
        </Card>
      </div>
    </div>
  );
}
