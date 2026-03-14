import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { featureFlagService } from "@/services/feature-flag-service";
import type {
  FeatureFlag,
  TenantFlagMatrix,
  FlagAuditLogEntry,
  PaginatedFlagAuditLogs,
} from "@/types/feature-flag";

type Tab = "matrix" | "flags" | "logs";

export default function FeatureFlagsPage() {
  const [tab, setTab] = useState<Tab>("matrix");

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">Feature Flags</h1>
        <p className="text-muted-foreground text-sm">
          Manage feature availability across tenants.
        </p>
      </div>

      <div className="flex gap-2 border-b pb-2">
        {(["matrix", "flags", "logs"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              tab === t
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted"
            }`}
          >
            {t === "matrix"
              ? "Toggle Matrix"
              : t === "flags"
                ? "Flag Definitions"
                : "Audit Logs"}
          </button>
        ))}
      </div>

      {tab === "matrix" && <MatrixView />}
      {tab === "flags" && <FlagDefinitions />}
      {tab === "logs" && <AuditLogsView />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Toggle Matrix
// ---------------------------------------------------------------------------

function MatrixView() {
  const [matrix, setMatrix] = useState<TenantFlagMatrix | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [notesModal, setNotesModal] = useState<{
    flagId: string;
    tenantId: string;
    tenantName: string;
    flagName: string;
    enabled: boolean;
  } | null>(null);
  const [notes, setNotes] = useState("");

  const loadMatrix = useCallback(async () => {
    try {
      const data = await featureFlagService.getMatrix();
      setMatrix(data);
    } catch {
      toast.error("Failed to load feature flag matrix");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMatrix();
  }, [loadMatrix]);

  const categories = useMemo(() => {
    if (!matrix) return [];
    return [...new Set(matrix.flags.map((f) => f.category))].sort();
  }, [matrix]);

  const filteredFlags = useMemo(() => {
    if (!matrix) return [];
    return matrix.flags.filter((f) => {
      if (
        search &&
        !f.name.toLowerCase().includes(search.toLowerCase()) &&
        !f.key.toLowerCase().includes(search.toLowerCase())
      )
        return false;
      if (categoryFilter && f.category !== categoryFilter) return false;
      return true;
    });
  }, [matrix, search, categoryFilter]);

  const isOverridden = (flagId: string, tenantId: string): boolean => {
    return matrix?.overrides[flagId]?.[tenantId] !== undefined;
  };

  const resolvedEnabled = (flag: FeatureFlag, tenantId: string): boolean => {
    const override = matrix?.overrides[flag.id]?.[tenantId];
    return override !== undefined ? override : flag.default_enabled;
  };

  const handleToggle = async (
    flag: FeatureFlag,
    tenantId: string,
    tenantName: string,
  ) => {
    const currentEnabled = resolvedEnabled(flag, tenantId);
    const newEnabled = !currentEnabled;

    // If turning off, prompt for notes
    if (!newEnabled) {
      setNotesModal({
        flagId: flag.id,
        tenantId,
        tenantName,
        flagName: flag.name,
        enabled: false,
      });
      setNotes("");
      return;
    }

    try {
      await featureFlagService.setTenantFlag(flag.id, tenantId, newEnabled);
      await loadMatrix();
      toast.success(`Enabled "${flag.name}" for ${tenantName}`);
    } catch {
      toast.error("Failed to update flag");
    }
  };

  const handleNotesSubmit = async () => {
    if (!notesModal) return;
    try {
      await featureFlagService.setTenantFlag(
        notesModal.flagId,
        notesModal.tenantId,
        notesModal.enabled,
        notes || undefined,
      );
      await loadMatrix();
      toast.success(
        `Disabled "${notesModal.flagName}" for ${notesModal.tenantName}`,
      );
      setNotesModal(null);
    } catch {
      toast.error("Failed to update flag");
    }
  };

  const handleResetOverride = async (flagId: string, tenantId: string) => {
    try {
      await featureFlagService.removeTenantOverride(flagId, tenantId);
      await loadMatrix();
      toast.success("Override removed — using default");
    } catch {
      toast.error("Failed to remove override");
    }
  };

  const handleBulkEnable = async (flagId: string) => {
    if (!matrix) return;
    const tenantIds = matrix.tenants.map((t) => t.id);
    try {
      const result = await featureFlagService.bulkSetFlag(
        flagId,
        tenantIds,
        true,
      );
      await loadMatrix();
      toast.success(`Enabled for ${result.updated} tenants`);
    } catch {
      toast.error("Bulk enable failed");
    }
  };

  if (loading) {
    return <p className="text-muted-foreground text-sm">Loading matrix...</p>;
  }

  if (!matrix || matrix.tenants.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">No tenants found.</p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Input
          placeholder="Search flags..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="rounded-md border bg-background px-3 py-2 text-sm"
        >
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>

      <div className="overflow-x-auto rounded-md border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="sticky left-0 z-10 bg-muted/50 px-4 py-3 text-left font-medium">
                Flag
              </th>
              <th className="px-3 py-3 text-center font-medium text-xs">
                Default
              </th>
              {matrix.tenants.map((t) => (
                <th
                  key={t.id}
                  className="px-3 py-3 text-center font-medium text-xs whitespace-nowrap"
                >
                  {t.name}
                </th>
              ))}
              <th className="px-3 py-3 text-center font-medium text-xs">
                Bulk
              </th>
            </tr>
          </thead>
          <tbody>
            {filteredFlags.map((flag) => (
              <tr key={flag.id} className="border-b hover:bg-muted/30">
                <td className="sticky left-0 z-10 bg-background px-4 py-2">
                  <div className="font-medium">{flag.name}</div>
                  <div className="text-muted-foreground text-xs">
                    {flag.key}
                  </div>
                </td>
                <td className="px-3 py-2 text-center">
                  <span
                    className={`inline-block h-3 w-3 rounded-full ${
                      flag.default_enabled ? "bg-green-500" : "bg-red-400"
                    }`}
                    title={
                      flag.default_enabled ? "Default: ON" : "Default: OFF"
                    }
                  />
                </td>
                {matrix.tenants.map((t) => {
                  const enabled = resolvedEnabled(flag, t.id);
                  const overridden = isOverridden(flag.id, t.id);
                  return (
                    <td key={t.id} className="px-3 py-2 text-center">
                      <button
                        onClick={() => handleToggle(flag, t.id, t.name)}
                        onContextMenu={(e) => {
                          e.preventDefault();
                          if (overridden)
                            handleResetOverride(flag.id, t.id);
                        }}
                        className={`inline-flex h-6 w-10 items-center rounded-full transition-colors ${
                          enabled ? "bg-green-500" : "bg-gray-300"
                        } ${overridden ? "ring-2 ring-blue-400 ring-offset-1" : ""}`}
                        title={
                          overridden
                            ? "Overridden (right-click to reset)"
                            : "Using default"
                        }
                      >
                        <span
                          className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
                            enabled ? "translate-x-5" : "translate-x-1"
                          }`}
                        />
                      </button>
                    </td>
                  );
                })}
                <td className="px-3 py-2 text-center">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleBulkEnable(flag.id)}
                    className="text-xs"
                  >
                    Enable All
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-muted-foreground text-xs">
        Blue ring = tenant override. Right-click a toggle to reset to default.
      </p>

      {/* Notes modal for disabling */}
      <Dialog
        open={!!notesModal}
        onOpenChange={() => setNotesModal(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Disable Feature Flag</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Disabling <strong>{notesModal?.flagName}</strong> for{" "}
            <strong>{notesModal?.tenantName}</strong>.
          </p>
          <div className="space-y-2">
            <Label htmlFor="notes">Reason (optional)</Label>
            <textarea
              id="notes"
              value={notes}
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setNotes(e.target.value)}
              placeholder="Why is this being disabled?"
            className="w-full rounded-md border bg-background px-3 py-2 text-sm"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setNotesModal(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleNotesSubmit}>
              Disable
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Flag Definitions (CRUD)
// ---------------------------------------------------------------------------

function FlagDefinitions() {
  const [flags, setFlags] = useState<FeatureFlag[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newFlag, setNewFlag] = useState({
    key: "",
    name: "",
    description: "",
    category: "general",
    default_enabled: false,
  });

  const loadFlags = useCallback(async () => {
    try {
      const data = await featureFlagService.listFlags();
      setFlags(data);
    } catch {
      toast.error("Failed to load flags");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFlags();
  }, [loadFlags]);

  const handleCreate = async () => {
    if (!newFlag.key || !newFlag.name) {
      toast.error("Key and name are required");
      return;
    }
    try {
      await featureFlagService.createFlag(newFlag);
      toast.success("Flag created");
      setShowCreate(false);
      setNewFlag({
        key: "",
        name: "",
        description: "",
        category: "general",
        default_enabled: false,
      });
      loadFlags();
    } catch {
      toast.error("Failed to create flag");
    }
  };

  const handleToggleDefault = async (flag: FeatureFlag) => {
    try {
      await featureFlagService.updateFlag(flag.id, {
        default_enabled: !flag.default_enabled,
      });
      loadFlags();
    } catch {
      toast.error("Failed to update flag");
    }
  };

  const handleDelete = async (flag: FeatureFlag) => {
    if (!confirm(`Delete flag "${flag.name}"? This removes all tenant overrides.`))
      return;
    try {
      await featureFlagService.deleteFlag(flag.id);
      toast.success("Flag deleted");
      loadFlags();
    } catch {
      toast.error("Failed to delete flag");
    }
  };

  if (loading) {
    return <p className="text-muted-foreground text-sm">Loading flags...</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {flags.length} flag{flags.length !== 1 ? "s" : ""} defined
        </p>
        <Button size="sm" onClick={() => setShowCreate(true)}>
          Add Flag
        </Button>
      </div>

      <div className="grid gap-3">
        {flags.map((flag) => (
          <Card key={flag.id}>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base">{flag.name}</CardTitle>
                  <CardDescription className="font-mono text-xs">
                    {flag.key}
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <span className="rounded bg-muted px-2 py-0.5 text-xs">
                    {flag.category}
                  </span>
                  <button
                    onClick={() => handleToggleDefault(flag)}
                    className={`inline-flex h-6 w-10 items-center rounded-full transition-colors ${
                      flag.default_enabled ? "bg-green-500" : "bg-gray-300"
                    }`}
                    title="Toggle default"
                  >
                    <span
                      className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
                        flag.default_enabled
                          ? "translate-x-5"
                          : "translate-x-1"
                      }`}
                    />
                  </button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-destructive text-xs"
                    onClick={() => handleDelete(flag)}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            </CardHeader>
            {flag.description && (
              <CardContent className="pt-0">
                <p className="text-muted-foreground text-sm">
                  {flag.description}
                </p>
              </CardContent>
            )}
          </Card>
        ))}
      </div>

      {/* Create dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Feature Flag</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label htmlFor="key">Key</Label>
              <Input
                id="key"
                placeholder="feature.my_feature"
                value={newFlag.key}
                onChange={(e) =>
                  setNewFlag({ ...newFlag, key: e.target.value })
                }
              />
            </div>
            <div>
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                placeholder="My Feature"
                value={newFlag.name}
                onChange={(e) =>
                  setNewFlag({ ...newFlag, name: e.target.value })
                }
              />
            </div>
            <div>
              <Label htmlFor="desc">Description</Label>
              <textarea
                id="desc"
                value={newFlag.description}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
                  setNewFlag({ ...newFlag, description: e.target.value })
                }
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              />
            </div>
            <div>
              <Label htmlFor="cat">Category</Label>
              <Input
                id="cat"
                value={newFlag.category}
                onChange={(e) =>
                  setNewFlag({ ...newFlag, category: e.target.value })
                }
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="default_enabled"
                checked={newFlag.default_enabled}
                onChange={(e) =>
                  setNewFlag({
                    ...newFlag,
                    default_enabled: e.target.checked,
                  })
                }
              />
              <Label htmlFor="default_enabled">Enabled by default</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreate(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate}>Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Audit Logs
// ---------------------------------------------------------------------------

function AuditLogsView() {
  const [logs, setLogs] = useState<FlagAuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState("");

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const data: PaginatedFlagAuditLogs =
        await featureFlagService.getAuditLogs({
          page,
          per_page: 50,
          action: actionFilter || undefined,
        });
      setLogs(data.items);
      setTotal(data.total);
    } catch {
      toast.error("Failed to load audit logs");
    } finally {
      setLoading(false);
    }
  }, [page, actionFilter]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  const actionBadge = (action: string) => {
    const colors: Record<string, string> = {
      blocked: "bg-red-100 text-red-800",
      toggled_on: "bg-green-100 text-green-800",
      toggled_off: "bg-yellow-100 text-yellow-800",
      override_removed: "bg-blue-100 text-blue-800",
    };
    return (
      <span
        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${colors[action] || "bg-gray-100 text-gray-800"}`}
      >
        {action.replace("_", " ")}
      </span>
    );
  };

  const totalPages = Math.ceil(total / 50);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <select
          value={actionFilter}
          onChange={(e) => {
            setActionFilter(e.target.value);
            setPage(1);
          }}
          className="rounded-md border bg-background px-3 py-2 text-sm"
        >
          <option value="">All actions</option>
          <option value="blocked">Blocked</option>
          <option value="toggled_on">Toggled On</option>
          <option value="toggled_off">Toggled Off</option>
          <option value="override_removed">Override Removed</option>
        </select>
        <span className="text-muted-foreground text-sm">
          {total} log{total !== 1 ? "s" : ""}
        </span>
      </div>

      {loading ? (
        <p className="text-muted-foreground text-sm">Loading...</p>
      ) : logs.length === 0 ? (
        <p className="text-muted-foreground text-sm">No audit logs found.</p>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-2 text-left font-medium">Time</th>
                <th className="px-4 py-2 text-left font-medium">Action</th>
                <th className="px-4 py-2 text-left font-medium">Flag</th>
                <th className="px-4 py-2 text-left font-medium">Endpoint</th>
                <th className="px-4 py-2 text-left font-medium">Details</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} className="border-b">
                  <td className="px-4 py-2 whitespace-nowrap text-xs">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2">{actionBadge(log.action)}</td>
                  <td className="px-4 py-2 font-mono text-xs">
                    {log.flag_key}
                  </td>
                  <td className="px-4 py-2 text-xs text-muted-foreground">
                    {log.endpoint || "—"}
                  </td>
                  <td className="px-4 py-2 text-xs text-muted-foreground">
                    {log.details || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button
            size="sm"
            variant="outline"
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
