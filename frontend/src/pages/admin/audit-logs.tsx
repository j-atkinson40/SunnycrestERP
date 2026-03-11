import { useCallback, useEffect, useState } from "react";
import { auditService } from "@/services/audit-service";
import type { AuditLogEntry, AuditLogFilters } from "@/types/audit";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const ACTION_OPTIONS = [
  { value: "", label: "All Actions" },
  { value: "created", label: "Created" },
  { value: "updated", label: "Updated" },
  { value: "deleted", label: "Deleted" },
  { value: "deactivated", label: "Deactivated" },
  { value: "login", label: "Login" },
  { value: "logout", label: "Logout" },
];

const ENTITY_OPTIONS = [
  { value: "", label: "All Entities" },
  { value: "user", label: "User" },
  { value: "role", label: "Role" },
  { value: "session", label: "Session" },
];

function actionBadgeVariant(
  action: string
): "default" | "secondary" | "destructive" | "outline" {
  switch (action) {
    case "created":
      return "default";
    case "updated":
      return "secondary";
    case "deleted":
    case "deactivated":
      return "destructive";
    case "login":
    case "logout":
      return "outline";
    default:
      return "secondary";
  }
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function ChangesDisplay({
  changes,
}: {
  changes: Record<string, { old: unknown; new: unknown }> | null;
}) {
  if (!changes || Object.keys(changes).length === 0) {
    return <p className="text-sm text-muted-foreground">No changes recorded</p>;
  }

  return (
    <div className="space-y-2">
      {Object.entries(changes).map(([field, diff]) => (
        <div key={field} className="rounded border p-2 text-sm">
          <span className="font-medium">{field}</span>
          <div className="mt-1 grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-muted-foreground">Old: </span>
              <span className="text-destructive">
                {JSON.stringify(diff.old)}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">New: </span>
              <span className="text-green-600 dark:text-green-400">
                {JSON.stringify(diff.new)}
              </span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function AuditLogs() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<AuditLogFilters>({});

  // Detail dialog
  const [selectedLog, setSelectedLog] = useState<AuditLogEntry | null>(null);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const data = await auditService.getAuditLogs(page, 50, filters);
      setLogs(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page, filters]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  function updateFilter(key: keyof AuditLogFilters, value: string) {
    setFilters((prev) => {
      const next = { ...prev };
      if (value) {
        next[key] = value;
      } else {
        delete next[key];
      }
      return next;
    });
    setPage(1);
  }

  const totalPages = Math.ceil(total / 50);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Audit Logs</h1>
        <p className="text-muted-foreground">
          {total} event{total !== 1 ? "s" : ""} recorded
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={filters.action || ""}
          onChange={(e) => updateFilter("action", e.target.value)}
        >
          {ACTION_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={filters.entity_type || ""}
          onChange={(e) => updateFilter("entity_type", e.target.value)}
        >
          {ENTITY_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <Input
          type="date"
          className="w-auto"
          value={filters.date_from || ""}
          onChange={(e) => updateFilter("date_from", e.target.value)}
          placeholder="From date"
        />
        <Input
          type="date"
          className="w-auto"
          value={filters.date_to || ""}
          onChange={(e) => updateFilter("date_to", e.target.value)}
          placeholder="To date"
        />
        {Object.keys(filters).length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setFilters({});
              setPage(1);
            }}
          >
            Clear Filters
          </Button>
        )}
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Timestamp</TableHead>
              <TableHead>User</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Entity</TableHead>
              <TableHead className="text-right">Details</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : logs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center">
                  No audit logs found
                </TableCell>
              </TableRow>
            ) : (
              logs.map((log) => (
                <TableRow key={log.id}>
                  <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                    {formatTimestamp(log.created_at)}
                  </TableCell>
                  <TableCell className="font-medium">
                    {log.user_name || "System"}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={actionBadgeVariant(log.action)}
                      className="capitalize"
                    >
                      {log.action}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <span className="capitalize">{log.entity_type}</span>
                    {log.entity_id && (
                      <span className="ml-1 text-xs text-muted-foreground">
                        ({log.entity_id.slice(0, 8)}...)
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setSelectedLog(log)}
                    >
                      View
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}

      {/* Detail Dialog */}
      <Dialog
        open={!!selectedLog}
        onOpenChange={(open) => {
          if (!open) setSelectedLog(null);
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Audit Log Detail</DialogTitle>
            <DialogDescription>
              Full details of this event.
            </DialogDescription>
          </DialogHeader>
          {selectedLog && (
            <div className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-y-2">
                <span className="text-muted-foreground">Timestamp</span>
                <span>{new Date(selectedLog.created_at).toLocaleString()}</span>

                <span className="text-muted-foreground">User</span>
                <span>{selectedLog.user_name || "System"}</span>

                <span className="text-muted-foreground">Action</span>
                <Badge
                  variant={actionBadgeVariant(selectedLog.action)}
                  className="capitalize w-fit"
                >
                  {selectedLog.action}
                </Badge>

                <span className="text-muted-foreground">Entity Type</span>
                <span className="capitalize">{selectedLog.entity_type}</span>

                <span className="text-muted-foreground">Entity ID</span>
                <span className="font-mono text-xs break-all">
                  {selectedLog.entity_id || "—"}
                </span>

                {selectedLog.ip_address && (
                  <>
                    <span className="text-muted-foreground">IP Address</span>
                    <span>{selectedLog.ip_address}</span>
                  </>
                )}

                {selectedLog.user_agent && (
                  <>
                    <span className="text-muted-foreground">User Agent</span>
                    <span className="text-xs break-all">
                      {selectedLog.user_agent}
                    </span>
                  </>
                )}
              </div>

              {selectedLog.changes && (
                <div>
                  <h4 className="font-medium mb-2">Changes</h4>
                  <ChangesDisplay changes={selectedLog.changes} />
                </div>
              )}
            </div>
          )}
          <DialogFooter showCloseButton />
        </DialogContent>
      </Dialog>
    </div>
  );
}
