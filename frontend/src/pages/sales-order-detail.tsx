import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { salesService } from "@/services/sales-service";
import type { SalesOrder } from "@/types/sales";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Tag } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtCurrency(n: string | number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Number(n));
}

function fmtDate(d: string | null) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString();
}

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

// ---------------------------------------------------------------------------
// Detail view
// ---------------------------------------------------------------------------

function SalesOrderDetailView({ id }: { id: string }) {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();

  const canCreateInvoice = hasPermission("ar.create_invoice");

  const [order, setOrder] = useState<SalesOrder | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionBusy, setActionBusy] = useState(false);

  const loadOrder = useCallback(async () => {
    setLoading(true);
    try {
      const data = await salesService.getSalesOrder(id);
      setOrder(data);
    } catch {
      setError("Failed to load sales order.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadOrder();
  }, [loadOrder]);

  async function handleCreateInvoice() {
    if (!order) return;
    setActionBusy(true);
    try {
      const newInvoice = await salesService.invoiceFromOrder(order.id);
      toast.success(`Invoice ${newInvoice.number} created`);
      navigate(`/ar/invoices/${newInvoice.id}`);
    } catch {
      toast.error("Failed to create invoice.");
    } finally {
      setActionBusy(false);
    }
  }

  async function handleStatusUpdate(newStatus: string) {
    if (!order) return;
    setActionBusy(true);
    try {
      const updated = await salesService.updateSalesOrder(order.id, {
        status: newStatus,
        ...(newStatus === "shipped"
          ? { shipped_date: new Date().toISOString().split("T")[0] }
          : {}),
      });
      setOrder(updated);
      toast.success(`Order marked as ${newStatus}`);
    } catch {
      toast.error("Failed to update status.");
    } finally {
      setActionBusy(false);
    }
  }

  if (loading) return <div className="p-8 text-center">Loading...</div>;
  if (error)
    return <div className="p-8 text-center text-destructive">{error}</div>;
  if (!order) return null;

  const isTerminal = order.status === "canceled" || order.status === "completed";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Link
            to="/ar/orders"
            className="text-sm text-muted-foreground hover:underline"
          >
            &larr; Sales Orders
          </Link>
          <div className="flex items-center gap-3 mt-1">
            <h1 className="text-3xl font-bold">{order.number}</h1>
            {statusBadge(order.status)}
          </div>
          <p className="text-muted-foreground">
            Customer: {order.customer_name || "—"}
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 flex-wrap justify-end">
          {!isTerminal && canCreateInvoice && (
            <Button onClick={handleCreateInvoice} disabled={actionBusy}>
              {actionBusy ? "Working..." : "Create Invoice"}
            </Button>
          )}
          {order.status === "draft" && (
            <Button
              variant="outline"
              disabled={actionBusy}
              onClick={() => handleStatusUpdate("confirmed")}
            >
              Mark as Confirmed
            </Button>
          )}
          {order.status === "confirmed" && (
            <Button
              variant="outline"
              disabled={actionBusy}
              onClick={() => handleStatusUpdate("processing")}
            >
              Mark as Processing
            </Button>
          )}
          {order.status === "processing" && (
            <Button
              variant="outline"
              disabled={actionBusy}
              onClick={() => handleStatusUpdate("shipped")}
            >
              Mark as Shipped
            </Button>
          )}
          {order.status === "shipped" && (
            <Button
              variant="outline"
              disabled={actionBusy}
              onClick={() => handleStatusUpdate("completed")}
            >
              Mark as Completed
            </Button>
          )}
          {!isTerminal && (
            <Button
              variant="destructive"
              size="sm"
              disabled={actionBusy}
              onClick={() => handleStatusUpdate("canceled")}
            >
              Cancel Order
            </Button>
          )}
        </div>
      </div>

      {/* Order info */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Customer</p>
          <p className="font-medium">{order.customer_name || "—"}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Order Date</p>
          <p className="font-medium">{fmtDate(order.order_date)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Required Date</p>
          <p className="font-medium">{fmtDate(order.required_date)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Shipped Date</p>
          <p className="font-medium">{fmtDate(order.shipped_date)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Payment Terms</p>
          <p className="font-medium">{order.payment_terms || "—"}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Ship To</p>
          <p className="font-medium text-sm">
            {order.ship_to_name
              ? `${order.ship_to_name}${order.ship_to_address ? `, ${order.ship_to_address}` : ""}`
              : order.ship_to_address || "—"}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Status</p>
          <div className="mt-1">{statusBadge(order.status)}</div>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Created By</p>
          <p className="font-medium">{order.created_by_name || "—"}</p>
        </Card>
      </div>

      {/* Line items */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold mb-4">Line Items</h2>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[35%]">Description</TableHead>
                <TableHead>Product</TableHead>
                <TableHead>Qty</TableHead>
                <TableHead>Shipped</TableHead>
                <TableHead>Unit Price</TableHead>
                <TableHead className="text-right">Line Total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {order.lines.map((line) => (
                <TableRow key={line.id}>
                  <TableCell>{line.description}</TableCell>
                  <TableCell>
                    {line.product_name ? (
                      <span className="text-sm">{line.product_name}</span>
                    ) : (
                      <span className="text-muted-foreground text-sm">—</span>
                    )}
                  </TableCell>
                  <TableCell>{line.quantity}</TableCell>
                  <TableCell>
                    <span
                      className={
                        Number(line.quantity_shipped) >= Number(line.quantity)
                          ? "text-green-600 font-medium"
                          : ""
                      }
                    >
                      {line.quantity_shipped}
                    </span>
                    {Number(line.quantity_shipped) >= Number(line.quantity) && (
                      <span className="ml-1 text-green-600">&check;</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {line.is_call_office ? (
                      <span className="text-muted-foreground italic text-sm">Price on request</span>
                    ) : (
                      <span className="flex items-center gap-1">
                        {fmtCurrency(line.unit_price)}
                        {line.has_conditional_pricing && (
                          <span
                            title={
                              line.price_without_our_product
                                ? `Includes vault discount. Standalone price: ${fmtCurrency(line.price_without_our_product)}`
                                : "Conditional pricing applied"
                            }
                            className="text-blue-500 cursor-help"
                          >
                            <Tag size={12} />
                          </span>
                        )}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    {fmtCurrency(line.line_total)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {/* Totals */}
        <div className="flex justify-end mt-4">
          <div className="space-y-1 text-right min-w-[200px]">
            <div className="flex justify-between gap-8 text-sm text-muted-foreground">
              <span>Subtotal</span>
              <span>{fmtCurrency(order.subtotal)}</span>
            </div>
            <div className="flex justify-between gap-8 text-sm text-muted-foreground">
              <span>Tax Rate</span>
              <span>{Number(order.tax_rate)}%</span>
            </div>
            <div className="flex justify-between gap-8 text-sm text-muted-foreground">
              <span>Tax Amount</span>
              <span>{fmtCurrency(order.tax_amount)}</span>
            </div>
            <div className="flex justify-between gap-8 text-lg font-bold border-t pt-1">
              <span>Total</span>
              <span>{fmtCurrency(order.total)}</span>
            </div>
          </div>
        </div>
      </Card>

      {/* Notes */}
      {order.notes && (
        <Card className="p-4">
          <p className="text-sm text-muted-foreground mb-1">Notes</p>
          <p className="text-sm whitespace-pre-wrap">{order.notes}</p>
        </Card>
      )}

      {/* Metadata */}
      <div className="text-xs text-muted-foreground space-y-0.5">
        {order.created_by_name && <p>Created by: {order.created_by_name}</p>}
        <p>Created: {new Date(order.created_at).toLocaleString()}</p>
        {order.modified_at && (
          <p>Last modified: {new Date(order.modified_at).toLocaleString()}</p>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page entry point
// ---------------------------------------------------------------------------

export default function SalesOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  if (!id) return null;
  return <SalesOrderDetailView id={id} />;
}
