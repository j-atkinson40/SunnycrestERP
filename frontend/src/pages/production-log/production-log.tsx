import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { productService } from "@/services/product-service";
import * as productionLogService from "@/services/production-log-service";
import { getApiErrorMessage } from "@/lib/api-error";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import type { Product } from "@/types/product";
import type { ProductionLogEntry, ProductionLogEntryCreate, ProductionLogEntryUpdate } from "@/types/production-log";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function fmtDateDisplay(dateStr: string) {
  const d = new Date(dateStr + "T12:00:00");
  return d.toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" });
}

function groupByProduct(entries: ProductionLogEntry[]) {
  const map = new Map<string, { product_name: string; total: number; entries: ProductionLogEntry[] }>();
  for (const e of entries) {
    let group = map.get(e.product_id);
    if (!group) {
      group = { product_name: e.product_name, total: 0, entries: [] };
      map.set(e.product_id, group);
    }
    group.total += e.quantity_produced;
    group.entries.push(e);
  }
  return Array.from(map.values());
}

// ---------------------------------------------------------------------------
// Success Animation Component
// ---------------------------------------------------------------------------

function SuccessFlash({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="animate-in fade-in slide-in-from-top-2 duration-300 rounded-lg bg-green-50 border border-green-200 px-4 py-3 text-center text-green-800 font-semibold text-lg">
      {message}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Inline Edit Row
// ---------------------------------------------------------------------------

interface EditRowProps {
  entry: ProductionLogEntry;
  onSave: (id: string, update: ProductionLogEntryUpdate) => Promise<void>;
  onCancel: () => void;
  saving: boolean;
}

function EditRow({ entry, onSave, onCancel, saving }: EditRowProps) {
  const [qty, setQty] = useState(String(entry.quantity_produced));
  const [batch, setBatch] = useState(entry.batch_count != null ? String(entry.batch_count) : "");
  const [notes, setNotes] = useState(entry.notes || "");

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-blue-200 bg-blue-50 p-3">
      <span className="font-medium text-sm">{entry.product_name}</span>
      <Input
        type="number"
        value={qty}
        onChange={(e) => setQty(e.target.value)}
        className="w-24"
        min={1}
      />
      <Input
        value={batch}
        onChange={(e) => setBatch(e.target.value)}
        className="w-24"
        placeholder="Batches"
        type="number"
      />
      <Input
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        className="flex-1 min-w-[120px]"
        placeholder="Notes"
      />
      <Button
        size="sm"
        onClick={() =>
          onSave(entry.id, {
            quantity_produced: Number(qty),
            batch_count: batch ? Number(batch) : undefined,
            notes: notes || undefined,
          })
        }
        disabled={saving || !qty || Number(qty) < 1}
      >
        {saving ? "Saving..." : "Save"}
      </Button>
      <Button size="sm" variant="outline" onClick={onCancel} disabled={saving}>
        Cancel
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function ProductionLogPage() {
  const { hasPermission } = useAuth();
  const canCreate = hasPermission("production_log.create") || hasPermission("inventory.create");
  const canEdit = hasPermission("production_log.edit") || hasPermission("inventory.edit");
  const canDelete = hasPermission("production_log.delete") || hasPermission("inventory.delete");

  // Date navigation
  const [selectedDate, setSelectedDate] = useState(todayStr);
  const isToday = selectedDate === todayStr();
  const isPast = selectedDate < todayStr();

  // Products for dropdown
  const [products, setProducts] = useState<Product[]>([]);
  const [productSearch, setProductSearch] = useState("");
  const [showProductDropdown, setShowProductDropdown] = useState(false);

  // Entries for selected date
  const [entries, setEntries] = useState<ProductionLogEntry[]>([]);
  const [loading, setLoading] = useState(true);

  // Quick entry form
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [quantity, setQuantity] = useState("");
  const [mixDesignId, setMixDesignId] = useState("");
  const [batchCount, setBatchCount] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const productInputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Edit / Delete
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editSaving, setEditSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ProductionLogEntry | null>(null);
  const [deleting, setDeleting] = useState(false);

  // ---------------------------------------------------------------------------
  // Data Fetching
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
        start_date: selectedDate,
        end_date: selectedDate,
        limit: 500,
      });
      setEntries(data);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [selectedDate]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  useEffect(() => {
    loadEntries();
  }, [loadEntries]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowProductDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // ---------------------------------------------------------------------------
  // Computed
  // ---------------------------------------------------------------------------

  const totalUnits = useMemo(() => entries.reduce((sum, e) => sum + e.quantity_produced, 0), [entries]);
  const uniqueProducts = useMemo(() => new Set(entries.map((e) => e.product_id)).size, [entries]);
  const productGroups = useMemo(() => groupByProduct(entries), [entries]);

  const filteredProducts = useMemo(() => {
    if (!productSearch.trim()) return products.slice(0, 20);
    const q = productSearch.toLowerCase();
    return products.filter((p) => p.name.toLowerCase().includes(q)).slice(0, 20);
  }, [products, productSearch]);

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const handleSubmit = useCallback(async () => {
    if (!selectedProduct || !quantity || Number(quantity) < 1) return;
    try {
      setSubmitting(true);

      const payload: ProductionLogEntryCreate = {
        log_date: selectedDate,
        product_id: selectedProduct.id,
        quantity_produced: Number(quantity),
        entry_method: "manual",
      };
      if (mixDesignId) payload.mix_design_id = mixDesignId;
      if (batchCount) payload.batch_count = Number(batchCount);
      if (notes) payload.notes = notes;

      const newEntry = await productionLogService.createEntry(payload);

      // Optimistic: add to list immediately
      setEntries((prev) => [newEntry, ...prev]);

      // Show success message
      setSuccessMsg(`+${quantity} ${selectedProduct.name}`);
      setTimeout(() => setSuccessMsg(null), 2000);

      // Reset form
      setSelectedProduct(null);
      setProductSearch("");
      setQuantity("");
      setMixDesignId("");
      setBatchCount("");
      setNotes("");

      // Focus product input
      productInputRef.current?.focus();

      // Refetch in background
      loadEntries();
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }, [selectedProduct, quantity, mixDesignId, batchCount, notes, selectedDate, loadEntries]);

  const handleEditSave = useCallback(
    async (id: string, update: ProductionLogEntryUpdate) => {
      try {
        setEditSaving(true);
        await productionLogService.updateEntry(id, update);
        toast.success("Entry updated");
        setEditingId(null);
        loadEntries();
      } catch (err) {
        toast.error(getApiErrorMessage(err));
      } finally {
        setEditSaving(false);
      }
    },
    [loadEntries],
  );

  const handleDelete = useCallback(async () => {
    if (!deleteTarget) return;
    try {
      setDeleting(true);
      await productionLogService.deleteEntry(deleteTarget.id);
      toast.success("Entry deleted");
      setDeleteTarget(null);
      setEntries((prev) => prev.filter((e) => e.id !== deleteTarget.id));
      loadEntries();
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setDeleting(false);
    }
  }, [deleteTarget, loadEntries]);

  const goYesterday = () => {
    const d = new Date(selectedDate + "T12:00:00");
    d.setDate(d.getDate() - 1);
    setSelectedDate(d.toISOString().slice(0, 10));
  };

  const goToday = () => setSelectedDate(todayStr());

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Production Log</h1>
          <p className="text-lg text-muted-foreground">{fmtDateDisplay(selectedDate)}</p>
        </div>
        <div className="flex items-center gap-3">
          <Card className="px-4 py-2 text-center">
            <p className="text-3xl font-bold">{totalUnits}</p>
            <p className="text-xs text-muted-foreground">
              units across {uniqueProducts} product{uniqueProducts !== 1 ? "s" : ""}
            </p>
          </Card>
          <Link
            to="/production-log/summary"
            className="text-sm text-primary hover:underline"
          >
            Monthly Summary
          </Link>
        </div>
      </div>

      {/* Date Navigation */}
      <div className="flex items-center gap-3">
        <Button variant="outline" size="sm" onClick={goYesterday}>
          &larr; Yesterday
        </Button>
        <Input
          type="date"
          value={selectedDate}
          onChange={(e) => setSelectedDate(e.target.value)}
          className="w-44"
          max={todayStr()}
        />
        {!isToday && (
          <Button variant="outline" size="sm" onClick={goToday}>
            Today &rarr;
          </Button>
        )}
        {isPast && (
          <Badge variant="secondary" className="text-xs">
            Read-only (past date)
          </Badge>
        )}
      </div>

      {/* Success Flash */}
      <SuccessFlash message={successMsg} />

      {/* Quick Entry Form — only for today */}
      {isToday && canCreate && (
        <Card className="p-4 border-green-200 bg-green-50/30">
          <h2 className="mb-3 text-sm font-semibold text-green-800 uppercase tracking-wide">Quick Entry</h2>
          <div className="flex flex-wrap items-end gap-3">
            {/* Product Dropdown */}
            <div className="relative flex-1 min-w-[200px]" ref={dropdownRef}>
              <Label className="text-xs">Product *</Label>
              <Input
                ref={productInputRef}
                value={selectedProduct ? selectedProduct.name : productSearch}
                onChange={(e) => {
                  setProductSearch(e.target.value);
                  setSelectedProduct(null);
                  setShowProductDropdown(true);
                }}
                onFocus={() => setShowProductDropdown(true)}
                placeholder="Type to search products..."
                className="mt-1"
              />
              {showProductDropdown && !selectedProduct && (
                <div className="absolute z-50 mt-1 max-h-60 w-full overflow-y-auto rounded-md border bg-popover shadow-lg">
                  {filteredProducts.length === 0 ? (
                    <div className="px-3 py-2 text-sm text-muted-foreground">No products found</div>
                  ) : (
                    filteredProducts.map((p) => (
                      <button
                        key={p.id}
                        className="flex w-full items-center px-3 py-2 text-sm hover:bg-accent-subtle text-left"
                        onClick={() => {
                          setSelectedProduct(p);
                          setProductSearch(p.name);
                          setShowProductDropdown(false);
                        }}
                      >
                        <span className="font-medium">{p.name}</span>
                        {p.category_name && (
                          <span className="ml-2 text-xs text-muted-foreground">({p.category_name})</span>
                        )}
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>

            {/* Quantity */}
            <div className="w-28">
              <Label className="text-xs">Quantity *</Label>
              <Input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="0"
                min={1}
                className="mt-1 text-lg font-bold text-center"
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSubmit();
                }}
              />
            </div>

            {/* Mix Design (optional) */}
            <div className="w-40">
              <Label className="text-xs">Mix Design</Label>
              <Input
                value={mixDesignId}
                onChange={(e) => setMixDesignId(e.target.value)}
                placeholder="Select mix design (optional)"
                className="mt-1"
              />
            </div>

            {/* Batch Count (optional) */}
            <div className="w-28">
              <Label className="text-xs">Batches</Label>
              <Input
                type="number"
                value={batchCount}
                onChange={(e) => setBatchCount(e.target.value)}
                placeholder="Optional"
                min={1}
                className="mt-1"
              />
            </div>

            {/* Notes (optional) */}
            <div className="flex-1 min-w-[150px]">
              <Label className="text-xs">Notes</Label>
              <Input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Optional notes"
                className="mt-1"
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSubmit();
                }}
              />
            </div>

            {/* Submit */}
            <Button
              onClick={handleSubmit}
              disabled={!selectedProduct || !quantity || Number(quantity) < 1 || submitting}
              className="bg-green-600 hover:bg-green-700 text-white px-6 h-10"
            >
              {submitting ? "Logging..." : "Log Production"}
            </Button>
          </div>
        </Card>
      )}

      {/* Today's Log */}
      <div>
        <h2 className="mb-3 text-lg font-semibold">
          {isToday ? "Today's Entries" : `Entries for ${fmtDateDisplay(selectedDate)}`}
          <span className="ml-2 text-sm font-normal text-muted-foreground">
            ({entries.length} entr{entries.length === 1 ? "y" : "ies"})
          </span>
        </h2>

        {loading && entries.length === 0 ? (
          <Card className="p-8 text-center text-muted-foreground">Loading entries...</Card>
        ) : entries.length === 0 ? (
          <Card className="p-8 text-center text-muted-foreground">
            No production logged for this date.
          </Card>
        ) : (
          <div className="space-y-4">
            {/* Product group summaries */}
            <div className="flex flex-wrap gap-2">
              {productGroups.map((g) => (
                <Badge key={g.product_name} variant="secondary" className="text-sm px-3 py-1">
                  {g.product_name}: <span className="font-bold ml-1">{g.total}</span> total
                </Badge>
              ))}
            </div>

            {/* Entry list */}
            <div className="space-y-2">
              {entries.map((entry) =>
                editingId === entry.id ? (
                  <EditRow
                    key={entry.id}
                    entry={entry}
                    onSave={handleEditSave}
                    onCancel={() => setEditingId(null)}
                    saving={editSaving}
                  />
                ) : (
                  <Card key={entry.id} className="p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex flex-wrap items-center gap-3 min-w-0 flex-1">
                        <span className="font-medium">{entry.product_name}</span>
                        <span className="text-2xl font-bold text-primary">
                          {entry.quantity_produced}
                        </span>
                        {entry.mix_design_name && (
                          <Badge variant="outline" className="text-xs">
                            Mix: {entry.mix_design_name}
                          </Badge>
                        )}
                        {entry.batch_count != null && (
                          <span className="text-xs text-muted-foreground">
                            {entry.batch_count} batch{entry.batch_count !== 1 ? "es" : ""}
                          </span>
                        )}
                        {entry.notes && (
                          <span className="text-xs text-muted-foreground italic truncate max-w-[200px]">
                            {entry.notes}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-xs text-muted-foreground">
                          {fmtTime(entry.created_at)} &middot; {entry.entered_by}
                        </span>
                        {isToday && canEdit && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setEditingId(entry.id)}
                            className="h-7 w-7 p-0"
                            title="Edit"
                          >
                            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                              <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
                              <path d="m15 5 4 4" />
                            </svg>
                          </Button>
                        )}
                        {isToday && canDelete && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setDeleteTarget(entry)}
                            className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                            title="Delete"
                          >
                            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                              <path d="M3 6h18" />
                              <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
                              <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
                            </svg>
                          </Button>
                        )}
                      </div>
                    </div>
                  </Card>
                ),
              )}
            </div>
          </div>
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Entry?</DialogTitle>
            <DialogDescription>
              This will remove {deleteTarget?.quantity_produced} {deleteTarget?.product_name} from today's log
              and reduce inventory by {deleteTarget?.quantity_produced} units.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)} disabled={deleting}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
              {deleting ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
