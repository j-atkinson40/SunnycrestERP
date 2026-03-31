import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import apiClient from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, ChevronUp, Loader2, Wand2, X } from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface OpenInvoice {
  id: string;
  number: string;
  invoice_date: string;
  due_date: string;
  total: number;
  amount_paid: number;
  balance_remaining: number;
  status: string;
  discount_deadline?: string | null;
  discounted_total?: number | null;
}

interface InvoiceApplication {
  invoice_id: string;
  invoice_number: string;
  balance_remaining: number;
  due_date: string;
  discount_deadline?: string | null;
  discounted_total?: number | null;
  amount: string; // controlled input string
  selected: boolean;
}

export interface RecordPaymentDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (payment: { id: string; amount: number; method: string }) => void;
  customerId: string;
  customerName: string;
  defaultInvoiceId?: string;
  openInvoices?: OpenInvoice[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtCurrency(n: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(n);
}

function fmtDate(d: string | null | undefined) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString();
}

function todayIso() {
  return new Date().toISOString().split("T")[0];
}

const METHOD_LABELS: Record<string, { label: string; refLabel: string }> = {
  check: { label: "Check", refLabel: "Check #" },
  ach: { label: "ACH", refLabel: "ACH Reference" },
  wire: { label: "Wire Transfer", refLabel: "Wire Reference" },
  credit_card: { label: "Credit Card", refLabel: "Transaction ID" },
  cash: { label: "Cash", refLabel: "Receipt #" },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RecordPaymentDialog({
  open,
  onClose,
  onSuccess,
  customerId,
  customerName,
  defaultInvoiceId,
  openInvoices: openInvoicesProp,
}: RecordPaymentDialogProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  // --- Form state ---
  const [paymentDate, setPaymentDate] = useState(todayIso());
  const [method, setMethod] = useState("check");
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");
  const [earlyPayment, setEarlyPayment] = useState(false);

  // --- Invoice state ---
  const [invoices, setInvoices] = useState<InvoiceApplication[]>([]);
  const [loadingInvoices, setLoadingInvoices] = useState(false);
  const [showAllInvoices, setShowAllInvoices] = useState(false);

  // --- Submit state ---
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Load open invoices for customer
  const loadInvoices = useCallback(async () => {
    if (!customerId) return;
    setLoadingInvoices(true);
    try {
      const params = new URLSearchParams({
        customer_id: customerId,
        status: "sent,partial,overdue",
        per_page: "100",
      });
      const r = await apiClient.get(`/sales/invoices?${params.toString()}`);
      const items: OpenInvoice[] = (r.data.items ?? []).map((inv: {
        id: string;
        number: string;
        invoice_date: string;
        due_date: string;
        total: string | number;
        amount_paid: string | number;
        balance_remaining: string | number;
        status: string;
        discount_deadline?: string | null;
        discounted_total?: string | number | null;
      }) => ({
        id: inv.id,
        number: inv.number,
        invoice_date: inv.invoice_date,
        due_date: inv.due_date,
        total: Number(inv.total),
        amount_paid: Number(inv.amount_paid),
        balance_remaining: Number(inv.balance_remaining),
        status: inv.status,
        discount_deadline: inv.discount_deadline ?? null,
        discounted_total:
          inv.discounted_total != null ? Number(inv.discounted_total) : null,
      }));
      buildApplicationList(items);
    } catch {
      // silently handle — user will see empty list
    } finally {
      setLoadingInvoices(false);
    }
  }, [customerId]); // eslint-disable-line react-hooks/exhaustive-deps

  function buildApplicationList(items: OpenInvoice[]) {
    // Sort oldest-first (FIFO)
    const sorted = [...items].sort(
      (a, b) =>
        new Date(a.invoice_date).getTime() - new Date(b.invoice_date).getTime()
    );

    const apps: InvoiceApplication[] = sorted.map((inv) => ({
      invoice_id: inv.id,
      invoice_number: inv.number,
      balance_remaining: inv.balance_remaining,
      due_date: inv.due_date,
      discount_deadline: inv.discount_deadline,
      discounted_total: inv.discounted_total,
      amount: defaultInvoiceId === inv.id
        ? String(inv.balance_remaining.toFixed(2))
        : "",
      selected: defaultInvoiceId === inv.id,
    }));

    setInvoices(apps);
  }

  // Reset and load on open
  useEffect(() => {
    if (!open) return;
    setPaymentDate(todayIso());
    setMethod("check");
    setReference("");
    setNotes("");
    setEarlyPayment(false);
    setError("");
    setShowAllInvoices(false);

    if (openInvoicesProp) {
      buildApplicationList(openInvoicesProp);
      setLoadingInvoices(false);
    } else {
      loadInvoices();
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  // Close on Escape
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && open) onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  // --- Derived values ---
  const selectedInvoices = invoices.filter((inv) => inv.selected);
  const defaultInvoice = invoices.find((inv) => inv.invoice_id === defaultInvoiceId);
  const hasDiscountOption =
    defaultInvoice?.discount_deadline != null &&
    defaultInvoice.discounted_total != null &&
    new Date(defaultInvoice.discount_deadline) >= new Date(todayIso());

  const appliedTotal = selectedInvoices.reduce(
    (sum, inv) => sum + (parseFloat(inv.amount) || 0),
    0
  );

  const totalOutstanding = invoices.reduce(
    (sum, inv) => sum + inv.balance_remaining,
    0
  );

  // Auto-apply FIFO
  function handleAutoApply() {
    setInvoices((prev) => {
      // Use sorted (oldest first) order
      const sorted = [...prev].sort(
        (a, b) =>
          new Date(a.due_date).getTime() - new Date(b.due_date).getTime()
      );
      return prev.map((inv) => {
        const sortedInv = sorted.find((s) => s.invoice_id === inv.invoice_id);
        const index = sorted.indexOf(sortedInv!);
        // Assign full balance to each in order (all get pre-filled)
        return {
          ...inv,
          selected: true,
          amount: inv.balance_remaining.toFixed(2),
          _sortIndex: index,
        };
      });
    });
    setShowAllInvoices(true);
  }

  function toggleInvoice(invoiceId: string) {
    setInvoices((prev) =>
      prev.map((inv) =>
        inv.invoice_id === invoiceId
          ? {
              ...inv,
              selected: !inv.selected,
              amount: !inv.selected
                ? inv.balance_remaining.toFixed(2)
                : "",
            }
          : inv
      )
    );
  }

  function updateAmount(invoiceId: string, value: string) {
    setInvoices((prev) =>
      prev.map((inv) =>
        inv.invoice_id === invoiceId ? { ...inv, amount: value } : inv
      )
    );
  }

  // Handle early payment toggle
  function handleEarlyPaymentToggle(isEarly: boolean) {
    setEarlyPayment(isEarly);
    if (defaultInvoice && defaultInvoice.discounted_total != null) {
      setInvoices((prev) =>
        prev.map((inv) =>
          inv.invoice_id === defaultInvoiceId
            ? {
                ...inv,
                selected: true,
                amount: isEarly
                  ? String(defaultInvoice.discounted_total!.toFixed(2))
                  : String(defaultInvoice.balance_remaining.toFixed(2)),
              }
            : inv
        )
      );
    }
  }

  async function handleSubmit() {
    setError("");

    const apps = selectedInvoices
      .filter((inv) => parseFloat(inv.amount) > 0)
      .map((inv) => ({
        invoice_id: inv.invoice_id,
        amount_applied: String(parseFloat(inv.amount).toFixed(2)),
      }));

    if (apps.length === 0) {
      setError("Select at least one invoice and enter an amount.");
      return;
    }

    const totalApplied = apps.reduce(
      (sum, a) => sum + parseFloat(a.amount_applied),
      0
    );

    setSubmitting(true);
    try {
      const payload = {
        customer_id: customerId,
        payment_date: paymentDate,
        total_amount: String(totalApplied.toFixed(2)),
        payment_method: method,
        reference_number: reference.trim() || null,
        notes: notes.trim() || null,
        applications: apps,
      };
      const r = await apiClient.post("/sales/payments", payload);
      toast.success(`Payment of ${fmtCurrency(totalApplied)} recorded`);
      onSuccess({ id: r.data.id, amount: totalApplied, method });
      onClose();
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to record payment"));
    } finally {
      setSubmitting(false);
    }
  }

  const refLabel = METHOD_LABELS[method]?.refLabel ?? "Reference #";

  // Show default invoice first, then the rest when expanded
  const primaryInvoices = invoices.filter(
    (inv) => inv.invoice_id === defaultInvoiceId
  );
  const secondaryInvoices = invoices.filter(
    (inv) => inv.invoice_id !== defaultInvoiceId
  );

  return (
    <>
      {/* Backdrop */}
      <div
        ref={overlayRef}
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />

      {/* Slide-over panel */}
      <div className="fixed right-0 top-0 h-full w-full max-w-lg bg-background shadow-2xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b shrink-0">
          <div>
            <h2 className="text-lg font-semibold">Record Payment</h2>
            <p className="text-sm text-muted-foreground">{customerName}</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1.5 hover:bg-muted transition-colors"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-5">
          {/* Error */}
          {error && (
            <div className="rounded-md bg-destructive/10 border border-destructive/20 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          )}

          {/* Payment Date */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Payment Date</label>
            <input
              type="date"
              value={paymentDate}
              onChange={(e) => setPaymentDate(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          {/* Payment Method */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Payment Method</label>
            <select
              value={method}
              onChange={(e) => setMethod(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              {Object.entries(METHOD_LABELS).map(([key, { label }]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          {/* Reference Number */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium">{refLabel}</label>
            <input
              type="text"
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              placeholder={`e.g. ${method === "check" ? "12345" : method === "ach" ? "ACH-20240101" : "REF-001"}`}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          {/* Notes */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium">
              Notes{" "}
              <span className="text-muted-foreground font-normal">(optional)</span>
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Any notes about this payment..."
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none"
            />
          </div>

          {/* Divider */}
          <div className="border-t" />

          {/* Early Payment Discount Option */}
          {hasDiscountOption && defaultInvoice && (
            <div className="rounded-lg border border-green-200 bg-green-50 dark:bg-green-950/20 dark:border-green-800 p-4 space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-green-800 dark:text-green-300">
                  Early Payment Discount Available
                </span>
                <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 text-xs">
                  5% off
                </Badge>
              </div>
              <p className="text-xs text-green-700 dark:text-green-400">
                Pay by{" "}
                <span className="font-medium">
                  {fmtDate(defaultInvoice.discount_deadline)}
                </span>{" "}
                to save{" "}
                <span className="font-medium">
                  {fmtCurrency(
                    defaultInvoice.balance_remaining -
                      (defaultInvoice.discounted_total ?? 0)
                  )}
                </span>
              </p>
              <div className="space-y-2">
                <label className="flex items-center gap-2.5 cursor-pointer">
                  <input
                    type="radio"
                    name="paymentType"
                    checked={earlyPayment}
                    onChange={() => handleEarlyPaymentToggle(true)}
                    className="accent-green-600"
                  />
                  <span className="text-sm font-medium text-green-800 dark:text-green-300">
                    Early payment —{" "}
                    {fmtCurrency(defaultInvoice.discounted_total ?? 0)}
                  </span>
                </label>
                <label className="flex items-center gap-2.5 cursor-pointer">
                  <input
                    type="radio"
                    name="paymentType"
                    checked={!earlyPayment}
                    onChange={() => handleEarlyPaymentToggle(false)}
                  />
                  <span className="text-sm text-muted-foreground">
                    Full amount —{" "}
                    {fmtCurrency(defaultInvoice.balance_remaining)}
                  </span>
                </label>
              </div>
            </div>
          )}

          {/* Invoice Application Section */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Apply to Invoices</h3>
              {invoices.length > 1 && (
                <button
                  type="button"
                  onClick={handleAutoApply}
                  className="flex items-center gap-1.5 text-xs text-primary hover:underline"
                >
                  <Wand2 className="w-3.5 h-3.5" />
                  Auto-apply (oldest first)
                </button>
              )}
            </div>

            {loadingInvoices ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
              </div>
            ) : invoices.length === 0 ? (
              <p className="text-sm text-muted-foreground py-2">
                No open invoices found for this customer.
              </p>
            ) : (
              <div className="space-y-2">
                {/* Primary invoice (if defaultInvoiceId set) */}
                {primaryInvoices.map((inv) => (
                  <InvoiceRow
                    key={inv.invoice_id}
                    inv={inv}
                    onToggle={toggleInvoice}
                    onAmountChange={updateAmount}
                    isPrimary
                    earlyPayment={earlyPayment && hasDiscountOption}
                  />
                ))}

                {/* Other invoices */}
                {secondaryInvoices.length > 0 && (
                  <>
                    {defaultInvoiceId && (
                      <button
                        type="button"
                        onClick={() => setShowAllInvoices((v) => !v)}
                        className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors w-full py-1"
                      >
                        {showAllInvoices ? (
                          <ChevronUp className="w-3.5 h-3.5" />
                        ) : (
                          <ChevronDown className="w-3.5 h-3.5" />
                        )}
                        {showAllInvoices ? "Hide" : "Show"}{" "}
                        {secondaryInvoices.length} other open invoice
                        {secondaryInvoices.length !== 1 ? "s" : ""}
                      </button>
                    )}

                    {(showAllInvoices || !defaultInvoiceId) &&
                      secondaryInvoices.map((inv) => (
                        <InvoiceRow
                          key={inv.invoice_id}
                          inv={inv}
                          onToggle={toggleInvoice}
                          onAmountChange={updateAmount}
                          isPrimary={false}
                          earlyPayment={false}
                        />
                      ))}
                  </>
                )}
              </div>
            )}
          </div>

          {/* Running total */}
          {selectedInvoices.length > 0 && (
            <div className="rounded-md bg-muted/50 border px-4 py-3 space-y-1">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Applied</span>
                <span className="font-semibold">{fmtCurrency(appliedTotal)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">
                  Outstanding ({invoices.length} invoice
                  {invoices.length !== 1 ? "s" : ""})
                </span>
                <span className="text-muted-foreground">
                  {fmtCurrency(totalOutstanding)}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t shrink-0 flex items-center justify-between gap-3">
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={submitting || appliedTotal <= 0}
            className="min-w-[140px]"
          >
            {submitting ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>Record {appliedTotal > 0 ? fmtCurrency(appliedTotal) : "Payment"}</>
            )}
          </Button>
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// InvoiceRow sub-component
// ---------------------------------------------------------------------------

interface InvoiceRowProps {
  inv: InvoiceApplication;
  onToggle: (id: string) => void;
  onAmountChange: (id: string, value: string) => void;
  isPrimary: boolean;
  earlyPayment: boolean;
}

function InvoiceRow({
  inv,
  onToggle,
  onAmountChange,
  isPrimary,
  earlyPayment,
}: InvoiceRowProps) {
  const isOverdue =
    inv.status === "overdue" || new Date(inv.due_date) < new Date();
  const enteredAmt = parseFloat(inv.amount) || 0;
  const overApplied = enteredAmt > inv.balance_remaining + 0.005;

  return (
    <div
      className={`rounded-md border px-3 py-3 space-y-2 transition-colors ${
        inv.selected
          ? "border-primary/50 bg-primary/5"
          : "border-border bg-background"
      } ${isPrimary ? "ring-1 ring-primary/20" : ""}`}
    >
      <div className="flex items-start gap-2.5">
        <input
          type="checkbox"
          checked={inv.selected}
          onChange={() => onToggle(inv.invoice_id)}
          className="mt-0.5 accent-primary cursor-pointer"
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm">{inv.invoice_number}</span>
            {isOverdue && (
              <Badge variant="destructive" className="text-xs py-0 px-1.5">
                Overdue
              </Badge>
            )}
            {inv.discount_deadline && inv.discounted_total && (
              <Badge className="text-xs py-0 px-1.5 bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                Discount avail.
              </Badge>
            )}
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">
            Due {fmtDate(inv.due_date)} &middot; Balance{" "}
            {fmtCurrency(inv.balance_remaining)}
          </div>
        </div>
      </div>

      {inv.selected && (
        <div className="pl-5">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground w-16 shrink-0">
              Amount
            </span>
            <div className="relative flex-1">
              <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
                $
              </span>
              <input
                type="number"
                step="0.01"
                min="0"
                max={inv.balance_remaining}
                value={inv.amount}
                onChange={(e) => onAmountChange(inv.invoice_id, e.target.value)}
                disabled={earlyPayment && inv.discounted_total != null}
                className={`w-full rounded border pl-6 pr-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring ${
                  overApplied
                    ? "border-destructive focus:ring-destructive"
                    : "border-input"
                } disabled:opacity-60 disabled:cursor-not-allowed bg-background`}
              />
            </div>
            <button
              type="button"
              onClick={() =>
                onAmountChange(
                  inv.invoice_id,
                  inv.balance_remaining.toFixed(2)
                )
              }
              className="text-xs text-primary hover:underline whitespace-nowrap"
              disabled={earlyPayment && inv.discounted_total != null}
            >
              Full balance
            </button>
          </div>
          {overApplied && (
            <p className="text-xs text-destructive mt-1 pl-0">
              Amount exceeds balance of {fmtCurrency(inv.balance_remaining)}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
