import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { qcService } from "@/services/qc-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type {
  QCInspectionListItem,
  QCDashboardStats,
  QCTemplate,
  InspectionStatus,
  ProductCategory,
} from "@/types/qc";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

const PRODUCT_CATEGORIES: { value: ProductCategory; label: string }[] = [
  { value: "burial_vault", label: "Burial Vault" },
  { value: "columbarium", label: "Columbarium" },
  { value: "monument", label: "Monument" },
  { value: "redi_rock", label: "Redi Rock" },
  { value: "precast_other", label: "Precast Other" },
];

const STATUS_OPTIONS: { value: InspectionStatus | ""; label: string }[] = [
  { value: "", label: "All Statuses" },
  { value: "pending", label: "Pending" },
  { value: "in_progress", label: "In Progress" },
  { value: "passed", label: "Passed" },
  { value: "failed", label: "Failed" },
  { value: "conditional_pass", label: "Conditional Pass" },
  { value: "rework_required", label: "Rework Required" },
];

function statusBadge(status: InspectionStatus) {
  const map: Record<InspectionStatus, { label: string; className: string }> = {
    pending: { label: "Pending", className: "bg-gray-100 text-gray-800 border-gray-300" },
    in_progress: { label: "In Progress", className: "bg-blue-100 text-blue-800 border-blue-300" },
    passed: { label: "Passed", className: "bg-green-100 text-green-800 border-green-300" },
    failed: { label: "Failed", className: "bg-red-100 text-red-800 border-red-300" },
    conditional_pass: { label: "Conditional", className: "bg-yellow-100 text-yellow-800 border-yellow-300" },
    rework_required: { label: "Rework", className: "bg-orange-100 text-orange-800 border-orange-300" },
  };
  const s = map[status];
  return <Badge variant="outline" className={s.className}>{s.label}</Badge>;
}

function categoryBadge(category: ProductCategory) {
  const map: Record<ProductCategory, { label: string; className: string }> = {
    burial_vault: { label: "Burial Vault", className: "bg-purple-100 text-purple-800 border-purple-300" },
    columbarium: { label: "Columbarium", className: "bg-indigo-100 text-indigo-800 border-indigo-300" },
    monument: { label: "Monument", className: "bg-teal-100 text-teal-800 border-teal-300" },
    redi_rock: { label: "Redi Rock", className: "bg-amber-100 text-amber-800 border-amber-300" },
    precast_other: { label: "Precast Other", className: "bg-slate-100 text-slate-800 border-slate-300" },
  };
  const c = map[category];
  return <Badge variant="outline" className={c.className}>{c.label}</Badge>;
}

function formatDate(iso: string | null): string {
  if (!iso) return "\u2014";
  return new Date(iso).toLocaleDateString();
}

export default function QCDashboardPage() {
  const navigate = useNavigate();

  // Stats
  const [stats, setStats] = useState<QCDashboardStats | null>(null);

  // Inspection list
  const [inspections, setInspections] = useState<QCInspectionListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterCategory, setFilterCategory] = useState("");
  const [loading, setLoading] = useState(true);

  // Create dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [newCategory, setNewCategory] = useState<ProductCategory | "">("");
  const [templates, setTemplates] = useState<QCTemplate[]>([]);
  const [newTemplateId, setNewTemplateId] = useState("");
  const [newItemId, setNewItemId] = useState("");
  const [newItemIdentifier, setNewItemIdentifier] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  const loadStats = useCallback(async () => {
    try {
      const data = await qcService.getDashboardStats();
      setStats(data);
    } catch {
      // Silent
    }
  }, []);

  const loadInspections = useCallback(async () => {
    setLoading(true);
    try {
      const data = await qcService.listInspections(
        page,
        20,
        filterStatus || undefined,
        filterCategory || undefined,
        search || undefined,
      );
      setInspections(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page, filterStatus, filterCategory, search]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(() => {
    loadInspections();
  }, [loadInspections]);

  // Load templates when category changes in create dialog
  useEffect(() => {
    if (!newCategory) {
      setTemplates([]);
      setNewTemplateId("");
      return;
    }
    qcService.listTemplates(newCategory).then(setTemplates).catch(() => setTemplates([]));
  }, [newCategory]);

  async function handleCreate() {
    if (!newCategory || !newItemIdentifier.trim()) return;
    setCreating(true);
    setCreateError("");
    try {
      const inspection = await qcService.createInspection({
        product_category: newCategory,
        template_id: newTemplateId || undefined,
        inventory_item_id: newItemId.trim() || undefined,
        item_identifier: newItemIdentifier.trim(),
      });
      setCreateOpen(false);
      setNewCategory("");
      setNewTemplateId("");
      setNewItemId("");
      setNewItemIdentifier("");
      toast.success("Inspection created");
      navigate(`/qc/inspections/${inspection.id}`);
    } catch (err: unknown) {
      setCreateError(getApiErrorMessage(err, "Failed to create inspection"));
    } finally {
      setCreating(false);
    }
  }

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Quality Control</h1>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger render={<Button />}>New Inspection</DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>New Inspection</DialogTitle>
              <DialogDescription>
                Start a new quality control inspection.
              </DialogDescription>
            </DialogHeader>
            {createError && (
              <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                {createError}
              </div>
            )}
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Item Identifier</Label>
                <Input
                  value={newItemIdentifier}
                  onChange={(e) => setNewItemIdentifier(e.target.value)}
                  placeholder="e.g. BV-2026-0042"
                />
              </div>
              <div className="space-y-2">
                <Label>Product Category</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value as ProductCategory | "")}
                >
                  <option value="">Select category...</option>
                  {PRODUCT_CATEGORIES.map((c) => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label>Template</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                  value={newTemplateId}
                  onChange={(e) => setNewTemplateId(e.target.value)}
                  disabled={!newCategory || templates.length === 0}
                >
                  <option value="">
                    {!newCategory
                      ? "Select a category first"
                      : templates.length === 0
                        ? "No templates available"
                        : "Select template..."}
                  </option>
                  {templates.map((t) => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label>Inventory Item ID (optional)</Label>
                <Input
                  value={newItemId}
                  onChange={(e) => setNewItemId(e.target.value)}
                  placeholder="Link to inventory item"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setCreateOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleCreate}
                disabled={!newCategory || !newItemIdentifier.trim() || creating}
              >
                {creating ? "Creating..." : "Create Inspection"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Pending Inspections
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.pending_count ?? "\u2014"}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              In Rework
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.in_rework_count ?? "\u2014"}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Awaiting Disposition
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.awaiting_disposition_count ?? "\u2014"}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Completed Today
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.completed_today_count ?? "\u2014"}</div>
          </CardContent>
        </Card>
      </div>

      {/* Filter Bar */}
      <div className="flex items-center gap-2">
        <Input
          placeholder="Search inspections..."
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
          {STATUS_OPTIONS.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={filterCategory}
          onChange={(e) => {
            setFilterCategory(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Categories</option>
          {PRODUCT_CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
      </div>

      {/* Inspections Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Inspection #</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Inspector</TableHead>
              <TableHead>Started</TableHead>
              <TableHead>Completed</TableHead>
              <TableHead>Pass / Fail</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : inspections.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center">
                  No inspections found
                </TableCell>
              </TableRow>
            ) : (
              inspections.map((insp) => (
                <TableRow
                  key={insp.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/qc/inspections/${insp.id}`)}
                >
                  <TableCell className="font-medium">
                    {insp.inspection_number}
                  </TableCell>
                  <TableCell>{categoryBadge(insp.product_category)}</TableCell>
                  <TableCell>{statusBadge(insp.status)}</TableCell>
                  <TableCell>{insp.inspector_name}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(insp.started_at)}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(insp.completed_at)}
                  </TableCell>
                  <TableCell>
                    <span className="text-green-600 font-medium">{insp.pass_count}</span>
                    {" / "}
                    <span className="text-red-600 font-medium">{insp.fail_count}</span>
                    <span className="text-muted-foreground text-xs ml-1">
                      of {insp.step_count}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">
                    <Link
                      to={`/qc/inspections/${insp.id}`}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Button variant="ghost" size="sm">View</Button>
                    </Link>
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
