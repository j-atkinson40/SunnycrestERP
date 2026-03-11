import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PlusIcon, Trash2Icon } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { productService } from "@/services/product-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type { PriceTier, ProductCategory } from "@/types/product";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";

/** Build hierarchical options for a category <select> */
function buildCategoryOptions(
  categories: ProductCategory[],
  currentId?: string,
) {
  const active = categories.filter((c) => c.is_active || c.id === currentId);
  const parents = active.filter((c) => !c.parent_id);
  const childrenOf = (parentId: string) =>
    active.filter((c) => c.parent_id === parentId);

  const options: { id: string; label: string }[] = [];
  for (const p of parents) {
    options.push({ id: p.id, label: p.name });
    for (const c of childrenOf(p.id)) {
      options.push({ id: c.id, label: `  └ ${c.name}` });
    }
  }
  return options;
}

export default function ProductDetailPage() {
  const { productId } = useParams<{ productId: string }>();
  const { hasPermission } = useAuth();
  const canEdit = hasPermission("products.edit");

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Product fields
  const [name, setName] = useState("");
  const [sku, setSku] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [price, setPrice] = useState("");
  const [costPrice, setCostPrice] = useState("");
  const [unitOfMeasure, setUnitOfMeasure] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [isActive, setIsActive] = useState(true);

  // Categories for dropdown
  const [categories, setCategories] = useState<ProductCategory[]>([]);

  // Price tiers
  const [tiers, setTiers] = useState<PriceTier[]>([]);
  const [newTierQty, setNewTierQty] = useState("");
  const [newTierPrice, setNewTierPrice] = useState("");
  const [newTierLabel, setNewTierLabel] = useState("");
  const [tierError, setTierError] = useState("");

  const categoryOptions = useMemo(
    () => buildCategoryOptions(categories, categoryId),
    [categories, categoryId],
  );

  const loadData = useCallback(async () => {
    if (!productId) return;
    try {
      setLoading(true);
      const [product, cats] = await Promise.all([
        productService.getProduct(productId),
        productService.getCategories(true),
      ]);
      setName(product.name);
      setSku(product.sku || "");
      setDescription(product.description || "");
      setCategoryId(product.category_id || "");
      setPrice(product.price !== null ? String(product.price) : "");
      setCostPrice(
        product.cost_price !== null ? String(product.cost_price) : "",
      );
      setUnitOfMeasure(product.unit_of_measure || "");
      setImageUrl(product.image_url || "");
      setIsActive(product.is_active);
      setCategories(cats);
      setTiers(product.price_tiers || []);
    } catch {
      setError("Failed to load product");
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!productId) return;
    setError("");
    setSaving(true);
    try {
      const updated = await productService.updateProduct(productId, {
        name,
        sku: sku.trim() || undefined,
        description: description.trim() || undefined,
        category_id: categoryId || null,
        price: price.trim() ? parseFloat(price) : null,
        cost_price: costPrice.trim() ? parseFloat(costPrice) : null,
        unit_of_measure: unitOfMeasure.trim() || undefined,
        image_url: imageUrl.trim() || undefined,
      });
      setName(updated.name);
      setSku(updated.sku || "");
      setDescription(updated.description || "");
      setCategoryId(updated.category_id || "");
      setPrice(updated.price !== null ? String(updated.price) : "");
      setCostPrice(
        updated.cost_price !== null ? String(updated.cost_price) : "",
      );
      setUnitOfMeasure(updated.unit_of_measure || "");
      setImageUrl(updated.image_url || "");
      setIsActive(updated.is_active);
      toast.success("Product saved");
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Failed to save product"));
    } finally {
      setSaving(false);
    }
  }

  async function handleAddTier() {
    if (!productId) return;
    setTierError("");
    const qty = parseInt(newTierQty);
    const p = parseFloat(newTierPrice);
    if (!qty || qty < 1) {
      setTierError("Min quantity must be at least 1");
      return;
    }
    if (isNaN(p) || p < 0) {
      setTierError("Price must be a valid number");
      return;
    }
    try {
      const tier = await productService.createPriceTier(productId, {
        min_quantity: qty,
        price: p,
        label: newTierLabel.trim() || undefined,
      });
      setTiers([...tiers, tier].sort((a, b) => a.min_quantity - b.min_quantity));
      setNewTierQty("");
      setNewTierPrice("");
      setNewTierLabel("");
      toast.success("Pricing tier added");
    } catch (err: unknown) {
      setTierError(getApiErrorMessage(err, "Failed to add pricing tier"));
    }
  }

  async function handleDeleteTier(tierId: string) {
    if (!productId) return;
    try {
      await productService.deletePriceTier(productId, tierId);
      setTiers(tiers.filter((t) => t.id !== tierId));
      toast.success("Pricing tier removed");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to remove pricing tier"));
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-2xl space-y-6">
        <h1 className="text-2xl font-bold">Product Details</h1>
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">{name || "Product Details"}</h1>
          <Badge variant={isActive ? "default" : "destructive"}>
            {isActive ? "Active" : "Inactive"}
          </Badge>
        </div>
        <Link
          to="/products"
          className="text-sm text-muted-foreground hover:underline"
        >
          ← Back to Products
        </Link>
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        {/* Product Info */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold">Product Information</h2>
          <Separator className="my-4" />
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Product Name</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={!canEdit}
                required
                placeholder="e.g. Red Geranium"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>SKU</Label>
                <Input
                  value={sku}
                  onChange={(e) => setSku(e.target.value)}
                  disabled={!canEdit}
                  placeholder="e.g. GER-RED-01"
                />
              </div>
              <div className="space-y-2">
                <Label>Category</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm disabled:cursor-not-allowed disabled:opacity-50"
                  value={categoryId}
                  onChange={(e) => setCategoryId(e.target.value)}
                  disabled={!canEdit}
                >
                  <option value="">No category</option>
                  {categoryOptions.map((opt) => (
                    <option key={opt.id} value={opt.id}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={!canEdit}
                rows={3}
                className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs transition-[color,box-shadow] focus-visible:border-ring focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
                placeholder="Product description..."
              />
            </div>
            <div className="space-y-2">
              <Label>Unit of Measure</Label>
              <Input
                value={unitOfMeasure}
                onChange={(e) => setUnitOfMeasure(e.target.value)}
                disabled={!canEdit}
                placeholder="e.g. each, flat, tray, lb"
              />
            </div>
          </div>
        </Card>

        {/* Pricing */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold">Pricing</h2>
          <Separator className="my-4" />
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Selling Price</Label>
              <Input
                type="number"
                step="0.01"
                min="0"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                disabled={!canEdit}
                placeholder="0.00"
              />
            </div>
            <div className="space-y-2">
              <Label>Cost Price</Label>
              <Input
                type="number"
                step="0.01"
                min="0"
                value={costPrice}
                onChange={(e) => setCostPrice(e.target.value)}
                disabled={!canEdit}
                placeholder="0.00"
              />
            </div>
          </div>
          {price && costPrice && (
            <p className="mt-3 text-sm text-muted-foreground">
              Margin: $
              {(parseFloat(price) - parseFloat(costPrice)).toFixed(2)} (
              {(
                ((parseFloat(price) - parseFloat(costPrice)) /
                  parseFloat(price)) *
                100
              ).toFixed(1)}
              %)
            </p>
          )}
        </Card>

        {/* Volume Pricing (Tiers) */}
        {canEdit && (
          <Card className="p-6">
            <h2 className="text-lg font-semibold">Volume Pricing</h2>
            <Separator className="my-4" />
            {tierError && (
              <div className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                {tierError}
              </div>
            )}
            {tiers.length > 0 && (
              <div className="mb-4 rounded-md border">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="px-3 py-2 text-left font-medium">Min Qty</th>
                      <th className="px-3 py-2 text-left font-medium">Price</th>
                      <th className="px-3 py-2 text-left font-medium">Label</th>
                      <th className="px-3 py-2 text-right font-medium w-16"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {tiers.map((tier) => (
                      <tr key={tier.id} className="border-b last:border-0">
                        <td className="px-3 py-2">{tier.min_quantity}+</td>
                        <td className="px-3 py-2">
                          ${Number(tier.price).toFixed(2)}
                        </td>
                        <td className="px-3 py-2 text-muted-foreground">
                          {tier.label || "—"}
                        </td>
                        <td className="px-3 py-2 text-right">
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-xs"
                            onClick={() => handleDeleteTier(tier.id)}
                          >
                            <Trash2Icon className="size-3.5 text-destructive" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="flex items-end gap-2">
              <div className="space-y-1 w-24">
                <Label className="text-xs">Min Qty</Label>
                <Input
                  type="number"
                  min="1"
                  value={newTierQty}
                  onChange={(e) => setNewTierQty(e.target.value)}
                  placeholder="10"
                />
              </div>
              <div className="space-y-1 w-28">
                <Label className="text-xs">Price</Label>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={newTierPrice}
                  onChange={(e) => setNewTierPrice(e.target.value)}
                  placeholder="0.00"
                />
              </div>
              <div className="space-y-1 flex-1">
                <Label className="text-xs">Label (optional)</Label>
                <Input
                  value={newTierLabel}
                  onChange={(e) => setNewTierLabel(e.target.value)}
                  placeholder="e.g. Wholesale"
                />
              </div>
              <Button
                type="button"
                variant="outline"
                size="default"
                onClick={handleAddTier}
                disabled={!newTierQty || !newTierPrice}
              >
                <PlusIcon className="mr-1 size-4" />
                Add
              </Button>
            </div>
            {tiers.length === 0 && (
              <p className="mt-3 text-xs text-muted-foreground">
                Add volume pricing tiers for quantity-based discounts.
              </p>
            )}
          </Card>
        )}

        {/* Image URL */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold">Image</h2>
          <Separator className="my-4" />
          <div className="space-y-2">
            <Label>Image URL</Label>
            <Input
              value={imageUrl}
              onChange={(e) => setImageUrl(e.target.value)}
              disabled={!canEdit}
              placeholder="https://example.com/image.jpg"
            />
            <p className="text-xs text-muted-foreground">
              Paste an external image URL. Image upload support coming soon.
            </p>
          </div>
        </Card>

        {canEdit && (
          <div className="flex justify-end">
            <Button type="submit" disabled={saving || !name.trim()}>
              {saving ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        )}
      </form>
    </div>
  );
}
