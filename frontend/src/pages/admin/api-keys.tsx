import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
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
import { apiKeyService } from "@/services/api-key-service";
import type { ApiKey, ApiKeyCreated, ApiKeyUsageSummary } from "@/types/api-key";

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [createdKey, setCreatedKey] = useState<ApiKeyCreated | null>(null);
  const [usageModal, setUsageModal] = useState<ApiKeyUsageSummary | null>(null);
  const [availableScopes, setAvailableScopes] = useState<string[]>([]);

  const loadKeys = useCallback(async () => {
    try {
      const data = await apiKeyService.list();
      setKeys(data);
    } catch {
      toast.error("Failed to load API keys");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadKeys();
    apiKeyService.getScopes().then(setAvailableScopes).catch(() => {});
  }, [loadKeys]);

  const handleRevoke = async (key: ApiKey) => {
    if (!confirm(`Revoke key "${key.name}"? It will stop working immediately.`))
      return;
    try {
      await apiKeyService.revoke(key.id);
      toast.success("API key revoked");
      loadKeys();
    } catch {
      toast.error("Failed to revoke key");
    }
  };

  const handleDelete = async (key: ApiKey) => {
    if (
      !confirm(
        `Permanently delete key "${key.name}"? This cannot be undone.`,
      )
    )
      return;
    try {
      await apiKeyService.delete(key.id);
      toast.success("API key deleted");
      loadKeys();
    } catch {
      toast.error("Failed to delete key");
    }
  };

  const handleViewUsage = async (key: ApiKey) => {
    try {
      const usage = await apiKeyService.getUsage(key.id);
      setUsageModal(usage);
    } catch {
      toast.error("Failed to load usage data");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="border-primary h-8 w-8 animate-spin rounded-full border-b-2" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">API Keys</h1>
          <p className="text-muted-foreground text-sm">
            Manage API keys for external integrations. Keys are separate from
            user authentication.
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)}>Create API Key</Button>
      </div>

      {keys.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              No API keys yet. Create one to enable external integrations.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {keys.map((key) => (
            <Card key={key.id}>
              <CardContent className="flex items-center gap-4 py-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{key.name}</span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        key.is_active
                          ? "bg-green-100 text-green-700"
                          : "bg-red-100 text-red-700"
                      }`}
                    >
                      {key.is_active ? "Active" : "Revoked"}
                    </span>
                  </div>
                  <div className="text-muted-foreground mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs">
                    <span>
                      Prefix:{" "}
                      <code className="bg-muted rounded px-1">
                        {key.key_prefix}...
                      </code>
                    </span>
                    <span>
                      Rate: {key.rate_limit_per_minute}/min
                    </span>
                    <span>
                      Scopes: {key.scopes.length === 0 ? "none" : key.scopes.length}
                    </span>
                    {key.expires_at && (
                      <span>
                        Expires:{" "}
                        {new Date(key.expires_at).toLocaleDateString()}
                      </span>
                    )}
                    {key.last_used_at && (
                      <span>
                        Last used:{" "}
                        {new Date(key.last_used_at).toLocaleString()}
                      </span>
                    )}
                    <span>
                      Created:{" "}
                      {new Date(key.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  {key.scopes.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {key.scopes.map((scope) => (
                        <span
                          key={scope}
                          className="bg-muted rounded px-1.5 py-0.5 text-xs"
                        >
                          {scope}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleViewUsage(key)}
                  >
                    Usage
                  </Button>
                  {key.is_active && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleRevoke(key)}
                    >
                      Revoke
                    </Button>
                  )}
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleDelete(key)}
                  >
                    Delete
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create modal */}
      {showCreate && (
        <CreateKeyModal
          availableScopes={availableScopes}
          onCreated={(created) => {
            setCreatedKey(created);
            setShowCreate(false);
            loadKeys();
          }}
          onClose={() => setShowCreate(false)}
        />
      )}

      {/* Key revealed modal */}
      {createdKey && (
        <KeyRevealedModal
          created={createdKey}
          onClose={() => setCreatedKey(null)}
        />
      )}

      {/* Usage modal */}
      {usageModal && (
        <UsageModal
          usage={usageModal}
          onClose={() => setUsageModal(null)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Create Key Modal
// ---------------------------------------------------------------------------

function CreateKeyModal({
  availableScopes,
  onCreated,
  onClose,
}: {
  availableScopes: string[];
  onCreated: (key: ApiKeyCreated) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState("");
  const [selectedScopes, setSelectedScopes] = useState<string[]>([]);
  const [rateLimit, setRateLimit] = useState(60);
  const [expiresIn, setExpiresIn] = useState("");
  const [saving, setSaving] = useState(false);

  const toggleScope = (scope: string) => {
    setSelectedScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope],
    );
  };

  const handleSubmit = async () => {
    if (!name.trim()) {
      toast.error("Name is required");
      return;
    }
    setSaving(true);
    try {
      let expires_at: string | null = null;
      if (expiresIn) {
        const days = parseInt(expiresIn);
        if (!isNaN(days) && days > 0) {
          const d = new Date();
          d.setDate(d.getDate() + days);
          expires_at = d.toISOString();
        }
      }
      const created = await apiKeyService.create({
        name: name.trim(),
        scopes: selectedScopes,
        rate_limit_per_minute: rateLimit,
        expires_at,
      });
      toast.success("API key created");
      onCreated(created);
    } catch {
      toast.error("Failed to create key");
    } finally {
      setSaving(false);
    }
  };

  // Group scopes by resource
  const scopeGroups: Record<string, string[]> = {};
  availableScopes.forEach((scope) => {
    const [resource] = scope.split(".");
    if (!scopeGroups[resource]) scopeGroups[resource] = [];
    scopeGroups[resource].push(scope);
  });

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Create API Key</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label htmlFor="key-name">Name</Label>
            <Input
              id="key-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., QuickBooks Sync, Warehouse Integration"
            />
          </div>
          <div>
            <Label htmlFor="key-rate">Rate Limit (requests/minute)</Label>
            <Input
              id="key-rate"
              type="number"
              min={1}
              max={10000}
              value={rateLimit}
              onChange={(e) => setRateLimit(parseInt(e.target.value) || 60)}
            />
          </div>
          <div>
            <Label htmlFor="key-expires">Expires In (days, blank = never)</Label>
            <Input
              id="key-expires"
              type="number"
              min={1}
              value={expiresIn}
              onChange={(e) => setExpiresIn(e.target.value)}
              placeholder="e.g., 90"
            />
          </div>
          <div>
            <Label>Scopes</Label>
            <p className="text-muted-foreground mb-2 text-xs">
              Select which resources this key can access. Leave empty for no
              access.
            </p>
            <div className="space-y-3">
              {Object.entries(scopeGroups).map(([resource, scopes]) => (
                <div key={resource}>
                  <p className="mb-1 text-xs font-semibold capitalize">
                    {resource.replace(/_/g, " ")}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {scopes.map((scope) => (
                      <button
                        key={scope}
                        type="button"
                        onClick={() => toggleScope(scope)}
                        className={`rounded-md border px-2 py-1 text-xs transition-colors ${
                          selectedScopes.includes(scope)
                            ? "border-primary bg-primary text-primary-foreground"
                            : "hover:bg-muted"
                        }`}
                      >
                        {scope.split(".")[1]}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={saving}>
            {saving ? "Creating..." : "Create Key"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Key Revealed Modal (shown once after creation)
// ---------------------------------------------------------------------------

function KeyRevealedModal({
  created,
  onClose,
}: {
  created: ApiKeyCreated;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);

  const copyKey = async () => {
    await navigator.clipboard.writeText(created.key);
    setCopied(true);
    toast.success("Key copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>API Key Created</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="rounded-md border border-yellow-300 bg-yellow-50 p-3">
            <p className="text-sm font-medium text-yellow-800">
              Copy this key now. It will not be shown again.
            </p>
          </div>
          <div>
            <Label>Key Name</Label>
            <p className="text-sm font-medium">{created.name}</p>
          </div>
          <div>
            <Label>API Key</Label>
            <div className="mt-1 flex items-center gap-2">
              <code className="bg-muted flex-1 rounded-md p-2 text-xs break-all">
                {created.key}
              </code>
              <Button variant="outline" size="sm" onClick={copyKey}>
                {copied ? "Copied!" : "Copy"}
              </Button>
            </div>
          </div>
          <div className="text-muted-foreground text-xs">
            <p>
              Use this key in the <code>X-API-Key</code> header for API
              requests.
            </p>
          </div>
        </div>
        <DialogFooter>
          <Button onClick={onClose}>Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Usage Modal
// ---------------------------------------------------------------------------

function UsageModal({
  usage,
  onClose,
}: {
  usage: ApiKeyUsageSummary;
  onClose: () => void;
}) {
  const maxRequests = Math.max(
    1,
    ...usage.hourly.map((h) => h.request_count),
  );

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            Usage: {usage.name}{" "}
            <span className="text-muted-foreground text-sm font-normal">
              ({usage.key_prefix}...)
            </span>
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <CardHeader className="pb-1">
                <CardDescription className="text-xs">
                  Requests (24h)
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">
                  {usage.total_requests_24h.toLocaleString()}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardDescription className="text-xs">
                  Errors (24h)
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-red-600">
                  {usage.total_errors_24h.toLocaleString()}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardDescription className="text-xs">
                  Last Used
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm font-medium">
                  {usage.last_used_at
                    ? new Date(usage.last_used_at).toLocaleString()
                    : "Never"}
                </p>
              </CardContent>
            </Card>
          </div>

          {usage.hourly.length > 0 ? (
            <div>
              <p className="mb-2 text-sm font-medium">Hourly Requests</p>
              <div className="flex items-end gap-0.5" style={{ height: 120 }}>
                {usage.hourly.map((h, i) => {
                  const pct = (h.request_count / maxRequests) * 100;
                  const hour = new Date(h.hour).getHours();
                  return (
                    <div
                      key={i}
                      className="group relative flex flex-1 flex-col items-center"
                    >
                      <div
                        className="bg-primary w-full min-w-[4px] rounded-t"
                        style={{ height: `${Math.max(2, pct)}%` }}
                        title={`${hour}:00 — ${h.request_count} requests, ${h.error_count} errors`}
                      />
                      {i % 4 === 0 && (
                        <span className="text-muted-foreground mt-1 text-[10px]">
                          {hour}h
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <p className="text-muted-foreground text-center text-sm">
              No usage data in the last 24 hours.
            </p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
