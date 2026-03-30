import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, CheckCircle, ClipboardCheck, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

interface InvoiceLine {
  id: string;
  description: string;
  quantity: number;
  unit_price: number;
  line_total: number;
  product_id: string | null;
}

interface ReviewInvoice {
  id: string;
  number: string;
  customer_id: string;
  customer_name: string | null;
  ship_to: string | null;
  invoice_date: string;
  due_date: string;
  subtotal: number;
  tax_amount: number;
  total: number;
  has_exceptions: boolean;
  review_notes: string | null;
  review_due_date: string | null;
  auto_generated: boolean;
  generation_reason: string | null;
  sales_order_id: string | null;
  order_number: string | null;
  scheduled_date: string | null;
  driver_exceptions: Array<{ product_id?: string; reason: string; notes?: string }> | null;
  lines: InvoiceLine[];
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(amount);
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}


interface InvoiceCardProps {
  invoice: ReviewInvoice;
  onApprove: (id: string) => Promise<void>;
  approving: boolean;
}

function InvoiceCard({ invoice, onApprove, approving }: InvoiceCardProps) {
  const navigate = useNavigate();

  return (
    <Card className={invoice.has_exceptions ? "border-amber-300" : ""}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle className="text-base font-semibold">
              {invoice.customer_name ?? "Unknown Customer"}
            </CardTitle>
            {invoice.ship_to && (
              <p className="text-sm text-muted-foreground mt-0.5">{invoice.ship_to}</p>
            )}
          </div>
          <div className="text-right shrink-0">
            <div className="text-sm font-medium text-muted-foreground">
              {formatDate(invoice.scheduled_date ?? invoice.invoice_date)}
            </div>
            {invoice.order_number && (
              <div className="text-xs text-muted-foreground">{invoice.order_number}</div>
            )}
          </div>
        </div>

        {invoice.has_exceptions && (
          <div className="mt-2 rounded-md bg-amber-50 border border-amber-200 p-3">
            <div className="flex items-center gap-1.5 text-amber-800 font-medium text-sm mb-1">
              <AlertTriangle className="w-4 h-4" />
              Driver exception reported
            </div>
            {invoice.review_notes && (
              <p className="text-sm text-amber-700">{invoice.review_notes}</p>
            )}
            {invoice.driver_exceptions && invoice.driver_exceptions.length > 0 && (
              <ul className="mt-1 space-y-0.5">
                {invoice.driver_exceptions.map((ex, i) => (
                  <li key={i} className="text-xs text-amber-700">
                    • <span className="font-medium capitalize">{ex.reason.replace(/_/g, " ")}</span>
                    {ex.notes ? ` — ${ex.notes}` : ""}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </CardHeader>

      <CardContent className="pt-0">
        <div className="space-y-1.5 mb-4">
          {invoice.lines.map((line) => (
            <div
              key={line.id}
              className="flex items-center justify-between text-sm"
            >
              <span className="text-foreground">{line.description}</span>
              <span className="text-foreground font-medium tabular-nums">
                {formatCurrency(line.line_total)}
              </span>
            </div>
          ))}
        </div>

        <Separator className="my-3" />

        <div className="flex justify-between text-sm font-semibold">
          <span>Total</span>
          <span className="tabular-nums">{formatCurrency(invoice.total)}</span>
        </div>

        <div className="flex gap-2 mt-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate(`/ar/invoices/${invoice.id}`)}
          >
            Edit Invoice
          </Button>
          <Button
            size="sm"
            onClick={() => onApprove(invoice.id)}
            disabled={approving}
            className="ml-auto"
          >
            <CheckCircle className="w-4 h-4 mr-1.5" />
            Approve & Post
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function InvoiceReviewQueue() {
  const [invoices, setInvoices] = useState<ReviewInvoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [approvingIds, setApprovingIds] = useState<Set<string>>(new Set());
  const [batchApproving, setBatchApproving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get("/sales/invoices/review");
      setInvoices(res.data);
    } catch (err) {
      toast.error(getApiErrorMessage(err) ?? "Failed to load review queue");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleApprove = useCallback(
    async (invoiceId: string) => {
      setApprovingIds((prev) => new Set(prev).add(invoiceId));
      try {
        await apiClient.post(`/sales/invoices/${invoiceId}/approve`);
        toast.success("Invoice approved and posted to AR");
        setInvoices((prev) => prev.filter((i) => i.id !== invoiceId));
      } catch (err) {
        toast.error(getApiErrorMessage(err) ?? "Failed to approve invoice");
      } finally {
        setApprovingIds((prev) => {
          const next = new Set(prev);
          next.delete(invoiceId);
          return next;
        });
      }
    },
    []
  );

  const handleApproveAll = useCallback(async () => {
    const noExceptions = invoices.filter((i) => !i.has_exceptions);
    if (noExceptions.length === 0) return;

    const confirmed = window.confirm(
      `Approve ${noExceptions.length} invoice${noExceptions.length !== 1 ? "s" : ""} with no exceptions?`
    );
    if (!confirmed) return;

    setBatchApproving(true);
    try {
      const res = await apiClient.post("/sales/invoices/approve-batch");
      const count: number = res.data.approved_count ?? 0;
      const amount: string = res.data.total_amount ?? "0";
      toast.success(
        `${count} invoice${count !== 1 ? "s" : ""} approved — $${parseFloat(amount).toLocaleString()} posted to AR`
      );
      await load();
    } catch (err) {
      toast.error(getApiErrorMessage(err) ?? "Bulk approve failed");
    } finally {
      setBatchApproving(false);
    }
  }, [invoices, load]);

  const withExceptions = invoices.filter((i) => i.has_exceptions);
  const withoutExceptions = invoices.filter((i) => !i.has_exceptions);
  const totalAmount = invoices.reduce((sum, i) => sum + i.total, 0);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[200px] text-muted-foreground">
        Loading review queue…
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <ClipboardCheck className="w-5 h-5" />
            Draft Invoice Review
          </h1>
          {invoices.length > 0 && (
            <p className="text-sm text-muted-foreground mt-0.5">
              {invoices.length} invoice{invoices.length !== 1 ? "s" : ""} pending —{" "}
              {formatCurrency(totalAmount)} total
              {withExceptions.length > 0 && (
                <span className="text-amber-600 ml-1">
                  ({withExceptions.length} with exceptions)
                </span>
              )}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={load} title="Refresh">
            <RefreshCw className="w-4 h-4" />
          </Button>
          {withoutExceptions.length > 0 && (
            <Button
              onClick={handleApproveAll}
              disabled={batchApproving}
              variant="outline"
            >
              <CheckCircle className="w-4 h-4 mr-1.5" />
              Approve All ({withoutExceptions.length})
            </Button>
          )}
        </div>
      </div>

      {invoices.length === 0 && (
        <div className="text-center py-16 text-muted-foreground">
          <ClipboardCheck className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="font-medium">No drafts waiting for review</p>
          <p className="text-sm mt-1">
            End-of-day batch invoices will appear here after 6 PM.
          </p>
        </div>
      )}

      {/* Exception invoices first */}
      {withExceptions.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-amber-700 flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4" />
            Requires individual review ({withExceptions.length})
          </h2>
          {withExceptions.map((inv) => (
            <InvoiceCard
              key={inv.id}
              invoice={inv}
              onApprove={handleApprove}
              approving={approvingIds.has(inv.id)}
            />
          ))}
        </div>
      )}

      {/* Clean invoices */}
      {withoutExceptions.length > 0 && (
        <div className="space-y-4">
          {withExceptions.length > 0 && (
            <h2 className="text-sm font-semibold text-muted-foreground">
              No exceptions ({withoutExceptions.length})
            </h2>
          )}
          {withoutExceptions.map((inv) => (
            <InvoiceCard
              key={inv.id}
              invoice={inv}
              onApprove={handleApprove}
              approving={approvingIds.has(inv.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
