import { useEffect, useState, useCallback, useMemo } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { funeralHomeService } from "@/services/funeral-home-service";
import type { FHPriceListItem } from "@/types/funeral-home";

const currency = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

export default function PriceListPage() {
  const [items, setItems] = useState<FHPriceListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [seeding, setSeeding] = useState(false);

  const [form, setForm] = useState({
    item_code: "",
    category: "",
    item_name: "",
    description: "",
    unit_price: "",
    price_type: "fixed",
    is_ftc_required_disclosure: false,
    ftc_disclosure_text: "",
    is_required_by_law: false,
    is_active: true,
    sort_order: "0",
  });

  const load = useCallback(async () => {
    try {
      const data = await funeralHomeService.listPriceList();
      setItems(data);
    } catch {
      toast.error("Failed to load price list");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const grouped = useMemo(() => {
    const groups: Record<string, FHPriceListItem[]> = {};
    for (const item of items) {
      const cat = item.category || "Other";
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(item);
    }
    // Sort within groups
    for (const cat of Object.keys(groups)) {
      groups[cat].sort((a, b) => a.sort_order - b.sort_order);
    }
    return groups;
  }, [items]);

  const resetForm = () => {
    setForm({
      item_code: "",
      category: "",
      item_name: "",
      description: "",
      unit_price: "",
      price_type: "fixed",
      is_ftc_required_disclosure: false,
      ftc_disclosure_text: "",
      is_required_by_law: false,
      is_active: true,
      sort_order: "0",
    });
    setEditingId(null);
    setShowForm(false);
  };

  const handleEdit = (item: FHPriceListItem) => {
    setForm({
      item_code: item.item_code,
      category: item.category,
      item_name: item.item_name,
      description: item.description ?? "",
      unit_price: String(item.unit_price),
      price_type: item.price_type,
      is_ftc_required_disclosure: item.is_ftc_required_disclosure,
      ftc_disclosure_text: item.ftc_disclosure_text ?? "",
      is_required_by_law: item.is_required_by_law,
      is_active: item.is_active,
      sort_order: String(item.sort_order),
    });
    setEditingId(item.id);
    setShowForm(true);
  };

  const handleSave = async () => {
    const payload = {
      ...form,
      unit_price: Number(form.unit_price) || 0,
      sort_order: Number(form.sort_order) || 0,
    };
    try {
      if (editingId) {
        await funeralHomeService.updatePriceListItem(editingId, payload);
        toast.success("Item updated");
      } else {
        await funeralHomeService.createPriceListItem(payload);
        toast.success("Item created");
      }
      resetForm();
      load();
    } catch {
      toast.error("Failed to save item");
    }
  };

  const handleSeedFTC = async () => {
    setSeeding(true);
    try {
      const result = await funeralHomeService.seedFTCItems();
      toast.success(result.message);
      load();
    } catch {
      toast.error("Failed to seed FTC items");
    } finally {
      setSeeding(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Loading price list...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">General Price List (GPL)</h1>
          <p className="text-sm text-muted-foreground mt-1">
            FTC Funeral Rule requires itemized pricing for all goods and services.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleSeedFTC} disabled={seeding}>
            {seeding ? "Seeding..." : "Seed FTC Items"}
          </Button>
          <Button
            onClick={() => {
              if (showForm) resetForm();
              else setShowForm(true);
            }}
          >
            {showForm ? "Cancel" : "Add Item"}
          </Button>
        </div>
      </div>

      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle>{editingId ? "Edit Item" : "Add Price List Item"}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-4">
              <div className="space-y-2">
                <Label>Item Code</Label>
                <Input value={form.item_code} onChange={(e) => setForm((p) => ({ ...p, item_code: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Category</Label>
                <Input value={form.category} onChange={(e) => setForm((p) => ({ ...p, category: e.target.value }))} placeholder="e.g., Professional Services" />
              </div>
              <div className="col-span-2 space-y-2">
                <Label>Item Name</Label>
                <Input value={form.item_name} onChange={(e) => setForm((p) => ({ ...p, item_name: e.target.value }))} />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <textarea value={form.description} onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))} rows={2} className="w-full rounded-md border border-input px-3 py-2 text-sm resize-none" />
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label>Unit Price</Label>
                <Input type="number" step="0.01" value={form.unit_price} onChange={(e) => setForm((p) => ({ ...p, unit_price: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Price Type</Label>
                <select value={form.price_type} onChange={(e) => setForm((p) => ({ ...p, price_type: e.target.value }))} className="w-full rounded-md border border-input px-3 py-2 text-sm">
                  <option value="fixed">Fixed</option>
                  <option value="range">Range</option>
                  <option value="per_mile">Per Mile</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label>Sort Order</Label>
                <Input type="number" value={form.sort_order} onChange={(e) => setForm((p) => ({ ...p, sort_order: e.target.value }))} />
              </div>
            </div>
            <div className="space-y-2">
              <Label>FTC Disclosure Text</Label>
              <textarea value={form.ftc_disclosure_text} onChange={(e) => setForm((p) => ({ ...p, ftc_disclosure_text: e.target.value }))} rows={2} className="w-full rounded-md border border-input px-3 py-2 text-sm resize-none" placeholder="Required FTC disclosure language..." />
            </div>
            <div className="flex flex-wrap gap-6">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.is_ftc_required_disclosure} onChange={(e) => setForm((p) => ({ ...p, is_ftc_required_disclosure: e.target.checked }))} className="h-4 w-4 rounded border-gray-300" />
                <span className="text-sm">FTC Required Disclosure</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.is_required_by_law} onChange={(e) => setForm((p) => ({ ...p, is_required_by_law: e.target.checked }))} className="h-4 w-4 rounded border-gray-300" />
                <span className="text-sm">Required by Law</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.is_active} onChange={(e) => setForm((p) => ({ ...p, is_active: e.target.checked }))} className="h-4 w-4 rounded border-gray-300" />
                <span className="text-sm">Active</span>
              </label>
            </div>
            <div className="flex gap-2">
              <Button onClick={handleSave} disabled={!form.item_name}>
                {editingId ? "Update" : "Create"}
              </Button>
              <Button variant="outline" onClick={resetForm}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {Object.entries(grouped).map(([category, categoryItems]) => (
        <Card key={category}>
          <CardHeader>
            <CardTitle className="text-sm">{category}</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead className="text-right">Price</TableHead>
                  <TableHead>FTC</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {categoryItems.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-mono text-xs">{item.item_code}</TableCell>
                    <TableCell>
                      <div>
                        <span className="font-medium">{item.item_name}</span>
                        {item.description && (
                          <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
                            {item.description}
                          </p>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-right font-medium">{currency(item.unit_price)}</TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {item.is_ftc_required_disclosure && (
                          <Badge variant="outline">FTC</Badge>
                        )}
                        {item.is_required_by_law && (
                          <Badge variant="secondary">Req</Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                          item.is_active
                            ? "bg-green-100 text-green-700"
                            : "bg-gray-100 text-gray-500",
                        )}
                      >
                        {item.is_active ? "Active" : "Inactive"}
                      </span>
                    </TableCell>
                    <TableCell>
                      <button
                        onClick={() => handleEdit(item)}
                        className="text-xs text-blue-600 hover:underline"
                      >
                        Edit
                      </button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ))}

      {items.length === 0 && (
        <Card>
          <CardContent className="py-8 text-center">
            <p className="text-muted-foreground">
              No price list items. Click "Seed FTC Items" to populate the standard FTC-required items.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
