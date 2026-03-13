import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { inventoryService } from "@/services/inventory-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type { InventoryItem, InventoryTransaction } from "@/types/inventory";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { toast } from "sonner";

export default function InventoryDetailPage() {
  const { productId } = useParams<{ productId: string }>();
  const { hasPermission } = useAuth();
  const canCreate = hasPermission("inventory.create");
  const canEdit = hasPermission("inventory.edit");

  // Inventory item state
  const [item, setItem] = useState<InventoryItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Settings form state
  const [reorderPoint, setReorderPoint] = useState("");
  const [reorderQuantity, setReorderQuantity] = useState("");
  const [location, setLocation] = useState("");
  const [saving, setSaving] = useState(false);

  // Receive dialog state
  const [receiveOpen, setReceiveOpen] = useState(false);
  const [receiveQty, setReceiveQty] = useState("");
  const [receiveRef, setReceiveRef] = useState("");
  const [receiveNotes, setReceiveNotes] = useState("");
  const [receiveError, setReceiveError] = useState("");

  // Adjust dialog state
  const [adjustOpen, setAdjustOpen] = useState(false);
  const [adjustQty, setAdjustQty] = useState("");
  const [adjustRef, setAdjustRef] = useState("");
  const [adjustNotes, setAdjustNotes] = useState("");
  const [adjustError, setAdjustError] = useState("");

  // Production dialog state
  const [productionOpen, setProductionOpen] = useState(false);
  const [prodQty, setProdQty] = useState("");
  const [prodRef, setProdRef] = useState("");
  const [prodNotes, setProdNotes] = useState("");
  const [prodError, setProdError] = useState("");

  // Write-off dialog state
  const [writeOffOpen, setWriteOffOpen] = useState(false);
  const [woQty, setWoQty] = useState("");
  const [woReason, setWoReason] = useState("");
  const [woRef, setWoRef] = useState("");
  const [woNotes, setWoNotes] = useState("");
  const [woError, setWoError] = useState("");

  // Transaction history
  const [transactions, setTransactions] = useState<InventoryTransaction[]>([]);
  const [txTotal, setTxTotal] = useState(0);
  const [txPage, setTxPage] = useState(1);

  const loadData = useCallback(async () => {
    if (!productId) return;
    try {
      setLoading(true);
      const [invItem, txData] = await Promise.all([
        inventoryService.getInventoryItem(productId),
        inventoryService.getTransactions(productId, txPage),
      ]);
      setItem(invItem);
      setReorderPoint(
        invItem.reorder_point !== null ? String(invItem.reorder_point) : "",
      );
      setReorderQuantity(
        invItem.reorder_quantity !== null
          ? String(invItem.reorder_quantity)
          : "",
      );
      setLocation(invItem.location || "");
      setTransactions(txData.items);
      setTxTotal(txData.total);
    } catch {
      setError("Failed to load inventory data");
    } finally {
      setLoading(false);
    }
  }, [productId, txPage]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleReceive() {
    if (!productId) return;
    setReceiveError("");
    try {
      await inventoryService.receiveStock(productId, {
        quantity: parseInt(receiveQty, 10),
        reference: receiveRef.trim() || undefined,
        notes: receiveNotes.trim() || undefined,
      });
      setReceiveOpen(false);
      setReceiveQty("");
      setReceiveRef("");
      setReceiveNotes("");
      toast.success("Stock received");
      loadData();
    } catch (err: unknown) {
      setReceiveError(getApiErrorMessage(err, "Failed to receive stock"));
    }
  }

  async function handleAdjust() {
    if (!productId) return;
    setAdjustError("");
    try {
      await inventoryService.adjustStock(productId, {
        new_quantity: parseInt(adjustQty, 10),
        reference: adjustRef.trim() || undefined,
        notes: adjustNotes.trim() || undefined,
      });
      setAdjustOpen(false);
      setAdjustQty("");
      setAdjustRef("");
      setAdjustNotes("");
      toast.success("Stock adjusted");
      loadData();
    } catch (err: unknown) {
      setAdjustError(getApiErrorMessage(err, "Failed to adjust stock"));
    }
  }

  async function handleProduction() {
    if (!productId) return;
    setProdError("");
    try {
      await inventoryService.recordProduction(productId, {
        quantity: parseInt(prodQty, 10),
        reference: prodRef.trim() || undefined,
        notes: prodNotes.trim() || undefined,
      });
      setProductionOpen(false);
      setProdQty("");
      setProdRef("");
      setProdNotes("");
      toast.success("Production recorded");
      loadData();
    } catch (err: unknown) {
      setProdError(getApiErrorMessage(err, "Failed to record production"));
    }
  }

  async function handleWriteOff() {
    if (!productId) return;
    setWoError("");
    try {
      await inventoryService.writeOffStock(productId, {
        quantity: parseInt(woQty, 10),
        reason: woReason.trim(),
        reference: woRef.trim() || undefined,
        notes: woNotes.trim() || undefined,
      });
      setWriteOffOpen(false);
      setWoQty("");
      setWoReason("");
      setWoRef("");
      setWoNotes("");
      toast.success("Stock written off");
      loadData();
    } catch (err: unknown) {
      setWoError(getApiErrorMessage(err, "Failed to write off stock"));
    }
  }

  async function handleSaveSettings(e: React.FormEvent) {
    e.preventDefault();
    if (!productId) return;
    setError("");
    setSaving(true);
    try {
      const updated = await inventoryService.updateSettings(productId, {
        reorder_point: reorderPoint.trim()
          ? parseInt(reorderPoint, 10)
          : null,
        reorder_quantity: reorderQuantity.trim()
          ? parseInt(reorderQuantity, 10)
          : null,
        location: location.trim() || null,
      });
      setReorderPoint(
        updated.reorder_point !== null ? String(updated.reorder_point) : "",
      );
      setReorderQuantity(
        updated.reorder_quantity !== null
          ? String(updated.reorder_quantity)
          : "",
      );
      setLocation(updated.location || "");
      setItem(updated);
      toast.success("Settings saved");
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Failed to save settings"));
    } finally {
      setSaving(false);
    }
  }

  function formatTxType(type: string): string {
    const map: Record<string, string> = {
      receive: "Received",
      sell: "Sold",
      adjust: "Adjusted",
      count: "Counted",
      return: "Returned",
      production: "Production",
      write_off: "Written Off",
    };
    return map[type] || type;
  }

  function txTypeBadgeVariant(
    type: string,
  ): "default" | "secondary" | "destructive" {
    if (type === "receive" || type === "return" || type === "production")
      return "default";
    if (type === "sell" || type === "write_off") return "destructive";
    return "secondary";
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <h1 className="text-2xl font-bold">Inventory Details</h1>
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (!item) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <h1 className="text-2xl font-bold">Inventory Details</h1>
        <p className="text-destructive">{error || "Item not found"}</p>
        <Link
          to="/inventory"
          className="text-sm text-muted-foreground hover:underline"
        >
          ← Back to Inventory
        </Link>
      </div>
    );
  }

  const txTotalPages = Math.ceil(txTotal / 20);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">
            {item.product_name || "Inventory Details"}
          </h1>
          {item.is_low_stock ? (
            <Badge variant="destructive">Low Stock</Badge>
          ) : (
            <Badge variant="default">OK</Badge>
          )}
        </div>
        <Link
          to="/inventory"
          className="text-sm text-muted-foreground hover:underline"
        >
          ← Back to Inventory
        </Link>
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Product Info */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold">Product Information</h2>
        <Separator className="my-4" />
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">Product</span>
            <p className="font-medium">
              <Link
                to={`/products/${item.product_id}`}
                className="hover:underline"
              >
                {item.product_name || "—"}
              </Link>
            </p>
          </div>
          <div>
            <span className="text-muted-foreground">SKU</span>
            <p className="font-medium">{item.product_sku || "—"}</p>
          </div>
          <div>
            <span className="text-muted-foreground">Category</span>
            <p className="font-medium">{item.category_name || "—"}</p>
          </div>
        </div>
      </Card>

      {/* Stock Level */}
      <Card className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Stock Level</h2>
            <p className="mt-2 text-4xl font-bold">
              {item.quantity_on_hand}
              <span className="ml-2 text-base font-normal text-muted-foreground">
                units
              </span>
            </p>
          </div>
          <div className="flex gap-2">
            {canCreate && (
              <Dialog open={receiveOpen} onOpenChange={setReceiveOpen}>
                <DialogTrigger render={<Button />}>
                  Receive Stock
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Receive Stock</DialogTitle>
                    <DialogDescription>
                      Add incoming stock for {item.product_name}.
                    </DialogDescription>
                  </DialogHeader>
                  {receiveError && (
                    <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                      {receiveError}
                    </div>
                  )}
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label>Quantity</Label>
                      <Input
                        type="number"
                        min="1"
                        value={receiveQty}
                        onChange={(e) => setReceiveQty(e.target.value)}
                        placeholder="e.g. 50"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Reference (optional)</Label>
                      <Input
                        value={receiveRef}
                        onChange={(e) => setReceiveRef(e.target.value)}
                        placeholder="e.g. PO-2026-001"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Notes (optional)</Label>
                      <Input
                        value={receiveNotes}
                        onChange={(e) => setReceiveNotes(e.target.value)}
                        placeholder="Additional notes..."
                      />
                    </div>
                  </div>
                  <DialogFooter>
                    <Button
                      variant="outline"
                      onClick={() => setReceiveOpen(false)}
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={handleReceive}
                      disabled={
                        !receiveQty || parseInt(receiveQty, 10) <= 0
                      }
                    >
                      Receive
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            )}
            {canCreate && (
              <Dialog open={productionOpen} onOpenChange={setProductionOpen}>
                <DialogTrigger render={<Button variant="outline" />}>
                  Record Production
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Record Production</DialogTitle>
                    <DialogDescription>
                      Record manufactured output for {item.product_name}.
                    </DialogDescription>
                  </DialogHeader>
                  {prodError && (
                    <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                      {prodError}
                    </div>
                  )}
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label>Quantity Produced</Label>
                      <Input
                        type="number"
                        min="1"
                        value={prodQty}
                        onChange={(e) => setProdQty(e.target.value)}
                        placeholder="e.g. 200"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Reference (optional)</Label>
                      <Input
                        value={prodRef}
                        onChange={(e) => setProdRef(e.target.value)}
                        placeholder="e.g. Batch-2026-0301"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Notes (optional)</Label>
                      <Input
                        value={prodNotes}
                        onChange={(e) => setProdNotes(e.target.value)}
                        placeholder="Additional notes..."
                      />
                    </div>
                  </div>
                  <DialogFooter>
                    <Button
                      variant="outline"
                      onClick={() => setProductionOpen(false)}
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={handleProduction}
                      disabled={!prodQty || parseInt(prodQty, 10) <= 0}
                    >
                      Record
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            )}
            {canEdit && (
              <Dialog open={writeOffOpen} onOpenChange={setWriteOffOpen}>
                <DialogTrigger render={<Button variant="destructive" />}>
                  Write Off
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Write Off Stock</DialogTitle>
                    <DialogDescription>
                      Write off damaged, expired, or lost stock for{" "}
                      {item.product_name}. Current: {item.quantity_on_hand}{" "}
                      units.
                    </DialogDescription>
                  </DialogHeader>
                  {woError && (
                    <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                      {woError}
                    </div>
                  )}
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label>Quantity</Label>
                      <Input
                        type="number"
                        min="1"
                        max={item.quantity_on_hand}
                        value={woQty}
                        onChange={(e) => setWoQty(e.target.value)}
                        placeholder="e.g. 10"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Reason</Label>
                      <Input
                        value={woReason}
                        onChange={(e) => setWoReason(e.target.value)}
                        placeholder="e.g. Damaged, Expired, Lost"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Reference (optional)</Label>
                      <Input
                        value={woRef}
                        onChange={(e) => setWoRef(e.target.value)}
                        placeholder="e.g. WO-2026-001"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Notes (optional)</Label>
                      <Input
                        value={woNotes}
                        onChange={(e) => setWoNotes(e.target.value)}
                        placeholder="Additional details..."
                      />
                    </div>
                  </div>
                  <DialogFooter>
                    <Button
                      variant="outline"
                      onClick={() => setWriteOffOpen(false)}
                    >
                      Cancel
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={handleWriteOff}
                      disabled={
                        !woQty ||
                        parseInt(woQty, 10) <= 0 ||
                        !woReason.trim()
                      }
                    >
                      Write Off
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            )}
            {canEdit && (
              <Dialog open={adjustOpen} onOpenChange={setAdjustOpen}>
                <DialogTrigger render={<Button variant="outline" />}>
                  Adjust Stock
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Adjust Stock</DialogTitle>
                    <DialogDescription>
                      Set the stock quantity for {item.product_name}. Current:{" "}
                      {item.quantity_on_hand} units.
                    </DialogDescription>
                  </DialogHeader>
                  {adjustError && (
                    <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                      {adjustError}
                    </div>
                  )}
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label>New Quantity</Label>
                      <Input
                        type="number"
                        min="0"
                        value={adjustQty}
                        onChange={(e) => setAdjustQty(e.target.value)}
                        placeholder="e.g. 42"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Reference (optional)</Label>
                      <Input
                        value={adjustRef}
                        onChange={(e) => setAdjustRef(e.target.value)}
                        placeholder="e.g. Physical count"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Notes (optional)</Label>
                      <Input
                        value={adjustNotes}
                        onChange={(e) => setAdjustNotes(e.target.value)}
                        placeholder="Reason for adjustment..."
                      />
                    </div>
                  </div>
                  <DialogFooter>
                    <Button
                      variant="outline"
                      onClick={() => setAdjustOpen(false)}
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={handleAdjust}
                      disabled={adjustQty === "" || parseInt(adjustQty, 10) < 0}
                    >
                      Adjust
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            )}
          </div>
        </div>
      </Card>

      {/* Reorder Settings */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold">Reorder Settings</h2>
        <Separator className="my-4" />
        <form onSubmit={handleSaveSettings} className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label>Reorder Point</Label>
              <Input
                type="number"
                min="0"
                value={reorderPoint}
                onChange={(e) => setReorderPoint(e.target.value)}
                disabled={!canEdit}
                placeholder="e.g. 10"
              />
              <p className="text-xs text-muted-foreground">
                Alert when stock falls to this level
              </p>
            </div>
            <div className="space-y-2">
              <Label>Reorder Quantity</Label>
              <Input
                type="number"
                min="0"
                value={reorderQuantity}
                onChange={(e) => setReorderQuantity(e.target.value)}
                disabled={!canEdit}
                placeholder="e.g. 50"
              />
              <p className="text-xs text-muted-foreground">
                Suggested quantity to reorder
              </p>
            </div>
            <div className="space-y-2">
              <Label>Location</Label>
              <Input
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                disabled={!canEdit}
                placeholder="e.g. Greenhouse A, Row 3"
              />
            </div>
          </div>
          {canEdit && (
            <div className="flex justify-end">
              <Button type="submit" disabled={saving}>
                {saving ? "Saving..." : "Save Settings"}
              </Button>
            </div>
          )}
        </form>
      </Card>

      {/* Transaction History */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold">Transaction History</h2>
        <Separator className="my-4" />
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Type</TableHead>
                <TableHead className="text-right">Change</TableHead>
                <TableHead className="text-right">After</TableHead>
                <TableHead>Reference</TableHead>
                <TableHead>Notes</TableHead>
                <TableHead>By</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {transactions.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center">
                    No transactions yet
                  </TableCell>
                </TableRow>
              ) : (
                transactions.map((tx) => (
                  <TableRow key={tx.id}>
                    <TableCell className="text-muted-foreground">
                      {new Date(tx.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <Badge variant={txTypeBadgeVariant(tx.transaction_type)}>
                        {formatTxType(tx.transaction_type)}
                      </Badge>
                    </TableCell>
                    <TableCell
                      className={`text-right font-mono ${
                        tx.quantity_change > 0
                          ? "text-green-600"
                          : tx.quantity_change < 0
                            ? "text-red-600"
                            : ""
                      }`}
                    >
                      {tx.quantity_change > 0 ? "+" : ""}
                      {tx.quantity_change}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {tx.quantity_after}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {tx.reference || "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground max-w-[150px] truncate">
                      {tx.notes || "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {tx.created_by_name || "—"}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
        {txTotalPages > 1 && (
          <div className="mt-4 flex items-center justify-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={txPage <= 1}
              onClick={() => setTxPage(txPage - 1)}
            >
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {txPage} of {txTotalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={txPage >= txTotalPages}
              onClick={() => setTxPage(txPage + 1)}
            >
              Next
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
