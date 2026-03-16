import { useEffect, useState } from "react";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import {
  listFeatureFlags,
  setTenantFlag,
  removeTenantFlagOverride,
} from "@/services/platform-service";
import type { FeatureFlagMatrix } from "@/types/platform";

export default function PlatformFeatureFlagsPage() {
  const [flags, setFlags] = useState<FeatureFlagMatrix[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listFeatureFlags()
      .then(setFlags)
      .catch(() => toast.error("Failed to load feature flags"))
      .finally(() => setLoading(false));
  }, []);

  async function handleToggle(
    flagId: string,
    tenantId: string,
    currentEnabled: boolean
  ) {
    try {
      await setTenantFlag(flagId, tenantId, !currentEnabled);
      // Update local state
      setFlags((prev) =>
        prev.map((f) =>
          f.id === flagId
            ? {
                ...f,
                tenants: f.tenants.map((t) =>
                  t.tenant_id === tenantId
                    ? { ...t, enabled: !currentEnabled, has_override: true }
                    : t
                ),
              }
            : f
        )
      );
      toast.success("Flag updated");
    } catch {
      toast.error("Failed to update flag");
    }
  }

  async function handleResetOverride(flagId: string, tenantId: string, defaultValue: boolean) {
    try {
      await removeTenantFlagOverride(flagId, tenantId);
      setFlags((prev) =>
        prev.map((f) =>
          f.id === flagId
            ? {
                ...f,
                tenants: f.tenants.map((t) =>
                  t.tenant_id === tenantId
                    ? { ...t, enabled: defaultValue, has_override: false }
                    : t
                ),
              }
            : f
        )
      );
      toast.success("Override removed — using default");
    } catch {
      toast.error("Failed to remove override");
    }
  }

  if (loading) {
    return <p className="text-muted-foreground">Loading feature flags...</p>;
  }

  if (flags.length === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Feature Flags</h1>
        <p className="text-muted-foreground">No feature flags configured.</p>
      </div>
    );
  }

  // Get tenant names from first flag
  const tenantNames = flags[0]?.tenants || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Feature Flags</h1>
        <p className="text-muted-foreground">
          Manage feature flags per tenant. Overrides shown in bold.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left">
              <th className="min-w-[200px] py-3 pr-4 font-medium">Flag</th>
              {tenantNames.map((t) => (
                <th
                  key={t.tenant_id}
                  className="min-w-[120px] px-2 py-3 text-center font-medium"
                >
                  {t.tenant_name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {flags.map((flag) => (
              <tr key={flag.id} className="border-b">
                <td className="py-3 pr-4">
                  <div className="font-medium">{flag.key}</div>
                  <div className="text-xs text-muted-foreground">
                    {flag.description}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Default: {flag.enabled_by_default ? "ON" : "OFF"}
                  </div>
                </td>
                {flag.tenants.map((t) => (
                  <td key={t.tenant_id} className="px-2 py-3 text-center">
                    <div className="flex flex-col items-center gap-1">
                      <Switch
                        checked={t.enabled}
                        onCheckedChange={() =>
                          handleToggle(flag.id, t.tenant_id, t.enabled)
                        }
                      />
                      {t.has_override && (
                        <button
                          onClick={() =>
                            handleResetOverride(
                              flag.id,
                              t.tenant_id,
                              flag.enabled_by_default
                            )
                          }
                          className="text-[10px] text-indigo-600 hover:underline"
                        >
                          Reset
                        </button>
                      )}
                    </div>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
