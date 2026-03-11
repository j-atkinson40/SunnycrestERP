import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { SparklesIcon, UploadIcon, XIcon } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { productService } from "@/services/product-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type { ImportResult, Product, ProductCategory } from "@/types/product";
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
import { AICommandBar } from "@/components/ai-command-bar";

const AI_SYSTEM_PROMPT = `You are a product catalog assistant for a nursery/garden center ERP system. The user will describe a product they are looking for in natural language. You have access to the full product catalog provided in the context data.

Your job is to find products that match the user's description. Match on product name, description, category, SKU, or any relevant attribute. Be flexible with spelling, synonyms, and partial matches.

Return a JSON object with:
- matchedProducts: array of product IDs that match the user's query
- confidence: "high", "medium", or "low" indicating how confident you are in the matches
- clarificationNeeded: boolean, true if the query was too vague or ambiguous to return useful results
- clarificationMessage: string (only when clarificationNeeded is true) — a follow-up question to help narrow down the search`;

/** Build hierarchical options for a category <select> */
function buildCategoryOptions(
  categories: ProductCategory[],
  activeOnly = true,
  currentId?: string,
) {
  const active = activeOnly
    ? categories.filter((c) => c.is_active || c.id === currentId)
    : categories;
  const parents = active.filter((c) => !c.parent_id);
  const childrenOf = (parentId: string) =>
    active.filter((c) => c.parent_id === parentId);

  const options: { id: string; label: string; isParent: boolean }[] = [];
  for (const p of parents) {
    options.push({ id: p.id, label: p.name, isParent: true });
    for (const c of childrenOf(p.id)) {
      options.push({ id: c.id, label: `  └ ${c.name}`, isParent: false });
    }
  }
  // Include categories that are children of inactive parents (orphans)
  const orphans = active.filter(
    (c) => c.parent_id && !active.some((p) => p.id === c.parent_id),
  );
  for (const o of orphans) {
    options.push({ id: o.id, label: o.name, isParent: false });
  }
  return options;
}

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

  // All products for AI context (loaded once, unpaginated)
  const [allProducts, setAllProducts] = useState<Product[]>([]);

  // AI search state
  const [aiMatchedIds, setAiMatchedIds] = useState<Set<string> | null>(null);
  const [aiConfidence, setAiConfidence] = useState<string | null>(null);
  const [aiMessage, setAiMessage] = useState<string | null>(null);

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
  const [newCatParentId, setNewCatParentId] = useState("");
  const [catError, setCatError] = useState("");

  // Import CSV dialog
  const [importOpen, setImportOpen] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [importError, setImportError] = useState("");

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

  // Load all products once for AI context
  const loadAllProducts = useCallback(async () => {
    try {
      const data = await productService.getProducts(1, 1000);
      setAllProducts(data.items);
    } catch {
      // Silent — AI search just won't have context
    }
  }, []);

  useEffect(() => {
    loadCategories();
  }, [loadCategories]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  useEffect(() => {
    loadAllProducts();
  }, [loadAllProducts]);

  // Build simplified catalog for AI context
  const aiContextData = useMemo(
    () => ({
      products: allProducts.map((p) => ({
        id: p.id,
        name: p.name,
        sku: p.sku,
        description: p.description,
        category: p.category_name,
        price: p.price,
        unit: p.unit_of_measure,
        active: p.is_active,
      })),
    }),
    [allProducts],
  );

  // Category hierarchy helpers
  const categoryOptions = useMemo(
    () => buildCategoryOptions(categories, true),
    [categories],
  );

  const rootCategories = useMemo(
    () => categories.filter((c) => !c.parent_id),
    [categories],
  );

  // Handle AI search result
  function handleAiResult(data: Record<string, unknown>) {
    const clarificationNeeded = data.clarificationNeeded as boolean;
    if (clarificationNeeded) {
      const message =
        (data.clarificationMessage as string) ||
        "Could you be more specific about what you're looking for?";
      setAiMessage(message);
      setAiMatchedIds(null);
      setAiConfidence(null);
      return;
    }

    const matchedProducts = (data.matchedProducts as string[]) || [];
    const confidence = (data.confidence as string) || "medium";

    if (matchedProducts.length === 0) {
      setAiMessage("No matching products found. Try a different description.");
      setAiMatchedIds(null);
      setAiConfidence(null);
      return;
    }

    setAiMatchedIds(new Set(matchedProducts));
    setAiConfidence(confidence);
    setAiMessage(null);
  }

  // Clear AI search
  function clearAiSearch() {
    setAiMatchedIds(null);
    setAiConfidence(null);
    setAiMessage(null);
  }

  // When AI search is active, show matched products from allProducts
  // Otherwise show the normal paginated products
  const displayProducts = aiMatchedIds
    ? allProducts.filter((p) => aiMatchedIds.has(p.id))
    : products;

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
      loadAllProducts();
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
      loadAllProducts();
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
        parent_id: newCatParentId || undefined,
      });
      setNewCatName("");
      setNewCatDescription("");
      setNewCatParentId("");
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

  async function handleImport() {
    if (!importFile) return;
    setImporting(true);
    setImportError("");
    setImportResult(null);
    try {
      const result = await productService.importProducts(importFile);
      setImportResult(result);
      if (result.created > 0) {
        toast.success(`Imported ${result.created} products`);
        loadProducts();
        loadAllProducts();
        loadCategories();
      }
    } catch (err: unknown) {
      setImportError(getApiErrorMessage(err, "Import failed"));
    } finally {
      setImporting(false);
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
                    Create and manage product categories and subcategories.
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
                    <Label>Parent Category (optional)</Label>
                    <select
                      className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                      value={newCatParentId}
                      onChange={(e) => setNewCatParentId(e.target.value)}
                    >
                      <option value="">None (top-level category)</option>
                      {rootCategories
                        .filter((c) => c.is_active)
                        .map((cat) => (
                          <option key={cat.id} value={cat.id}>
                            {cat.name}
                          </option>
                        ))}
                    </select>
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
                      <div className="space-y-1">
                        {categories
                          .filter((c) => !c.parent_id)
                          .map((cat) => (
                            <div key={cat.id}>
                              <div className="flex items-center justify-between rounded-md border px-3 py-2">
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
                                    onClick={() =>
                                      handleToggleCategoryActive(cat)
                                    }
                                  >
                                    {cat.is_active ? "Deactivate" : "Activate"}
                                  </Button>
                                )}
                              </div>
                              {/* Subcategories */}
                              {categories
                                .filter((sc) => sc.parent_id === cat.id)
                                .map((sub) => (
                                  <div
                                    key={sub.id}
                                    className="ml-6 flex items-center justify-between rounded-md border px-3 py-1.5 mt-1"
                                  >
                                    <div>
                                      <span className="text-sm text-muted-foreground">
                                        └{" "}
                                      </span>
                                      <span className="text-sm">{sub.name}</span>
                                      {!sub.is_active && (
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
                                        size="xs"
                                        onClick={() =>
                                          handleToggleCategoryActive(sub)
                                        }
                                      >
                                        {sub.is_active
                                          ? "Deactivate"
                                          : "Activate"}
                                      </Button>
                                    )}
                                  </div>
                                ))}
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
            <Dialog
              open={importOpen}
              onOpenChange={(open) => {
                setImportOpen(open);
                if (!open) {
                  setImportFile(null);
                  setImportResult(null);
                  setImportError("");
                }
              }}
            >
              <DialogTrigger render={<Button variant="outline" />}>
                <UploadIcon className="mr-1 size-4" />
                Import CSV
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Import Products from CSV</DialogTitle>
                  <DialogDescription>
                    Upload a CSV file to bulk-create products. Categories will be
                    auto-created if they don't exist.
                  </DialogDescription>
                </DialogHeader>
                {importError && (
                  <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                    {importError}
                  </div>
                )}
                {!importResult ? (
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label>CSV File</Label>
                      <Input
                        type="file"
                        accept=".csv"
                        onChange={(e) =>
                          setImportFile(e.target.files?.[0] || null)
                        }
                      />
                    </div>
                    <div className="rounded-md bg-muted p-3">
                      <p className="text-xs font-medium text-muted-foreground mb-1">
                        Expected columns:
                      </p>
                      <p className="text-xs text-muted-foreground">
                        name (required), sku, description, category, price,
                        cost_price, unit_of_measure
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Column headers are flexible — e.g. "Product Name", "Item
                        Number", "UOM" all work.
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="flex gap-4">
                      <div className="rounded-md bg-green-50 dark:bg-green-950/30 p-3 flex-1 text-center">
                        <p className="text-2xl font-bold text-green-700 dark:text-green-400">
                          {importResult.created}
                        </p>
                        <p className="text-xs text-green-600 dark:text-green-500">
                          Created
                        </p>
                      </div>
                      {importResult.skipped > 0 && (
                        <div className="rounded-md bg-yellow-50 dark:bg-yellow-950/30 p-3 flex-1 text-center">
                          <p className="text-2xl font-bold text-yellow-700 dark:text-yellow-400">
                            {importResult.skipped}
                          </p>
                          <p className="text-xs text-yellow-600 dark:text-yellow-500">
                            Skipped
                          </p>
                        </div>
                      )}
                    </div>
                    {importResult.errors.length > 0 && (
                      <div className="space-y-1">
                        <p className="text-sm font-medium text-destructive">
                          Errors:
                        </p>
                        <div className="max-h-40 overflow-y-auto rounded-md border p-2 text-xs space-y-0.5">
                          {importResult.errors.map((err, i) => (
                            <p key={i} className="text-muted-foreground">
                              <span className="font-medium">Row {err.row}:</span>{" "}
                              {err.message}
                            </p>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
                <DialogFooter>
                  {!importResult ? (
                    <>
                      <Button
                        variant="outline"
                        onClick={() => setImportOpen(false)}
                      >
                        Cancel
                      </Button>
                      <Button
                        onClick={handleImport}
                        disabled={!importFile || importing}
                      >
                        {importing ? "Importing..." : "Upload & Import"}
                      </Button>
                    </>
                  ) : (
                    <Button onClick={() => setImportOpen(false)}>Done</Button>
                  )}
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

      {/* AI-powered natural language search */}
      <AICommandBar
        placeholder="Search products by description, category, or specifications..."
        systemPrompt={AI_SYSTEM_PROMPT}
        contextData={aiContextData}
        onResult={handleAiResult}
        disabled={allProducts.length === 0}
      />

      {/* AI clarification message */}
      {aiMessage && (
        <div className="flex items-start gap-3 rounded-md border border-blue-200 bg-blue-50 p-3 dark:border-blue-900 dark:bg-blue-950">
          <SparklesIcon className="mt-0.5 size-4 shrink-0 text-blue-600 dark:text-blue-400" />
          <p className="flex-1 text-sm text-blue-800 dark:text-blue-200">
            {aiMessage}
          </p>
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={clearAiSearch}
            className="shrink-0"
          >
            <XIcon className="size-3" />
          </Button>
        </div>
      )}

      {/* AI search results banner */}
      {aiMatchedIds && (
        <div className="flex items-center gap-3 rounded-md border border-green-200 bg-green-50 p-3 dark:border-green-900 dark:bg-green-950">
          <SparklesIcon className="size-4 shrink-0 text-green-600 dark:text-green-400" />
          <span className="flex-1 text-sm text-green-800 dark:text-green-200">
            Found {aiMatchedIds.size} matching{" "}
            {aiMatchedIds.size === 1 ? "product" : "products"}
            {aiConfidence && (
              <Badge variant="secondary" className="ml-2">
                {aiConfidence} confidence
              </Badge>
            )}
          </span>
          <Button variant="ghost" size="sm" onClick={clearAiSearch}>
            <XIcon className="mr-1 size-3" />
            Clear
          </Button>
        </div>
      )}

      {/* Standard filters — hidden during AI search */}
      {!aiMatchedIds && (
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
            {categoryOptions.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      )}

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
            {loading && !aiMatchedIds ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : displayProducts.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  {aiMatchedIds
                    ? "No matching products found"
                    : "No products found"}
                </TableCell>
              </TableRow>
            ) : (
              displayProducts.map((product) => (
                <TableRow
                  key={product.id}
                  className={
                    aiMatchedIds?.has(product.id)
                      ? "bg-green-50 dark:bg-green-950/30"
                      : undefined
                  }
                >
                  <TableCell className="font-medium">
                    <Link
                      to={`/products/${product.id}`}
                      className="hover:underline"
                    >
                      {product.name}
                    </Link>
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

      {/* Pagination — hidden during AI search */}
      {!aiMatchedIds && totalPages > 1 && (
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
