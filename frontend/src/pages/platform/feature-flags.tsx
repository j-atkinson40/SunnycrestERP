import { useCallback, useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  createFeatureFlag,
  deleteFeatureFlag,
  listFeatureFlags,
  setTenantFlag,
  removeTenantFlagOverride,
} from "@/services/platform-service";
import type { FeatureFlagMatrix } from "@/types/platform";

const CATEGORIES = ["general", "delivery", "billing", "integration", "experimental"];

export default function PlatformFeatureFlagsPage() {
  const [flags, setFlags] = useState<FeatureFlagMatrix[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    key: "",
    name: "",
    description: "",
    category: "general",
    default_enabled: false,
    is_global: false,
  });

  const fetchFlags = useCallback(async () => {
    try {
      const data = await listFeatureFlags();
      setFlags(data);
    } catch {
      toast.error("Failed to load feature flags");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchFlags();
  }, [fetchFlags]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.key.trim()) {
      toast.error("Key is required");
      return;
    }
    setCreating(true);
    try {
      await createFeatureFlag(form);
      toast.success(`Flag "${form.key}" created`);
      setForm({
        key: "",
        name: "",
        description: "",
        category: "general",
        default_enabled: false,
        is_global: false,
      });
      setShowCreate(false);
      // Refresh the full list (includes tenant columns)
      setLoading(true);
      await fetchFlags();
    } catch {
      toast.error("Failed to create flag");
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(flagId: string, flagKey: string) {
    if (!confirm(`Delete flag "${flagKey}"? This removes all tenant overrides too.`)) {
      return;
    }
    try {
      await deleteFeatureFlag(flagId);
      setFlags((prev) => prev.filter((f) => f.id !== flagId));
      toast.success(`Flag "${flagKey}" deleted`);
    } catch {
      toast.error("Failed to delete flag");
    }
  }

  async function handleToggle(
    flagId: string,
    tenantId: string,
    currentEnabled: boolean
  ) {
    try {
      await setTenantFlag(flagId, tenantId, !currentEnabled);
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

  // Get tenant names from first flag (if any)
  const tenantNames = flags[0]?.tenants || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Feature Flags</h1>
          <p className="text-muted-foreground">
            {flags.length} flag{flags.length !== 1 ? "s" : ""} configured.
            Manage per-tenant overrides below.
          </p>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          {showCreate ? "Cancel" : "Create Flag"}
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <Card className="p-4">
          <h3 className="mb-3 font-semibold">New Feature Flag</h3>
          <form onSubmit={handleCreate} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <label className="mb-1 block text-sm font-medium">
                Key <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={form.key}
                onChange={(e) =>
                  setForm((f) => ({ ...f, key: e.target.value }))
                }
                placeholder="e.g. sms_carrier_updates"
                className="w-full rounded-md border px-3 py-2 text-sm"
                required
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">
                Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={form.name}
                onChange={(e) =>
                  setForm((f) => ({ ...f, name: e.target.value }))
                }
                placeholder="e.g. SMS Carrier Updates"
                className="w-full rounded-md border px-3 py-2 text-sm"
                required
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Category</label>
              <select
                value={form.category}
                onChange={(e) =>
                  setForm((f) => ({ ...f, category: e.target.value }))
                }
                className="w-full rounded-md border px-3 py-2 text-sm"
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c.charAt(0).toUpperCase() + c.slice(1)}
                  </option>
                ))}
              </select>
            </div>
            <div className="sm:col-span-2 lg:col-span-3">
              <label className="mb-1 block text-sm font-medium">Description</label>
              <input
                type="text"
                value={form.description}
                onChange={(e) =>
                  setForm((f) => ({ ...f, description: e.target.value }))
                }
                placeholder="What does this flag control?"
                className="w-full rounded-md border px-3 py-2 text-sm"
              />
            </div>
            <div className="flex items-center gap-6">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.default_enabled}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, default_enabled: e.target.checked }))
                  }
                  className="rounded"
                />
                Enabled by default
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.is_global}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, is_global: e.target.checked }))
                  }
                  className="rounded"
                />
                Global (all tenants)
              </label>
            </div>
            <div className="flex items-end">
              <button
                type="submit"
                disabled={creating}
                className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                {creating ? "Creating..." : "Create Flag"}
              </button>
            </div>
          </form>
        </Card>
      )}

      {/* Flag matrix */}
      {flags.length === 0 ? (
        <Card className="p-8 text-center">
          <p className="text-muted-foreground">
            No feature flags configured yet. Click "Create Flag" to add one.
          </p>
        </Card>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50 text-left">
                <th className="min-w-[250px] py-3 pr-4 pl-4 font-medium">Flag</th>
                {tenantNames.map((t) => (
                  <th
                    key={t.tenant_id}
                    className="min-w-[120px] px-2 py-3 text-center font-medium"
                  >
                    {t.tenant_name}
                  </th>
                ))}
                <th className="w-[80px] px-2 py-3 text-center font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {flags.map((flag) => (
                <tr key={flag.id} className="border-b hover:bg-gray-50/50">
                  <td className="py-3 pr-4 pl-4">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{flag.key}</span>
                      <Badge
                        variant={flag.enabled_by_default ? "default" : "secondary"}
                        className={`text-[10px] ${flag.enabled_by_default ? "bg-green-100 text-green-800" : ""}`}
                      >
                        {flag.enabled_by_default ? "ON" : "OFF"}
                      </Badge>
                    </div>
                    {flag.description && (
                      <div className="mt-0.5 text-xs text-muted-foreground">
                        {flag.description}
                      </div>
                    )}
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
                  <td className="px-2 py-3 text-center">
                    <button
                      onClick={() => handleDelete(flag.id, flag.key)}
                      className="rounded px-2 py-1 text-xs text-red-600 transition-colors hover:bg-red-50"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
