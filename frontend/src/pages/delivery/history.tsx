import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { deliveryService } from "@/services/delivery-service";
import { getApiErrorMessage } from "@/lib/api-error";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "sonner";
import type { DeliveryListItem } from "@/types/delivery";

function typeBadge(type: string) {
  const colors: Record<string, string> = {
    funeral_vault: "bg-purple-100 text-purple-800",
    precast: "bg-blue-100 text-blue-800",
    redi_rock: "bg-orange-100 text-orange-800",
  };
  const labels: Record<string, string> = {
    funeral_vault: "Vault",
    precast: "Precast",
    redi_rock: "Redi-Rock",
  };
  return <Badge className={colors[type] || ""}>{labels[type] || type}</Badge>;
}

function statusBadge(status: string) {
  const map: Record<string, { className: string; label: string }> = {
    pending: { className: "bg-gray-100 text-gray-800", label: "Pending" },
    scheduled: { className: "bg-blue-100 text-blue-800", label: "Scheduled" },
    in_transit: { className: "bg-yellow-100 text-yellow-800", label: "In Transit" },
    arrived: { className: "bg-indigo-100 text-indigo-800", label: "Arrived" },
    setup: { className: "bg-purple-100 text-purple-800", label: "Setup" },
    completed: { className: "bg-green-100 text-green-800", label: "Completed" },
    cancelled: { className: "", label: "Cancelled" },
    failed: { className: "", label: "Failed" },
  };
  const info = map[status];
  if (info) return <Badge className={info.className}>{info.label}</Badge>;
  return <Badge variant="outline">{status}</Badge>;
}

function fmtDate(d: string | null) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString();
}

export default function HistoryPage() {
  const [items, setItems] = useState<DeliveryListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const perPage = 20;

  // Filters
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const res = await deliveryService.getDeliveries(page, perPage, {
        status: statusFilter || undefined,
        delivery_type: typeFilter || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter, typeFilter, dateFrom, dateTo]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    setPage(1);
  }, [statusFilter, typeFilter, dateFrom, dateTo]);

  const totalPages = Math.ceil(total / perPage);

  const handleExport = () => {
    // Build CSV from current items
    const headers = [
      "Type",
      "Customer",
      "Address",
      "Carrier",
      "Status",
      "Priority",
      "Requested Date",
      "Weight (lbs)",
    ];
    const rows = items.map((d) => [
      d.delivery_type,
      d.customer_name || "",
      d.delivery_address || "",
      d.carrier_name || "",
      d.status,
      d.priority,
      d.requested_date || "",
      d.weight_lbs || "",
    ]);
    const csv = [headers, ...rows].map((r) => r.map((c) => `"${c}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `deliveries-export-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("CSV exported");
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Delivery History</h1>
          <p className="text-sm text-muted-foreground">
            {total} total deliveries
          </p>
        </div>
        <Button variant="outline" onClick={handleExport} disabled={items.length === 0}>
          Export CSV
        </Button>
      </div>

      {/* Filters */}
      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-4">
          <div className="space-y-1">
            <Label className="text-xs">Status</Label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-md border bg-background px-3 py-2 text-sm"
            >
              <option value="">All</option>
              <option value="pending">Pending</option>
              <option value="scheduled">Scheduled</option>
              <option value="in_transit">In Transit</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
              <option value="failed">Failed</option>
            </select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Type</Label>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="rounded-md border bg-background px-3 py-2 text-sm"
            >
              <option value="">All Types</option>
              <option value="funeral_vault">Funeral Vault</option>
              <option value="precast">Precast</option>
              <option value="redi_rock">Redi-Rock</option>
            </select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">From</Label>
            <Input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="w-40"
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">To</Label>
            <Input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="w-40"
            />
          </div>
          {(statusFilter || typeFilter || dateFrom || dateTo) && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setStatusFilter("");
                setTypeFilter("");
                setDateFrom("");
                setDateTo("");
              }}
            >
              Clear
            </Button>
          )}
        </div>
      </Card>

      {/* Table */}
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Type</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Address</TableHead>
              <TableHead>Carrier</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Requested</TableHead>
              <TableHead className="text-right">Weight</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground">
                  Loading...
                </TableCell>
              </TableRow>
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground">
                  No deliveries found
                </TableCell>
              </TableRow>
            ) : (
              items.map((d) => (
                <TableRow key={d.id}>
                  <TableCell>{typeBadge(d.delivery_type)}</TableCell>
                  <TableCell>
                    <Link
                      to={`/delivery/deliveries/${d.id}`}
                      className="font-medium hover:underline"
                    >
                      {d.customer_name || "—"}
                    </Link>
                  </TableCell>
                  <TableCell className="max-w-48 truncate text-sm">
                    {d.delivery_address || "—"}
                  </TableCell>
                  <TableCell className="text-sm">
                    {d.carrier_name || "Own Fleet"}
                  </TableCell>
                  <TableCell>{statusBadge(d.status)}</TableCell>
                  <TableCell className="text-sm">{fmtDate(d.requested_date)}</TableCell>
                  <TableCell className="text-right text-sm">
                    {d.weight_lbs ? `${d.weight_lbs} lbs` : "—"}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <p className="text-muted-foreground">
            Page {page} of {totalPages} ({total} records)
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
