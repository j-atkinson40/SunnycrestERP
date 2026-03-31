import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { salesService } from "@/services/sales-service";
import type { CustomerPayment } from "@/types/sales";
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
import { AlertTriangle, Camera, CreditCard, FileText, Upload, X } from "lucide-react";
import apiClient from "@/lib/api-client";
import { RecordPaymentDialog } from "@/components/record-payment-dialog";
import { CheckScanner, type ScannedCheck } from "@/components/check-scanner";

// ---------------------------------------------------------------------------
// Customer selector flow
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
        onSuccess={() => {
          onSuccess();
          onClose();
        }}
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
          <button
            onClick={onClose}
            className="rounded-md p-1.5 hover:bg-muted transition-colors"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          <p className="text-sm text-muted-foreground">
            Search for the customer to record a payment for.
          </p>
          <input
            type="text"
            autoFocus
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Type customer name..."
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          {loadingCustomers && (
            <p className="text-sm text-muted-foreground">Searching...</p>
          )}
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
                  <span className="ml-2 text-sm text-muted-foreground">
                    #{c.account_number}
                  </span>
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
  if (payment.applications.length === 1) {
    return payment.applications[0].invoice_number ?? payment.applications[0].invoice_id;
  }
  return `${payment.applications.length} invoices`;
}

// Alert types to show in Needs Attention section
const PAYMENT_ALERT_TYPES = new Set([
  "short_pay_late_discount",
  "unmatched_payment",
  "overpayment",
  "short_pay",
  "discount_expiring",
]);

interface AgentAlertItem {
  id: string;
  alert_type: string;
  severity: string;
  title: string;
  message: string;
  action_label: string | null;
  action_url: string | null;
  created_at: string | null;
}

const PER_PAGE = 20;

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function CustomerPaymentsPage() {
  const { hasPermission } = useAuth();
  const navigate = useNavigate();
  const canRecordPayment = hasPermission("ar.record_payment");

  const [payments, setPayments] = useState<CustomerPayment[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [voidingId, setVoidingId] = useState<string | null>(null);

  // Alerts
  const [alerts, setAlerts] = useState<AgentAlertItem[]>([]);
  const [resolvingAlertId, setResolvingAlertId] = useState<string | null>(null);

  // UI state
  const [showManualEntry, setShowManualEntry] = useState(false);
  const [showCheckScanner, setShowCheckScanner] = useState(false);

  // ---------------------------------------------------------------------------
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

  const loadAlerts = useCallback(async () => {
    try {
      const r = await apiClient.get("/agents/alerts?resolved=false&limit=50");
      const all: AgentAlertItem[] = r.data ?? [];
      setAlerts(all.filter((a) => PAYMENT_ALERT_TYPES.has(a.alert_type)));
    } catch {
      // non-critical
    }
  }, []);

  useEffect(() => {
    loadPayments();
  }, [loadPayments]);

  useEffect(() => {
    loadAlerts();
  }, [loadAlerts]);

  // ---------------------------------------------------------------------------

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

  async function handleResolveAlert(alertId: string) {
    setResolvingAlertId(alertId);
    try {
      await apiClient.post(`/agents/alerts/${alertId}/resolve`);
      setAlerts((prev) => prev.filter((a) => a.id !== alertId));
    } catch {
      toast.error("Failed to dismiss alert");
    } finally {
      setResolvingAlertId(null);
    }
  }

  function handleCheckScanComplete(result: ScannedCheck) {
    setShowCheckScanner(false);
    // If we have a matched customer, open RecordPaymentDialog with pre-fill info
    // For now just show the manual entry flow — user can use the scanned data
    toast.success(
      result.matched_customer
        ? `Check matched to ${result.matched_customer.name}`
        : "Check scanned — enter payment manually"
    );
    setShowManualEntry(true);
  }

  const totalPages = Math.ceil(total / PER_PAGE);

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold">Customer Payments</h1>
          <p className="text-muted-foreground">{total} payments</p>
        </div>

        {canRecordPayment && (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              onClick={() => setShowCheckScanner(true)}
            >
              <Camera className="w-4 h-4 mr-2" />
              Scan Check
            </Button>
            <Button onClick={() => setShowManualEntry(true)}>
              <CreditCard className="w-4 h-4 mr-2" />
              Enter Manually
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                const input = document.createElement("input");
                input.type = "file";
                input.accept = ".csv";
                input.onchange = async (e) => {
                  const file = (e.target as HTMLInputElement).files?.[0];
                  if (!file) return;
                  const fd = new FormData();
                  fd.append("file", file);
                  try {
                    await apiClient.post("/sales/payments/import", fd, {
                      headers: { "Content-Type": "multipart/form-data" },
                    });
                    toast.success("Payments imported");
                    loadPayments();
                  } catch {
                    toast.error("Import failed");
                  }
                };
                input.click();
              }}
            >
              <Upload className="w-4 h-4 mr-2" />
              Import CSV
            </Button>
          </div>
        )}
      </div>

      {/* Needs Attention */}
      {alerts.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Needs Attention ({alerts.length})
          </h2>
          {alerts.map((alert) => (
            <Card key={alert.id} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-2.5">
                  <AlertTriangle
                    className={`w-4 h-4 mt-0.5 shrink-0 ${
                      alert.severity === "warning"
                        ? "text-yellow-500"
                        : "text-blue-500"
                    }`}
                  />
                  <div className="space-y-1">
                    <p className="text-sm font-medium">{alert.title}</p>
                    <p className="text-xs text-muted-foreground">{alert.message}</p>
                    {alert.action_label && alert.action_url && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="mt-2 h-7 text-xs"
                        onClick={() => {
                          if (alert.action_url!.startsWith("/api/")) {
                            apiClient.post(alert.action_url!).then(() => {
                              toast.success("Action completed");
                              loadAlerts();
                              loadPayments();
                            });
                          } else {
                            navigate(alert.action_url!);
                          }
                        }}
                      >
                        {alert.action_label}
                      </Button>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => handleResolveAlert(alert.id)}
                  disabled={resolvingAlertId === alert.id}
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors shrink-0"
                >
                  {resolvingAlertId === alert.id ? "..." : "Dismiss"}
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Payment History */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Payment History
        </h2>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Customer</TableHead>
                <TableHead className="text-right">Amount</TableHead>
                <TableHead>Method</TableHead>
                <TableHead>Reference #</TableHead>
                <TableHead>Applied To</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                    Loading...
                  </TableCell>
                </TableRow>
              ) : payments.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                    No payments found
                  </TableCell>
                </TableRow>
              ) : (
                payments.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="text-muted-foreground">
                      {fmtDate(p.payment_date)}
                    </TableCell>
                    <TableCell className="font-medium">
                      {p.customer_name ?? "\u2014"}
                    </TableCell>
                    <TableCell className="text-right font-medium">
                      {fmtCurrency(p.total_amount)}
                    </TableCell>
                    <TableCell>{methodBadge(p.payment_method)}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {p.reference_number ?? "\u2014"}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-xs">
                      {appliedTo(p)}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-xs h-7"
                          onClick={() => navigate(`/ar/payments/${p.id}`)}
                        >
                          <FileText className="w-3 h-3 mr-1" />
                          View
                        </Button>
                        {canRecordPayment && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-muted-foreground hover:text-destructive text-xs h-7"
                            disabled={voidingId === p.id}
                            onClick={() => handleVoidPayment(p.id)}
                          >
                            {voidingId === p.id ? "Voiding..." : "Void"}
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
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

      {/* Check Scanner */}
      {showCheckScanner && (
        <CheckScanner
          onComplete={handleCheckScanComplete}
          onClose={() => setShowCheckScanner(false)}
        />
      )}

      {/* Manual entry / customer picker */}
      {showManualEntry && (
        <CustomerPaymentEntryFlow
          onClose={() => setShowManualEntry(false)}
          onSuccess={loadPayments}
        />
      )}
    </div>
  );
}
