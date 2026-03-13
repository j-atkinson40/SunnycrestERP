import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { vendorPaymentService } from "@/services/vendor-payment-service";
import { vendorBillService } from "@/services/vendor-bill-service";
import { vendorService } from "@/services/vendor-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type {
  VendorPaymentListItem,
  PaymentApplicationCreate,
} from "@/types/vendor-payment";
import type { VendorBillListItem } from "@/types/vendor-bill";
import type { VendorListItem } from "@/types/vendor";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
    case "wire":
      return (
        <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
          Wire
        </Badge>
      );
    case "credit_card":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Credit Card
        </Badge>
      );
    case "cash":
      return <Badge variant="secondary">Cash</Badge>;
    default:
      return <Badge variant="outline">{method}</Badge>;
  }
}

// ---- New Payment form ----

interface BillAppRow {
  bill_id: string;
  bill_number: string;
  balance: number;
  amount_applied: string;
}

function NewPaymentForm({ onCreated }: { onCreated: () => void }) {
  const [vendors, setVendors] = useState<VendorListItem[]>([]);
  const [vendorId, setVendorId] = useState("");
  const [paymentDate, setPaymentDate] = useState(
    new Date().toISOString().split("T")[0],
  );
  const [paymentMethod, setPaymentMethod] = useState("check");
  const [referenceNumber, setReferenceNumber] = useState("");
  const [notes, setNotes] = useState("");
  const [openBills, setOpenBills] = useState<VendorBillListItem[]>([]);
  const [billApps, setBillApps] = useState<BillAppRow[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    vendorService
      .getVendors(1, 200)
      .then((d) => setVendors(d.items))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (vendorId) {
      vendorBillService
        .getAll(1, 100, undefined, undefined, vendorId)
        .then((d) => {
          const open = d.items.filter(
            (b) =>
              ["approved", "partial", "pending"].includes(b.status) &&
              b.balance_remaining > 0,
          );
          setOpenBills(open);
          setBillApps(
            open.map((b) => ({
              bill_id: b.id,
              bill_number: b.number,
              balance: b.balance_remaining,
              amount_applied: "",
            })),
          );
        })
        .catch(() => {});
    } else {
      setOpenBills([]);
      setBillApps([]);
    }
  }, [vendorId]);

  const totalApplied = billApps.reduce(
    (s, a) => s + (parseFloat(a.amount_applied) || 0),
    0,
  );

  function updateApp(billId: string, value: string) {
    setBillApps(
      billApps.map((a) =>
        a.bill_id === billId ? { ...a, amount_applied: value } : a,
      ),
    );
  }

  async function handleSave() {
    setError("");
    if (!vendorId) {
      setError("Select a vendor");
      return;
    }
    const applications: PaymentApplicationCreate[] = billApps
      .filter((a) => parseFloat(a.amount_applied) > 0)
      .map((a) => ({
        bill_id: a.bill_id,
        amount_applied: parseFloat(a.amount_applied),
      }));
    if (applications.length === 0) {
      setError("Apply payment to at least one bill");
      return;
    }
    setSaving(true);
    try {
      await vendorPaymentService.create({
        vendor_id: vendorId,
        payment_date: paymentDate,
        total_amount: totalApplied,
        payment_method: paymentMethod,
        reference_number: referenceNumber || undefined,
        notes: notes || undefined,
        applications,
      });
      toast.success("Payment recorded");
      setShowForm(false);
      setVendorId("");
      setReferenceNumber("");
      setNotes("");
      setBillApps([]);
      onCreated();
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to record payment"));
    } finally {
      setSaving(false);
    }
  }

  if (!showForm) {
    return (
      <Button onClick={() => setShowForm(true)}>Record Payment</Button>
    );
  }

  return (
    <Card className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Record Payment</h2>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowForm(false)}
        >
          Cancel
        </Button>
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="space-y-2">
          <Label>Vendor</Label>
          <select
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            value={vendorId}
            onChange={(e) => setVendorId(e.target.value)}
          >
            <option value="">Select vendor...</option>
            {vendors.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-2">
          <Label>Payment Date</Label>
          <Input
            type="date"
            value={paymentDate}
            onChange={(e) => setPaymentDate(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label>Payment Method</Label>
          <select
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            value={paymentMethod}
            onChange={(e) => setPaymentMethod(e.target.value)}
          >
            <option value="check">Check</option>
            <option value="ach">ACH</option>
            <option value="wire">Wire Transfer</option>
            <option value="credit_card">Credit Card</option>
            <option value="cash">Cash</option>
          </select>
        </div>
        <div className="space-y-2">
          <Label>Reference / Check #</Label>
          <Input
            value={referenceNumber}
            onChange={(e) => setReferenceNumber(e.target.value)}
            placeholder="Check #, transaction ID, etc."
          />
        </div>
        <div className="space-y-2 md:col-span-2">
          <Label>Notes</Label>
          <Input
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Optional notes"
          />
        </div>
      </div>

      {/* Bill applications */}
      {vendorId && (
        <>
          <h3 className="text-sm font-medium mt-4">Apply to Bills</h3>
          {openBills.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No open bills for this vendor.
            </p>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Bill #</TableHead>
                    <TableHead>Due Date</TableHead>
                    <TableHead className="text-right">Balance</TableHead>
                    <TableHead>Apply Amount</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {billApps.map((app) => {
                    const bill = openBills.find((b) => b.id === app.bill_id);
                    return (
                      <TableRow key={app.bill_id}>
                        <TableCell className="font-medium">
                          {app.bill_number}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {bill ? fmtDate(bill.due_date) : "\u2014"}
                        </TableCell>
                        <TableCell className="text-right">
                          {fmtCurrency(app.balance)}
                        </TableCell>
                        <TableCell>
                          <Input
                            type="number"
                            step="0.01"
                            min="0"
                            max={app.balance}
                            value={app.amount_applied}
                            onChange={(e) =>
                              updateApp(app.bill_id, e.target.value)
                            }
                            placeholder="0.00"
                            className="w-32"
                          />
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
          <div className="flex items-center justify-between">
            <p className="text-lg font-bold">
              Total: {fmtCurrency(totalApplied)}
            </p>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? "Saving..." : "Save Payment"}
            </Button>
          </div>
        </>
      )}
    </Card>
  );
}

// ---- Main page ----

export default function VendorPaymentsPage() {
  const { hasPermission } = useAuth();
  const canRecord = hasPermission("ap.record_payment");

  const [payments, setPayments] = useState<VendorPaymentListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const loadPayments = useCallback(async () => {
    setLoading(true);
    try {
      const data = await vendorPaymentService.getAll(page, 20);
      setPayments(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    loadPayments();
  }, [loadPayments]);

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Vendor Payments</h1>
          <p className="text-muted-foreground">{total} total payments</p>
        </div>
        {canRecord && <NewPaymentForm onCreated={loadPayments} />}
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Vendor</TableHead>
              <TableHead>Method</TableHead>
              <TableHead>Reference</TableHead>
              <TableHead className="text-right">Amount</TableHead>
              <TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : payments.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center">
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
                    {p.vendor_name || "\u2014"}
                  </TableCell>
                  <TableCell>{methodBadge(p.payment_method)}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {p.reference_number || "\u2014"}
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    {fmtCurrency(p.total_amount)}
                  </TableCell>
                  <TableCell>
                    <Link
                      to={`/ap/payments/${p.id}`}
                      className="text-sm hover:underline"
                    >
                      View
                    </Link>
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
