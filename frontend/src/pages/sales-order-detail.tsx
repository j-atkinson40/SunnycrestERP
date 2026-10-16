import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { salesService } from "@/services/sales-service";
import type { SalesOrder } from "@/types/sales";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Tag } from "lucide-react";
import { HistoryButton } from "@/components/core/HistoryButton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "sonner";
import LegacyProofStatusCard from "@/components/legacy/LegacyProofStatusCard";

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

function statusLabel(status: string): string {
  switch (status) {
    case "delivered":
    case "shipped": return "Delivered";
    case "processing": return "In Production";
    default: return status.charAt(0).toUpperCase() + status.slice(1);
  }
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
          In Production
        </Badge>
      );
    case "delivered":
    case "shipped":
      return (
        <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
          Delivered
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

function fmtQty(n: string | number): string {
  const num = Number(n);
  return Number.isInteger(num) ? String(num) : num.toFixed(2);
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
    } catch (err: unknown) {
      // ⚠️ THE SERVER'S MESSAGE, for the same reason as the status handler. The 409 here
      // names the existing invoice ("Order SO-… is already invoiced (INV-…, open). Void
      // it first if this is a re-issue."), which is the whole next step. A generic
      // "Failed to create invoice." threw that away.
      const detail = (err as { response?: { data?: { detail?: unknown } } })
        ?.response?.data?.detail;
      toast.error(
        typeof detail === "string" && detail ? detail : "Failed to create invoice.",
      );
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
        ...(newStatus === "delivered"
          ? { shipped_date: new Date().toISOString().split("T")[0] }
          : {}),
      });
      setOrder(updated);
      toast.success(
        newStatus === "draft"
          ? "Confirmation undone — the order is a draft again."
          : `Order marked as ${statusLabel(newStatus)}`,
      );
    } catch (err: unknown) {
      // ⚠️ THE SERVER'S MESSAGE IS SHOWN, NOT A GENERIC ONE. This was a bare
      // `catch { toast.error("Failed to update status.") }`, which is adequate for a
      // network blip and useless for the two refusals that matter: the transition graph
      // says what the order CAN become, and the undo blocker names the invoice to void
      // or tells you to cancel instead. Both are 409s with a sentence written for the
      // office, and swallowing them turned actionable refusals into a dead end.
      const detail = (
        err as { response?: { data?: { detail?: unknown } } }
      )?.response?.data?.detail;
      toast.error(
        typeof detail === "string" && detail
          ? detail
          : "Failed to update status.",
      );
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
          <HistoryButton
            entityType="order"
            entityId={id!}
            entityName={order.number || `Order ${id}`}
            variant="outline"
            size="sm"
          />
          {/* ── billing: three cases, three controls (James's step 3, item 6) ──
              ⚠️ THIS WAS ONE UNCONDITIONAL "Create Invoice" BUTTON. The page had no
              view of the order's invoices, so it offered the control on an
              already-invoiced order and the 409 came back as "Failed to create
              invoice." Now: a live invoice is a LINK, never a second create; a
              void-only order gets an explicit re-bill; an uninvoiced order gets the
              plain create. */}
          {order.live_invoice_number ? (
            <Button
              variant="outline"
              onClick={() => navigate(`/ar/invoices?q=${order.live_invoice_number}`)}
              data-testid="order-live-invoice"
            >
              Invoice {order.live_invoice_number}
            </Button>
          ) : !isTerminal && canCreateInvoice ? (
            <Button
              onClick={handleCreateInvoice}
              disabled={actionBusy}
              data-testid={
                (order.voided_invoice_count ?? 0) > 0
                  ? "order-rebill"
                  : "order-create-invoice"
              }
              // ⚠️ A DIFFERENT LABEL, NOT JUST A DIFFERENT TESTID. Re-billing after a
              // void is a deliberate act — the end-of-day batch will never do it,
              // because a voided invoice keeps the order out of the batch permanently.
              // The office is the only thing that can re-bill, so the button says so.
              title={
                (order.voided_invoice_count ?? 0) > 0
                  ? "This order's invoice was voided. The nightly batch will not re-bill it — create a new invoice here."
                  : undefined
              }
            >
              {actionBusy
                ? "Working..."
                : (order.voided_invoice_count ?? 0) > 0
                  ? "Create new invoice"
                  : "Create Invoice"}
            </Button>
          ) : null}
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
              Move to Production
            </Button>
          )}
          {/* ⚠️ UNDO CONFIRM (James 2026-10-16). Confirming is what puts an order in
              front of the end-of-day batch, and before this the only way back was
              cancelling — which loses the order number and the capture's record of what
              the director said. Shown only while `confirmed`: the server refuses it once
              the order is delivered or invoiced, and a button that is usually refused is
              worse than no button. */}
          {order.status === "confirmed" && (
            <Button
              variant="ghost"
              disabled={actionBusy}
              onClick={() => handleStatusUpdate("draft")}
              title="Put this order back to draft. It will not be delivered or invoiced until it is confirmed again."
            >
              Undo confirm
            </Button>
          )}
          {order.status === "processing" && (
            <Button
              variant="outline"
              disabled={actionBusy}
              onClick={() => handleStatusUpdate("delivered")}
            >
              Mark as Delivered
            </Button>
          )}
          {(order.status === "delivered" || order.status === "shipped") && (
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

      {/* Burial details */}
      {(order.deceased_name || order.scheduled_date) && (
        <Card className="p-6 border-l-4 border-primary">
          <div className="grid grid-cols-2 gap-x-8 gap-y-3 md:grid-cols-4">
            {order.deceased_name && (
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-primary mb-0.5">Deceased</p>
                <p className="font-semibold">{order.deceased_name}</p>
              </div>
            )}
            {order.scheduled_date && (
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-primary mb-0.5">Burial Date</p>
                <p className="font-semibold">{fmtDate(order.scheduled_date)}</p>
              </div>
            )}
            {order.service_time && (
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-primary mb-0.5">Service Time</p>
                <p className="font-semibold">{order.service_time}</p>
              </div>
            )}
            {/* ⚠️ ADDED 2026-10-06. The column predates Piece 4 and nothing
                captured it; the label above used to read "Burial Time" over
                service_time, which is the conflation these two rows replace. */}
            {order.eta && (
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-primary mb-0.5">Cemetery Arrival (ETA)</p>
                <p className="font-semibold">{order.eta}</p>
              </div>
            )}
            {order.cemetery_name && (
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-primary mb-0.5">Cemetery</p>
                <p className="font-semibold">{order.cemetery_name}</p>
              </div>
            )}
          </div>
        </Card>
      )}

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
          <p className="text-sm text-muted-foreground">Delivered Date</p>
          <p className="font-medium">{fmtDate(order.shipped_date)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Payment Terms</p>
          <p className="font-medium">{order.payment_terms || "—"}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Deliver To</p>
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
                <TableHead>Delivered</TableHead>
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
                  <TableCell>{fmtQty(line.quantity)}</TableCell>
                  <TableCell>
                    <span
                      className={
                        Number(line.quantity_shipped) >= Number(line.quantity)
                          ? "text-green-600 font-medium"
                          : ""
                      }
                    >
                      {fmtQty(line.quantity_shipped)}
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

      {/* Legacy proof status */}
      <LegacyProofStatusCard orderId={id} />

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
