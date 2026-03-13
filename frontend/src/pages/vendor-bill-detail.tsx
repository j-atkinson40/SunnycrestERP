import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { vendorBillService } from "@/services/vendor-bill-service";
import { vendorService } from "@/services/vendor-service";
import { purchaseOrderService } from "@/services/purchase-order-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type { VendorBill, BillLineCreate } from "@/types/vendor-bill";
import type { VendorListItem } from "@/types/vendor";
import type { PurchaseOrderListItem } from "@/types/purchase-order";
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

function billStatusBadge(status: string) {
  switch (status) {
    case "draft":
      return <Badge variant="outline">Draft</Badge>;
    case "pending":
      return (
        <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
          Pending
        </Badge>
      );
    case "approved":
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
          Approved
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
    case "void":
      return <Badge variant="destructive">Void</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

// ---- New Bill form ----
interface NewLineRow {
  key: number;
  description: string;
  quantity: string;
  unit_cost: string;
  amount: string;
  expense_category: string;
}

function NewBillForm() {
  const navigate = useNavigate();
  const [vendors, setVendors] = useState<VendorListItem[]>([]);
  const [purchaseOrders, setPurchaseOrders] = useState<PurchaseOrderListItem[]>(
    [],
  );
  const [vendorId, setVendorId] = useState("");
  const [poId, setPoId] = useState("");
  const [vendorInvoiceNumber, setVendorInvoiceNumber] = useState("");
  const [billDate, setBillDate] = useState(
    new Date().toISOString().split("T")[0],
  );
  const [dueDate, setDueDate] = useState("");
  const [taxAmount, setTaxAmount] = useState("0");
  const [paymentTerms, setPaymentTerms] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<NewLineRow[]>([
    {
      key: 1,
      description: "",
      quantity: "",
      unit_cost: "",
      amount: "",
      expense_category: "",
    },
  ]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    vendorService
      .getVendors(1, 200)
      .then((d) => setVendors(d.items))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (vendorId) {
      purchaseOrderService
        .getAll(1, 100, undefined, undefined, vendorId)
        .then((d) => setPurchaseOrders(d.items))
        .catch(() => {});
    } else {
      setPurchaseOrders([]);
      setPoId("");
    }
  }, [vendorId]);

  function addLine() {
    setLines([
      ...lines,
      {
        key: Date.now(),
        description: "",
        quantity: "",
        unit_cost: "",
        amount: "",
        expense_category: "",
      },
    ]);
  }

  function removeLine(key: number) {
    if (lines.length <= 1) return;
    setLines(lines.filter((l) => l.key !== key));
  }

  function updateLine(key: number, field: string, value: string) {
    setLines(lines.map((l) => (l.key === key ? { ...l, [field]: value } : l)));
  }

  const subtotal = lines.reduce(
    (s, l) => s + (parseFloat(l.amount) || 0),
    0,
  );
  const tax = parseFloat(taxAmount) || 0;
  const total = subtotal + tax;

  async function handleSave() {
    setError("");
    if (!vendorId) {
      setError("Select a vendor");
      return;
    }

    setSaving(true);
    try {
      const billLines: BillLineCreate[] = lines
        .filter((l) => l.description.trim() && l.amount)
        .map((l, i) => ({
          description: l.description.trim(),
          quantity: l.quantity ? parseFloat(l.quantity) : undefined,
          unit_cost: l.unit_cost ? parseFloat(l.unit_cost) : undefined,
          amount: parseFloat(l.amount),
          expense_category: l.expense_category || undefined,
          sort_order: i,
        }));

      const bill = await vendorBillService.create({
        vendor_id: vendorId,
        po_id: poId || undefined,
        vendor_invoice_number: vendorInvoiceNumber || undefined,
        bill_date: billDate,
        due_date: dueDate || undefined,
        tax_amount: tax,
        payment_terms: paymentTerms || undefined,
        notes: notes || undefined,
        lines: billLines.length > 0 ? billLines : undefined,
      });
      toast.success(`Bill ${bill.number} created`);
      navigate(`/ap/bills/${bill.id}`);
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to create bill"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link
            to="/ap/bills"
            className="text-sm text-muted-foreground hover:underline"
          >
            &larr; Vendor Bills
          </Link>
          <h1 className="text-3xl font-bold">New Vendor Bill</h1>
        </div>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : "Create Bill"}
        </Button>
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <Card className="p-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
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
            <Label>Purchase Order (optional)</Label>
            <select
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
              value={poId}
              onChange={(e) => setPoId(e.target.value)}
              disabled={!vendorId}
            >
              <option value="">None — enter lines manually</option>
              {purchaseOrders.map((po) => (
                <option key={po.id} value={po.id}>
                  {po.number} — {fmtCurrency(po.total)}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label>Vendor Invoice #</Label>
            <Input
              value={vendorInvoiceNumber}
              onChange={(e) => setVendorInvoiceNumber(e.target.value)}
              placeholder="Vendor's invoice number"
            />
          </div>
          <div className="space-y-2">
            <Label>Bill Date</Label>
            <Input
              type="date"
              value={billDate}
              onChange={(e) => setBillDate(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label>Due Date</Label>
            <Input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              placeholder="Auto-calculated from payment terms"
            />
          </div>
          <div className="space-y-2">
            <Label>Payment Terms</Label>
            <Input
              value={paymentTerms}
              onChange={(e) => setPaymentTerms(e.target.value)}
              placeholder="e.g. Net 30"
            />
          </div>
          <div className="space-y-2">
            <Label>Tax Amount</Label>
            <Input
              type="number"
              step="0.01"
              min="0"
              value={taxAmount}
              onChange={(e) => setTaxAmount(e.target.value)}
            />
          </div>
          <div className="space-y-2 md:col-span-2">
            <Label>Notes</Label>
            <textarea
              className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm min-h-[60px]"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Internal notes"
            />
          </div>
        </div>
      </Card>

      {/* Line items — only show when no PO selected (PO auto-populates lines) */}
      {!poId && (
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Line Items</h2>
            <Button variant="outline" size="sm" onClick={addLine}>
              Add Line
            </Button>
          </div>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[35%]">Description</TableHead>
                  <TableHead>Qty</TableHead>
                  <TableHead>Unit Cost</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead className="w-10"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {lines.map((l) => (
                  <TableRow key={l.key}>
                    <TableCell>
                      <Input
                        value={l.description}
                        onChange={(e) =>
                          updateLine(l.key, "description", e.target.value)
                        }
                        placeholder="Description"
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        step="0.001"
                        min="0"
                        value={l.quantity}
                        onChange={(e) =>
                          updateLine(l.key, "quantity", e.target.value)
                        }
                        className="w-24"
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        step="0.01"
                        min="0"
                        value={l.unit_cost}
                        onChange={(e) =>
                          updateLine(l.key, "unit_cost", e.target.value)
                        }
                        className="w-28"
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        step="0.01"
                        min="0"
                        value={l.amount}
                        onChange={(e) =>
                          updateLine(l.key, "amount", e.target.value)
                        }
                        className="w-28"
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        value={l.expense_category}
                        onChange={(e) =>
                          updateLine(l.key, "expense_category", e.target.value)
                        }
                        placeholder="Category"
                        className="w-28"
                      />
                    </TableCell>
                    <TableCell>
                      {lines.length > 1 && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeLine(l.key)}
                          className="text-destructive"
                        >
                          &times;
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="flex justify-end mt-4 space-y-1 text-right">
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">
                Subtotal: {fmtCurrency(subtotal)}
              </p>
              <p className="text-sm text-muted-foreground">
                Tax: {fmtCurrency(tax)}
              </p>
              <p className="text-lg font-bold">Total: {fmtCurrency(total)}</p>
            </div>
          </div>
        </Card>
      )}

      {poId && (
        <Card className="p-6">
          <p className="text-sm text-muted-foreground">
            Lines will be auto-populated from the selected purchase order.
          </p>
        </Card>
      )}
    </div>
  );
}

// ---- Bill Detail view ----

function VendorBillDetailView({ id }: { id: string }) {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const canApprove = hasPermission("ap.approve_bill");
  const canVoid = hasPermission("ap.void");
  const canCreate = hasPermission("ap.create_bill");

  const [bill, setBill] = useState<VendorBill | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadBill = useCallback(async () => {
    setLoading(true);
    try {
      const data = await vendorBillService.get(id);
      setBill(data);
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to load bill"));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadBill();
  }, [loadBill]);

  async function handleApprove() {
    try {
      await vendorBillService.approve(id);
      toast.success("Bill approved");
      loadBill();
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to approve bill"));
    }
  }

  async function handleVoid() {
    if (!window.confirm("Void this bill? This cannot be undone.")) return;
    try {
      await vendorBillService.void(id);
      toast.success("Bill voided");
      loadBill();
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to void bill"));
    }
  }

  async function handleDelete() {
    if (!window.confirm("Delete this draft bill?")) return;
    try {
      await vendorBillService.delete(id);
      toast.success("Bill deleted");
      navigate("/ap/bills");
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to delete bill"));
    }
  }

  if (loading) return <div className="p-8 text-center">Loading...</div>;
  if (error)
    return (
      <div className="p-8 text-center text-destructive">{error}</div>
    );
  if (!bill) return null;

  const isOverdue =
    !["paid", "void"].includes(bill.status) &&
    new Date(bill.due_date) < new Date();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Link
            to="/ap/bills"
            className="text-sm text-muted-foreground hover:underline"
          >
            &larr; Vendor Bills
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold">{bill.number}</h1>
            {billStatusBadge(bill.status)}
            {isOverdue && (
              <Badge variant="destructive">Overdue</Badge>
            )}
          </div>
          <p className="text-muted-foreground">
            Vendor: {bill.vendor_name || "\u2014"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {["draft", "pending"].includes(bill.status) && canApprove && (
            <Button onClick={handleApprove}>Approve</Button>
          )}
          {["draft", "pending"].includes(bill.status) && canCreate && (
            <Button
              variant="destructive"
              size="sm"
              onClick={handleDelete}
            >
              Delete
            </Button>
          )}
          {!["void", "paid"].includes(bill.status) &&
            canVoid &&
            bill.amount_paid === 0 && (
              <Button variant="destructive" size="sm" onClick={handleVoid}>
                Void
              </Button>
            )}
        </div>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Bill Date</p>
          <p className="font-medium">
            {new Date(bill.bill_date).toLocaleDateString()}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Due Date</p>
          <p className={`font-medium ${isOverdue ? "text-red-600" : ""}`}>
            {new Date(bill.due_date).toLocaleDateString()}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Total</p>
          <p className="text-xl font-bold">{fmtCurrency(bill.total)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Balance Remaining</p>
          <p
            className={`text-xl font-bold ${bill.balance_remaining > 0 ? "text-orange-600" : "text-green-600"}`}
          >
            {fmtCurrency(bill.balance_remaining)}
          </p>
        </Card>
      </div>

      {/* Additional details */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {bill.vendor_invoice_number && (
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Vendor Invoice #</p>
            <p className="font-medium">{bill.vendor_invoice_number}</p>
          </Card>
        )}
        {bill.po_number && (
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Purchase Order</p>
            <p className="font-medium">{bill.po_number}</p>
          </Card>
        )}
        {bill.payment_terms && (
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Payment Terms</p>
            <p className="font-medium">{bill.payment_terms}</p>
          </Card>
        )}
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Amount Paid</p>
          <p className="font-medium">{fmtCurrency(bill.amount_paid)}</p>
        </Card>
      </div>

      {bill.notes && (
        <Card className="p-4">
          <p className="text-sm text-muted-foreground mb-1">Notes</p>
          <p className="text-sm whitespace-pre-wrap">{bill.notes}</p>
        </Card>
      )}

      {/* Line items */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold mb-4">Line Items</h2>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[35%]">Description</TableHead>
                <TableHead>Qty</TableHead>
                <TableHead>Unit Cost</TableHead>
                <TableHead className="text-right">Amount</TableHead>
                <TableHead>Category</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {bill.lines.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground">
                    No line items
                  </TableCell>
                </TableRow>
              ) : (
                bill.lines.map((line) => (
                  <TableRow key={line.id}>
                    <TableCell>{line.description}</TableCell>
                    <TableCell>{line.quantity ?? "\u2014"}</TableCell>
                    <TableCell>
                      {line.unit_cost != null
                        ? fmtCurrency(line.unit_cost)
                        : "\u2014"}
                    </TableCell>
                    <TableCell className="text-right font-medium">
                      {fmtCurrency(line.amount)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {line.expense_category || "\u2014"}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
        <div className="flex justify-end mt-4 space-y-1 text-right">
          <div className="space-y-1">
            <p className="text-sm text-muted-foreground">
              Subtotal: {fmtCurrency(bill.subtotal)}
            </p>
            <p className="text-sm text-muted-foreground">
              Tax: {fmtCurrency(bill.tax_amount)}
            </p>
            <p className="text-lg font-bold">
              Total: {fmtCurrency(bill.total)}
            </p>
          </div>
        </div>
      </Card>

      {/* Metadata */}
      <div className="text-xs text-muted-foreground space-y-0.5">
        {bill.created_by_name && <p>Created by: {bill.created_by_name}</p>}
        <p>Created: {new Date(bill.created_at).toLocaleString()}</p>
        {bill.approved_by_name && (
          <p>
            Approved by: {bill.approved_by_name} on{" "}
            {bill.approved_at
              ? new Date(bill.approved_at).toLocaleString()
              : ""}
          </p>
        )}
      </div>
    </div>
  );
}

// ---- Router ----

export default function VendorBillDetailPage() {
  const { id } = useParams<{ id: string }>();
  if (id === "new") return <NewBillForm />;
  if (!id) return null;
  return <VendorBillDetailView id={id} />;
}
