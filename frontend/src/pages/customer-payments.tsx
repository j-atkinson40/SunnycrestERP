import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/contexts/auth-context";
import { salesService } from "@/services/sales-service";
import type { CustomerPayment } from "@/types/sales";
import { Button } from "@/components/ui/button";
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
import { CreditCard, X } from "lucide-react";
import apiClient from "@/lib/api-client";
import { RecordPaymentDialog } from "@/components/record-payment-dialog";

// ---------------------------------------------------------------------------
// Customer selector flow — used when opening from global "Record Payment" btn
// ---------------------------------------------------------------------------

interface CustomerOption {
  id: string;
  name: string;
  account_number: string | null;
}

function CustomerPaymentEntryFlow({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [search, setSearch] = useState("");
  const [customers, setCustomers] = useState<CustomerOption[]>([]);
  const [loadingCustomers, setLoadingCustomers] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerOption | null>(null);

  useEffect(() => {
    if (search.trim().length < 2) {
      setCustomers([]);
      return;
    }
    const timer = setTimeout(async () => {
      setLoadingCustomers(true);
      try {
        const r = await apiClient.get(`/customers?search=${encodeURIComponent(search)}&per_page=10`);
        setCustomers(r.data.items ?? []);
      } finally {
        setLoadingCustomers(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  if (selectedCustomer) {
    return (
      <RecordPaymentDialog
        open
        onClose={onClose}
        onSuccess={() => { onSuccess(); onClose(); }}
        customerId={selectedCustomer.id}
        customerName={selectedCustomer.name}
      />
    );
  }

  return (
    <>
      <div className="fixed inset-0 bg-black/50 z-40" onClick={onClose} />
      <div className="fixed right-0 top-0 h-full w-full max-w-lg bg-background shadow-2xl z-50 flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b shrink-0">
          <h2 className="text-lg font-semibold">Select Customer</h2>
          <button onClick={onClose} className="rounded-md p-1.5 hover:bg-muted transition-colors" aria-label="Close">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          <p className="text-sm text-muted-foreground">Search for the customer to record a payment for.</p>
          <input
            type="text"
            autoFocus
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Type customer name..."
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          {loadingCustomers && <p className="text-sm text-muted-foreground">Searching...</p>}
          {!loadingCustomers && customers.length === 0 && search.trim().length >= 2 && (
            <p className="text-sm text-muted-foreground">No customers found.</p>
          )}
          <div className="space-y-1">
            {customers.map((c) => (
              <button
                key={c.id}
                onClick={() => setSelectedCustomer(c)}
                className="w-full text-left rounded-md border px-4 py-3 hover:bg-muted transition-colors"
              >
                <span className="font-medium">{c.name}</span>
                {c.account_number && (
                  <span className="ml-2 text-sm text-muted-foreground">#{c.account_number}</span>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>
    </>
  );
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
  if (!d) return "\u2014";
  return new Date(d).toLocaleDateString();
}

function methodBadge(method: string) {
  switch (method) {
    case "check":
      return <Badge variant="outline">Check</Badge>;
    case "ach":
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
          ACH
        </Badge>
      );
    case "credit_card":
      return (
        <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
          Credit Card
        </Badge>
      );
    case "cash":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Cash
        </Badge>
      );
    case "wire":
      return (
        <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
          Wire
        </Badge>
      );
    default:
      return <Badge variant="outline">{method}</Badge>;
  }
}

function appliedTo(payment: CustomerPayment): string {
  if (!payment.applications || payment.applications.length === 0) return "\u2014";
  return payment.applications
    .map((a) => a.invoice_number ?? a.invoice_id)
    .filter(Boolean)
    .join(", ");
}

const PER_PAGE = 20;

export default function CustomerPaymentsPage() {
  const { hasPermission } = useAuth();
  const canRecordPayment = hasPermission("ar.record_payment");

  const [payments, setPayments] = useState<CustomerPayment[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [paymentDialogOpen, setPaymentDialogOpen] = useState(false);
  const [voidingId, setVoidingId] = useState<string | null>(null);

  const loadPayments = useCallback(async () => {
    setLoading(true);
    try {
      const data = await salesService.getPayments(page, PER_PAGE);
      setPayments(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    loadPayments();
  }, [loadPayments]);

  async function handleVoidPayment(paymentId: string) {
    if (!window.confirm("Void this payment? This will reverse all invoice applications.")) return;
    setVoidingId(paymentId);
    try {
      await salesService.voidPayment(paymentId);
      toast.success("Payment voided");
      loadPayments();
    } catch {
      toast.error("Failed to void payment");
    } finally {
      setVoidingId(null);
    }
  }

  const totalPages = Math.ceil(total / PER_PAGE);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold">Customer Payments</h1>
          <p className="text-muted-foreground">{total} payments</p>
        </div>
        {canRecordPayment && (
          <Button onClick={() => setPaymentDialogOpen(true)}>
            <CreditCard className="w-4 h-4 mr-2" />
            Record Payment
          </Button>
        )}
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Customer</TableHead>
              <TableHead>Date</TableHead>
              <TableHead className="text-right">Amount</TableHead>
              <TableHead>Method</TableHead>
              <TableHead>Reference #</TableHead>
              <TableHead>Applied To</TableHead>
              {canRecordPayment && <TableHead />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={canRecordPayment ? 7 : 6} className="text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : payments.length === 0 ? (
              <TableRow>
                <TableCell colSpan={canRecordPayment ? 7 : 6} className="text-center">
                  No payments found
                </TableCell>
              </TableRow>
            ) : (
              payments.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="font-medium">
                    {p.customer_name ?? "\u2014"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {fmtDate(p.payment_date)}
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    {fmtCurrency(p.total_amount)}
                  </TableCell>
                  <TableCell>{methodBadge(p.payment_method)}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {p.reference_number ?? "\u2014"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {appliedTo(p)}
                  </TableCell>
                  {canRecordPayment && (
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-muted-foreground hover:text-destructive text-xs"
                        disabled={voidingId === p.id}
                        onClick={() => handleVoidPayment(p.id)}
                      >
                        {voidingId === p.id ? "Voiding..." : "Void"}
                      </Button>
                    </TableCell>
                  )}
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
      {/* Customer picker before payment dialog */}
      {paymentDialogOpen && (
        <CustomerPaymentEntryFlow
          onClose={() => setPaymentDialogOpen(false)}
          onSuccess={loadPayments}
        />
      )}
    </div>
  );
}
