import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { productService } from "@/services/product-service";
import * as productionLogService from "@/services/production-log-service";
import { getApiErrorMessage } from "@/lib/api-error";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import type { Product } from "@/types/product";
import type { ProductionLogEntry, ProductionLogEntryCreate } from "@/types/production-log";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

export default function MobileProductionLogPage() {
  // Products
  const [products, setProducts] = useState<Product[]>([]);
  const [productSearch, setProductSearch] = useState("");

  // Today's data
  const [entries, setEntries] = useState<ProductionLogEntry[]>([]);
  const [loading, setLoading] = useState(true);

  // Form
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [quantity, setQuantity] = useState("");
  const [showOptional, setShowOptional] = useState(false);
  const [mixDesignId, setMixDesignId] = useState("");
  const [batchCount, setBatchCount] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const quantityRef = useRef<HTMLInputElement>(null);

  // Recently used product IDs (ordered)
  const [recentProductIds, setRecentProductIds] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem("recent_prod_ids") || "[]");
    } catch {
      return [];
    }
  });

  // ---------------------------------------------------------------------------
  // Data
  // ---------------------------------------------------------------------------

  const loadProducts = useCallback(async () => {
    try {
      const res = await productService.getProducts(1, 500);
      setProducts(res.items);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    }
  }, []);

  const loadEntries = useCallback(async () => {
    try {
      setLoading(true);
      const data = await productionLogService.listEntries({
        start_date: todayStr(),
        end_date: todayStr(),
        limit: 500,
      });
      setEntries(data);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProducts();
    loadEntries();
  }, [loadProducts, loadEntries]);

  // ---------------------------------------------------------------------------
  // Computed
  // ---------------------------------------------------------------------------

  const totalUnits = useMemo(() => entries.reduce((s, e) => s + e.quantity_produced, 0), [entries]);
  const uniqueProducts = useMemo(() => new Set(entries.map((e) => e.product_id)).size, [entries]);

  const sortedProducts = useMemo(() => {
    // Put recently used first, then alphabetical
    const recentSet = new Set(recentProductIds);
    const recent: Product[] = [];
    const rest: Product[] = [];

    for (const p of products) {
      if (recentSet.has(p.id)) recent.push(p);
      else rest.push(p);
    }

    // Sort recent by order in recentProductIds
    recent.sort((a, b) => recentProductIds.indexOf(a.id) - recentProductIds.indexOf(b.id));
    rest.sort((a, b) => a.name.localeCompare(b.name));

    return [...recent, ...rest];
  }, [products, recentProductIds]);

  const filteredProducts = useMemo(() => {
    if (!productSearch.trim()) return sortedProducts;
    const q = productSearch.toLowerCase();
    return sortedProducts.filter((p) => p.name.toLowerCase().includes(q));
  }, [sortedProducts, productSearch]);

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const selectProduct = (p: Product) => {
    setSelectedProduct(p);
    setQuantity("");
    setShowOptional(false);
    setMixDesignId("");
    setBatchCount("");
    // Focus quantity input after render
    setTimeout(() => quantityRef.current?.focus(), 100);
  };

  const handleSubmit = useCallback(async () => {
    if (!selectedProduct || !quantity || Number(quantity) < 1) return;
    try {
      setSubmitting(true);

      const payload: ProductionLogEntryCreate = {
        log_date: todayStr(),
        product_id: selectedProduct.id,
        quantity_produced: Number(quantity),
        entry_method: "mobile",
      };
      if (mixDesignId) payload.mix_design_id = mixDesignId;
      if (batchCount) payload.batch_count = Number(batchCount);

      const newEntry = await productionLogService.createEntry(payload);
      setEntries((prev) => [newEntry, ...prev]);

      // Update recently used
      const updated = [selectedProduct.id, ...recentProductIds.filter((id) => id !== selectedProduct.id)].slice(0, 10);
      setRecentProductIds(updated);
      localStorage.setItem("recent_prod_ids", JSON.stringify(updated));

      // Show success
      setSuccessMsg(`${quantity} ${selectedProduct.name} logged`);
      setTimeout(() => {
        setSuccessMsg(null);
        setSelectedProduct(null);
        setQuantity("");
        setShowOptional(false);
        setMixDesignId("");
        setBatchCount("");
      }, 2000);

      loadEntries();
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }, [selectedProduct, quantity, mixDesignId, batchCount, recentProductIds, loadEntries]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  // Success overlay
  if (successMsg) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-green-50 p-6">
        <div className="text-center">
          <div className="text-5xl mb-4">&#10003;</div>
          <p className="text-2xl font-bold text-green-800">{successMsg}</p>
        </div>
      </div>
    );
  }

  // Product selected — show quantity entry
  if (selectedProduct) {
    return (
      <div className="flex min-h-screen flex-col bg-background">
        {/* Header */}
        <div className="border-b bg-muted/30 px-4 py-3">
          <button
            onClick={() => setSelectedProduct(null)}
            className="text-sm text-primary mb-1"
          >
            &larr; Back to products
          </button>
          <p className="text-lg font-bold">{selectedProduct.name}</p>
          <p className="text-xs text-muted-foreground">
            Today: {totalUnits} units across {uniqueProducts} product{uniqueProducts !== 1 ? "s" : ""}
          </p>
        </div>

        {/* Quantity */}
        <div className="flex-1 p-4 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Quantity *</label>
            <Input
              ref={quantityRef}
              type="number"
              inputMode="numeric"
              pattern="[0-9]*"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              placeholder="0"
              className="text-3xl font-bold text-center h-16"
              min={1}
              autoFocus
            />
          </div>

          {/* Optional fields toggle */}
          {!showOptional ? (
            <button
              onClick={() => setShowOptional(true)}
              className="text-sm text-primary"
            >
              + Add mix design & batch count
            </button>
          ) : (
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium mb-1">Mix Design</label>
                <Input
                  value={mixDesignId}
                  onChange={(e) => setMixDesignId(e.target.value)}
                  placeholder="Optional"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Batch Count</label>
                <Input
                  type="number"
                  inputMode="numeric"
                  value={batchCount}
                  onChange={(e) => setBatchCount(e.target.value)}
                  placeholder="Optional"
                  min={1}
                />
              </div>
            </div>
          )}
        </div>

        {/* Submit button */}
        <div className="p-4 border-t">
          <Button
            onClick={handleSubmit}
            disabled={!quantity || Number(quantity) < 1 || submitting}
            className="w-full h-14 text-lg font-bold bg-green-600 hover:bg-green-700 text-white"
          >
            {submitting ? "Logging..." : "Log It"}
          </Button>
        </div>
      </div>
    );
  }

  // Default: product selection list
  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Header */}
      <div className="border-b bg-muted/30 px-4 py-3">
        <h1 className="text-xl font-bold">Production Log</h1>
        <p className="text-sm text-muted-foreground">
          Today: {loading ? "..." : `${totalUnits} units across ${uniqueProducts} product${uniqueProducts !== 1 ? "s" : ""}`}
        </p>
      </div>

      {/* Search */}
      <div className="px-4 pt-3">
        <Input
          value={productSearch}
          onChange={(e) => setProductSearch(e.target.value)}
          placeholder="Search products..."
          className="h-12"
        />
      </div>

      {/* Product List */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {filteredProducts.length === 0 ? (
          <p className="text-center text-sm text-muted-foreground py-8">No products found</p>
        ) : (
          <div className="space-y-2">
            {recentProductIds.length > 0 && !productSearch && (
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Recently Used</p>
            )}
            {filteredProducts.map((p, i) => {
              const isRecent = recentProductIds.includes(p.id);
              const showRestHeader = !productSearch && i > 0 && isRecent === false &&
                recentProductIds.includes(filteredProducts[i - 1]?.id);

              return (
                <div key={p.id}>
                  {showRestHeader && (
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mt-4 mb-1">All Products</p>
                  )}
                  <button
                    onClick={() => selectProduct(p)}
                    className="w-full rounded-lg border p-4 text-left transition-colors hover:bg-accent active:bg-accent"
                  >
                    <span className="text-base font-medium">{p.name}</span>
                    {p.category_name && (
                      <span className="ml-2 text-xs text-muted-foreground">({p.category_name})</span>
                    )}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Recent entries summary */}
      {entries.length > 0 && (
        <div className="border-t bg-muted/30 px-4 py-3">
          <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wide">
            Today's Entries ({entries.length})
          </p>
          <div className="flex flex-wrap gap-2">
            {entries.slice(0, 5).map((e) => (
              <span key={e.id} className="inline-flex items-center rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800">
                {e.product_name}: {e.quantity_produced}
              </span>
            ))}
            {entries.length > 5 && (
              <span className="text-xs text-muted-foreground">+{entries.length - 5} more</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
