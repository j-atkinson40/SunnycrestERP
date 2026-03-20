/**
 * Sync Health Dashboard — full view of accounting connection health,
 * sync activity, logs, and settings summary.
 * Route: /settings/integrations/accounting
 */

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import {
  Activity,
  AlertCircle,
  ArrowRight,
  Check,
  CheckCircle2,
  Clock,
  ExternalLink,
  FileText,
  Loader2,
  Plug,
  PlugZap,
  RefreshCw,
  Settings,
  Unplug,
  Users,
  X,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import apiClient from "@/lib/api-client";
import { AccountingErrorCard } from "@/components/accounting-error-card";

// ── Types ────────────────────────────────────────────────────────

interface ConnectionInfo {
  provider: string | null;
  provider_label: string;
  status: string;
  connected_since: string | null;
  last_sync_at: string | null;
  last_sync_status: string | null;
  last_sync_error: string | null;
  last_sync_error_code: string | null;
  qbo_company_name: string | null;
  sync_config: Record<string, boolean> | null;
}

interface WeeklyStats {
  invoices_pushed: number;
  payments_synced: number;
  customers_pushed: number;
  sync_errors: number;
}

interface SyncLogEntry {
  id: string;
  timestamp: string;
  type: string;
  status: string;
  details: string;
  error_code: string | null;
}

interface SyncLogResponse {
  items: SyncLogEntry[];
  total: number;
}

type LogFilter = "all" | "invoices" | "payments" | "customers" | "errors";

const PER_PAGE = 25;

// ── Helpers ──────────────────────────────────────────────────────

function fmtDate(d: string | null): string {
  if (!d) return "Never";
  return new Date(d).toLocaleDateString();
}

function fmtDateTime(d: string | null): string {
  if (!d) return "Never";
  const date = new Date(d);
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

function providerLabel(provider: string | null): string {
  switch (provider) {
    case "quickbooks_online":
      return "QuickBooks Online";
    case "quickbooks_desktop":
      return "QuickBooks Desktop";
    case "sage_100":
      return "Sage 100";
    default:
      return "Not connected";
  }
}

function statusBadge(status: string) {
  switch (status) {
    case "success":
      return (
        <Badge className="bg-green-100 text-green-800">
          <Check className="h-3 w-3 mr-1" />
          Success
        </Badge>
      );
    case "error":
    case "failed":
      return (
        <Badge variant="destructive">
          <X className="h-3 w-3 mr-1" />
          Failed
        </Badge>
      );
    case "pending":
      return (
        <Badge variant="outline">
          <Clock className="h-3 w-3 mr-1" />
          Pending
        </Badge>
      );
    case "skipped":
      return (
        <Badge variant="outline" className="text-muted-foreground">
          Skipped
        </Badge>
      );
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

// ── Main Component ───────────────────────────────────────────────

export default function SyncHealthDashboardPage() {
  const [connection, setConnection] = useState<ConnectionInfo | null>(null);
  const [weeklyStats, setWeeklyStats] = useState<WeeklyStats | null>(null);
  const [logs, setLogs] = useState<SyncLogEntry[]>([]);
  const [logTotal, setLogTotal] = useState(0);
  const [logPage, setLogPage] = useState(1);
  const [logFilter, setLogFilter] = useState<LogFilter>("all");
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<"success" | "error" | null>(
    null,
  );
  const [disconnecting, setDisconnecting] = useState(false);
  const [rerunningMatch, setRerunningMatch] = useState(false);

  // Load connection info + weekly stats
  useEffect(() => {
    const loadData = async () => {
      try {
        const [connRes, statsRes] = await Promise.all([
          apiClient.get("/accounting-connection/status"),
          apiClient
            .get("/accounting-connection/weekly-stats")
            .catch(() => ({ data: null })),
        ]);
        setConnection({
          provider: connRes.data.provider,
          provider_label: providerLabel(connRes.data.provider),
          status: connRes.data.status,
          connected_since: connRes.data.connected_since || null,
          last_sync_at: connRes.data.last_sync_at,
          last_sync_status: connRes.data.last_sync_status,
          last_sync_error: connRes.data.last_sync_error,
          last_sync_error_code: connRes.data.last_sync_error_code || null,
          qbo_company_name: connRes.data.qbo_company_name,
          sync_config: connRes.data.sync_config,
        });
        if (statsRes.data) {
          setWeeklyStats(statsRes.data);
        }
      } catch {
        // Connection may not exist yet
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  // Load sync logs
  const loadLogs = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      params.set("page", String(logPage));
      params.set("per_page", String(PER_PAGE));
      if (logFilter !== "all") {
        params.set("filter", logFilter);
      }
      const res = await apiClient.get(
        `/accounting-connection/sync-log?${params.toString()}`,
      );
      const data = res.data as SyncLogResponse;
      setLogs(data.items);
      setLogTotal(data.total);
    } catch {
      // Sync log endpoint may not exist yet
      setLogs([]);
      setLogTotal(0);
    }
  }, [logPage, logFilter]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await apiClient.post(
        "/accounting-connection/test-connection",
      );
      if (res.data.success) {
        setTestResult("success");
        toast.success("Connection test passed");
      } else {
        setTestResult("error");
        toast.error(res.data.message || "Connection test failed");
      }
    } catch {
      setTestResult("error");
      toast.error("Connection test failed");
    } finally {
      setTesting(false);
    }
  };

  const handleDisconnect = async () => {
    if (
      !window.confirm(
        "Are you sure you want to disconnect your accounting software? Syncing will stop immediately.",
      )
    ) {
      return;
    }
    setDisconnecting(true);
    try {
      await apiClient.post("/accounting-connection/disconnect");
      toast.success("Accounting software disconnected");
      setConnection((prev) =>
        prev ? { ...prev, status: "disconnected" } : null,
      );
    } catch {
      toast.error("Failed to disconnect");
    } finally {
      setDisconnecting(false);
    }
  };

  const handleRerunMatching = async () => {
    setRerunningMatch(true);
    try {
      await apiClient.post("/accounting-connection/customer-matches/rerun");
      toast.success("Customer matching started");
    } catch {
      toast.error("Failed to start customer matching");
    } finally {
      setRerunningMatch(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const isConnected = connection?.status === "connected";
  const logTotalPages = Math.ceil(logTotal / PER_PAGE);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Accounting Integration</h1>
        <p className="text-muted-foreground">
          Manage your accounting connection, view sync activity, and resolve
          errors.
        </p>
      </div>

      {/* Section 1 — Connection Status */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plug className="h-5 w-5" />
            Connection Status
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">
                  {connection?.provider_label || "Not connected"}
                </span>
                {isConnected ? (
                  <Badge className="bg-green-100 text-green-800">
                    <CheckCircle2 className="h-3 w-3 mr-1" />
                    Connected
                  </Badge>
                ) : (
                  <Badge variant="outline" className="text-muted-foreground">
                    Disconnected
                  </Badge>
                )}
              </div>
              {connection?.qbo_company_name && (
                <p className="text-xs text-muted-foreground">
                  Company: {connection.qbo_company_name}
                </p>
              )}
              {connection?.connected_since && (
                <p className="text-xs text-muted-foreground">
                  Connected since {fmtDate(connection.connected_since)}
                </p>
              )}
              {connection?.last_sync_at && (
                <p className="text-xs text-muted-foreground">
                  Last sync: {fmtDateTime(connection.last_sync_at)}
                </p>
              )}
            </div>

            <div className="flex items-center gap-2">
              {isConnected && (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={testing}
                    onClick={handleTestConnection}
                  >
                    {testing ? (
                      <Loader2 className="h-4 w-4 animate-spin mr-1" />
                    ) : (
                      <PlugZap className="h-4 w-4 mr-1" />
                    )}
                    Test Connection
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={disconnecting}
                    onClick={handleDisconnect}
                    className="text-red-600 hover:text-red-700 hover:bg-red-50"
                  >
                    {disconnecting ? (
                      <Loader2 className="h-4 w-4 animate-spin mr-1" />
                    ) : (
                      <Unplug className="h-4 w-4 mr-1" />
                    )}
                    Disconnect
                  </Button>
                </>
              )}
              {!isConnected && (
                <Link to="/onboarding/accounting">
                  <Button size="sm">
                    <ExternalLink className="h-4 w-4 mr-1" />
                    Connect Now
                  </Button>
                </Link>
              )}
            </div>
          </div>

          {/* Test result */}
          {testResult === "success" && (
            <div className="flex items-center gap-2 rounded-lg bg-green-50 border border-green-200 p-3">
              <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0" />
              <span className="text-sm text-green-800">
                Connection test passed — everything looks good.
              </span>
            </div>
          )}
          {testResult === "error" && (
            <div className="flex items-center gap-2 rounded-lg bg-red-50 border border-red-200 p-3">
              <AlertCircle className="h-4 w-4 text-red-600 shrink-0" />
              <span className="text-sm text-red-800">
                Connection test failed — check your configuration.
              </span>
            </div>
          )}

          {/* Show error card if there's a sync error */}
          {connection?.last_sync_error_code && (
            <AccountingErrorCard
              errorCode={connection.last_sync_error_code}
            />
          )}
        </CardContent>
      </Card>

      {/* Section 2 — Weekly Stats */}
      {isConnected && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              This Week&apos;s Sync Activity
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <StatCard
                icon={<FileText className="h-5 w-5 text-blue-600" />}
                label="Invoices Pushed"
                value={weeklyStats?.invoices_pushed ?? 0}
              />
              <StatCard
                icon={<Zap className="h-5 w-5 text-green-600" />}
                label="Payments Synced"
                value={weeklyStats?.payments_synced ?? 0}
              />
              <StatCard
                icon={<Users className="h-5 w-5 text-purple-600" />}
                label="Customers Pushed"
                value={weeklyStats?.customers_pushed ?? 0}
              />
              <StatCard
                icon={<AlertCircle className="h-5 w-5 text-red-600" />}
                label="Sync Errors"
                value={weeklyStats?.sync_errors ?? 0}
                isError={(weeklyStats?.sync_errors ?? 0) > 0}
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Section 3 — Sync Log */}
      {isConnected && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5" />
                Sync Log
              </CardTitle>
              <Button variant="ghost" size="sm" onClick={loadLogs}>
                <RefreshCw className="h-4 w-4 mr-1" />
                Refresh
              </Button>
            </div>
            <CardDescription>
              Recent sync activity across all data types.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Filters */}
            <div className="flex flex-wrap gap-1">
              {(
                [
                  ["all", "All"],
                  ["invoices", "Invoices"],
                  ["payments", "Payments"],
                  ["customers", "Customers"],
                  ["errors", "Errors Only"],
                ] as [LogFilter, string][]
              ).map(([key, label]) => (
                <Button
                  key={key}
                  variant={logFilter === key ? "default" : "outline"}
                  size="sm"
                  onClick={() => {
                    setLogFilter(key);
                    setLogPage(1);
                  }}
                >
                  {label}
                </Button>
              ))}
            </div>

            {/* Table */}
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Time</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Details</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {logs.length === 0 ? (
                    <TableRow>
                      <TableCell
                        colSpan={4}
                        className="text-center text-muted-foreground"
                      >
                        No sync logs found
                      </TableCell>
                    </TableRow>
                  ) : (
                    logs.map((log) => (
                      <TableRow key={log.id}>
                        <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                          {fmtDateTime(log.timestamp)}
                        </TableCell>
                        <TableCell className="text-sm capitalize">
                          {log.type}
                        </TableCell>
                        <TableCell>{statusBadge(log.status)}</TableCell>
                        <TableCell className="text-sm max-w-xs truncate">
                          {log.details}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>

            {/* Pagination */}
            {logTotalPages > 1 && (
              <div className="flex items-center justify-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={logPage <= 1}
                  onClick={() => setLogPage(logPage - 1)}
                >
                  Previous
                </Button>
                <span className="text-sm text-muted-foreground">
                  Page {logPage} of {logTotalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={logPage >= logTotalPages}
                  onClick={() => setLogPage(logPage + 1)}
                >
                  Next
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Section 4 — Settings Summary */}
      {isConnected && connection?.sync_config && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Settings className="h-5 w-5" />
                Settings Summary
              </CardTitle>
              <Link to="/onboarding/accounting">
                <Button variant="ghost" size="sm">
                  Edit settings
                  <ArrowRight className="h-4 w-4 ml-1" />
                </Button>
              </Link>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              {[
                {
                  label: "Customer Sync",
                  enabled: connection.sync_config.sync_customers,
                },
                {
                  label: "Invoice Sync",
                  enabled: connection.sync_config.sync_invoices,
                },
                {
                  label: "Payment Sync",
                  enabled: connection.sync_config.sync_payments,
                },
                {
                  label: "Inventory Sync",
                  enabled: connection.sync_config.sync_inventory,
                },
              ].map((item) => (
                <div
                  key={item.label}
                  className="flex items-center gap-2 rounded-lg border p-3"
                >
                  {item.enabled ? (
                    <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0" />
                  ) : (
                    <X className="h-4 w-4 text-muted-foreground shrink-0" />
                  )}
                  <span className="text-sm">{item.label}</span>
                </div>
              ))}
            </div>

            <Button
              variant="outline"
              size="sm"
              disabled={rerunningMatch}
              onClick={handleRerunMatching}
            >
              {rerunningMatch ? (
                <Loader2 className="h-4 w-4 animate-spin mr-1" />
              ) : (
                <RefreshCw className="h-4 w-4 mr-1" />
              )}
              Re-run customer matching
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ── Stat Card ────────────────────────────────────────────────────

function StatCard({
  icon,
  label,
  value,
  isError = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  isError?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border p-4 text-center",
        isError && "border-red-200 bg-red-50/50",
      )}
    >
      <div className="flex justify-center mb-2">{icon}</div>
      <p
        className={cn(
          "text-2xl font-bold",
          isError ? "text-red-600" : "text-foreground",
        )}
      >
        {value}
      </p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  );
}
