import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { sageExportService } from "@/services/sage-export-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type { SageExportConfig, SyncLogEntry } from "@/types/sage-export";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "sonner";

export default function SageExportsPage() {
  const { hasPermission } = useAuth();
  const canEdit = hasPermission("inventory.edit");

  // Config state
  const [config, setConfig] = useState<SageExportConfig | null>(null);
  const [warehouseCode, setWarehouseCode] = useState("");
  const [exportDir, setExportDir] = useState("");
  const [configLoading, setConfigLoading] = useState(true);
  const [configSaving, setConfigSaving] = useState(false);

  // Export state
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [generating, setGenerating] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [csvPreview, setCsvPreview] = useState<string | null>(null);
  const [recordCount, setRecordCount] = useState<number | null>(null);

  // History state
  const [history, setHistory] = useState<SyncLogEntry[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyPage, setHistoryPage] = useState(1);

  // Set default dates (last 7 days)
  useEffect(() => {
    const now = new Date();
    const weekAgo = new Date(now);
    weekAgo.setDate(weekAgo.getDate() - 7);
    setDateTo(now.toISOString().slice(0, 10));
    setDateFrom(weekAgo.toISOString().slice(0, 10));
  }, []);

  const loadConfig = useCallback(async () => {
    try {
      const cfg = await sageExportService.getConfig();
      setConfig(cfg);
      setWarehouseCode(cfg.warehouse_code);
      setExportDir(cfg.export_directory || "");
    } catch {
      // Will show default state
    } finally {
      setConfigLoading(false);
    }
  }, []);

  const loadHistory = useCallback(async () => {
    try {
      const data = await sageExportService.getExportHistory(historyPage);
      setHistory(data.items);
      setHistoryTotal(data.total);
    } catch {
      // silently fail
    }
  }, [historyPage]);

  useEffect(() => {
    loadConfig();
    loadHistory();
  }, [loadConfig, loadHistory]);

  async function handleSaveConfig(e: React.FormEvent) {
    e.preventDefault();
    setConfigSaving(true);
    try {
      const updated = await sageExportService.updateConfig({
        warehouse_code: warehouseCode.trim() || undefined,
        export_directory: exportDir.trim() || undefined,
      });
      setConfig(updated);
      toast.success("Configuration saved");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to save configuration"));
    } finally {
      setConfigSaving(false);
    }
  }

  async function handleGenerate() {
    if (!dateFrom || !dateTo) {
      toast.error("Please select a date range");
      return;
    }
    setGenerating(true);
    setCsvPreview(null);
    setRecordCount(null);
    try {
      const result = await sageExportService.generateExport({
        date_from: new Date(dateFrom).toISOString(),
        date_to: new Date(dateTo + "T23:59:59").toISOString(),
      });
      setCsvPreview(result.csv_data);
      setRecordCount(result.record_count);
      toast.success(`Generated export with ${result.record_count} records`);
      loadHistory(); // refresh history
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to generate export"));
    } finally {
      setGenerating(false);
    }
  }

  async function handleDownload() {
    if (!dateFrom || !dateTo) return;
    setDownloading(true);
    try {
      await sageExportService.downloadExport(
        new Date(dateFrom).toISOString(),
        new Date(dateTo + "T23:59:59").toISOString(),
      );
      toast.success("CSV downloaded");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to download CSV"));
    } finally {
      setDownloading(false);
    }
  }

  const historyTotalPages = Math.ceil(historyTotal / 20);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Sage CSV Export</h1>
          <p className="text-sm text-muted-foreground">
            Export inventory transactions as Sage 100-compatible CSV files.
          </p>
        </div>
        <Link
          to="/inventory"
          className="text-sm text-muted-foreground hover:underline"
        >
          ← Back to Inventory
        </Link>
      </div>

      {/* Configuration */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold">Export Configuration</h2>
        <Separator className="my-4" />
        {configLoading ? (
          <p className="text-muted-foreground">Loading configuration...</p>
        ) : (
          <form onSubmit={handleSaveConfig} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Warehouse Code</Label>
                <Input
                  value={warehouseCode}
                  onChange={(e) => setWarehouseCode(e.target.value)}
                  placeholder="MAIN"
                  disabled={!canEdit}
                />
                <p className="text-xs text-muted-foreground">
                  Default warehouse code in Sage 100
                </p>
              </div>
              <div className="space-y-2">
                <Label>Export Directory (optional)</Label>
                <Input
                  value={exportDir}
                  onChange={(e) => setExportDir(e.target.value)}
                  placeholder="/path/to/sage/imports"
                  disabled={!canEdit}
                />
                <p className="text-xs text-muted-foreground">
                  For future automated nightly exports
                </p>
              </div>
            </div>
            {config?.last_export_at && (
              <p className="text-xs text-muted-foreground">
                Last export:{" "}
                {new Date(config.last_export_at).toLocaleString()}
              </p>
            )}
            {canEdit && (
              <div className="flex justify-end">
                <Button type="submit" disabled={configSaving}>
                  {configSaving ? "Saving..." : "Save Configuration"}
                </Button>
              </div>
            )}
          </form>
        )}
      </Card>

      {/* Generate Export */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold">Generate Export</h2>
        <Separator className="my-4" />
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>From Date</Label>
              <Input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>To Date</Label>
              <Input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
              />
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              onClick={handleGenerate}
              disabled={generating || !dateFrom || !dateTo}
            >
              {generating ? "Generating..." : "Generate & Preview"}
            </Button>
            {csvPreview && (
              <Button
                variant="outline"
                onClick={handleDownload}
                disabled={downloading}
              >
                {downloading ? "Downloading..." : "Download CSV"}
              </Button>
            )}
          </div>

          {recordCount !== null && (
            <div className="flex items-center gap-2">
              <Badge variant="secondary">{recordCount} records</Badge>
              <span className="text-sm text-muted-foreground">
                in the selected date range
              </span>
            </div>
          )}

          {csvPreview && (
            <div className="space-y-2">
              <Label>CSV Preview</Label>
              <pre className="max-h-64 overflow-auto rounded-md bg-muted p-4 text-xs font-mono">
                {csvPreview.split("\n").slice(0, 25).join("\n")}
                {csvPreview.split("\n").length > 25 && "\n... (truncated)"}
              </pre>
            </div>
          )}
        </div>
      </Card>

      {/* Export History */}
      <Card className="p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Export History</h2>
          <Badge variant="secondary">{historyTotal} total</Badge>
        </div>
        <Separator className="my-4" />
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Records</TableHead>
                <TableHead className="text-right">Failed</TableHead>
                <TableHead>Error</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {history.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center">
                    No exports yet
                  </TableCell>
                </TableRow>
              ) : (
                history.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell className="text-muted-foreground">
                      {new Date(log.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          log.status === "completed"
                            ? "default"
                            : log.status === "failed"
                              ? "destructive"
                              : "secondary"
                        }
                      >
                        {log.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {log.records_processed}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {log.records_failed}
                    </TableCell>
                    <TableCell className="max-w-[200px] truncate text-muted-foreground">
                      {log.error_message || "—"}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
        {historyTotalPages > 1 && (
          <div className="mt-4 flex items-center justify-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={historyPage <= 1}
              onClick={() => setHistoryPage(historyPage - 1)}
            >
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {historyPage} of {historyTotalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={historyPage >= historyTotalPages}
              onClick={() => setHistoryPage(historyPage + 1)}
            >
              Next
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
