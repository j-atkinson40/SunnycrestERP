import { useEffect, useState } from "react";
import { ArrowRight, X, AlertTriangle } from "lucide-react";
import { useLocations } from "@/contexts/location-context";
import apiClient from "@/lib/api-client";
import { cn } from "@/lib/utils";

interface Product {
  id: string;
  name: string;
  sku?: string;
}

interface TransferRequestProps {
  onClose: () => void;
  onCreated?: () => void;
}

export function TransferRequest({ onClose, onCreated }: TransferRequestProps) {
  const { accessibleLocations, isMultiLocation, selectedLocationId } =
    useLocations();

  const [fromLocationId, setFromLocationId] = useState(
    selectedLocationId ?? accessibleLocations[0]?.id ?? ""
  );
  const [toLocationId, setToLocationId] = useState("");
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState<number | "">(1);
  const [neededBy, setNeededBy] = useState("");
  const [notes, setNotes] = useState("");
  const [products, setProducts] = useState<Product[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .get("/products", { params: { limit: 200 } })
      .then((r) => {
        const items = Array.isArray(r.data) ? r.data : r.data?.items ?? [];
        setProducts(items);
      })
      .catch(() => {});
  }, []);

  // Not visible for single-location companies
  if (!isMultiLocation) return null;

  const toLocations = accessibleLocations.filter((l) => l.id !== fromLocationId);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!fromLocationId || !toLocationId || !productId || !quantity) return;
    setSaving(true);
    setError(null);
    try {
      await apiClient.post("/vault/items", {
        item_type: "event",
        event_type: "inventory_transfer",
        title: `Inventory Transfer Request`,
        metadata_json: {
          from_location_id: fromLocationId,
          to_location_id: toLocationId,
          product_id: productId,
          quantity: Number(quantity),
          needed_by: neededBy || null,
          notes: notes || null,
          status: "pending",
        },
      });
      onCreated?.();
      onClose();
    } catch {
      setError("Failed to create transfer request. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  const fromLocation = accessibleLocations.find((l) => l.id === fromLocationId);
  const toLocation = accessibleLocations.find((l) => l.id === toLocationId);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-xl border bg-popover shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="text-base font-semibold">Inventory Transfer Request</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="size-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 p-5">
          {/* From / To locations */}
          <div className="flex items-center gap-2">
            <div className="flex-1 min-w-0">
              <label className="mb-1 block text-xs font-medium">From</label>
              <select
                value={fromLocationId}
                onChange={(e) => {
                  setFromLocationId(e.target.value);
                  if (e.target.value === toLocationId) setToLocationId("");
                }}
                className="w-full rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring"
              >
                {accessibleLocations.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="mt-5 shrink-0">
              <ArrowRight className="size-4 text-muted-foreground" />
            </div>

            <div className="flex-1 min-w-0">
              <label className="mb-1 block text-xs font-medium">To</label>
              <select
                value={toLocationId}
                onChange={(e) => setToLocationId(e.target.value)}
                className="w-full rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">Select location...</option>
                {toLocations.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Visual confirmation */}
          {fromLocation && toLocation && (
            <div className="flex items-center gap-2 rounded-md bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
              <span className="font-medium text-foreground">
                {fromLocation.name}
              </span>
              <ArrowRight className="size-3.5 shrink-0" />
              <span className="font-medium text-foreground">
                {toLocation.name}
              </span>
            </div>
          )}

          {/* Product */}
          <div>
            <label className="mb-1 block text-xs font-medium">Product</label>
            <select
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
              className="w-full rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">Select product...</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.sku ? `[${p.sku}] ` : ""}
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {/* Quantity + Needed by */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium">Quantity</label>
              <input
                type="number"
                min={1}
                value={quantity}
                onChange={(e) =>
                  setQuantity(e.target.value === "" ? "" : Number(e.target.value))
                }
                className="w-full rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium">
                Needed by
              </label>
              <input
                type="date"
                value={neededBy}
                onChange={(e) => setNeededBy(e.target.value)}
                className="w-full rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>

          {/* Notes */}
          <div>
            <label className="mb-1 block text-xs font-medium">Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Optional notes about the transfer..."
              className="w-full rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring resize-none"
            />
          </div>

          {error && (
            <p
              className={cn(
                "flex items-center gap-1.5 text-sm text-destructive"
              )}
            >
              <AlertTriangle className="size-3.5 shrink-0" />
              {error}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md px-4 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={
                saving ||
                !fromLocationId ||
                !toLocationId ||
                !productId ||
                !quantity
              }
              className="rounded-md bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-50 hover:opacity-90 transition-opacity"
            >
              {saving ? "Submitting..." : "Submit Request"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
