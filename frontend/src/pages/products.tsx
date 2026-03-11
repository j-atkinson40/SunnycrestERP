import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { productService } from "@/services/product-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type { Product, ProductCategory } from "@/types/product";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
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

export default function ProductsPage() {
  const { hasPermission } = useAuth();
  const canCreate = hasPermission("products.create");
  const canEdit = hasPermission("products.edit");
  const canDelete = hasPermission("products.delete");

  // Product list state
  const [products, setProducts] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [filterCategory, setFilterCategory] = useState("");
  const [loading, setLoading] = useState(true);

  // Categories
  const [categories, setCategories] = useState<ProductCategory[]>([]);

  // Create product dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [newProduct, setNewProduct] = useState({
    name: "",
    sku: "",
    description: "",
    category_id: "",
    price: "",
    cost_price: "",
    unit_of_measure: "",
  });
  const [createError, setCreateError] = useState("");

  // Manage categories dialog
  const [catDialogOpen, setCatDialogOpen] = useState(false);
  const [newCatName, setNewCatName] = useState("");
  const [newCatDescription, setNewCatDescription] = useState("");
  const [catError, setCatError] = useState("");

  const loadCategories = useCallback(async () => {
    try {
      const data = await productService.getCategories(true);
      setCategories(data);
    } catch {
      // Categories may fail if permissions not ready
    }
  }, []);

  const loadProducts = useCallback(async () => {
    setLoading(true);
    try {
      const data = await productService.getProducts(
        page,
        20,
        search || undefined,
        filterCategory || undefined,
      );
      setProducts(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page, search, filterCategory]);

  useEffect(() => {
    loadCategories();
  }, [loadCategories]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  async function handleCreateProduct() {
    setCreateError("");
    try {
      await productService.createProduct({
        name: newProduct.name,
        sku: newProduct.sku.trim() || undefined,
        description: newProduct.description.trim() || undefined,
        category_id: newProduct.category_id || undefined,
        price: newProduct.price.trim()
          ? parseFloat(newProduct.price)
          : undefined,
        cost_price: newProduct.cost_price.trim()
          ? parseFloat(newProduct.cost_price)
          : undefined,
        unit_of_measure: newProduct.unit_of_measure.trim() || undefined,
      });
      setCreateOpen(false);
      setNewProduct({
        name: "",
        sku: "",
        description: "",
        category_id: "",
        price: "",
        cost_price: "",
        unit_of_measure: "",
      });
      toast.success("Product created");
      loadProducts();
    } catch (err: unknown) {
      setCreateError(getApiErrorMessage(err, "Failed to create product"));
    }
  }

  async function handleToggleActive(product: Product) {
    try {
      if (product.is_active) {
        await productService.deleteProduct(product.id);
        toast.success("Product deactivated");
      } else {
        await productService.updateProduct(product.id, { is_active: true });
        toast.success("Product activated");
      }
      loadProducts();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to update product"));
    }
  }

  async function handleCreateCategory() {
    setCatError("");
    try {
      await productService.createCategory({
        name: newCatName.trim(),
        description: newCatDescription.trim() || undefined,
      });
      setNewCatName("");
      setNewCatDescription("");
      toast.success("Category created");
      loadCategories();
    } catch (err: unknown) {
      setCatError(getApiErrorMessage(err, "Failed to create category"));
    }
  }

  async function handleToggleCategoryActive(cat: ProductCategory) {
    try {
      if (cat.is_active) {
        await productService.deleteCategory(cat.id);
        toast.success("Category deactivated");
      } else {
        await productService.updateCategory(cat.id, { is_active: true });
        toast.success("Category activated");
      }
      loadCategories();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to update category"));
    }
  }

  function formatPrice(value: number | null): string {
    if (value === null || value === undefined) return "—";
    return `$${Number(value).toFixed(2)}`;
  }

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Products</h1>
          <p className="text-muted-foreground">{total} total products</p>
        </div>
        <div className="flex gap-2">
          {canCreate && (
            <Dialog open={catDialogOpen} onOpenChange={setCatDialogOpen}>
              <DialogTrigger render={<Button variant="outline" />}>
                Manage Categories
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Manage Categories</DialogTitle>
                  <DialogDescription>
                    Create and manage product categories.
                  </DialogDescription>
                </DialogHeader>
                {catError && (
                  <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                    {catError}
                  </div>
                )}
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>Category Name</Label>
                    <Input
                      value={newCatName}
                      onChange={(e) => setNewCatName(e.target.value)}
                      placeholder="e.g. Annuals"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Description (optional)</Label>
                    <Input
                      value={newCatDescription}
                      onChange={(e) => setNewCatDescription(e.target.value)}
                      placeholder="Optional description"
                    />
                  </div>
                  <Button
                    onClick={handleCreateCategory}
                    disabled={!newCatName.trim()}
                    className="w-full"
                  >
                    Add Category
                  </Button>
                  {categories.length > 0 && (
                    <div className="border-t pt-4">
                      <p className="mb-2 text-sm font-medium text-muted-foreground">
                        Existing Categories
                      </p>
                      <div className="space-y-2">
                        {categories.map((cat) => (
                          <div
                            key={cat.id}
                            className="flex items-center justify-between rounded-md border px-3 py-2"
                          >
                            <div>
                              <span className="text-sm font-medium">
                                {cat.name}
                              </span>
                              {!cat.is_active && (
                                <Badge
                                  variant="destructive"
                                  className="ml-2"
                                >
                                  Inactive
                                </Badge>
                              )}
                            </div>
                            {canDelete && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleToggleCategoryActive(cat)}
                              >
                                {cat.is_active ? "Deactivate" : "Activate"}
                              </Button>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => setCatDialogOpen(false)}
                  >
                    Close
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}
          {canCreate && (
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
              <DialogTrigger render={<Button />}>Add Product</DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create New Product</DialogTitle>
                  <DialogDescription>
                    Add a new product to the catalog.
                  </DialogDescription>
                </DialogHeader>
                {createError && (
                  <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                    {createError}
                  </div>
                )}
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>Product Name</Label>
                    <Input
                      value={newProduct.name}
                      onChange={(e) =>
                        setNewProduct({ ...newProduct, name: e.target.value })
                      }
                      placeholder="e.g. Red Geranium"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>SKU</Label>
                      <Input
                        value={newProduct.sku}
                        onChange={(e) =>
                          setNewProduct({ ...newProduct, sku: e.target.value })
                        }
                        placeholder="e.g. GER-RED-01"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Category</Label>
                      <select
                        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                        value={newProduct.category_id}
                        onChange={(e) =>
                          setNewProduct({
                            ...newProduct,
                            category_id: e.target.value,
                          })
                        }
                      >
                        <option value="">No category</option>
                        {categories
                          .filter((c) => c.is_active)
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
                    <Input
                      value={newProduct.description}
                      onChange={(e) =>
                        setNewProduct({
                          ...newProduct,
                          description: e.target.value,
                        })
                      }
                      placeholder="Optional description"
                    />
                  </div>
                  <div className="grid grid-cols-3 gap-4">
                    <div className="space-y-2">
                      <Label>Price</Label>
                      <Input
                        type="number"
                        step="0.01"
                        min="0"
                        value={newProduct.price}
                        onChange={(e) =>
                          setNewProduct({
                            ...newProduct,
                            price: e.target.value,
                          })
                        }
                        placeholder="0.00"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Cost Price</Label>
                      <Input
                        type="number"
                        step="0.01"
                        min="0"
                        value={newProduct.cost_price}
                        onChange={(e) =>
                          setNewProduct({
                            ...newProduct,
                            cost_price: e.target.value,
                          })
                        }
                        placeholder="0.00"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Unit</Label>
                      <Input
                        value={newProduct.unit_of_measure}
                        onChange={(e) =>
                          setNewProduct({
                            ...newProduct,
                            unit_of_measure: e.target.value,
                          })
                        }
                        placeholder="each"
                      />
                    </div>
                  </div>
                </div>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => setCreateOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleCreateProduct}
                    disabled={!newProduct.name.trim()}
                  >
                    Create Product
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Input
          placeholder="Search products..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="max-w-sm"
        />
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={filterCategory}
          onChange={(e) => {
            setFilterCategory(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Categories</option>
          {categories
            .filter((c) => c.is_active)
            .map((cat) => (
              <option key={cat.id} value={cat.id}>
                {cat.name}
              </option>
            ))}
        </select>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>SKU</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Price</TableHead>
              <TableHead>Unit</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : products.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  No products found
                </TableCell>
              </TableRow>
            ) : (
              products.map((product) => (
                <TableRow key={product.id}>
                  <TableCell className="font-medium">
                    {product.name}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {product.sku || "—"}
                  </TableCell>
                  <TableCell>
                    {product.category_name ? (
                      <Badge variant="secondary">
                        {product.category_name}
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell>{formatPrice(product.price)}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {product.unit_of_measure || "—"}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={product.is_active ? "default" : "destructive"}
                    >
                      {product.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right space-x-1">
                    {canEdit && (
                      <Link to={`/products/${product.id}`}>
                        <Button variant="ghost" size="sm">
                          Edit
                        </Button>
                      </Link>
                    )}
                    {canDelete && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleToggleActive(product)}
                      >
                        {product.is_active ? "Deactivate" : "Activate"}
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
