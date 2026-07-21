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
import { CheckCircle2, CreditCard, ExternalLink, FileMinus2, Send, Undo2, Wallet } from "lucide-react";
import { RecordPaymentDialog } from "@/components/record-payment-dialog";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

interface InvoicePaymentRecord {
  payment_id: string;
  payment_date: string | null;
  payment_method: string;
  reference_number: string | null;
  amount_applied: number;
  notes: string | null;
}

interface CreditMemoRecord {
  id: string;
  number: string;
  amount: number;
  reason: string;
  status: string;
  created_at: string | null;
  void_reason: string | null;
}

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
  const s = status.toLowerCase();
  switch (s) {
    case "draft":
      return <Badge className="bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300">Draft</Badge>;
    case "open":
      return <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">Open</Badge>;
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
      return <Badge className="bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">Overdue</Badge>;
    case "void":
      return (
        <Badge className="bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400">
          Void
        </Badge>
      );
    case "write_off":
      return <Badge className="bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400">Write-Off</Badge>;
    default:
      return <Badge className="bg-gray-100 text-gray-700">{status.charAt(0).toUpperCase() + status.slice(1)}</Badge>;
  }
}

function fmtQty(n: string | number): string {
  const num = Number(n);
  return Number.isInteger(num) ? String(num) : num.toFixed(2);
}

// ---------------------------------------------------------------------------
// Detail view
// ---------------------------------------------------------------------------

export default function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { hasPermission } = useAuth();

  const canVoid = hasPermission("ar.void");
  const canRecordPayment = hasPermission("ar.record_payment");

  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [paymentDialogOpen, setPaymentDialogOpen] = useState(false);
  const [paymentHistory, setPaymentHistory] = useState<InvoicePaymentRecord[]>([]);
  const [loadingPayments, setLoadingPayments] = useState(false);
  // Exceptions arc — memos, write-off, the credit pocket
  const [memos, setMemos] = useState<CreditMemoRecord[]>([]);
  const [customerCredit, setCustomerCredit] = useState(0);
  const [memoOpen, setMemoOpen] = useState(false);
  const [memoAmount, setMemoAmount] = useState("");
  const [memoReason, setMemoReason] = useState("");
  const [writeOffOpen, setWriteOffOpen] = useState(false);
  const [writeOffReason, setWriteOffReason] = useState("");
  const [reinstateOpen, setReinstateOpen] = useState(false);
  const [reinstateReason, setReinstateReason] = useState("");
  const [applyOpen, setApplyOpen] = useState(false);
  const [applyAmount, setApplyAmount] = useState("");
  const [busy, setBusy] = useState(false);

  const loadPaymentHistory = useCallback(async () => {
    if (!id) return;
    setLoadingPayments(true);
    try {
      const r = await apiClient.get(`/sales/invoices/${id}/payments`);
      setPaymentHistory(r.data);
    } catch {
      // non-critical — silently ignore
    } finally {
      setLoadingPayments(false);
    }
  }, [id]);

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

  const loadMemos = useCallback(async () => {
    if (!id) return;
    try {
      const r = await apiClient.get(`/sales/invoices/${id}/credit-memos`);
      setMemos(r.data);
    } catch {
      // non-critical
    }
  }, [id]);

  useEffect(() => {
    loadInvoice();
    loadPaymentHistory();
    loadMemos();
  }, [loadInvoice, loadPaymentHistory, loadMemos]);

  // The pocket's balance — shown only when the customer holds credit.
  useEffect(() => {
    if (!invoice?.customer_id) return;
    apiClient.get(`/customers/${invoice.customer_id}`)
      .then((r) => setCustomerCredit(Number(r.data.credit_balance ?? 0)))
      .catch(() => setCustomerCredit(0));
  }, [invoice?.customer_id]);

  const refreshAll = useCallback(() => {
    loadInvoice();
    loadMemos();
    loadPaymentHistory();
  }, [loadInvoice, loadMemos, loadPaymentHistory]);

  async function act(fn: () => Promise<unknown>, ok: string) {
    setBusy(true);
    try {
      await fn();
      toast.success(ok);
      refreshAll();
      return true;
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Action failed"));
      return false;
    } finally {
      setBusy(false);
    }
  }

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

  const canShowRecordPayment =
    canRecordPayment &&
    ["sent", "partial", "overdue", "open"].includes(invoice.status) &&
    balanceNum > 0;

  // Exceptions arc verbs
  const openStatuses = ["sent", "partial", "overdue", "open"];
  const canShowMemo = canVoid && openStatuses.includes(invoice.status) && balanceNum > 0;
  const canShowWriteOff = canShowMemo;
  const canShowReinstate = canVoid && invoice.status === "write_off";
  const canShowApplyCredit =
    canVoid && openStatuses.includes(invoice.status) && balanceNum > 0 && customerCredit > 0;
  const amountCredited = Number(invoice.amount_credited ?? 0);

  const daysOverdue = isOverdue
    ? Math.floor(
        (new Date().getTime() - new Date(invoice.due_date).getTime()) /
          (1000 * 60 * 60 * 24)
      )
    : 0;

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
          {canShowRecordPayment && (
            <Button onClick={() => setPaymentDialogOpen(true)}>
              <CreditCard className="w-4 h-4 mr-1.5" />
              Record Payment
            </Button>
          )}
          {canShowApplyCredit && (
            <Button variant="outline" size="sm" onClick={() => { setApplyAmount(String(Math.min(customerCredit, balanceNum))); setApplyOpen(true); }}>
              <Wallet className="w-4 h-4 mr-1.5" />
              Apply Credit
            </Button>
          )}
          {canShowMemo && (
            <Button variant="outline" size="sm" onClick={() => { setMemoAmount(""); setMemoReason(""); setMemoOpen(true); }}>
              <FileMinus2 className="w-4 h-4 mr-1.5" />
              Credit Memo
            </Button>
          )}
          {canShowWriteOff && (
            <Button variant="outline" size="sm" onClick={() => { setWriteOffReason(""); setWriteOffOpen(true); }}>
              Write Off
            </Button>
          )}
          {canShowReinstate && (
            <Button variant="outline" size="sm" onClick={() => { setReinstateReason(""); setReinstateOpen(true); }}>
              <Undo2 className="w-4 h-4 mr-1.5" />
              Reinstate
            </Button>
          )}
          {canShowVoid && (
            <Button variant="destructive" size="sm" onClick={handleVoid}>
              Void Invoice
            </Button>
          )}
        </div>
      </div>

      {/* Write-off banner — the reason on the record */}
      {invoice.status === "write_off" && (
        <div className="rounded-md border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/40 px-4 py-3 text-sm text-muted-foreground">
          <span className="font-medium text-foreground">
            {fmtCurrency(invoice.written_off_amount ?? "0")} written off AR
          </span>
          {invoice.write_off_reason && <> — “{invoice.write_off_reason}”</>}
          <span className="block mt-0.5 text-xs">
            The remainder moved off the customer's balance. Reinstating is a
            deliberate action with its own reason.
          </span>
        </div>
      )}

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
                  className="text-blue-600 hover:text-blue-800 hover:underline font-medium inline-flex items-center gap-1"
                >
                  View Order
                  <ExternalLink className="w-3.5 h-3.5" />
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
            <dd className={`font-medium flex items-center gap-2 ${isOverdue ? "text-red-600" : ""}`}>
              {fmtDate(invoice.due_date)}
              {isOverdue && daysOverdue > 0 && (
                <span className="text-xs font-normal text-red-500">
                  ({daysOverdue} day{daysOverdue !== 1 ? "s" : ""} overdue)
                </span>
              )}
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
                    <TableCell className="text-right">{fmtQty(line.quantity)}</TableCell>
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
            {Number((invoice as Invoice & { discount_amount?: string }).discount_amount) > 0 && (
              <div className="flex justify-between gap-8">
                <span className="text-sm text-green-600 dark:text-green-400">Early payment discount</span>
                <span className="text-sm text-green-600 dark:text-green-400">
                  -{fmtCurrency((invoice as Invoice & { discount_amount?: string }).discount_amount ?? "0")}
                </span>
              </div>
            )}
            <div className="flex justify-between gap-8">
              <span className="text-sm text-muted-foreground">Amount Paid</span>
              <span className="text-sm">{fmtCurrency(invoice.amount_paid)}</span>
            </div>
            {amountCredited > 0 && (
              <div className="flex justify-between gap-8">
                <span className="text-sm text-muted-foreground">Credited (memos)</span>
                <span className="text-sm">-{fmtCurrency(amountCredited)}</span>
              </div>
            )}
            {Number(invoice.written_off_amount ?? 0) > 0 && (
              <div className="flex justify-between gap-8">
                <span className="text-sm text-muted-foreground">Written off</span>
                <span className="text-sm">-{fmtCurrency(invoice.written_off_amount ?? "0")}</span>
              </div>
            )}
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

      {/* Paid status callout */}
      {invoice.status === "paid" && (
        <div className="flex items-center gap-2 rounded-md bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800 px-4 py-3">
          <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400 shrink-0" />
          <span className="text-sm font-medium text-green-800 dark:text-green-300">
            Paid in full
            {(invoice as Invoice & { paid_at?: string }).paid_at && (
              <> on {fmtDate((invoice as Invoice & { paid_at?: string }).paid_at ?? null)}</>
            )}
          </span>
        </div>
      )}

      {/* Credit memos — the credit documents on this invoice */}
      {memos.length > 0 && (
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">Credit Memos</h2>
          <div className="divide-y">
            {memos.map((m) => (
              <div key={m.id} className="flex items-center gap-3 py-2.5">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">
                    {m.number}
                    {m.status === "void" && (
                      <span className="ml-2 text-xs text-muted-foreground">void{m.void_reason ? ` — ${m.void_reason}` : ""}</span>
                    )}
                  </p>
                  <p className="text-xs text-muted-foreground italic">“{m.reason}”</p>
                </div>
                <span className={`text-sm font-semibold ${m.status === "void" ? "line-through text-muted-foreground" : ""}`}>
                  -{fmtCurrency(m.amount)}
                </span>
                {m.status === "posted" && canVoid && invoice.status !== "write_off" && (
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={busy}
                    onClick={() => {
                      const reason = window.prompt("Void this memo — why? (optional)") ?? undefined;
                      act(
                        () => apiClient.post(`/sales/credit-memos/${m.id}/void`, { reason }),
                        `Memo ${m.number} voided`,
                      );
                    }}
                  >
                    Void
                  </Button>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Payments Applied */}
      {(hasPayments || paymentHistory.length > 0) && (
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">Payments Applied</h2>
          {loadingPayments ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : paymentHistory.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Total paid:{" "}
              <span className="font-medium text-foreground">
                {fmtCurrency(invoice.amount_paid)}
              </span>
            </p>
          ) : (
            <>
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Method</TableHead>
                      <TableHead>Reference</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                      <TableHead>Notes</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {paymentHistory.map((p) => (
                      <TableRow key={p.payment_id}>
                        <TableCell className="text-muted-foreground whitespace-nowrap">
                          {fmtDate(p.payment_date)}
                        </TableCell>
                        <TableCell className="capitalize">
                          {p.payment_method.replace("_", " ")}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {p.reference_number ?? "—"}
                        </TableCell>
                        <TableCell className="text-right font-medium text-green-600 dark:text-green-400">
                          {fmtCurrency(p.amount_applied)}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {p.notes ?? "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <div className="flex justify-end mt-3">
                <div className="space-y-1 text-right min-w-[200px]">
                  <div className="flex justify-between gap-8 text-sm">
                    <span className="text-muted-foreground">Total Payments</span>
                    <span className="font-medium text-green-600 dark:text-green-400">{fmtCurrency(invoice.amount_paid)}</span>
                  </div>
                  <div className="flex justify-between gap-8 text-sm border-t pt-1">
                    <span className="font-semibold">Remaining Balance</span>
                    <span className={`font-bold ${balanceNum > 0 ? "text-red-600" : "text-green-600"}`}>
                      {fmtCurrency(invoice.balance_remaining)}
                    </span>
                  </div>
                </div>
              </div>
            </>
          )}
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

      {/* Record Payment dialog */}
      <RecordPaymentDialog
        open={paymentDialogOpen}
        onClose={() => setPaymentDialogOpen(false)}
        onSuccess={() => {
          loadInvoice();
          loadPaymentHistory();
        }}
        customerId={invoice.customer_id}
        customerName={invoice.customer_name ?? ""}
        defaultInvoiceId={id}
      />

      {/* Credit memo dialog — the reason is the record */}
      <Dialog open={memoOpen} onOpenChange={(o) => !o && setMemoOpen(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Credit memo on {invoice.number}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Credits reduce the open balance ({fmtCurrency(invoice.balance_remaining)}) and
            post to AR as the negative. A memo can't exceed the balance — an
            overpayment is recorded as customer credit instead.
          </p>
          <Input
            type="number"
            min="0.01"
            step="0.01"
            value={memoAmount}
            onChange={(e) => setMemoAmount(e.target.value)}
            placeholder="Amount"
          />
          <Input
            value={memoReason}
            onChange={(e) => setMemoReason(e.target.value)}
            placeholder="Why — e.g. damaged liner on delivery"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setMemoOpen(false)}>Cancel</Button>
            <Button
              disabled={busy || !memoAmount || !memoReason.trim()}
              onClick={async () => {
                const ok = await act(
                  () => apiClient.post(`/sales/invoices/${id}/credit-memos`, {
                    amount: memoAmount, reason: memoReason.trim(),
                  }),
                  "Credit memo posted",
                );
                if (ok) setMemoOpen(false);
              }}
            >
              Post memo
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Write-off dialog */}
      <Dialog open={writeOffOpen} onOpenChange={(o) => !o && setWriteOffOpen(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Write off {invoice.number}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Writes the remaining {fmtCurrency(invoice.balance_remaining)} off AR —
            {hasPayments && " the payments already received stay received —"} a
            money move with its reason kept on the record. (This is an AR
            write-off, distinct from inventory write-offs.)
          </p>
          <Input
            value={writeOffReason}
            onChange={(e) => setWriteOffReason(e.target.value)}
            placeholder="Why — e.g. customer closed, uncollectable"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setWriteOffOpen(false)}>Cancel</Button>
            <Button
              variant="destructive"
              disabled={busy || !writeOffReason.trim()}
              onClick={async () => {
                const ok = await act(
                  () => apiClient.post(`/sales/invoices/${id}/write-off`, { reason: writeOffReason.trim() }),
                  "Remainder written off",
                );
                if (ok) setWriteOffOpen(false);
              }}
            >
              Write off
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reinstate dialog */}
      <Dialog open={reinstateOpen} onOpenChange={(o) => !o && setReinstateOpen(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reinstate {invoice.number}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Restores {fmtCurrency(invoice.written_off_amount ?? "0")} onto the
            customer's balance. Reinstating is deliberate — it carries its own reason.
          </p>
          <Input
            value={reinstateReason}
            onChange={(e) => setReinstateReason(e.target.value)}
            placeholder="Why — e.g. customer resurfaced and will pay"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setReinstateOpen(false)}>Cancel</Button>
            <Button
              disabled={busy || !reinstateReason.trim()}
              onClick={async () => {
                const ok = await act(
                  () => apiClient.post(`/sales/invoices/${id}/reinstate`, { reason: reinstateReason.trim() }),
                  "Invoice reinstated",
                );
                if (ok) setReinstateOpen(false);
              }}
            >
              Reinstate
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Apply credit dialog — the pocket's door */}
      <Dialog open={applyOpen} onOpenChange={(o) => !o && setApplyOpen(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Apply customer credit</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {invoice.customer_name} holds {fmtCurrency(customerCredit)} of credit.
            Apply up to the open balance ({fmtCurrency(invoice.balance_remaining)});
            anything left stays in the pocket.
          </p>
          <Input
            type="number"
            min="0.01"
            step="0.01"
            value={applyAmount}
            onChange={(e) => setApplyAmount(e.target.value)}
            placeholder="Amount"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setApplyOpen(false)}>Cancel</Button>
            <Button
              disabled={busy || !applyAmount}
              onClick={async () => {
                const ok = await act(
                  () => apiClient.post(`/sales/customers/${invoice.customer_id}/credit/apply`, {
                    invoice_id: id, amount: applyAmount,
                  }),
                  "Credit applied",
                );
                if (ok) {
                  setApplyOpen(false);
                  setCustomerCredit((c) => Math.max(0, c - Number(applyAmount)));
                }
              }}
            >
              Apply
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
