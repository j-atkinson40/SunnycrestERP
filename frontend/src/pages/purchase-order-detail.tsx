import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { purchaseOrderService } from "@/services/purchase-order-service";
import { vendorService } from "@/services/vendor-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type {
  PurchaseOrder,
  POLineCreate,
  ReceiveLineItem,
} from "@/types/purchase-order";
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
        <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
          Partial
        </Badge>
      );
    case "received":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Received
        </Badge>
      );
    case "closed":
      return <Badge variant="secondary">Closed</Badge>;
    case "cancelled":
      return <Badge variant="destructive">Cancelled</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

// ---- New PO form ----
interface NewLineRow {
  key: number;
  description: string;
  quantity_ordered: string;
  unit_cost: string;
  product_id: string;
}

function NewPurchaseOrderForm() {
  const navigate = useNavigate();
  const [vendors, setVendors] = useState<VendorListItem[]>([]);
  const [vendorId, setVendorId] = useState("");
  const [orderDate, setOrderDate] = useState(
    new Date().toISOString().split("T")[0],
  );
  const [expectedDate, setExpectedDate] = useState("");
  const [shippingAddress, setShippingAddress] = useState("");
  const [taxAmount, setTaxAmount] = useState("0");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<NewLineRow[]>([
    { key: 1, description: "", quantity_ordered: "", unit_cost: "", product_id: "" },
  ]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    vendorService
      .getVendors(1, 200)
      .then((d) => setVendors(d.items))
      .catch(() => {});
  }, []);

  function addLine() {
    setLines([
      ...lines,
      {
        key: Date.now(),
        description: "",
        quantity_ordered: "",
        unit_cost: "",
        product_id: "",
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

  function lineTotal(l: NewLineRow) {
    const qty = parseFloat(l.quantity_ordered) || 0;
    const cost = parseFloat(l.unit_cost) || 0;
    return qty * cost;
  }

  const subtotal = lines.reduce((s, l) => s + lineTotal(l), 0);
  const tax = parseFloat(taxAmount) || 0;
  const total = subtotal + tax;

  async function handleSave() {
    setError("");
    if (!vendorId) {
      setError("Select a vendor");
      return;
    }
    const validLines = lines.filter(
      (l) => l.description.trim() && l.quantity_ordered && l.unit_cost,
    );
    if (validLines.length === 0) {
      setError("Add at least one line item");
      return;
    }
    setSaving(true);
    try {
      const poLines: POLineCreate[] = validLines.map((l, i) => ({
        description: l.description.trim(),
        quantity_ordered: parseFloat(l.quantity_ordered),
        unit_cost: parseFloat(l.unit_cost),
        product_id: l.product_id || undefined,
        sort_order: i,
      }));
      const po = await purchaseOrderService.create({
        vendor_id: vendorId,
        order_date: orderDate || undefined,
        expected_date: expectedDate || undefined,
        shipping_address: shippingAddress || undefined,
        tax_amount: tax,
        notes: notes || undefined,
        lines: poLines,
      });
      toast.success(`PO ${po.number} created`);
      navigate(`/ap/purchase-orders/${po.id}`);
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to create PO"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link
            to="/ap/purchase-orders"
            className="text-sm text-muted-foreground hover:underline"
          >
            &larr; Purchase Orders
          </Link>
          <h1 className="text-3xl font-bold">New Purchase Order</h1>
        </div>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : "Create PO"}
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
            <Label>Order Date</Label>
            <Input
              type="date"
              value={orderDate}
              onChange={(e) => setOrderDate(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label>Expected Delivery Date</Label>
            <Input
              type="date"
              value={expectedDate}
              onChange={(e) => setExpectedDate(e.target.value)}
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
            <Label>Shipping Address</Label>
            <Input
              value={shippingAddress}
              onChange={(e) => setShippingAddress(e.target.value)}
              placeholder="Optional shipping address"
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

      {/* Line items */}
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
                <TableHead className="w-[40%]">Description</TableHead>
                <TableHead>Qty</TableHead>
                <TableHead>Unit Cost</TableHead>
                <TableHead className="text-right">Total</TableHead>
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
                      value={l.quantity_ordered}
                      onChange={(e) =>
                        updateLine(l.key, "quantity_ordered", e.target.value)
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
                  <TableCell className="text-right font-medium">
                    {fmtCurrency(lineTotal(l))}
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
    </div>
  );
}

// ---- PO Detail view ----

function PurchaseOrderDetailView({ id }: { id: string }) {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const canReceive = hasPermission("ap.receive");
  const canEdit = hasPermission("ap.create_po");

  const [po, setPo] = useState<PurchaseOrder | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Receiving state
  const [receiveMode, setReceiveMode] = useState(false);
  const [receiveQtys, setReceiveQtys] = useState<Record<string, string>>({});
  const [receiving, setReceiving] = useState(false);

  const loadPo = useCallback(async () => {
    setLoading(true);
    try {
      const data = await purchaseOrderService.get(id);
      setPo(data);
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to load PO"));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadPo();
  }, [loadPo]);

  async function handleSend() {
    try {
      await purchaseOrderService.send(id);
      toast.success("PO marked as sent");
      loadPo();
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to send PO"));
    }
  }

  async function handleCancel() {
    if (!window.confirm("Cancel this purchase order?")) return;
    try {
      await purchaseOrderService.cancel(id);
      toast.success("PO cancelled");
      loadPo();
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to cancel PO"));
    }
  }

  async function handleDelete() {
    if (!window.confirm("Delete this draft PO?")) return;
    try {
      await purchaseOrderService.delete(id);
      toast.success("PO deleted");
      navigate("/ap/purchase-orders");
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to delete PO"));
    }
  }

  async function handleReceive() {
    const lines: ReceiveLineItem[] = [];
    for (const [lineId, qty] of Object.entries(receiveQtys)) {
      const n = parseFloat(qty);
      if (n > 0) {
        lines.push({ po_line_id: lineId, quantity_received: n });
      }
    }
    if (lines.length === 0) {
      toast.error("Enter quantities to receive");
      return;
    }
    setReceiving(true);
    try {
      await purchaseOrderService.receive(id, lines);
      toast.success("Receiving recorded");
      setReceiveMode(false);
      setReceiveQtys({});
      loadPo();
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to record receiving"));
    } finally {
      setReceiving(false);
    }
  }

  if (loading) return <div className="p-8 text-center">Loading...</div>;
  if (error)
    return (
      <div className="p-8 text-center text-destructive">{error}</div>
    );
  if (!po) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Link
            to="/ap/purchase-orders"
            className="text-sm text-muted-foreground hover:underline"
          >
            &larr; Purchase Orders
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold">{po.number}</h1>
            {statusBadge(po.status)}
          </div>
          <p className="text-muted-foreground">
            Vendor: {po.vendor_name || "\u2014"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {po.status === "draft" && canEdit && (
            <>
              <Button variant="outline" onClick={handleSend}>
                Mark as Sent
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleDelete}
              >
                Delete
              </Button>
            </>
          )}
          {(po.status === "sent" || po.status === "partial") && canReceive && (
            <>
              {!receiveMode ? (
                <Button onClick={() => setReceiveMode(true)}>
                  Record Receiving
                </Button>
              ) : (
                <>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setReceiveMode(false);
                      setReceiveQtys({});
                    }}
                  >
                    Cancel
                  </Button>
                  <Button onClick={handleReceive} disabled={receiving}>
                    {receiving ? "Saving..." : "Save Receiving"}
                  </Button>
                </>
              )}
            </>
          )}
          {!["cancelled", "closed"].includes(po.status) &&
            po.status !== "draft" &&
            canEdit && (
              <Button variant="destructive" size="sm" onClick={handleCancel}>
                Cancel PO
              </Button>
            )}
        </div>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Order Date</p>
          <p className="font-medium">
            {new Date(po.order_date).toLocaleDateString()}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Expected</p>
          <p className="font-medium">
            {po.expected_date
              ? new Date(po.expected_date).toLocaleDateString()
              : "\u2014"}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Subtotal</p>
          <p className="font-medium">{fmtCurrency(po.subtotal)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Total</p>
          <p className="text-xl font-bold">{fmtCurrency(po.total)}</p>
        </Card>
      </div>

      {po.shipping_address && (
        <Card className="p-4">
          <p className="text-sm text-muted-foreground mb-1">
            Shipping Address
          </p>
          <p className="text-sm">{po.shipping_address}</p>
        </Card>
      )}

      {po.notes && (
        <Card className="p-4">
          <p className="text-sm text-muted-foreground mb-1">Notes</p>
          <p className="text-sm whitespace-pre-wrap">{po.notes}</p>
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
                <TableHead>Ordered</TableHead>
                <TableHead>Received</TableHead>
                <TableHead>Unit Cost</TableHead>
                <TableHead className="text-right">Line Total</TableHead>
                {receiveMode && <TableHead>Receive Qty</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {po.lines.map((line) => {
                const remaining =
                  line.quantity_ordered - line.quantity_received;
                return (
                  <TableRow key={line.id}>
                    <TableCell>
                      <div>{line.description}</div>
                      {line.product_name && (
                        <div className="text-xs text-muted-foreground">
                          Product: {line.product_name}
                        </div>
                      )}
                    </TableCell>
                    <TableCell>{line.quantity_ordered}</TableCell>
                    <TableCell>
                      <span
                        className={
                          line.quantity_received >= line.quantity_ordered
                            ? "text-green-600 font-medium"
                            : ""
                        }
                      >
                        {line.quantity_received}
                      </span>
                      {line.quantity_received >= line.quantity_ordered && (
                        <span className="ml-1 text-green-600">&check;</span>
                      )}
                    </TableCell>
                    <TableCell>{fmtCurrency(line.unit_cost)}</TableCell>
                    <TableCell className="text-right font-medium">
                      {fmtCurrency(line.line_total)}
                    </TableCell>
                    {receiveMode && (
                      <TableCell>
                        {remaining > 0 ? (
                          <Input
                            type="number"
                            step="0.001"
                            min="0"
                            max={remaining}
                            value={receiveQtys[line.id] || ""}
                            onChange={(e) =>
                              setReceiveQtys({
                                ...receiveQtys,
                                [line.id]: e.target.value,
                              })
                            }
                            placeholder={`Max ${remaining}`}
                            className="w-28"
                          />
                        ) : (
                          <span className="text-sm text-green-600">
                            Fully received
                          </span>
                        )}
                      </TableCell>
                    )}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </Card>

      {/* Created by / metadata */}
      <div className="text-xs text-muted-foreground space-y-0.5">
        {po.created_by_name && <p>Created by: {po.created_by_name}</p>}
        <p>Created: {new Date(po.created_at).toLocaleString()}</p>
        {po.sent_at && (
          <p>Sent: {new Date(po.sent_at).toLocaleString()}</p>
        )}
      </div>
    </div>
  );
}

// ---- Router ----

export default function PurchaseOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  if (id === "new") return <NewPurchaseOrderForm />;
  if (!id) return null;
  return <PurchaseOrderDetailView id={id} />;
}
