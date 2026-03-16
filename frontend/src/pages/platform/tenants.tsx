import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  impersonateTenant,
  listTenants,
} from "@/services/platform-service";
import type { TenantOverview } from "@/types/platform";

export default function TenantsPage() {
  const [tenants, setTenants] = useState<TenantOverview[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  const fetch = useCallback(async () => {
    try {
      const data = await listTenants({
        search: search || undefined,
        limit: 100,
      });
      setTenants(data.items);
      setTotal(data.total);
    } catch {
      toast.error("Failed to load tenants");
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  async function handleImpersonate(tenant: TenantOverview) {
    try {
      const result = await impersonateTenant(tenant.id);

      // Store impersonation info for the banner
      localStorage.setItem(
        "impersonation_info",
        JSON.stringify({
          session_id: result.session_id,
          tenant_name: result.tenant_name,
          user_name: result.impersonated_user_name,
          expires_at: Date.now() + result.expires_in_minutes * 60 * 1000,
        })
      );

      // Store impersonation token as regular tenant token
      localStorage.setItem("access_token", result.access_token);

      // Always stay on the same origin for impersonation.
      // Subdomain redirects break because localStorage (where the token lives)
      // is per-origin — admin.localhost can't share tokens with tenant.localhost.
      localStorage.setItem("company_slug", result.tenant_slug);
      localStorage.removeItem("platform_mode");
      window.location.href = "/dashboard";
    } catch {
      toast.error("Failed to start impersonation");
    }
  }

  if (loading) {
    return <p className="text-muted-foreground">Loading tenants...</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Tenants</h1>
          <p className="text-muted-foreground">{total} total</p>
        </div>
        <input
          type="text"
          placeholder="Search tenants..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="rounded-md border px-3 py-1.5 text-sm"
        />
      </div>

      <div className="space-y-3">
        {tenants.map((t) => (
          <Card key={t.id} className="flex items-center justify-between p-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Link
                  to={`/tenants/${t.id}`}
                  className="font-medium hover:underline"
                >
                  {t.name}
                </Link>
                <Badge
                  variant={t.is_active ? "default" : "secondary"}
                  className={`text-xs ${t.is_active ? "bg-green-100 text-green-800" : ""}`}
                >
                  {t.is_active ? "Active" : "Inactive"}
                </Badge>
                {t.subscription_status && (
                  <Badge variant="outline" className="text-xs">
                    {t.plan_name || t.subscription_status}
                  </Badge>
                )}
              </div>
              <div className="flex gap-4 text-xs text-muted-foreground">
                <span>Slug: {t.slug}</span>
                <span>{t.user_count} users</span>
                <span>
                  Created: {new Date(t.created_at).toLocaleDateString()}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleImpersonate(t)}
                className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-700"
              >
                Impersonate
              </button>
              <Link
                to={`/tenants/${t.id}`}
                className="rounded-md border px-3 py-1.5 text-xs font-medium transition-colors hover:bg-gray-50"
              >
                Details
              </Link>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
