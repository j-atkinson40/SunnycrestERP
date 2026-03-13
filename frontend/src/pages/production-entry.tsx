import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { inventoryService } from "@/services/inventory-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type { InventoryItem, BatchProductionEntry } from "@/types/inventory";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";

interface EntryRow {
  id: string; // local key for React
  product_id: string;
  quantity: string;
  notes: string;
}

function makeRow(): EntryRow {
  return { id: crypto.randomUUID(), product_id: "", quantity: "", notes: "" };
}

export default function ProductionEntryPage() {
  const [products, setProducts] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [batchRef, setBatchRef] = useState("");
  const [rows, setRows] = useState<EntryRow[]>([makeRow()]);
  const [submitting, setSubmitting] = useState(false);
  const [results, setResults] = useState<
    Array<{ product_id: string; success: boolean; error?: string }> | null
  >(null);

  const loadProducts = useCallback(async () => {
    try {
      const data = await inventoryService.getInventoryItems(1, 500);
      setProducts(data.items);
    } catch {
      toast.error("Failed to load products");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  function updateRow(index: number, field: keyof EntryRow, value: string) {
    setRows((prev) =>
      prev.map((r, i) => (i === index ? { ...r, [field]: value } : r)),
    );
  }

  function removeRow(index: number) {
    setRows((prev) => (prev.length > 1 ? prev.filter((_, i) => i !== index) : prev));
  }

  function addRow() {
    setRows((prev) => [...prev, makeRow()]);
  }

  async function handleSubmit() {
    const entries: BatchProductionEntry[] = rows
      .filter((r) => r.product_id && r.quantity && parseInt(r.quantity, 10) > 0)
      .map((r) => ({
        product_id: r.product_id,
        quantity: parseInt(r.quantity, 10),
        notes: r.notes.trim() || undefined,
      }));

    if (entries.length === 0) {
      toast.error("Add at least one product with a valid quantity");
      return;
    }

    setSubmitting(true);
    setResults(null);
    try {
      const result = await inventoryService.batchRecordProduction({
        entries,
        batch_reference: batchRef.trim() || undefined,
      });
      setResults(result.results);
      if (result.failure_count === 0) {
        toast.success(
          `All ${result.success_count} production entries recorded`,
        );
        setRows([makeRow()]);
        setBatchRef("");
      } else {
        toast.warning(
          `${result.success_count} succeeded, ${result.failure_count} failed`,
        );
      }
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to record production"));
    } finally {
      setSubmitting(false);
    }
  }

  function getProductName(productId: string): string {
    const p = products.find((pr) => pr.product_id === productId);
    return p?.product_name || productId;
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl space-y-6">
        <h1 className="text-2xl font-bold">Production Entry</h1>
        <p className="text-muted-foreground">Loading products...</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Production Entry</h1>
          <p className="text-sm text-muted-foreground">
            Record manufactured output for multiple products in one batch.
          </p>
        </div>
        <Link
          to="/inventory"
          className="text-sm text-muted-foreground hover:underline"
        >
          ← Back to Inventory
        </Link>
      </div>

      <Card className="p-6">
        <div className="space-y-6">
          {/* Batch reference */}
          <div className="max-w-sm space-y-2">
            <Label>Batch Reference (optional)</Label>
            <Input
              value={batchRef}
              onChange={(e) => setBatchRef(e.target.value)}
              placeholder="e.g. Batch-2026-0301"
            />
            <p className="text-xs text-muted-foreground">
              Shared reference applied to all entries without their own
              reference.
            </p>
          </div>

          <Separator />

          {/* Entry rows */}
          <div className="space-y-4">
            <h3 className="text-sm font-semibold">Products</h3>
            {rows.map((row, index) => (
              <div
                key={row.id}
                className="flex items-end gap-3 rounded-md border p-3"
              >
                <div className="flex-1 space-y-2">
                  <Label>Product</Label>
                  <select
                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    value={row.product_id}
                    onChange={(e) =>
                      updateRow(index, "product_id", e.target.value)
                    }
                  >
                    <option value="">Select product...</option>
                    {products.map((p) => (
                      <option key={p.product_id} value={p.product_id}>
                        {p.product_name}
                        {p.product_sku ? ` (${p.product_sku})` : ""}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="w-28 space-y-2">
                  <Label>Quantity</Label>
                  <Input
                    type="number"
                    min="1"
                    value={row.quantity}
                    onChange={(e) =>
                      updateRow(index, "quantity", e.target.value)
                    }
                    placeholder="0"
                  />
                </div>
                <div className="flex-1 space-y-2">
                  <Label>Notes (optional)</Label>
                  <Input
                    value={row.notes}
                    onChange={(e) => updateRow(index, "notes", e.target.value)}
                    placeholder="QC passed, etc."
                  />
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => removeRow(index)}
                  disabled={rows.length === 1}
                  className="text-muted-foreground"
                >
                  Remove
                </Button>
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={addRow}>
              + Add Product
            </Button>
          </div>

          <Separator />

          {/* Submit */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              {rows.filter((r) => r.product_id && r.quantity).length} product(s)
              ready
            </p>
            <Button onClick={handleSubmit} disabled={submitting}>
              {submitting ? "Recording..." : "Record All Production"}
            </Button>
          </div>
        </div>
      </Card>

      {/* Results */}
      {results && (
        <Card className="p-6">
          <h2 className="text-lg font-semibold">Results</h2>
          <Separator className="my-4" />
          <div className="space-y-2">
            {results.map((r, i) => (
              <div
                key={i}
                className="flex items-center justify-between rounded-md border p-3"
              >
                <span className="text-sm">{getProductName(r.product_id)}</span>
                {r.success ? (
                  <Badge variant="default">Recorded</Badge>
                ) : (
                  <Badge variant="destructive">{r.error || "Failed"}</Badge>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
