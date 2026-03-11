import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { productService } from "@/services/product-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type { ProductCategory } from "@/types/product";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";

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
                  {categories
                    .filter((c) => c.is_active || c.id === categoryId)
                    .map((cat) => (
                      <option key={cat.id} value={cat.id}>
                        {cat.name}
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
