import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Package,
  Plus,
  Pencil,
  Trash2,
  DollarSign,
  Check,
  FlaskConical,
  BadgeCheck,
  MinusCircle,
} from "lucide-react";
import * as bundleService from "@/services/bundle-service";
import apiClient from "@/lib/api-client";
import type { ProductBundle, BundleCreate } from "@/types/bundle";

interface EquipmentProduct {
  id: string;
  name: string;
  sku: string | null;
  price: number | null;
  pricing_type: string;
}

// ---------------------------------------------------------------------------
// PricingSimulator — inline simulator for conditional pricing bundles
// ---------------------------------------------------------------------------
function PricingSimulator({ bundle }: { bundle: ProductBundle }) {
  const [hasVault, setHasVault] = useState(true);

  if (!bundle.has_conditional_pricing) return null;

  const activePrice = hasVault
    ? bundle.with_vault_price
    : bundle.standalone_price;
  const inactivePrice = hasVault
    ? bundle.standalone_price
    : bundle.with_vault_price;
  const savings =
    bundle.standalone_price !== null && bundle.with_vault_price !== null
      ? bundle.standalone_price - bundle.with_vault_price
      : null;

  return (
    <div className="mt-3 rounded-lg border border-dashed border-primary/30 bg-primary/5 p-3 space-y-2">
      <div className="flex items-center gap-2 text-xs font-semibold text-primary">
        <FlaskConical className="h-3.5 w-3.5" />
        Pricing Simulator
      </div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => setHasVault(true)}
          className={cn(
            "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
            hasVault
              ? "bg-green-100 text-green-800 ring-1 ring-green-300"
              : "bg-gray-100 text-gray-600 hover:bg-gray-200",
          )}
        >
          <BadgeCheck className="h-3.5 w-3.5" />
          With Vault
        </button>
        <button
          type="button"
          onClick={() => setHasVault(false)}
          className={cn(
            "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
            !hasVault
              ? "bg-amber-100 text-amber-800 ring-1 ring-amber-300"
              : "bg-gray-100 text-gray-600 hover:bg-gray-200",
          )}
        >
          <MinusCircle className="h-3.5 w-3.5" />
          Equipment Only
        </button>
      </div>
      <div className="flex items-center gap-4">
        <div>
          <span className="text-xs text-muted-foreground">Resolved price:</span>
          <span className="ml-1.5 text-lg font-bold">
            ${activePrice?.toFixed(2) ?? "—"}
          </span>
        </div>
        {savings !== null && savings > 0 && hasVault && (
          <span className="text-xs text-green-600 font-medium">
            Saves ${savings.toFixed(2)} vs standalone
          </span>
        )}
        {inactivePrice !== null && (
          <span className="text-xs text-muted-foreground">
            ({hasVault ? "standalone" : "w/ vault"}: ${inactivePrice.toFixed(2)})
          </span>
        )}
      </div>
    </div>
  );
}

export default function BundleManager() {
  const [bundles, setBundles] = useState<ProductBundle[]>([]);
  const [equipment, setEquipment] = useState<EquipmentProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  // Form state
  const [formName, setFormName] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formSku, setFormSku] = useState("");
  const [formPrice, setFormPrice] = useState("");
  const [selectedProducts, setSelectedProducts] = useState<Set<string>>(new Set());
  const [formConditionalPricing, setFormConditionalPricing] = useState(false);
  const [formWithVaultPrice, setFormWithVaultPrice] = useState("");
  const [formStandalonePrice, setFormStandalonePrice] = useState("");

  const loadData = useCallback(async () => {
    try {
      const [bundleData, productData] = await Promise.all([
        bundleService.listBundles(false),
        apiClient.get("/products", { params: { product_line: "Cemetery Equipment", per_page: 100 } }),
      ]);
      setBundles(bundleData);
      setEquipment(
        (productData.data.items || productData.data || []).map((p: any) => ({
          id: p.id,
          name: p.name,
          sku: p.sku,
          price: p.price ? parseFloat(p.price) : null,
          pricing_type: p.pricing_type || "rental",
        })),
      );
    } catch {
      toast.error("Failed to load bundle data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const resetForm = () => {
    setFormName("");
    setFormDescription("");
    setFormSku("");
    setFormPrice("");
    setSelectedProducts(new Set());
    setFormConditionalPricing(false);
    setFormWithVaultPrice("");
    setFormStandalonePrice("");
    setShowCreate(false);
    setEditingId(null);
  };

  const startEdit = (bundle: ProductBundle) => {
    setEditingId(bundle.id);
    setFormName(bundle.name);
    setFormDescription(bundle.description || "");
    setFormSku(bundle.sku || "");
    setFormPrice(bundle.price?.toString() || "");
    setSelectedProducts(new Set(bundle.components.map((c) => c.product_id)));
    setFormConditionalPricing(bundle.has_conditional_pricing || false);
    setFormWithVaultPrice(bundle.with_vault_price?.toString() || "");
    setFormStandalonePrice(bundle.standalone_price?.toString() || "");
    setShowCreate(true);
  };

  const handleSave = async () => {
    if (!formName.trim()) {
      toast.error("Bundle name is required");
      return;
    }
    if (selectedProducts.size === 0) {
      toast.error("Select at least one product");
      return;
    }

    const payload: BundleCreate = {
      name: formName.trim(),
      description: formDescription.trim() || undefined,
      sku: formSku.trim() || undefined,
      price: formConditionalPricing
        ? (formStandalonePrice ? parseFloat(formStandalonePrice) : undefined)
        : (formPrice ? parseFloat(formPrice) : undefined),
      components: [...selectedProducts].map((pid) => ({ product_id: pid, quantity: 1 })),
      has_conditional_pricing: formConditionalPricing,
      standalone_price: formConditionalPricing && formStandalonePrice ? parseFloat(formStandalonePrice) : undefined,
      with_vault_price: formConditionalPricing && formWithVaultPrice ? parseFloat(formWithVaultPrice) : undefined,
    };

    try {
      if (editingId) {
        await bundleService.updateBundle(editingId, payload);
        toast.success("Bundle updated");
      } else {
        await bundleService.createBundle(payload);
        toast.success("Bundle created");
      }
      resetForm();
      loadData();
    } catch {
      toast.error("Failed to save bundle");
    }
  };

  const handleDeactivate = async (id: string) => {
    try {
      await bundleService.deleteBundle(id);
      toast.success("Bundle deactivated");
      loadData();
    } catch {
      toast.error("Failed to deactivate bundle");
    }
  };

  const toggleProduct = (pid: string) => {
    setSelectedProducts((prev) => {
      const next = new Set(prev);
      if (next.has(pid)) next.delete(pid);
      else next.add(pid);
      return next;
    });
  };

  const selectedTotal = equipment
    .filter((e) => selectedProducts.has(e.id))
    .reduce((sum, e) => sum + (e.price || 0), 0);

  const priceParsed = formPrice ? parseFloat(formPrice) : null;
  const savings = priceParsed !== null && selectedTotal > 0 ? selectedTotal - priceParsed : null;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Package className="h-6 w-6" /> Equipment Bundles
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Create named equipment packages that combine multiple items at a bundle price.
          </p>
        </div>
        {!showCreate && (
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="mr-1 h-4 w-4" /> Create Bundle
          </Button>
        )}
      </div>

      {/* Create / Edit Form */}
      {showCreate && (
        <Card className="border-primary/30">
          <CardHeader>
            <CardTitle className="text-lg">
              {editingId ? "Edit Bundle" : "New Bundle"}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label>Bundle Name *</Label>
                <Input
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g., Full Equipment"
                />
              </div>
              <div className="space-y-1.5">
                <Label>SKU</Label>
                <Input
                  value={formSku}
                  onChange={(e) => setFormSku(e.target.value)}
                  placeholder="e.g., BUNDLE-FULL"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label>Description</Label>
              <Input
                value={formDescription}
                onChange={(e) => setFormDescription(e.target.value)}
                placeholder="Includes lowering device, tent, mats, and chairs"
              />
            </div>

            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label>Pricing</Label>
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="radio"
                      name="pricing_mode"
                      checked={!formConditionalPricing}
                      onChange={() => setFormConditionalPricing(false)}
                      className="accent-primary"
                    />
                    Same price regardless of order contents
                  </label>
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="radio"
                      name="pricing_mode"
                      checked={formConditionalPricing}
                      onChange={() => setFormConditionalPricing(true)}
                      className="accent-primary"
                    />
                    Different price when ordered with a vault
                  </label>
                </div>
              </div>

              {formConditionalPricing ? (
                <div className="space-y-2 rounded-lg border border-primary/20 bg-primary/5 p-3">
                  <div className="flex items-center gap-4">
                    <div className="space-y-1">
                      <Label className="text-xs">With vault order</Label>
                      <div className="relative">
                        <DollarSign className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                        <Input
                          type="number"
                          step="0.01"
                          min="0"
                          value={formWithVaultPrice}
                          onChange={(e) => setFormWithVaultPrice(e.target.value)}
                          className="pl-8 w-36"
                          placeholder="0.00"
                        />
                      </div>
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Equipment only</Label>
                      <div className="relative">
                        <DollarSign className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                        <Input
                          type="number"
                          step="0.01"
                          min="0"
                          value={formStandalonePrice}
                          onChange={(e) => setFormStandalonePrice(e.target.value)}
                          className="pl-8 w-36"
                          placeholder="0.00"
                        />
                      </div>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Burial vaults and urn vaults qualify for the lower price.
                  </p>
                  {formWithVaultPrice && formStandalonePrice &&
                    parseFloat(formWithVaultPrice) > parseFloat(formStandalonePrice) && (
                    <p className="text-xs text-amber-600">
                      Usually the vault order price is lower. Is this correct?
                    </p>
                  )}
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  <div className="relative">
                    <DollarSign className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      type="number"
                      step="0.01"
                      min="0"
                      value={formPrice}
                      onChange={(e) => setFormPrice(e.target.value)}
                      className="pl-8 w-36"
                      placeholder="0.00"
                    />
                  </div>
                  {savings !== null && savings > 0 && (
                    <span className="text-sm text-green-600 font-medium">
                      Saves ${savings.toFixed(2)} vs a la carte
                    </span>
                  )}
                  {savings !== null && savings < 0 && (
                    <span className="text-sm text-amber-600 font-medium">
                      ${Math.abs(savings).toFixed(2)} more than a la carte
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Product selector */}
            <div className="space-y-2">
              <Label>Equipment Included *</Label>
              {equipment.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No cemetery equipment products found. Create equipment products first in the catalog builder.
                </p>
              ) : (
                <div className="space-y-1.5">
                  {equipment.map((prod) => (
                    <button
                      key={prod.id}
                      type="button"
                      onClick={() => toggleProduct(prod.id)}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-lg border p-3 text-left transition-colors",
                        selectedProducts.has(prod.id)
                          ? "border-primary/30 bg-primary/5"
                          : "border-border hover:bg-muted/50",
                      )}
                    >
                      <div
                        className={cn(
                          "flex h-5 w-5 items-center justify-center rounded border",
                          selectedProducts.has(prod.id)
                            ? "border-primary bg-primary text-white"
                            : "border-muted-foreground/30",
                        )}
                      >
                        {selectedProducts.has(prod.id) && <Check className="h-3 w-3" />}
                      </div>
                      <span className="flex-1 text-sm font-medium">{prod.name}</span>
                      {prod.sku && (
                        <span className="text-xs text-muted-foreground font-mono">{prod.sku}</span>
                      )}
                      {prod.price !== null && (
                        <span className="text-sm font-mono">
                          ${prod.price.toFixed(2)}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}
              {selectedProducts.size > 0 && (
                <div className="text-sm text-muted-foreground">
                  {selectedProducts.size} item{selectedProducts.size !== 1 ? "s" : ""} selected
                  {selectedTotal > 0 && ` — a la carte total: $${selectedTotal.toFixed(2)}`}
                </div>
              )}
            </div>

            <div className="flex items-center gap-3 pt-2">
              <Button onClick={handleSave} disabled={!formName.trim() || selectedProducts.size === 0}>
                {editingId ? "Update Bundle" : "Create Bundle"}
              </Button>
              <Button variant="outline" onClick={resetForm}>
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Bundle List */}
      {bundles.length === 0 && !showCreate ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Package className="mx-auto h-12 w-12 text-muted-foreground/40" />
            <h3 className="mt-4 font-medium">No Equipment Bundles</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Create bundles to offer equipment packages at flat rates.
            </p>
            <Button className="mt-4" onClick={() => setShowCreate(true)}>
              <Plus className="mr-1 h-4 w-4" /> Create Your First Bundle
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {bundles.map((bundle) => (
            <Card
              key={bundle.id}
              className={cn(!bundle.is_active && "opacity-60")}
            >
              <CardContent className="p-5">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold">{bundle.name}</h3>
                      {bundle.sku && (
                        <span className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono text-muted-foreground">
                          {bundle.sku}
                        </span>
                      )}
                      {!bundle.is_active && (
                        <span className="rounded bg-red-100 px-1.5 py-0.5 text-xs text-red-700">
                          Inactive
                        </span>
                      )}
                      {bundle.source === "catalog_builder" && (
                        <span className="rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-700">
                          From Catalog Builder
                        </span>
                      )}
                    </div>
                    {bundle.description && (
                      <p className="mt-1 text-sm text-muted-foreground">{bundle.description}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="text-right mr-3">
                      {bundle.has_conditional_pricing ? (
                        <>
                          {bundle.with_vault_price !== null && (
                            <div className="text-sm">
                              <span className="text-muted-foreground text-xs">w/ vault: </span>
                              <span className="font-bold">${bundle.with_vault_price.toFixed(2)}</span>
                            </div>
                          )}
                          {bundle.standalone_price !== null && (
                            <div className="text-sm">
                              <span className="text-muted-foreground text-xs">standalone: </span>
                              <span className="font-bold">${bundle.standalone_price.toFixed(2)}</span>
                            </div>
                          )}
                        </>
                      ) : (
                        <>
                          {bundle.price !== null && (
                            <div className="text-lg font-bold">${bundle.price.toFixed(2)}</div>
                          )}
                          {bundle.savings !== null && bundle.savings > 0 && (
                            <div className="text-xs text-green-600">
                              Save ${bundle.savings.toFixed(2)}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => startEdit(bundle)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    {bundle.is_active && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive"
                        onClick={() => handleDeactivate(bundle.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </div>

                {/* Components */}
                <div className="mt-3 space-y-1">
                  {bundle.components.map((comp) => (
                    <div
                      key={comp.id}
                      className="flex items-center justify-between rounded bg-muted/50 px-3 py-1.5 text-sm"
                    >
                      <span>{comp.product_name}</span>
                      <span className="font-mono text-muted-foreground">
                        ${comp.product_price.toFixed(2)}
                      </span>
                    </div>
                  ))}
                  {bundle.components.length > 0 && (
                    <div className="flex items-center justify-between px-3 py-1.5 text-sm border-t mt-1 pt-2">
                      <span className="text-muted-foreground">
                        A la carte total ({bundle.component_count} items)
                      </span>
                      <span className="font-mono font-medium">
                        ${bundle.à_la_carte_total.toFixed(2)}
                      </span>
                    </div>
                  )}
                </div>

                {/* Pricing Simulator for conditional pricing bundles */}
                <PricingSimulator bundle={bundle} />
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
