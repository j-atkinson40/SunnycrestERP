import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  getTenantModules,
  setTenantModule,
  applyPresetToTenant,
  listVerticalPresets,
} from "@/services/platform-service";
import type { TenantModuleConfig, VerticalPreset } from "@/types/platform";

const CATEGORY_LABELS: Record<string, string> = {
  core: "Core (Always Enabled)",
  business: "Business",
  operations: "Operations",
  manufacturing: "Manufacturing",
  funeral: "Funeral Home",
  cemetery: "Cemetery",
  crematory: "Crematory",
  addon: "Add-ons",
};

const CATEGORY_ORDER = [
  "core",
  "business",
  "operations",
  "manufacturing",
  "funeral",
  "cemetery",
  "crematory",
  "addon",
];

export default function TenantModulesPage() {
  const { tenantId } = useParams<{ tenantId: string }>();
  const [modules, setModules] = useState<TenantModuleConfig[]>([]);
  const [presets, setPresets] = useState<VerticalPreset[]>([]);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState<string | null>(null);
  const [applyingPreset, setApplyingPreset] = useState(false);

  const fetchData = useCallback(async () => {
    if (!tenantId) return;
    try {
      const [mods, pres] = await Promise.all([
        getTenantModules(tenantId),
        listVerticalPresets(),
      ]);
      setModules(mods);
      setPresets(pres);
    } catch {
      toast.error("Failed to load module configuration");
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function handleToggle(moduleKey: string, currentEnabled: boolean) {
    if (!tenantId) return;
    setToggling(moduleKey);
    try {
      await setTenantModule(tenantId, moduleKey, !currentEnabled);
      setModules((prev) =>
        prev.map((m) =>
          m.key === moduleKey ? { ...m, enabled: !currentEnabled } : m
        )
      );
      toast.success(
        `${moduleKey} ${!currentEnabled ? "enabled" : "disabled"}`
      );
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      toast.error(
        axiosErr.response?.data?.detail || "Failed to update module"
      );
    } finally {
      setToggling(null);
    }
  }

  async function handleApplyPreset(presetKey: string) {
    if (!tenantId) return;
    if (
      !confirm(
        `Apply the "${presetKey}" preset? This will reset all module settings for this tenant.`
      )
    )
      return;

    setApplyingPreset(true);
    try {
      await applyPresetToTenant(tenantId, presetKey);
      toast.success(`Preset "${presetKey}" applied`);
      // Refresh modules
      setLoading(true);
      await fetchData();
    } catch {
      toast.error("Failed to apply preset");
    } finally {
      setApplyingPreset(false);
    }
  }

  const groupedModules = useMemo(() => {
    const groups: Record<string, TenantModuleConfig[]> = {};
    for (const cat of CATEGORY_ORDER) {
      const items = modules.filter((m) => m.category === cat);
      if (items.length > 0) groups[cat] = items;
    }
    return groups;
  }, [modules]);

  const enabledCount = modules.filter((m) => m.enabled).length;

  if (loading) {
    return <p className="text-muted-foreground">Loading modules...</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Link
              to={`/tenants/${tenantId}`}
              className="text-sm text-indigo-600 hover:underline"
            >
              &larr; Back to tenant
            </Link>
          </div>
          <h1 className="mt-1 text-2xl font-bold">Module Configuration</h1>
          <p className="text-muted-foreground">
            {enabledCount} of {modules.length} modules enabled
          </p>
        </div>
      </div>

      {/* Quick presets */}
      <Card className="p-4">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-gray-500">
          Apply Vertical Preset
        </h3>
        <div className="flex flex-wrap gap-2">
          {presets.map((preset) => (
            <button
              key={preset.key}
              onClick={() => handleApplyPreset(preset.key)}
              disabled={applyingPreset}
              className="rounded-md border px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-indigo-50 hover:border-indigo-300 hover:text-indigo-700 disabled:opacity-50"
            >
              {preset.name}
              {preset.module_keys.length > 0 && (
                <span className="ml-1 text-xs text-gray-400">
                  ({preset.module_keys.length})
                </span>
              )}
            </button>
          ))}
        </div>
      </Card>

      {/* Module groups */}
      {CATEGORY_ORDER.map((cat) => {
        const items = groupedModules[cat];
        if (!items) return null;
        return (
          <div key={cat}>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-gray-500">
              {CATEGORY_LABELS[cat] || cat}
            </h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((m) => (
                <Card
                  key={m.key}
                  className={`p-4 ${
                    m.enabled
                      ? "border-indigo-200 bg-indigo-50/30"
                      : ""
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{m.name}</span>
                        {m.is_core && (
                          <Badge
                            variant="secondary"
                            className="text-[10px]"
                          >
                            Core
                          </Badge>
                        )}
                      </div>
                      {m.description && (
                        <p className="mt-1 text-xs text-gray-500 line-clamp-2">
                          {m.description}
                        </p>
                      )}
                      {m.dependencies.length > 0 && (
                        <p className="mt-1 text-[10px] text-gray-400">
                          Requires: {m.dependencies.join(", ")}
                        </p>
                      )}
                    </div>
                    <Switch
                      checked={m.enabled}
                      onCheckedChange={() =>
                        handleToggle(m.key, m.enabled)
                      }
                      disabled={m.is_core || toggling === m.key}
                    />
                  </div>
                </Card>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
