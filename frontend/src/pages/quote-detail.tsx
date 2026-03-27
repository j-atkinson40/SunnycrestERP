import { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { salesService } from "@/services/sales-service";
import { customerService } from "@/services/customer-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type { Quote, QuoteLineCreate } from "@/types/sales";
import type { CustomerListItem } from "@/types/customer";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
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

function fmtCurrency(n: string | number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(n));
}

function fmtDate(d: string | null) {
  if (!d) return "\u2014";
  return new Date(d).toLocaleDateString();
}

function quoteStatusBadge(status: string) {
  switch (status) {
    case "draft":
      return <Badge variant="outline">Draft</Badge>;
    case "sent":
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
          Sent
        </Badge>
      );
    case "accepted":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Accepted
        </Badge>
      );
    case "rejected":
      return <Badge variant="destructive">Rejected</Badge>;
    case "expired":
      return (
        <Badge variant="outline" className="text-muted-foreground">
          Expired
        </Badge>
      );
    case "converted":
      return (
        <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
          Converted
        </Badge>
      );
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

// ── New Quote Form ──────────────────────────────────────────────────────────

interface NewLineRow {
  key: number;
  description: string;
  quantity: string;
  unit_price: string;
}

function NewQuoteForm() {
  const navigate = useNavigate();
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [customerId, setCustomerId] = useState("");
  const [quoteDate, setQuoteDate] = useState(new Date().toISOString().split("T")[0]);
  const [expiryDate, setExpiryDate] = useState("");
  const [paymentTerms, setPaymentTerms] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<NewLineRow[]>([
    { key: 1, description: "", quantity: "1", unit_price: "" },
  ]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    customerService.getCustomers(1, 200).then((d) => setCustomers(d.items)).catch(() => {});
  }, []);

  function addLine() {
    setLines([...lines, { key: Date.now(), description: "", quantity: "1", unit_price: "" }]);
  }

  function removeLine(key: number) {
    if (lines.length <= 1) return;
    setLines(lines.filter((l) => l.key !== key));
  }

  function updateLine(key: number, field: keyof Omit<NewLineRow, "key">, value: string) {
    setLines(lines.map((l) => (l.key === key ? { ...l, [field]: value } : l)));
  }

  async function handleSave() {
    setError("");
    if (!customerId) { setError("Select a customer"); return; }
    if (!expiryDate) { setError("Expiry date is required"); return; }
    const validLines: QuoteLineCreate[] = lines
      .filter((l) => l.description.trim() && l.unit_price)
      .map((l, i) => ({
        description: l.description.trim(),
        quantity: l.quantity || "1",
        unit_price: l.unit_price,
        sort_order: i,
      }));
    if (validLines.length === 0) { setError("Add at least one line item"); return; }
    setSaving(true);
    try {
      const quote = await salesService.createQuote({
        customer_id: customerId,
        quote_date: quoteDate,
        expiry_date: expiryDate,
        payment_terms: paymentTerms || undefined,
        notes: notes || undefined,
        lines: validLines,
      });
      navigate(`/ar/quotes/${quote.id}`);
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to create quote"));
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link to="/ar/quotes" className="text-sm text-muted-foreground hover:underline">
            &larr; Quotes
          </Link>
          <h1 className="text-3xl font-bold mt-1">New Quote</h1>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate("/ar/quotes")}>Cancel</Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save Quote"}
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label>Customer *</Label>
          <select
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
          >
            <option value="">Select customer</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
        <div className="space-y-2">
          <Label>Payment Terms</Label>
          <Input value={paymentTerms} onChange={(e) => setPaymentTerms(e.target.value)} placeholder="e.g. Net 30" />
        </div>
        <div className="space-y-2">
          <Label>Quote Date *</Label>
          <Input type="date" value={quoteDate} onChange={(e) => setQuoteDate(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label>Expiry Date *</Label>
          <Input type="date" value={expiryDate} onChange={(e) => setExpiryDate(e.target.value)} />
        </div>
      </div>

      <Card className="p-6">
        <h2 className="text-lg font-semibold mb-4">Line Items</h2>
        <div className="space-y-2">
          <div className="grid grid-cols-[1fr_80px_100px_32px] gap-2 text-xs font-medium text-muted-foreground px-1">
            <span>Description</span><span>Qty</span><span>Unit Price</span><span />
          </div>
          {lines.map((line) => (
            <div key={line.key} className="grid grid-cols-[1fr_80px_100px_32px] gap-2 items-center">
              <Input
                placeholder="Description"
                value={line.description}
                onChange={(e) => updateLine(line.key, "description", e.target.value)}
              />
              <Input
                type="number"
                min="0"
                placeholder="1"
                value={line.quantity}
                onChange={(e) => updateLine(line.key, "quantity", e.target.value)}
              />
              <Input
                type="number"
                min="0"
                step="0.01"
                placeholder="0.00"
                value={line.unit_price}
                onChange={(e) => updateLine(line.key, "unit_price", e.target.value)}
              />
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
                onClick={() => removeLine(line.key)}
                disabled={lines.length <= 1}
              >
                ×
              </Button>
            </div>
          ))}
        </div>
        <Button variant="outline" size="sm" className="mt-3" onClick={addLine}>
          + Add Line
        </Button>
      </Card>

      <div className="space-y-2">
        <Label>Notes</Label>
        <textarea
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Optional notes for this quote"
          rows={3}
        />
      </div>
    </div>
  );
}

// ── Detail View ─────────────────────────────────────────────────────────────

export default function QuoteDetailPage() {
  const { id } = useParams<{ id: string }>();
  if (id === "new") return <NewQuoteForm />;

  const navigate = useNavigate();
  const { hasPermission } = useAuth();

  const canConvert = hasPermission("ar.create_order");

  const [quote, setQuote] = useState<Quote | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [converting, setConverting] = useState(false);
  const [updatingStatus, setUpdatingStatus] = useState(false);

  const loadQuote = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const data = await salesService.getQuote(id);
      setQuote(data);
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to load quote"));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadQuote();
  }, [loadQuote]);

  async function handleConvert() {
    if (!id) return;
    if (!window.confirm("Convert this quote to a sales order?")) return;
    setConverting(true);
    try {
      const newOrder = await salesService.convertQuote(id);
      toast.success(`Quote converted — Order ${newOrder.number} created`);
      navigate(`/ar/orders/${newOrder.id}`);
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to convert quote"));
    } finally {
      setConverting(false);
    }
  }

  async function handleStatusUpdate(newStatus: string) {
    if (!id) return;
    setUpdatingStatus(true);
    try {
      const updated = await salesService.updateQuote(id, { status: newStatus });
      setQuote(updated);
      toast.success(`Quote marked as ${newStatus}`);
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to update status"));
    } finally {
      setUpdatingStatus(false);
    }
  }

  if (loading) return <div className="p-8 text-center">Loading...</div>;
  if (error)
    return <div className="p-8 text-center text-destructive">{error}</div>;
  if (!quote) return null;

  const convertibleStatuses = ["draft", "sent", "accepted"];
  const canConvertNow = convertibleStatuses.includes(quote.status) && canConvert;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Link
            to="/ar/quotes"
            className="text-sm text-muted-foreground hover:underline"
          >
            &larr; Quotes
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold">{quote.number}</h1>
            {quoteStatusBadge(quote.status)}
          </div>
          <p className="text-muted-foreground">
            Customer: {quote.customer_name || "\u2014"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {quote.status === "draft" && (
            <Button
              variant="outline"
              disabled={updatingStatus}
              onClick={() => handleStatusUpdate("sent")}
            >
              Mark as Sent
            </Button>
          )}
          {quote.status === "sent" && (
            <>
              <Button
                variant="outline"
                disabled={updatingStatus}
                onClick={() => handleStatusUpdate("accepted")}
              >
                Mark Accepted
              </Button>
              <Button
                variant="outline"
                disabled={updatingStatus}
                onClick={() => handleStatusUpdate("rejected")}
                className="text-destructive"
              >
                Mark Rejected
              </Button>
            </>
          )}
          {canConvertNow && (
            <Button onClick={handleConvert} disabled={converting}>
              {converting ? "Converting..." : "Convert to Order"}
            </Button>
          )}
        </div>
      </div>

      {/* Quote Info */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Customer</p>
          <p className="font-medium">{quote.customer_name || "\u2014"}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Quote Date</p>
          <p className="font-medium">{fmtDate(quote.quote_date)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Expiry Date</p>
          <p className="font-medium">{fmtDate(quote.expiry_date)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Payment Terms</p>
          <p className="font-medium">{quote.payment_terms || "\u2014"}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Status</p>
          <div className="mt-1">{quoteStatusBadge(quote.status)}</div>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Created By</p>
          <p className="font-medium">{quote.created_by_name || "\u2014"}</p>
        </Card>
      </div>

      {/* Line Items */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold mb-4">Line Items</h2>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[35%]">Description</TableHead>
                <TableHead>Product</TableHead>
                <TableHead>Qty</TableHead>
                <TableHead>Unit Price</TableHead>
                <TableHead className="text-right">Line Total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {quote.lines.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="text-center text-muted-foreground"
                  >
                    No line items
                  </TableCell>
                </TableRow>
              ) : (
                quote.lines.map((line) => (
                  <TableRow key={line.id}>
                    <TableCell>{line.description}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {line.product_name || "\u2014"}
                    </TableCell>
                    <TableCell>{line.quantity}</TableCell>
                    <TableCell>{fmtCurrency(line.unit_price)}</TableCell>
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
            <p className="text-sm text-muted-foreground">
              Subtotal:{" "}
              <span className="font-medium text-foreground">
                {fmtCurrency(quote.subtotal)}
              </span>
            </p>
            <p className="text-sm text-muted-foreground">
              Tax Rate:{" "}
              <span className="font-medium text-foreground">
                {Number(quote.tax_rate)}%
              </span>
            </p>
            <p className="text-sm text-muted-foreground">
              Tax Amount:{" "}
              <span className="font-medium text-foreground">
                {fmtCurrency(quote.tax_amount)}
              </span>
            </p>
            <p className="text-lg font-bold">Total: {fmtCurrency(quote.total)}</p>
          </div>
        </div>
      </Card>

      {/* Notes */}
      {quote.notes && (
        <Card className="p-4">
          <p className="text-sm text-muted-foreground mb-1">Notes</p>
          <p className="text-sm whitespace-pre-wrap">{quote.notes}</p>
        </Card>
      )}

      {/* Metadata */}
      <div className="text-xs text-muted-foreground space-y-0.5">
        {quote.created_by_name && <p>Created by: {quote.created_by_name}</p>}
        <p>Created: {new Date(quote.created_at).toLocaleString()}</p>
        {quote.modified_at && (
          <p>Last modified: {new Date(quote.modified_at).toLocaleString()}</p>
        )}
      </div>
    </div>
  );
}
