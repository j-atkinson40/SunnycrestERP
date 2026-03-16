import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/contexts/auth-context";
import apiClient from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

interface ModuleInfo {
  module: string;
  enabled: boolean;
  label: string;
  description: string;
  locked: boolean;
}

export default function ModulesPage() {
  const { isAdmin, refreshUser } = useAuth();
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState<string | null>(null);

  const fetchModules = useCallback(async () => {
    try {
      const { data } = await apiClient.get("/modules/");
      setModules(data);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchModules();
  }, [fetchModules]);

  async function handleToggle(mod: ModuleInfo) {
    if (mod.locked || !isAdmin) return;

    const newEnabled = !mod.enabled;
    setToggling(mod.module);

    // Optimistic update
    setModules((prev) =>
      prev.map((m) =>
        m.module === mod.module ? { ...m, enabled: newEnabled } : m
      )
    );

    try {
      await apiClient.put(`/modules/${mod.module}`, { enabled: newEnabled });
      toast.success(
        `${mod.label} ${newEnabled ? "enabled" : "disabled"}`
      );
      // Refresh user context so sidebar updates immediately
      if (refreshUser) {
        await refreshUser();
      }
    } catch (err) {
      // Rollback
      setModules((prev) =>
        prev.map((m) =>
          m.module === mod.module ? { ...m, enabled: mod.enabled } : m
        )
      );
      toast.error(getApiErrorMessage(err));
    } finally {
      setToggling(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-muted-foreground">Loading modules...</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Modules</h1>
        <p className="text-muted-foreground">
          Enable or disable feature modules for your company. Changes take
          effect immediately.
        </p>
      </div>

      <div className="space-y-3">
        {modules.map((mod) => (
          <Card key={mod.module} className="flex items-center justify-between p-4">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <span className="font-medium">{mod.label}</span>
                {mod.locked && (
                  <Badge variant="secondary" className="text-xs">
                    Required
                  </Badge>
                )}
                {mod.enabled && !mod.locked && (
                  <Badge className="bg-green-100 text-green-800 text-xs">
                    Active
                  </Badge>
                )}
              </div>
              <p className="text-sm text-muted-foreground">
                {mod.description}
              </p>
            </div>
            <Switch
              checked={mod.enabled}
              onCheckedChange={() => handleToggle(mod)}
              disabled={mod.locked || !isAdmin || toggling === mod.module}
            />
          </Card>
        ))}
      </div>
    </div>
  );
}
