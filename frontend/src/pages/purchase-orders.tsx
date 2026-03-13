import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { purchaseOrderService } from "@/services/purchase-order-service";
import type { PurchaseOrderListItem, POStats } from "@/types/purchase-order";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function statusBadge(status: string) {
  switch (status) {
    case "draft":
      return <Badge variant="outline">Draft</Badge>;
    case "sent":
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
          Sent
        </Badge>
      );
    case "partial":
      return (
        <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
          Partial
        </Badge>
      );
    case "received":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Received
        </Badge>
      );
    case "closed":
      return <Badge variant="secondary">Closed</Badge>;
    case "cancelled":
      return <Badge variant="destructive">Cancelled</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function fmtCurrency(n: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(n);
}

function fmtDate(d: string | null) {
  if (!d) return "\u2014";
  return new Date(d).toLocaleDateString();
}

export default function PurchaseOrdersPage() {
  const { hasPermission } = useAuth();
  const navigate = useNavigate();
  const canCreate = hasPermission("ap.create_po");

  const [orders, setOrders] = useState<PurchaseOrderListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<POStats | null>(null);

  const loadOrders = useCallback(async () => {
    setLoading(true);
    try {
      const data = await purchaseOrderService.getAll(
        page,
        20,
        search || undefined,
        filterStatus || undefined,
      );
      setOrders(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page, search, filterStatus]);

  const loadStats = useCallback(async () => {
    try {
      setStats(await purchaseOrderService.getStats());
    } catch {
      /* non-critical */
    }
  }, []);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Purchase Orders</h1>
          <p className="text-muted-foreground">{total} total orders</p>
        </div>
        {canCreate && (
          <Button onClick={() => navigate("/ap/purchase-orders/new")}>
            New Purchase Order
          </Button>
        )}
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-3 gap-4 md:grid-cols-6">
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Total</p>
            <p className="text-2xl font-bold">{stats.total_pos}</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Draft</p>
            <p className="text-2xl font-bold">{stats.draft}</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Sent</p>
            <p className="text-2xl font-bold text-blue-600">{stats.sent}</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Partial</p>
            <p className="text-2xl font-bold text-yellow-600">
              {stats.partial}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Received</p>
            <p className="text-2xl font-bold text-green-600">
              {stats.received}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Closed</p>
            <p className="text-2xl font-bold">{stats.closed}</p>
          </Card>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <Input
          placeholder="Search PO numbers..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="max-w-sm"
        />
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={filterStatus}
          onChange={(e) => {
            setFilterStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="sent">Sent</option>
          <option value="partial">Partial</option>
          <option value="received">Received</option>
          <option value="closed">Closed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>PO #</TableHead>
              <TableHead>Vendor</TableHead>
              <TableHead>Order Date</TableHead>
              <TableHead>Expected</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Total</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : orders.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center">
                  No purchase orders found
                </TableCell>
              </TableRow>
            ) : (
              orders.map((po) => (
                <TableRow key={po.id}>
                  <TableCell className="font-medium">
                    <Link
                      to={`/ap/purchase-orders/${po.id}`}
                      className="hover:underline"
                    >
                      {po.number}
                    </Link>
                  </TableCell>
                  <TableCell>{po.vendor_name || "\u2014"}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {fmtDate(po.order_date)}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {fmtDate(po.expected_date)}
                  </TableCell>
                  <TableCell>{statusBadge(po.status)}</TableCell>
                  <TableCell className="text-right font-medium">
                    {fmtCurrency(po.total)}
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
    </div>
  );
}
