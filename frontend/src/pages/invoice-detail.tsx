import { useCallback, useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { salesService } from "@/services/sales-service";
import { getApiErrorMessage } from "@/lib/api-error";
import apiClient from "@/lib/api-client";
import type { Invoice } from "@/types/sales";
import { Button } from "@/components/ui/button";
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
import { toast } from "sonner";
import { ExternalLink, Send } from "lucide-react";

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
    case "sent":
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
          Sent
        </Badge>
      );
    case "partial":
      return (
        <Badge className="bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200">
          Partial
        </Badge>
      );
    case "paid":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Paid
        </Badge>
      );
    case "overdue":
      return <Badge variant="destructive">Overdue</Badge>;
    case "void":
      return (
        <Badge variant="outline" className="text-gray-400">
          Void
        </Badge>
      );
    case "write_off":
      return <Badge variant="outline">Write-Off</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

// ---------------------------------------------------------------------------
// Detail view
// ---------------------------------------------------------------------------

export default function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { hasPermission } = useAuth();

  const canVoid = hasPermission("ar.void");

  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadInvoice = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const data = await salesService.getInvoice(id);
      setInvoice(data);
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to load invoice"));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadInvoice();
  }, [loadInvoice]);

  async function handleMarkSent() {
    if (!id) return;
    try {
      await salesService.updateInvoice(id, { status: "sent" });
      toast.success("Invoice marked as sent");
      loadInvoice();
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to update invoice"));
    }
  }

  async function handleSendInvoice() {
    if (!id) return;
    try {
      await apiClient.post(`/sales/invoices/${id}/send`);
      toast.success("Invoice emailed successfully");
      loadInvoice();
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to send invoice"));
    }
  }

  function handlePreviewPdf() {
    window.open(`/api/v1/sales/invoices/${id}/preview?format=pdf`, "_blank");
  }

  async function handleVoid() {
    if (!id) return;
    if (!window.confirm("Void this invoice? This cannot be undone.")) return;
    try {
      await salesService.voidInvoice(id);
      toast.success("Invoice voided");
      loadInvoice();
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to void invoice"));
    }
  }

  if (loading) return <div className="p-8 text-center">Loading...</div>;
  if (error)
    return <div className="p-8 text-center text-destructive">{error}</div>;
  if (!invoice) return null;

  const isOverdue =
    !["paid", "void", "draft"].includes(invoice.status) &&
    new Date(invoice.due_date) < new Date();

  const balanceNum = Number(invoice.balance_remaining);
  const hasPayments = Number(invoice.amount_paid) > 0;
  const canShowVoid =
    !["void", "paid"].includes(invoice.status) &&
    !hasPayments &&
    canVoid;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Link
            to="/ar/invoices"
            className="text-sm text-muted-foreground hover:underline"
          >
            &larr; Invoices
          </Link>
          <div className="flex items-center gap-3 mt-1">
            <h1 className="text-3xl font-bold">{invoice.number}</h1>
            {statusBadge(invoice.status)}
            {isOverdue && invoice.status !== "overdue" && (
              <Badge variant="destructive">Overdue</Badge>
            )}
          </div>
          <p className="text-muted-foreground mt-0.5">
            {invoice.customer_name || "—"}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handlePreviewPdf}>
            <ExternalLink className="w-4 h-4 mr-1.5" />
            Preview PDF
          </Button>
          <Button variant="outline" size="sm" onClick={handleSendInvoice}>
            <Send className="w-4 h-4 mr-1.5" />
            Send Invoice
          </Button>
          {invoice.status === "draft" && (
            <Button variant="outline" onClick={handleMarkSent}>
              Mark as Sent
            </Button>
          )}
          {canShowVoid && (
            <Button variant="destructive" size="sm" onClick={handleVoid}>
              Void Invoice
            </Button>
          )}
        </div>
      </div>

      {/* RE — deceased name callout */}
      {invoice.deceased_name && (
        <div className="rounded-md border-l-4 border-primary bg-muted/40 px-4 py-3">
          <p className="text-xs font-bold uppercase tracking-wide text-primary mb-0.5">RE</p>
          <p className="font-semibold text-base">{invoice.deceased_name}</p>
        </div>
      )}

      {/* Sent status */}
      {invoice.sent_at && (
        <div className="text-sm text-muted-foreground">
          Emailed to <span className="font-medium">{invoice.sent_to_email}</span> on {new Date(invoice.sent_at).toLocaleDateString()}
        </div>
      )}

      {/* Invoice info */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold mb-4">Invoice Details</h2>
        <dl className="grid grid-cols-2 gap-x-8 gap-y-3 md:grid-cols-3">
          <div>
            <dt className="text-sm text-muted-foreground">Customer</dt>
            <dd className="font-medium">{invoice.customer_name || "—"}</dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">Sales Order</dt>
            <dd className="font-medium">
              {invoice.sales_order_id ? (
                <Link
                  to={`/ar/orders/${invoice.sales_order_id}`}
                  className="text-primary hover:underline"
                >
                  View Order
                </Link>
              ) : (
                "—"
              )}
            </dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">Invoice Date</dt>
            <dd className="font-medium">{fmtDate(invoice.invoice_date)}</dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">Due Date</dt>
            <dd
              className={`font-medium ${isOverdue ? "text-red-600" : ""}`}
            >
              {fmtDate(invoice.due_date)}
            </dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">Payment Terms</dt>
            <dd className="font-medium">{invoice.payment_terms || "—"}</dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">Status</dt>
            <dd>{statusBadge(invoice.status)}</dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">Created By</dt>
            <dd className="font-medium">{invoice.created_by_name || "—"}</dd>
          </div>
        </dl>
      </Card>

      {/* Line items */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold mb-4">Line Items</h2>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[40%]">Description</TableHead>
                <TableHead>Product</TableHead>
                <TableHead className="text-right">Qty</TableHead>
                <TableHead className="text-right">Unit Price</TableHead>
                <TableHead className="text-right">Line Total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {invoice.lines.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="text-center text-muted-foreground"
                  >
                    No line items
                  </TableCell>
                </TableRow>
              ) : (
                invoice.lines.map((line) => (
                  <TableRow key={line.id}>
                    <TableCell>{line.description}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {line.product_name || "—"}
                    </TableCell>
                    <TableCell className="text-right">{line.quantity}</TableCell>
                    <TableCell className="text-right">
                      {fmtCurrency(line.unit_price)}
                    </TableCell>
                    <TableCell className="text-right font-medium">
                      {fmtCurrency(line.line_total)}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>

        {/* Totals */}
        <div className="flex justify-end mt-4">
          <div className="space-y-1 text-right min-w-[200px]">
            <div className="flex justify-between gap-8">
              <span className="text-sm text-muted-foreground">Subtotal</span>
              <span className="text-sm">{fmtCurrency(invoice.subtotal)}</span>
            </div>
            <div className="flex justify-between gap-8">
              <span className="text-sm text-muted-foreground">Tax</span>
              <span className="text-sm">{fmtCurrency(invoice.tax_amount)}</span>
            </div>
            <div className="flex justify-between gap-8 border-t pt-1">
              <span className="font-semibold">Total</span>
              <span className="font-semibold">{fmtCurrency(invoice.total)}</span>
            </div>
            <div className="flex justify-between gap-8">
              <span className="text-sm text-muted-foreground">Amount Paid</span>
              <span className="text-sm">{fmtCurrency(invoice.amount_paid)}</span>
            </div>
            <div className="flex justify-between gap-8 border-t pt-1">
              <span className="font-semibold">Balance Remaining</span>
              <span
                className={`font-bold ${balanceNum > 0 ? "text-red-600" : ""}`}
              >
                {fmtCurrency(invoice.balance_remaining)}
              </span>
            </div>
          </div>
        </div>
      </Card>

      {/* Payment history */}
      {hasPayments && (
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">Payment History</h2>
          <p className="text-sm text-muted-foreground">
            Total paid:{" "}
            <span className="font-medium text-foreground">
              {fmtCurrency(invoice.amount_paid)}
            </span>
          </p>
        </Card>
      )}

      {/* Notes */}
      {invoice.notes && (
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-2">Notes</h2>
          <p className="text-sm whitespace-pre-wrap">{invoice.notes}</p>
        </Card>
      )}

      {/* Metadata */}
      <div className="text-xs text-muted-foreground space-y-0.5">
        {invoice.created_by_name && (
          <p>Created by: {invoice.created_by_name}</p>
        )}
        <p>Created: {new Date(invoice.created_at).toLocaleString()}</p>
        {invoice.modified_at && (
          <p>Last modified: {new Date(invoice.modified_at).toLocaleString()}</p>
        )}
      </div>
    </div>
  );
}
