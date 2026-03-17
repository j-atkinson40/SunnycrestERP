import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { bomService } from "@/services/bom-service";
import { productService } from "@/services/product-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type { BOMListItem, BOMStatus } from "@/types/bom";
import type { Product } from "@/types/product";
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

function statusBadge(status: BOMStatus) {
  switch (status) {
    case "draft":
      return <Badge variant="outline">Draft</Badge>;
    case "active":
      return <Badge variant="default">Active</Badge>;
    case "archived":
      return <Badge variant="secondary">Archived</Badge>;
  }
}

function formatCurrency(value: number | null): string {
  if (value === null || value === undefined) return "—";
  return `$${Number(value).toFixed(2)}`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString();
}

export default function BOMListPage() {
  const { hasPermission } = useAuth();
  const canCreate = hasPermission("inventory.create");
  const canEdit = hasPermission("inventory.edit");
  const canDelete = hasPermission("inventory.delete");

  // BOM list state
  const [boms, setBoms] = useState<BOMListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterProduct, setFilterProduct] = useState("");
  const [loading, setLoading] = useState(true);

  // Products for filter / create dialog
  const [products, setProducts] = useState<Product[]>([]);

  // Create BOM dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [newBOM, setNewBOM] = useState({ product_id: "", notes: "" });
  const [createError, setCreateError] = useState("");

  const loadProducts = useCallback(async () => {
    try {
      const data = await productService.getProducts(1, 1000);
      setProducts(data.items);
    } catch {
      // Silent — products just won't be available for filter
    }
  }, []);

  const loadBOMs = useCallback(async () => {
    setLoading(true);
    try {
      const data = await bomService.listBOMs(
        page,
        20,
        search || undefined,
        filterStatus || undefined,
        filterProduct || undefined,
      );
      setBoms(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page, search, filterStatus, filterProduct]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  useEffect(() => {
    loadBOMs();
  }, [loadBOMs]);

  async function handleCreateBOM() {
    setCreateError("");
    try {
      const bom = await bomService.createBOM({
        product_id: newBOM.product_id,
        notes: newBOM.notes.trim() || undefined,
      });
      setCreateOpen(false);
      setNewBOM({ product_id: "", notes: "" });
      toast.success("BOM created");
      // Navigate to the new BOM detail page
      window.location.href = `/bom/${bom.id}`;
    } catch (err: unknown) {
      setCreateError(getApiErrorMessage(err, "Failed to create BOM"));
    }
  }

  async function handleActivate(bom: BOMListItem) {
    try {
      await bomService.activateBOM(bom.id);
      toast.success("BOM activated");
      loadBOMs();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to activate BOM"));
    }
  }

  async function handleArchive(bom: BOMListItem) {
    try {
      await bomService.archiveBOM(bom.id);
      toast.success("BOM archived");
      loadBOMs();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to archive BOM"));
    }
  }

  async function handleClone(bom: BOMListItem) {
    try {
      const cloned = await bomService.cloneBOM(bom.id);
      toast.success(`BOM cloned as v${cloned.version}`);
      loadBOMs();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to clone BOM"));
    }
  }

  async function handleDelete(bom: BOMListItem) {
    if (!confirm(`Delete BOM for "${bom.product_name}" v${bom.version}?`)) return;
    try {
      await bomService.deleteBOM(bom.id);
      toast.success("BOM deleted");
      loadBOMs();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to delete BOM"));
    }
  }

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Bill of Materials</h1>
          <p className="text-muted-foreground">{total} total BOMs</p>
        </div>
        <div className="flex gap-2">
          {canCreate && (
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
              <DialogTrigger render={<Button />}>Create BOM</DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create New BOM</DialogTitle>
                  <DialogDescription>
                    Create a new bill of materials for a product.
                  </DialogDescription>
                </DialogHeader>
                {createError && (
                  <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                    {createError}
                  </div>
                )}
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>Product</Label>
                    <select
                      className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                      value={newBOM.product_id}
                      onChange={(e) =>
                        setNewBOM({ ...newBOM, product_id: e.target.value })
                      }
                    >
                      <option value="">Select a product...</option>
                      {products
                        .filter((p) => p.is_active)
                        .map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name}
                            {p.sku ? ` (${p.sku})` : ""}
                          </option>
                        ))}
                    </select>
                  </div>
                  <div className="space-y-2">
                    <Label>Notes (optional)</Label>
                    <Input
                      value={newBOM.notes}
                      onChange={(e) =>
                        setNewBOM({ ...newBOM, notes: e.target.value })
                      }
                      placeholder="Optional notes about this BOM"
                    />
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
                    onClick={handleCreateBOM}
                    disabled={!newBOM.product_id}
                  >
                    Create BOM
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2">
        <Input
          placeholder="Search by product name..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="max-w-sm"
        />
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={filterStatus}
          onChange={(e) => {
            setFilterStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="active">Active</option>
          <option value="archived">Archived</option>
        </select>
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={filterProduct}
          onChange={(e) => {
            setFilterProduct(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Products</option>
          {products
            .filter((p) => p.is_active)
            .map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
        </select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Product Name</TableHead>
              <TableHead>Version</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Lines</TableHead>
              <TableHead>Cost Total</TableHead>
              <TableHead>Created</TableHead>
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
            ) : boms.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  No BOMs found
                </TableCell>
              </TableRow>
            ) : (
              boms.map((bom) => (
                <TableRow key={bom.id}>
                  <TableCell className="font-medium">
                    <Link
                      to={`/bom/${bom.id}`}
                      className="hover:underline"
                    >
                      {bom.product_name}
                    </Link>
                    {bom.product_sku && (
                      <span className="ml-2 text-xs text-muted-foreground">
                        {bom.product_sku}
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">v{bom.version}</Badge>
                  </TableCell>
                  <TableCell>{statusBadge(bom.status)}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {bom.line_count}
                  </TableCell>
                  <TableCell>{formatCurrency(bom.cost_total)}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(bom.created_at)}
                  </TableCell>
                  <TableCell className="text-right space-x-1">
                    <Link to={`/bom/${bom.id}`}>
                      <Button variant="ghost" size="sm">
                        View
                      </Button>
                    </Link>
                    {canEdit && bom.status === "draft" && (
                      <Link to={`/bom/${bom.id}`}>
                        <Button variant="ghost" size="sm">
                          Edit
                        </Button>
                      </Link>
                    )}
                    {canEdit && bom.status === "draft" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleActivate(bom)}
                      >
                        Activate
                      </Button>
                    )}
                    {canEdit && bom.status === "active" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleArchive(bom)}
                      >
                        Archive
                      </Button>
                    )}
                    {canCreate && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleClone(bom)}
                      >
                        Clone
                      </Button>
                    )}
                    {canDelete && bom.status === "draft" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(bom)}
                      >
                        Delete
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
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
