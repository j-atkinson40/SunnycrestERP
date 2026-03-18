import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import * as urnService from "@/services/urn-catalog-service";
import type { UrnProduct, UrnCatalogStats } from "@/types/urn-catalog";

// ── Category badge colors ────────────────────────────────────────

const CATEGORY_COLORS: Record<string, string> = {
  "Cultured Marble": "bg-purple-100 text-purple-800",
  "Companion": "bg-indigo-100 text-indigo-800",
  "Other Common": "bg-gray-100 text-gray-800",
  "Metal": "bg-blue-100 text-blue-800",
  "Wood": "bg-amber-100 text-amber-800",
  "Biodegradable": "bg-green-100 text-green-800",
  "Keepsake": "bg-pink-100 text-pink-800",
  "Infant": "bg-rose-100 text-rose-800",
  "Custom": "bg-orange-100 text-orange-800",
};

const SOURCE_COLORS: Record<string, string> = {
  "Starter Set": "bg-emerald-100 text-emerald-700",
  "Imported": "bg-blue-100 text-blue-700",
  "Manual": "bg-gray-100 text-gray-700",
};

function categoryBadgeClass(category: string | null): string {
  if (!category) return "bg-gray-100 text-gray-600";
  return CATEGORY_COLORS[category] || "bg-gray-100 text-gray-600";
}

function sourceBadgeClass(source: string | null): string {
  if (!source) return "bg-gray-100 text-gray-600";
  return SOURCE_COLORS[source] || "bg-gray-100 text-gray-600";
}

function calcMarkup(wholesale: number | null, selling: number | null): string {
  if (!wholesale || !selling || wholesale <= 0) return "-";
  return `${(((selling - wholesale) / wholesale) * 100).toFixed(1)}%`;
}

function formatCurrency(value: number | null): string {
  if (value == null) return "-";
  return `$${value.toFixed(2)}`;
}

// ── Edit Modal ───────────────────────────────────────────────────

interface EditModalProps {
  urn: UrnProduct;
  onClose: () => void;
  onSave: (updated: UrnProduct) => void;
}

function EditModal({ urn, onClose, onSave }: EditModalProps) {
  const [name, setName] = useState(urn.name);
  const [price, setPrice] = useState(urn.price?.toString() ?? "");
  const [wholesaleCost, setWholesaleCost] = useState(urn.wholesale_cost?.toString() ?? "");
  const [category, setCategory] = useState(urn.category ?? "");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-lg border bg-background p-6 shadow-xl">
        <h3 className="text-lg font-semibold">Edit Urn</h3>
        <div className="mt-4 space-y-4">
          <div className="space-y-1">
            <Label className="text-sm">Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <Label className="text-sm">Wholesale Cost</Label>
              <div className="relative">
                <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">$</span>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={wholesaleCost}
                  onChange={(e) => setWholesaleCost(e.target.value)}
                  className="pl-6"
                />
              </div>
            </div>
            <div className="space-y-1">
              <Label className="text-sm">Selling Price</Label>
              <div className="relative">
                <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">$</span>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  className="pl-6"
                />
              </div>
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-sm">Category</Label>
            <Input value={category} onChange={(e) => setCategory(e.target.value)} />
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button
            onClick={() => {
              onSave({
                ...urn,
                name,
                price: price ? parseFloat(price) : null,
                wholesale_cost: wholesaleCost ? parseFloat(wholesaleCost) : null,
                category: category || null,
              });
            }}
          >
            Save
          </Button>
        </div>
      </div>
    </div>
  );
}

// ── Add Manual Urn Modal ─────────────────────────────────────────

interface AddUrnModalProps {
  onClose: () => void;
  onSave: (urn: { name: string; price?: number; category?: string }) => void;
}

function AddUrnModal({ onClose, onSave }: AddUrnModalProps) {
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [category, setCategory] = useState("");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-lg border bg-background p-6 shadow-xl">
        <h3 className="text-lg font-semibold">Add Urn Manually</h3>
        <div className="mt-4 space-y-4">
          <div className="space-y-1">
            <Label className="text-sm">Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Cherry Wood Urn" />
          </div>
          <div className="space-y-1">
            <Label className="text-sm">Selling Price</Label>
            <div className="relative">
              <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">$</span>
              <Input type="number" step="0.01" min="0" value={price} onChange={(e) => setPrice(e.target.value)} className="pl-6" />
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-sm">Category</Label>
            <Input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="e.g. Wood" />
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button
            disabled={!name.trim()}
            onClick={() => {
              onSave({
                name: name.trim(),
                price: price ? parseFloat(price) : undefined,
                category: category.trim() || undefined,
              });
            }}
          >
            Add Urn
          </Button>
        </div>
      </div>
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────────

export default function UrnCatalogPage() {
  const navigate = useNavigate();
  const [urns, setUrns] = useState<UrnProduct[]>([]);
  const [stats, setStats] = useState<UrnCatalogStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"active" | "inactive">("active");
  const [search, setSearch] = useState("");
  const [editingUrn, setEditingUrn] = useState<UrnProduct | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [activeUrns, inactiveUrns, urnStats] = await Promise.all([
        urnService.listUrns(true),
        urnService.listUrns(false),
        urnService.getStats(),
      ]);
      // Combine active and inactive, deduplicating by id
      const allUrns = [...activeUrns];
      for (const u of inactiveUrns) {
        if (!allUrns.find((a) => a.id === u.id)) {
          allUrns.push(u);
        }
      }
      setUrns(allUrns);
      setStats(urnStats);
    } catch {
      toast.error("Failed to load urn catalog");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const activeUrns = useMemo(
    () => urns.filter((u) => u.is_active),
    [urns],
  );
  const inactiveUrns = useMemo(
    () => urns.filter((u) => !u.is_active),
    [urns],
  );

  const displayedUrns = useMemo(() => {
    const list = tab === "active" ? activeUrns : inactiveUrns;
    if (!search.trim()) return list;
    const q = search.toLowerCase();
    return list.filter(
      (u) =>
        u.name.toLowerCase().includes(q) ||
        (u.wilbert_sku && u.wilbert_sku.toLowerCase().includes(q)) ||
        (u.category && u.category.toLowerCase().includes(q)),
    );
  }, [tab, activeUrns, inactiveUrns, search]);

  const isStaleImport = useMemo(() => {
    if (!stats?.last_import_at) return false;
    const lastImport = new Date(stats.last_import_at);
    const twelveMonthsAgo = new Date();
    twelveMonthsAgo.setMonth(twelveMonthsAgo.getMonth() - 12);
    return lastImport < twelveMonthsAgo;
  }, [stats]);

  const handleDeactivate = async (urn: UrnProduct) => {
    try {
      await urnService.deactivateUrn(urn.id);
      setUrns((prev) =>
        prev.map((u) => (u.id === urn.id ? { ...u, is_active: false } : u)),
      );
      toast.success(`${urn.name} deactivated`);
    } catch {
      toast.error("Failed to deactivate urn");
    }
  };

  const handleActivate = async (urn: UrnProduct) => {
    try {
      await urnService.activateUrn(urn.id);
      setUrns((prev) =>
        prev.map((u) => (u.id === urn.id ? { ...u, is_active: true } : u)),
      );
      toast.success(`${urn.name} activated`);
    } catch {
      toast.error("Failed to activate urn");
    }
  };

  const handleEditSave = (updated: UrnProduct) => {
    setUrns((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    setEditingUrn(null);
    toast.success("Urn updated");
  };

  const handleAddUrn = async (urn: { name: string; price?: number; category?: string }) => {
    try {
      const created = await urnService.createUrn(urn);
      setUrns((prev) => [...prev, created]);
      setShowAddModal(false);
      toast.success(`${urn.name} added`);
    } catch {
      toast.error("Failed to add urn");
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Urn Catalog</h1>
          <p className="text-sm text-muted-foreground">
            Manage your complete urn product list
          </p>
          {stats && (
            <p className="mt-1 text-sm text-muted-foreground">
              {stats.active_count} urns active &middot; {stats.inactive_count} inactive
              {stats.imported_count > 0 && (
                <> &middot; {stats.imported_count} imported from Wilbert price list</>
              )}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setShowAddModal(true)}>
            Add Urn Manually
          </Button>
          <Button onClick={() => navigate("/products/urns/import")}>
            Import from Wilbert Price List
          </Button>
        </div>
      </div>

      {/* Stale import warning */}
      {isStaleImport && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
          <p className="text-sm font-medium text-amber-900">
            Your last Wilbert price list import was over 12 months ago.
          </p>
          <p className="mt-1 text-sm text-amber-700">
            Prices may be outdated. Consider re-importing your latest Wilbert price list to keep costs current.
          </p>
        </div>
      )}

      {/* Search + Tabs */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-1 rounded-lg border p-1">
          <button
            type="button"
            onClick={() => setTab("active")}
            className={cn(
              "rounded-md px-4 py-1.5 text-sm font-medium transition-colors",
              tab === "active"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted",
            )}
          >
            Active ({activeUrns.length})
          </button>
          <button
            type="button"
            onClick={() => setTab("inactive")}
            className={cn(
              "rounded-md px-4 py-1.5 text-sm font-medium transition-colors",
              tab === "inactive"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted",
            )}
          >
            Inactive ({inactiveUrns.length})
          </button>
        </div>
        <Input
          placeholder="Search urns..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
      </div>

      {/* Table */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">
            {tab === "active" ? "Active Urns" : "Inactive Urns"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {displayedUrns.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              {search ? "No urns match your search." : tab === "active" ? "No active urns. Import or add urns to get started." : "No inactive urns."}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th className="pb-2 pr-4 font-medium">Product Name</th>
                    <th className="pb-2 pr-4 font-medium">Category</th>
                    <th className="pb-2 pr-4 font-medium">Wilbert SKU</th>
                    <th className="pb-2 pr-4 font-medium text-right">Wholesale</th>
                    <th className="pb-2 pr-4 font-medium text-right">Selling Price</th>
                    <th className="pb-2 pr-4 font-medium text-right">Markup</th>
                    <th className="pb-2 pr-4 font-medium">Source</th>
                    <th className="pb-2 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {displayedUrns.map((urn) => (
                    <tr key={urn.id} className="hover:bg-muted/30">
                      <td className="py-3 pr-4 font-medium">{urn.name}</td>
                      <td className="py-3 pr-4">
                        {urn.category && (
                          <span className={cn("inline-block rounded-full px-2.5 py-0.5 text-xs font-medium", categoryBadgeClass(urn.category))}>
                            {urn.category}
                          </span>
                        )}
                      </td>
                      <td className="py-3 pr-4 font-mono text-xs text-muted-foreground">
                        {urn.wilbert_sku || "-"}
                      </td>
                      <td className="py-3 pr-4 text-right text-muted-foreground">
                        {formatCurrency(urn.wholesale_cost)}
                      </td>
                      <td className="py-3 pr-4 text-right font-semibold">
                        {formatCurrency(urn.price)}
                      </td>
                      <td className="py-3 pr-4 text-right text-muted-foreground">
                        {calcMarkup(urn.wholesale_cost, urn.price)}
                      </td>
                      <td className="py-3 pr-4">
                        {urn.source && (
                          <span className={cn("inline-block rounded-full px-2.5 py-0.5 text-xs font-medium", sourceBadgeClass(urn.source))}>
                            {urn.source}
                          </span>
                        )}
                      </td>
                      <td className="py-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 px-2 text-xs"
                            onClick={() => setEditingUrn(urn)}
                          >
                            Edit
                          </Button>
                          {tab === "active" ? (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 px-2 text-xs text-destructive hover:text-destructive"
                              onClick={() => handleDeactivate(urn)}
                            >
                              Deactivate
                            </Button>
                          ) : (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 px-2 text-xs text-green-700 hover:text-green-800"
                              onClick={() => handleActivate(urn)}
                            >
                              Activate
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Edit Modal */}
      {editingUrn && (
        <EditModal
          urn={editingUrn}
          onClose={() => setEditingUrn(null)}
          onSave={handleEditSave}
        />
      )}

      {/* Add Urn Modal */}
      {showAddModal && (
        <AddUrnModal
          onClose={() => setShowAddModal(false)}
          onSave={handleAddUrn}
        />
      )}
    </div>
  );
}
