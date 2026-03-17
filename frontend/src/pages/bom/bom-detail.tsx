import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeftIcon } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { bomService } from "@/services/bom-service";
import { productService } from "@/services/product-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type { BOM, BOMLine } from "@/types/bom";
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
} from "@/components/ui/dialog";
import { toast } from "sonner";

function statusBadge(status: string) {
  switch (status) {
    case "draft":
      return <Badge variant="outline">Draft</Badge>;
    case "active":
      return <Badge variant="default">Active</Badge>;
    case "archived":
      return <Badge variant="secondary">Archived</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function formatCurrency(value: number | null): string {
  if (value === null || value === undefined) return "—";
  return `$${Number(value).toFixed(2)}`;
}

export default function BOMDetailPage() {
  const { bomId } = useParams<{ bomId: string }>();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const canEdit = hasPermission("inventory.edit");
  const canCreate = hasPermission("inventory.create");
  const canDelete = hasPermission("inventory.delete");

  const [bom, setBom] = useState<BOM | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Products list for the add-line dialog
  const [products, setProducts] = useState<Product[]>([]);

  // Add line dialog
  const [addLineOpen, setAddLineOpen] = useState(false);
  const [newLine, setNewLine] = useState({
    component_product_id: "",
    quantity: "",
    unit_of_measure: "",
    waste_percent: "",
    notes: "",
  });
  const [addLineError, setAddLineError] = useState("");

  // Edit line dialog
  const [editLineOpen, setEditLineOpen] = useState(false);
  const [editingLine, setEditingLine] = useState<BOMLine | null>(null);
  const [editLine, setEditLine] = useState({
    component_product_id: "",
    quantity: "",
    unit_of_measure: "",
    waste_percent: "",
    notes: "",
  });
  const [editLineError, setEditLineError] = useState("");

  // Edit BOM notes dialog
  const [editNotesOpen, setEditNotesOpen] = useState(false);
  const [editNotes, setEditNotes] = useState("");
  const [editNotesError, setEditNotesError] = useState("");

  const loadBOM = useCallback(async () => {
    if (!bomId) return;
    setLoading(true);
    setError("");
    try {
      const data = await bomService.getBOM(bomId);
      setBom(data);
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Failed to load BOM"));
    } finally {
      setLoading(false);
    }
  }, [bomId]);

  const loadProducts = useCallback(async () => {
    try {
      const data = await productService.getProducts(1, 1000);
      setProducts(data.items);
    } catch {
      // Silent
    }
  }, []);

  useEffect(() => {
    loadBOM();
  }, [loadBOM]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  const isDraft = bom?.status === "draft";

  // -----------------------------------------------------------------------
  // BOM Actions
  // -----------------------------------------------------------------------

  async function handleActivate() {
    if (!bom) return;
    try {
      const updated = await bomService.activateBOM(bom.id);
      setBom(updated);
      toast.success("BOM activated");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to activate BOM"));
    }
  }

  async function handleArchive() {
    if (!bom) return;
    try {
      const updated = await bomService.archiveBOM(bom.id);
      setBom(updated);
      toast.success("BOM archived");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to archive BOM"));
    }
  }

  async function handleClone() {
    if (!bom) return;
    try {
      const cloned = await bomService.cloneBOM(bom.id);
      toast.success(`Cloned as v${cloned.version}`);
      navigate(`/bom/${cloned.id}`);
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to clone BOM"));
    }
  }

  async function handleDelete() {
    if (!bom) return;
    if (!confirm(`Delete BOM for "${bom.product_name}" v${bom.version}?`)) return;
    try {
      await bomService.deleteBOM(bom.id);
      toast.success("BOM deleted");
      navigate("/bom");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to delete BOM"));
    }
  }

  // -----------------------------------------------------------------------
  // Notes
  // -----------------------------------------------------------------------

  function openEditNotes() {
    if (!bom) return;
    setEditNotes(bom.notes || "");
    setEditNotesError("");
    setEditNotesOpen(true);
  }

  async function handleUpdateNotes() {
    if (!bom) return;
    setEditNotesError("");
    try {
      const updated = await bomService.updateBOM(bom.id, {
        notes: editNotes.trim() || undefined,
      });
      setBom(updated);
      setEditNotesOpen(false);
      toast.success("Notes updated");
    } catch (err: unknown) {
      setEditNotesError(getApiErrorMessage(err, "Failed to update notes"));
    }
  }

  // -----------------------------------------------------------------------
  // Lines
  // -----------------------------------------------------------------------

  function resetNewLine() {
    setNewLine({
      component_product_id: "",
      quantity: "",
      unit_of_measure: "",
      waste_percent: "",
      notes: "",
    });
    setAddLineError("");
  }

  async function handleAddLine() {
    if (!bom) return;
    setAddLineError("");
    try {
      const updated = await bomService.addLine(bom.id, {
        component_product_id: newLine.component_product_id,
        quantity: parseFloat(newLine.quantity),
        unit_of_measure: newLine.unit_of_measure.trim() || undefined,
        waste_percent: newLine.waste_percent.trim()
          ? parseFloat(newLine.waste_percent)
          : undefined,
        notes: newLine.notes.trim() || undefined,
      });
      setBom(updated);
      setAddLineOpen(false);
      resetNewLine();
      toast.success("Line added");
    } catch (err: unknown) {
      setAddLineError(getApiErrorMessage(err, "Failed to add line"));
    }
  }

  function openEditLine(line: BOMLine) {
    setEditingLine(line);
    setEditLine({
      component_product_id: line.component_product_id,
      quantity: String(line.quantity),
      unit_of_measure: line.unit_of_measure || "",
      waste_percent: String(line.waste_percent),
      notes: line.notes || "",
    });
    setEditLineError("");
    setEditLineOpen(true);
  }

  async function handleUpdateLine() {
    if (!bom || !editingLine) return;
    setEditLineError("");
    try {
      const updated = await bomService.updateLine(bom.id, editingLine.id, {
        component_product_id: editLine.component_product_id,
        quantity: parseFloat(editLine.quantity),
        unit_of_measure: editLine.unit_of_measure.trim() || undefined,
        waste_percent: editLine.waste_percent.trim()
          ? parseFloat(editLine.waste_percent)
          : undefined,
        notes: editLine.notes.trim() || undefined,
      });
      setBom(updated);
      setEditLineOpen(false);
      setEditingLine(null);
      toast.success("Line updated");
    } catch (err: unknown) {
      setEditLineError(getApiErrorMessage(err, "Failed to update line"));
    }
  }

  async function handleRemoveLine(line: BOMLine) {
    if (!bom) return;
    if (!confirm(`Remove "${line.component_product_name}" from this BOM?`)) return;
    try {
      const updated = await bomService.removeLine(bom.id, line.id);
      setBom(updated);
      toast.success("Line removed");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to remove line"));
    }
  }

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">Loading BOM...</p>
      </div>
    );
  }

  if (error || !bom) {
    return (
      <div className="space-y-4">
        <Link to="/bom" className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeftIcon className="mr-1 size-4" />
          Back to BOMs
        </Link>
        <div className="rounded-md bg-destructive/10 p-4 text-sm text-destructive">
          {error || "BOM not found"}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link to="/bom" className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeftIcon className="mr-1 size-4" />
        Back to BOMs
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold">{bom.product_name}</h1>
            <Badge variant="outline">v{bom.version}</Badge>
            {statusBadge(bom.status)}
          </div>
          {bom.product_sku && (
            <p className="text-muted-foreground mt-1">SKU: {bom.product_sku}</p>
          )}
          {bom.notes && (
            <p className="text-muted-foreground mt-1">{bom.notes}</p>
          )}
        </div>
        <div className="flex gap-2">
          {canEdit && isDraft && (
            <Button variant="outline" size="sm" onClick={openEditNotes}>
              Edit Notes
            </Button>
          )}
          {canEdit && isDraft && (
            <Button size="sm" onClick={handleActivate}>
              Activate
            </Button>
          )}
          {canEdit && bom.status === "active" && (
            <Button variant="outline" size="sm" onClick={handleArchive}>
              Archive
            </Button>
          )}
          {canCreate && (
            <Button variant="outline" size="sm" onClick={handleClone}>
              Clone
            </Button>
          )}
          {canDelete && isDraft && (
            <Button variant="destructive" size="sm" onClick={handleDelete}>
              Delete
            </Button>
          )}
        </div>
      </div>

      {/* Cost Summary Card */}
      <div className="rounded-md border p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-muted-foreground">
              Total BOM Cost
            </p>
            <p className="text-2xl font-bold">
              {formatCurrency(bom.cost_total)}
            </p>
          </div>
          <div className="text-right">
            <p className="text-sm text-muted-foreground">
              {bom.lines.length} component{bom.lines.length !== 1 ? "s" : ""}
            </p>
          </div>
        </div>
      </div>

      {/* Lines Table */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Components</h2>
          {canEdit && isDraft && (
            <Button
              size="sm"
              onClick={() => {
                resetNewLine();
                setAddLineOpen(true);
              }}
            >
              Add Component
            </Button>
          )}
        </div>

        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Component</TableHead>
                <TableHead>Qty</TableHead>
                <TableHead>UOM</TableHead>
                <TableHead>Waste %</TableHead>
                <TableHead>Effective Qty</TableHead>
                <TableHead>Unit Cost</TableHead>
                <TableHead>Line Cost</TableHead>
                <TableHead>Notes</TableHead>
                {canEdit && isDraft && (
                  <TableHead className="text-right">Actions</TableHead>
                )}
              </TableRow>
            </TableHeader>
            <TableBody>
              {bom.lines.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={canEdit && isDraft ? 9 : 8}
                    className="text-center"
                  >
                    No components added yet
                  </TableCell>
                </TableRow>
              ) : (
                bom.lines.map((line) => (
                  <TableRow key={line.id}>
                    <TableCell className="font-medium">
                      {line.component_product_name}
                      {line.component_sku && (
                        <span className="ml-2 text-xs text-muted-foreground">
                          {line.component_sku}
                        </span>
                      )}
                    </TableCell>
                    <TableCell>{line.quantity}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {line.unit_of_measure || "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {line.waste_percent > 0 ? `${line.waste_percent}%` : "—"}
                    </TableCell>
                    <TableCell>{line.effective_quantity.toFixed(2)}</TableCell>
                    <TableCell>{formatCurrency(line.unit_cost)}</TableCell>
                    <TableCell>{formatCurrency(line.line_cost)}</TableCell>
                    <TableCell className="text-muted-foreground max-w-[200px] truncate">
                      {line.notes || "—"}
                    </TableCell>
                    {canEdit && isDraft && (
                      <TableCell className="text-right space-x-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEditLine(line)}
                        >
                          Edit
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveLine(line)}
                        >
                          Remove
                        </Button>
                      </TableCell>
                    )}
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </div>

      {/* Add Line Dialog */}
      <Dialog
        open={addLineOpen}
        onOpenChange={(open) => {
          setAddLineOpen(open);
          if (!open) resetNewLine();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Component</DialogTitle>
            <DialogDescription>
              Add a component product to this BOM.
            </DialogDescription>
          </DialogHeader>
          {addLineError && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {addLineError}
            </div>
          )}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Component Product</Label>
              <select
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                value={newLine.component_product_id}
                onChange={(e) =>
                  setNewLine({ ...newLine, component_product_id: e.target.value })
                }
              >
                <option value="">Select a product...</option>
                {products
                  .filter((p) => p.is_active && p.id !== bom.product_id)
                  .map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                      {p.sku ? ` (${p.sku})` : ""}
                    </option>
                  ))}
              </select>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>Quantity</Label>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={newLine.quantity}
                  onChange={(e) =>
                    setNewLine({ ...newLine, quantity: e.target.value })
                  }
                  placeholder="1.00"
                />
              </div>
              <div className="space-y-2">
                <Label>Unit of Measure</Label>
                <Input
                  value={newLine.unit_of_measure}
                  onChange={(e) =>
                    setNewLine({ ...newLine, unit_of_measure: e.target.value })
                  }
                  placeholder="each"
                />
              </div>
              <div className="space-y-2">
                <Label>Waste %</Label>
                <Input
                  type="number"
                  step="0.1"
                  min="0"
                  max="100"
                  value={newLine.waste_percent}
                  onChange={(e) =>
                    setNewLine({ ...newLine, waste_percent: e.target.value })
                  }
                  placeholder="0"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Notes (optional)</Label>
              <Input
                value={newLine.notes}
                onChange={(e) =>
                  setNewLine({ ...newLine, notes: e.target.value })
                }
                placeholder="Optional notes"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddLineOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleAddLine}
              disabled={
                !newLine.component_product_id || !newLine.quantity.trim()
              }
            >
              Add Component
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Line Dialog */}
      <Dialog
        open={editLineOpen}
        onOpenChange={(open) => {
          setEditLineOpen(open);
          if (!open) setEditingLine(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Component</DialogTitle>
            <DialogDescription>
              Update the component details.
            </DialogDescription>
          </DialogHeader>
          {editLineError && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {editLineError}
            </div>
          )}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Component Product</Label>
              <select
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                value={editLine.component_product_id}
                onChange={(e) =>
                  setEditLine({
                    ...editLine,
                    component_product_id: e.target.value,
                  })
                }
              >
                <option value="">Select a product...</option>
                {products
                  .filter((p) => p.is_active && p.id !== bom.product_id)
                  .map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                      {p.sku ? ` (${p.sku})` : ""}
                    </option>
                  ))}
              </select>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>Quantity</Label>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={editLine.quantity}
                  onChange={(e) =>
                    setEditLine({ ...editLine, quantity: e.target.value })
                  }
                  placeholder="1.00"
                />
              </div>
              <div className="space-y-2">
                <Label>Unit of Measure</Label>
                <Input
                  value={editLine.unit_of_measure}
                  onChange={(e) =>
                    setEditLine({ ...editLine, unit_of_measure: e.target.value })
                  }
                  placeholder="each"
                />
              </div>
              <div className="space-y-2">
                <Label>Waste %</Label>
                <Input
                  type="number"
                  step="0.1"
                  min="0"
                  max="100"
                  value={editLine.waste_percent}
                  onChange={(e) =>
                    setEditLine({ ...editLine, waste_percent: e.target.value })
                  }
                  placeholder="0"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Notes (optional)</Label>
              <Input
                value={editLine.notes}
                onChange={(e) =>
                  setEditLine({ ...editLine, notes: e.target.value })
                }
                placeholder="Optional notes"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditLineOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleUpdateLine}
              disabled={
                !editLine.component_product_id || !editLine.quantity.trim()
              }
            >
              Update Component
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Notes Dialog */}
      <Dialog open={editNotesOpen} onOpenChange={setEditNotesOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit BOM Notes</DialogTitle>
            <DialogDescription>
              Update the notes for this BOM.
            </DialogDescription>
          </DialogHeader>
          {editNotesError && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {editNotesError}
            </div>
          )}
          <div className="space-y-2">
            <Label>Notes</Label>
            <Input
              value={editNotes}
              onChange={(e) => setEditNotes(e.target.value)}
              placeholder="BOM notes"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditNotesOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdateNotes}>Save Notes</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
