import { useCallback, useEffect, useState } from "react";
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
import { accountingService } from "@/services/accounting-service";
import type {
  AccountingProviderInfo,
  AccountingStatus,
  SyncResult,
} from "@/types/accounting";

type Tab = "provider" | "sync" | "mappings";

export default function AccountingPage() {
  const [tab, setTab] = useState<Tab>("provider");

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">Accounting Integration</h1>
        <p className="text-muted-foreground text-sm">
          Configure your accounting provider and manage data sync.
        </p>
      </div>

      <div className="flex gap-2 border-b pb-2">
        {(["provider", "sync", "mappings"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              tab === t
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted"
            }`}
          >
            {t === "provider"
              ? "Provider"
              : t === "sync"
                ? "Sync"
                : "Account Mapping"}
          </button>
        ))}
      </div>

      {tab === "provider" && <ProviderTab />}
      {tab === "sync" && <SyncTab />}
      {tab === "mappings" && <MappingsTab />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Provider Tab
// ---------------------------------------------------------------------------

function ProviderTab() {
  const [providers, setProviders] = useState<AccountingProviderInfo[]>([]);
  const [status, setStatus] = useState<AccountingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);

  const load = useCallback(async () => {
    try {
      const [provs, stat] = await Promise.all([
        accountingService.getProviders(),
        accountingService.getStatus(),
      ]);
      setProviders(provs);
      setStatus(stat);
    } catch {
      toast.error("Failed to load accounting settings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleSwitch = async (providerKey: string) => {
    try {
      const newStatus = await accountingService.setProvider(providerKey);
      setStatus(newStatus);
      toast.success("Accounting provider updated");
    } catch {
      toast.error("Failed to switch provider");
    }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      const result = await accountingService.testConnection();
      setStatus(result);
      if (result.connected) {
        toast.success("Connection successful!");
      } else {
        toast.error(result.error || "Connection failed");
      }
    } catch {
      toast.error("Connection test failed");
    } finally {
      setTesting(false);
    }
  };

  const handleQBOConnect = async () => {
    try {
      const { authorization_url } = await accountingService.qboConnect();
      window.open(authorization_url, "_blank", "width=600,height=700");
    } catch {
      toast.error("Failed to initiate QuickBooks connection");
    }
  };

  const handleQBODisconnect = async () => {
    if (!confirm("Disconnect QuickBooks Online? This will revoke access tokens."))
      return;
    try {
      await accountingService.qboDisconnect();
      await load();
      toast.success("QuickBooks disconnected");
    } catch {
      toast.error("Failed to disconnect");
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
    <div className="space-y-6">
      {/* Connection status */}
      {status && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Connection Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <div
                className={`h-3 w-3 rounded-full ${
                  status.connected ? "bg-green-500" : "bg-red-500"
                }`}
              />
              <div>
                <p className="font-medium">
                  {providers.find((p) => p.key === status.provider)?.name ||
                    status.provider}
                </p>
                <p className="text-muted-foreground text-sm">
                  {status.connected ? "Connected" : status.error || "Not connected"}
                </p>
                {status.last_sync_at && (
                  <p className="text-muted-foreground text-xs">
                    Last sync: {new Date(status.last_sync_at).toLocaleString()}
                  </p>
                )}
              </div>
              <div className="ml-auto flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleTest}
                  disabled={testing}
                >
                  {testing ? "Testing..." : "Test Connection"}
                </Button>
                {status.provider === "quickbooks_online" && status.connected && (
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={handleQBODisconnect}
                  >
                    Disconnect
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Provider selection */}
      <div className="grid gap-4 md:grid-cols-3">
        {providers.map((provider) => {
          const isActive = status?.provider === provider.key;
          return (
            <Card
              key={provider.key}
              className={isActive ? "border-primary ring-primary/20 ring-2" : ""}
            >
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  {provider.name}
                  {isActive && (
                    <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                      Active
                    </span>
                  )}
                </CardTitle>
                <CardDescription>{provider.description}</CardDescription>
              </CardHeader>
              <CardContent>
                {provider.supports_sync && (
                  <p className="text-muted-foreground mb-3 text-xs">
                    Supports bidirectional sync
                  </p>
                )}
                {!isActive && provider.key !== "quickbooks_online" && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleSwitch(provider.key)}
                  >
                    Switch to {provider.name}
                  </Button>
                )}
                {!isActive && provider.key === "quickbooks_online" && (
                  <Button size="sm" onClick={handleQBOConnect}>
                    Connect QuickBooks
                  </Button>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sync Tab
// ---------------------------------------------------------------------------

const SYNC_TYPES = [
  { key: "customers", label: "Customers", icon: "👥" },
  { key: "bills", label: "Vendor Bills", icon: "📄" },
  { key: "bill_payments", label: "Vendor Payments", icon: "💳" },
  { key: "inventory", label: "Inventory Transactions", icon: "📦" },
  { key: "invoices", label: "Invoices", icon: "🧾" },
  { key: "payments", label: "AR Payments", icon: "💰" },
];

function SyncTab() {
  const [syncing, setSyncing] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, SyncResult>>({});
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const handleSync = async (syncType: string) => {
    setSyncing(syncType);
    try {
      const result = await accountingService.runSync({
        sync_type: syncType,
        direction: "push",
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      });
      setResults((prev) => ({ ...prev, [syncType]: result }));
      if (result.success) {
        toast.success(
          `Synced ${result.records_synced} records${
            result.records_failed > 0
              ? ` (${result.records_failed} failed)`
              : ""
          }`,
        );
      } else {
        toast.error(result.error_message || "Sync failed");
      }
    } catch {
      toast.error("Sync request failed");
    } finally {
      setSyncing(null);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Date Range (optional)</CardTitle>
          <CardDescription>
            Filter synced records by date. Leave blank to sync all.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex gap-4">
          <div>
            <Label htmlFor="sync-from">From</Label>
            <Input
              id="sync-from"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="sync-to">To</Label>
            <Input
              id="sync-to"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {SYNC_TYPES.map(({ key, label }) => {
          const result = results[key];
          return (
            <Card key={key}>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">{label}</CardTitle>
              </CardHeader>
              <CardContent>
                {result && (
                  <div className="mb-3 text-sm">
                    {result.success ? (
                      <p className="text-green-700">
                        {result.records_synced} synced
                        {result.records_failed > 0 && (
                          <span className="text-red-600">
                            , {result.records_failed} failed
                          </span>
                        )}
                      </p>
                    ) : (
                      <p className="text-red-600">
                        {result.error_message || "Failed"}
                      </p>
                    )}
                  </div>
                )}
                <Button
                  size="sm"
                  onClick={() => handleSync(key)}
                  disabled={syncing === key}
                >
                  {syncing === key ? "Syncing..." : "Sync Now"}
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mappings Tab
// ---------------------------------------------------------------------------

function MappingsTab() {
  const [status, setStatus] = useState<AccountingStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    accountingService
      .getStatus()
      .then(setStatus)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="border-primary h-8 w-8 animate-spin rounded-full border-b-2" />
      </div>
    );
  }

  if (status?.provider === "sage_csv" || status?.provider === "none") {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-muted-foreground">
            Account mapping is only available for providers with a chart of
            accounts (e.g., QuickBooks Online). Sage CSV export does not
            require account mapping.
          </p>
        </CardContent>
      </Card>
    );
  }

  return <AccountMappingView />;
}

function AccountMappingView() {
  const [accounts, setAccounts] = useState<
    { id: string; name: string; account_type: string; number: string | null }[]
  >([]);
  const [mappings, setMappings] = useState<
    {
      internal_id: string;
      internal_name: string;
      provider_id: string | null;
    }[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [editModal, setEditModal] = useState<{
    internalId: string;
    internalName: string;
  } | null>(null);
  const [selectedAccount, setSelectedAccount] = useState("");

  const load = useCallback(async () => {
    try {
      const [accts, maps] = await Promise.all([
        accountingService.getChartOfAccounts(),
        accountingService.getMappings(),
      ]);
      setAccounts(accts);
      setMappings(maps);
    } catch {
      toast.error("Failed to load account data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleSaveMapping = async () => {
    if (!editModal || !selectedAccount) return;
    try {
      await accountingService.setMapping(editModal.internalId, selectedAccount);
      toast.success("Mapping saved");
      setEditModal(null);
      load();
    } catch {
      toast.error("Failed to save mapping");
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
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Account Mappings</CardTitle>
          <CardDescription>
            Map internal accounts to your accounting provider's chart of
            accounts.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {mappings.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No mappings configured yet. Mappings will appear as you set them
              up.
            </p>
          ) : (
            <div className="space-y-2">
              {mappings.map((m) => (
                <div
                  key={m.internal_id}
                  className="flex items-center justify-between rounded-md border px-3 py-2"
                >
                  <div>
                    <p className="text-sm font-medium">{m.internal_name}</p>
                    <p className="text-muted-foreground text-xs">
                      {m.provider_id
                        ? `Mapped to: ${m.provider_id}`
                        : "Not mapped"}
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setEditModal({
                        internalId: m.internal_id,
                        internalName: m.internal_name,
                      });
                      setSelectedAccount(m.provider_id || "");
                    }}
                  >
                    Edit
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {accounts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Provider Chart of Accounts</CardTitle>
            <CardDescription>
              {accounts.length} accounts loaded from provider
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="max-h-64 overflow-y-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-muted-foreground border-b text-left text-xs">
                    <th className="pb-2">Number</th>
                    <th className="pb-2">Name</th>
                    <th className="pb-2">Type</th>
                  </tr>
                </thead>
                <tbody>
                  {accounts.map((a) => (
                    <tr key={a.id} className="border-b last:border-0">
                      <td className="py-1.5">{a.number || "-"}</td>
                      <td className="py-1.5">{a.name}</td>
                      <td className="py-1.5 capitalize">{a.account_type}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Edit mapping modal */}
      {editModal && (
        <Dialog open onOpenChange={() => setEditModal(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Map: {editModal.internalName}</DialogTitle>
            </DialogHeader>
            <div>
              <Label htmlFor="provider-account">Provider Account</Label>
              <select
                id="provider-account"
                className="border-input mt-1 w-full rounded-md border px-3 py-2 text-sm"
                value={selectedAccount}
                onChange={(e) => setSelectedAccount(e.target.value)}
              >
                <option value="">-- Select account --</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.number ? `${a.number} - ` : ""}
                    {a.name} ({a.account_type})
                  </option>
                ))}
              </select>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditModal(null)}>
                Cancel
              </Button>
              <Button onClick={handleSaveMapping} disabled={!selectedAccount}>
                Save
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
