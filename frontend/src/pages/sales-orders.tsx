import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { usePresetTheme } from "@/contexts/preset-theme-context";
import { salesService } from "@/services/sales-service";
import type { SalesOrder } from "@/types/sales";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// Lazy-load the Spring Burials page so it's only fetched when the tab is active
import { lazy, Suspense } from "react";
const SpringBurialList = lazy(
  () => import("@/pages/spring-burials/spring-burial-list"),
);

function statusBadge(status: string) {
  switch (status) {
    case "draft":
      return <Badge variant="outline">Draft</Badge>;
    case "confirmed":
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
          Confirmed
        </Badge>
      );
    case "processing":
      return (
        <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
          Processing
        </Badge>
      );
    case "shipped":
      return (
        <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
          Shipped
        </Badge>
      );
    case "completed":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Completed
        </Badge>
      );
    case "canceled":
      return <Badge variant="destructive">Canceled</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function fmtCurrency(n: string | number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(n));
}

function fmtDate(d: string | null) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString();
}

export default function SalesOrdersPage() {
  useAuth();
  const { tenantSettings } = usePresetTheme();
  const [searchParams, setSearchParams] = useSearchParams();

  const springBurialsEnabled = tenantSettings.spring_burials_enabled === true;
  const activeTab = searchParams.get("tab") === "spring-burials" && springBurialsEnabled
    ? "spring-burials"
    : "all";

  const setTab = (tab: string) => {
    if (tab === "all") {
      searchParams.delete("tab");
    } else {
      searchParams.set("tab", tab);
    }
    setSearchParams(searchParams, { replace: true });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Orders</h1>
      </div>

      {/* Tabs — only show if Spring Burials is enabled */}
      {springBurialsEnabled && (
        <div className="flex items-center gap-1 border-b">
          <button
            onClick={() => setTab("all")}
            className={cn(
              "px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px",
              activeTab === "all"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground hover:border-gray-300",
            )}
          >
            All Orders
          </button>
          <button
            onClick={() => setTab("spring-burials")}
            className={cn(
              "px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px",
              activeTab === "spring-burials"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground hover:border-gray-300",
            )}
          >
            Spring Burials
          </button>
        </div>
      )}

      {/* Tab content */}
      {activeTab === "spring-burials" ? (
        <Suspense
          fallback={
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
            </div>
          }
        >
          <SpringBurialList />
        </Suspense>
      ) : (
        <OrdersTable />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Orders table — extracted to keep tab switching clean
// ---------------------------------------------------------------------------

function OrdersTable() {
  const [orders, setOrders] = useState<SalesOrder[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterStatus, setFilterStatus] = useState("");
  const [loading, setLoading] = useState(true);

  const loadOrders = useCallback(async () => {
    setLoading(true);
    try {
      const data = await salesService.getSalesOrders(
        page,
        20,
        filterStatus || undefined,
      );
      setOrders(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page, filterStatus]);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);

  const totalPages = Math.ceil(total / 20);

  return (
    <>
      <div className="flex items-center justify-between">
        <p className="text-muted-foreground text-sm">{total} orders</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={filterStatus}
          onChange={(e) => {
            setFilterStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All</option>
          <option value="draft">Draft</option>
          <option value="confirmed">Confirmed</option>
          <option value="processing">Processing</option>
          <option value="shipped">Shipped</option>
          <option value="completed">Completed</option>
          <option value="canceled">Canceled</option>
        </select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Order #</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Order Date</TableHead>
              <TableHead>Required Date</TableHead>
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
                  No sales orders found
                </TableCell>
              </TableRow>
            ) : (
              orders.map((order) => (
                <TableRow key={order.id}>
                  <TableCell className="font-medium">
                    <Link
                      to={`/ar/orders/${order.id}`}
                      className="hover:underline"
                    >
                      {order.number}
                    </Link>
                  </TableCell>
                  <TableCell>{order.customer_name || "—"}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {fmtDate(order.order_date)}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {fmtDate(order.required_date)}
                  </TableCell>
                  <TableCell>{statusBadge(order.status)}</TableCell>
                  <TableCell className="text-right font-medium">
                    {fmtCurrency(order.total)}
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
    </>
  );
}
