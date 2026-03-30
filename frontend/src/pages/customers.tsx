import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AlertTriangle, Building2, HardHat, Info, Plus, UploadIcon } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { useExtensions } from "@/contexts/extension-context";
import { customerService } from "@/services/customer-service";
import { cemeteryService } from "@/services/cemetery-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type {
  Cemetery,
  CemeteryCreate,
  CustomerImportResult,
  CustomerListItem,
  CustomerStats,
} from "@/types/customer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
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
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function statusBadge(status: string) {
  switch (status) {
    case "active":
      return <Badge variant="default">Active</Badge>;
    case "hold":
      return <Badge variant="secondary" className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">Hold</Badge>;
    case "suspended":
      return <Badge variant="destructive">Suspended</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function formatCurrency(value: number | null): string {
  if (value === null || value === undefined) return "—";
  return `$${Number(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function equipmentSummary(cemetery: Cemetery): string {
  const provides: string[] = [];
  if (cemetery.cemetery_provides_lowering_device) provides.push("lowering device");
  if (cemetery.cemetery_provides_grass) provides.push("grass");
  if (cemetery.cemetery_provides_tent) provides.push("tent");
  if (cemetery.cemetery_provides_chairs) provides.push("chairs");

  if (provides.length === 0) return "Full service";
  if (provides.length === 4) return "Cemetery handles all";
  return `Partial — provides ${provides.join(", ")}`;
}

// ---------------------------------------------------------------------------
// Cemetery Detail Dialog
// ---------------------------------------------------------------------------

const EMPTY_CEMETERY: CemeteryCreate = {
  name: "",
  state: "",
  county: "",
  city: "",
  address: "",
  zip_code: "",
  phone: "",
  contact_name: "",
  cemetery_provides_lowering_device: false,
  cemetery_provides_grass: false,
  cemetery_provides_tent: false,
  cemetery_provides_chairs: false,
  access_notes: "",
};

function equipmentPreviewLabel(form: CemeteryCreate): string {
  const canProvide: string[] = [];
  if (!form.cemetery_provides_lowering_device) canProvide.push("lowering device");
  if (!form.cemetery_provides_grass) canProvide.push("grass service");
  if (!form.cemetery_provides_tent) canProvide.push("tent");
  if (!form.cemetery_provides_chairs) canProvide.push("chairs");

  if (canProvide.length === 0) return "No equipment needed";
  if (canProvide.length === 4) return "Full Equipment";
  if (
    !form.cemetery_provides_lowering_device &&
    !form.cemetery_provides_grass &&
    form.cemetery_provides_tent &&
    form.cemetery_provides_chairs
  )
    return "Lowering Device & Grass";
  if (
    !form.cemetery_provides_lowering_device &&
    form.cemetery_provides_grass &&
    form.cemetery_provides_tent
  )
    return "Lowering Device Only";
  if (
    form.cemetery_provides_lowering_device &&
    form.cemetery_provides_grass &&
    !form.cemetery_provides_tent
  )
    return "Tent Only";
  return canProvide.map((s) => s.replace(/\b\w/g, (c) => c.toUpperCase())).join(" & ");
}

interface CemeteryDialogProps {
  cemetery?: Cemetery | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
  companyId: string;
}

function CemeteryDialog({ cemetery, open, onOpenChange, onSaved }: CemeteryDialogProps) {
  const isEdit = !!cemetery;
  const [form, setForm] = useState<CemeteryCreate>(
    cemetery
      ? {
          name: cemetery.name,
          state: cemetery.state ?? "",
          county: cemetery.county ?? "",
          city: cemetery.city ?? "",
          address: cemetery.address ?? "",
          zip_code: cemetery.zip_code ?? "",
          phone: cemetery.phone ?? "",
          contact_name: cemetery.contact_name ?? "",
          cemetery_provides_lowering_device: cemetery.cemetery_provides_lowering_device,
          cemetery_provides_grass: cemetery.cemetery_provides_grass,
          cemetery_provides_tent: cemetery.cemetery_provides_tent,
          cemetery_provides_chairs: cemetery.cemetery_provides_chairs,
          access_notes: cemetery.access_notes ?? "",
        }
      : EMPTY_CEMETERY,
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setForm(
        cemetery
          ? {
              name: cemetery.name,
              state: cemetery.state ?? "",
              county: cemetery.county ?? "",
              city: cemetery.city ?? "",
              address: cemetery.address ?? "",
              zip_code: cemetery.zip_code ?? "",
              phone: cemetery.phone ?? "",
              contact_name: cemetery.contact_name ?? "",
              cemetery_provides_lowering_device: cemetery.cemetery_provides_lowering_device,
              cemetery_provides_grass: cemetery.cemetery_provides_grass,
              cemetery_provides_tent: cemetery.cemetery_provides_tent,
              cemetery_provides_chairs: cemetery.cemetery_provides_chairs,
              access_notes: cemetery.access_notes ?? "",
            }
          : EMPTY_CEMETERY,
      );
      setError("");
    }
  }, [open, cemetery]);

  async function handleSave() {
    if (!form.name.trim()) {
      setError("Cemetery name is required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      if (isEdit && cemetery) {
        await cemeteryService.updateCemetery(cemetery.id, form);
        toast.success("Cemetery updated");
      } else {
        await cemeteryService.createCemetery(form);
        toast.success("Cemetery created");
      }
      onSaved();
      onOpenChange(false);
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Failed to save cemetery"));
    } finally {
      setSaving(false);
    }
  }

  const previewLabel = equipmentPreviewLabel(form);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Cemetery" : "Add Cemetery"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update this cemetery's details and equipment settings."
              : "Add a new cemetery to track equipment preferences and history."}
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        <div className="space-y-4">
          {/* Basic Info */}
          <div className="space-y-2">
            <Label>Cemetery Name *</Label>
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. Oak Hill Cemetery"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>County</Label>
              <Input
                value={form.county ?? ""}
                onChange={(e) => setForm({ ...form, county: e.target.value })}
                placeholder="e.g. Cayuga"
              />
            </div>
            <div className="space-y-2">
              <Label>State</Label>
              <Input
                value={form.state ?? ""}
                onChange={(e) => setForm({ ...form, state: e.target.value })}
                placeholder="e.g. NY"
                maxLength={2}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>City</Label>
              <Input
                value={form.city ?? ""}
                onChange={(e) => setForm({ ...form, city: e.target.value })}
                placeholder="e.g. Auburn"
              />
            </div>
            <div className="space-y-2">
              <Label>ZIP</Label>
              <Input
                value={form.zip_code ?? ""}
                onChange={(e) => setForm({ ...form, zip_code: e.target.value })}
                placeholder="e.g. 13021"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Address</Label>
            <Input
              value={form.address ?? ""}
              onChange={(e) => setForm({ ...form, address: e.target.value })}
              placeholder="Street address"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>Phone</Label>
              <Input
                value={form.phone ?? ""}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                placeholder="(555) 123-4567"
              />
            </div>
            <div className="space-y-2">
              <Label>Contact Name</Label>
              <Input
                value={form.contact_name ?? ""}
                onChange={(e) => setForm({ ...form, contact_name: e.target.value })}
                placeholder="e.g. Jane Smith"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Access Notes</Label>
            <textarea
              className="flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm resize-none placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              value={form.access_notes ?? ""}
              onChange={(e) => setForm({ ...form, access_notes: e.target.value })}
              placeholder="e.g. Call ahead for gate code. Section 12 requires 4WD."
            />
          </div>

          {/* Equipment Settings */}
          <div className="rounded-md border p-4 space-y-3">
            <div>
              <p className="text-sm font-medium">Equipment Settings</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Which equipment does this cemetery provide themselves?
              </p>
            </div>

            {[
              { key: "cemetery_provides_lowering_device" as const, label: "Lowering device" },
              { key: "cemetery_provides_grass" as const, label: "Grass service" },
              { key: "cemetery_provides_tent" as const, label: "Tent" },
              { key: "cemetery_provides_chairs" as const, label: "Chairs" },
            ].map(({ key, label }) => (
              <div key={key} className="flex items-center justify-between">
                <Label className="text-sm font-normal">{label}</Label>
                <Switch
                  checked={form[key] ?? false}
                  onCheckedChange={(checked) => setForm({ ...form, [key]: checked })}
                />
              </div>
            ))}

            {/* Live preview */}
            <div className="mt-2 rounded-md bg-muted px-3 py-2">
              <p className="text-xs text-muted-foreground">
                When selected on an order, we will suggest:
              </p>
              <p className="text-sm font-medium mt-0.5">{previewLabel}</p>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving || !form.name.trim()}>
            {saving ? "Saving..." : isEdit ? "Save Cemetery" : "Add Cemetery"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Cemeteries Tab
// ---------------------------------------------------------------------------

function CemeteriesTab({ canCreate }: { canCreate: boolean }) {
  const [cemeteries, setCemeteries] = useState<Cemetery[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setCemeterySearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selected, setSelected] = useState<Cemetery | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await cemeteryService.getCemeteries({
        search: search || undefined,
        per_page: 100,
      });
      setCemeteries(data.items);
      setTotal(data.total);
    } catch {
      // non-critical
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    load();
  }, [load]);

  function openCreate() {
    setSelected(null);
    setDialogOpen(true);
  }

  function openEdit(cemetery: Cemetery) {
    setSelected(cemetery);
    setDialogOpen(true);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">{total} cemeteries</p>
        <div className="flex items-center gap-2">
          <Input
            placeholder="Search cemeteries..."
            value={search}
            onChange={(e) => setCemeterySearch(e.target.value)}
            className="max-w-xs"
          />
          {canCreate && (
            <Button onClick={openCreate}>
              <Plus className="mr-1 size-4" />
              Add Cemetery
            </Button>
          )}
        </div>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>County</TableHead>
              <TableHead>State</TableHead>
              <TableHead>Equipment</TableHead>
              {canCreate && <TableHead className="w-20" />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={canCreate ? 5 : 4} className="text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : cemeteries.length === 0 ? (
              <TableRow>
                <TableCell colSpan={canCreate ? 5 : 4} className="py-12 text-center">
                  <Building2 className="mx-auto mb-2 size-8 text-muted-foreground/40" />
                  <p className="text-muted-foreground">No cemeteries yet</p>
                  {canCreate && (
                    <Button variant="outline" size="sm" className="mt-3" onClick={openCreate}>
                      <Plus className="mr-1 size-4" />
                      Add your first cemetery
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ) : (
              cemeteries.map((c) => (
                <TableRow
                  key={c.id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => openEdit(c)}
                >
                  <TableCell className="font-medium">{c.name}</TableCell>
                  <TableCell className="text-muted-foreground">{c.county || "—"}</TableCell>
                  <TableCell className="text-muted-foreground">{c.state || "—"}</TableCell>
                  <TableCell>
                    <span
                      className={
                        c.cemetery_provides_lowering_device &&
                        c.cemetery_provides_grass &&
                        c.cemetery_provides_tent &&
                        c.cemetery_provides_chairs
                          ? "text-muted-foreground text-sm"
                          : !c.cemetery_provides_lowering_device &&
                              !c.cemetery_provides_grass &&
                              !c.cemetery_provides_tent &&
                              !c.cemetery_provides_chairs
                            ? "text-sm text-green-700 dark:text-green-400"
                            : "text-sm text-yellow-700 dark:text-yellow-400"
                      }
                    >
                      {equipmentSummary(c)}
                    </span>
                  </TableCell>
                  {canCreate && (
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          openEdit(c);
                        }}
                      >
                        Edit
                      </Button>
                    </TableCell>
                  )}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <CemeteryDialog
        cemetery={selected}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSaved={load}
        companyId=""
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function CustomersPage() {
  const { hasPermission } = useAuth();
  const { isExtensionEnabled } = useExtensions();
  const canCreate = hasPermission("customers.create");

  const hasProductLineExtension =
    isExtensionEnabled("wastewater") ||
    isExtensionEnabled("redi_rock") ||
    isExtensionEnabled("rosetta");

  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab =
    (searchParams.get("tab") as "funeral_homes" | "contractors" | "cemeteries") ??
    "funeral_homes";

  function setTab(tab: "funeral_homes" | "contractors" | "cemeteries") {
    setSearchParams({ tab }, { replace: true });
    setPage(1);
  }

  // First-time contractors banner
  const [contractorsBannerDismissed, setContractorsBannerDismissed] = useState(
    () => localStorage.getItem("contractors_tab_seen") === "true"
  );
  function dismissContractorsBanner() {
    localStorage.setItem("contractors_tab_seen", "true");
    setContractorsBannerDismissed(true);
  }

  // Customer list state
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [loading, setLoading] = useState(true);

  // Stats
  const [stats, setStats] = useState<CustomerStats | null>(null);

  // Create customer dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [newCustomer, setNewCustomer] = useState({
    name: "",
    account_number: "",
    contact_name: "",
    email: "",
    phone: "",
    city: "",
    state: "",
    payment_terms: "",
    credit_limit: "",
  });
  const [createError, setCreateError] = useState("");

  // Import CSV dialog
  const [importOpen, setImportOpen] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<CustomerImportResult | null>(null);
  const [importError, setImportError] = useState("");

  const loadCustomers = useCallback(async () => {
    setLoading(true);
    try {
      const customerType = activeTab === "contractors" ? "contractor" : "funeral_home";
      const data = await customerService.getCustomers(
        page,
        20,
        search || undefined,
        filterStatus || undefined,
        includeInactive,
        customerType,
      );
      setCustomers(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page, search, filterStatus, includeInactive, activeTab]);

  const loadStats = useCallback(async () => {
    try {
      const data = await customerService.getStats();
      setStats(data);
    } catch {
      // Stats may fail — non-critical
    }
  }, []);

  useEffect(() => {
    if (activeTab === "funeral_homes" || activeTab === "contractors") {
      loadCustomers();
    }
  }, [loadCustomers, activeTab]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  async function handleCreateCustomer() {
    setCreateError("");
    try {
      await customerService.createCustomer({
        name: newCustomer.name,
        account_number: newCustomer.account_number.trim() || undefined,
        contact_name: newCustomer.contact_name.trim() || undefined,
        email: newCustomer.email.trim() || undefined,
        phone: newCustomer.phone.trim() || undefined,
        city: newCustomer.city.trim() || undefined,
        state: newCustomer.state.trim() || undefined,
        payment_terms: newCustomer.payment_terms.trim() || undefined,
        credit_limit: newCustomer.credit_limit.trim()
          ? parseFloat(newCustomer.credit_limit)
          : undefined,
      });
      setCreateOpen(false);
      setNewCustomer({
        name: "",
        account_number: "",
        contact_name: "",
        email: "",
        phone: "",
        city: "",
        state: "",
        payment_terms: "",
        credit_limit: "",
      });
      toast.success("Customer created");
      loadCustomers();
      loadStats();
    } catch (err: unknown) {
      setCreateError(getApiErrorMessage(err, "Failed to create customer"));
    }
  }

  async function handleImport() {
    if (!importFile) return;
    setImporting(true);
    setImportError("");
    setImportResult(null);
    try {
      const result = await customerService.importCustomers(importFile);
      setImportResult(result);
      if (result.created > 0) {
        toast.success(`Imported ${result.created} customers`);
        loadCustomers();
        loadStats();
      }
    } catch (err: unknown) {
      setImportError(getApiErrorMessage(err, "Import failed"));
    } finally {
      setImporting(false);
    }
  }

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Customers</h1>
          <p className="text-muted-foreground">
            {activeTab === "funeral_homes"
              ? `${total} funeral home${total !== 1 ? "s" : ""}`
              : activeTab === "contractors"
              ? `${total} contractor${total !== 1 ? "s" : ""}`
              : "Cemetery management"}
          </p>
        </div>
        {activeTab === "funeral_homes" && canCreate && (
          <div className="flex items-center gap-2">
            {/* Import CSV */}
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
                  <DialogTitle>Import Customers from CSV</DialogTitle>
                  <DialogDescription>
                    Upload a CSV file to bulk-create customers. Duplicate account
                    numbers will be skipped.
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
                        name (required), account_number, email, phone,
                        contact_name, city, state, zip_code, credit_limit,
                        payment_terms
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
                        <p className="text-xs text-green-600 dark:text-green-500">Created</p>
                      </div>
                      {importResult.skipped > 0 && (
                        <div className="rounded-md bg-yellow-50 dark:bg-yellow-950/30 p-3 flex-1 text-center">
                          <p className="text-2xl font-bold text-yellow-700 dark:text-yellow-400">
                            {importResult.skipped}
                          </p>
                          <p className="text-xs text-yellow-600 dark:text-yellow-500">Skipped</p>
                        </div>
                      )}
                    </div>
                    {importResult.errors.length > 0 && (
                      <div className="space-y-1">
                        <p className="text-sm font-medium text-destructive">Errors:</p>
                        <div className="max-h-40 overflow-y-auto rounded-md border p-2 text-xs space-y-0.5">
                          {importResult.errors.map((err, i) => (
                            <p key={i} className="text-muted-foreground">
                              <span className="font-medium">Row {err.row}:</span> {err.message}
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
                      <Button variant="outline" onClick={() => setImportOpen(false)}>
                        Cancel
                      </Button>
                      <Button onClick={handleImport} disabled={!importFile || importing}>
                        {importing ? "Importing..." : "Upload & Import"}
                      </Button>
                    </>
                  ) : (
                    <Button onClick={() => setImportOpen(false)}>Done</Button>
                  )}
                </DialogFooter>
              </DialogContent>
            </Dialog>

            {/* Add Customer */}
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
              <DialogTrigger render={<Button />}>Add Customer</DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create New Customer</DialogTitle>
                  <DialogDescription>Add a new funeral home to the database.</DialogDescription>
                </DialogHeader>
                {createError && (
                  <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                    {createError}
                  </div>
                )}
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>Customer Name</Label>
                    <Input
                      value={newCustomer.name}
                      onChange={(e) => setNewCustomer({ ...newCustomer, name: e.target.value })}
                      placeholder="e.g. Johnson Funeral Home"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Account #</Label>
                      <Input
                        value={newCustomer.account_number}
                        onChange={(e) =>
                          setNewCustomer({ ...newCustomer, account_number: e.target.value })
                        }
                        placeholder="e.g. JFH-001"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Contact Name</Label>
                      <Input
                        value={newCustomer.contact_name}
                        onChange={(e) =>
                          setNewCustomer({ ...newCustomer, contact_name: e.target.value })
                        }
                        placeholder="e.g. John Smith"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Email</Label>
                      <Input
                        type="email"
                        value={newCustomer.email}
                        onChange={(e) =>
                          setNewCustomer({ ...newCustomer, email: e.target.value })
                        }
                        placeholder="john@example.com"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Phone</Label>
                      <Input
                        value={newCustomer.phone}
                        onChange={(e) =>
                          setNewCustomer({ ...newCustomer, phone: e.target.value })
                        }
                        placeholder="(555) 123-4567"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>City</Label>
                      <Input
                        value={newCustomer.city}
                        onChange={(e) =>
                          setNewCustomer({ ...newCustomer, city: e.target.value })
                        }
                        placeholder="e.g. Auburn"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>State</Label>
                      <Input
                        value={newCustomer.state}
                        onChange={(e) =>
                          setNewCustomer({ ...newCustomer, state: e.target.value })
                        }
                        placeholder="e.g. NY"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Payment Terms</Label>
                      <Input
                        value={newCustomer.payment_terms}
                        onChange={(e) =>
                          setNewCustomer({ ...newCustomer, payment_terms: e.target.value })
                        }
                        placeholder="e.g. Net 30"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Credit Limit</Label>
                      <Input
                        type="number"
                        step="0.01"
                        min="0"
                        value={newCustomer.credit_limit}
                        onChange={(e) =>
                          setNewCustomer({ ...newCustomer, credit_limit: e.target.value })
                        }
                        placeholder="0.00"
                      />
                    </div>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setCreateOpen(false)}>
                    Cancel
                  </Button>
                  <Button
                    onClick={handleCreateCustomer}
                    disabled={!newCustomer.name.trim()}
                  >
                    Create Customer
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        )}
      </div>

      {/* Stats bar — only on Funeral Homes tab */}
      {activeTab === "funeral_homes" && stats && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Total Customers</p>
            <p className="text-2xl font-bold">{stats.total_customers}</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Active</p>
            <p className="text-2xl font-bold text-green-600 dark:text-green-400">
              {stats.active_customers}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">On Hold</p>
            <p className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
              {stats.on_hold}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Over Limit</p>
            <p className="text-2xl font-bold text-red-600 dark:text-red-400">
              {stats.over_limit_count}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Total Outstanding</p>
            <p className="text-2xl font-bold">{formatCurrency(stats.total_outstanding)}</p>
          </Card>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b">
        <button
          className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
            activeTab === "funeral_homes"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
          onClick={() => setTab("funeral_homes")}
        >
          Funeral Homes
        </button>
        {hasProductLineExtension && (
          <button
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px flex items-center gap-1.5 ${
              activeTab === "contractors"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => setTab("contractors")}
          >
            <HardHat className="h-3.5 w-3.5" />
            Contractors
          </button>
        )}
        <button
          className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
            activeTab === "cemeteries"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
          onClick={() => setTab("cemeteries")}
        >
          Cemeteries
        </button>
      </div>

      {/* Tab: Funeral Homes */}
      {activeTab === "funeral_homes" && (
        <>
          {/* Filters */}
          <div className="flex flex-wrap items-center gap-2">
            <Input
              placeholder="Search funeral homes..."
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
              <option value="active">Active</option>
              <option value="hold">On Hold</option>
              <option value="suspended">Suspended</option>
            </select>
            <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={includeInactive}
                onChange={(e) => {
                  setIncludeInactive(e.target.checked);
                  setPage(1);
                }}
                className="size-4 rounded border-input"
              />
              Include inactive
            </label>
          </div>

          {/* Customer Table */}
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Account #</TableHead>
                  <TableHead>Contact</TableHead>
                  <TableHead>City / State</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Balance</TableHead>
                  <TableHead>Terms</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center">Loading...</TableCell>
                  </TableRow>
                ) : customers.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center">No funeral homes found</TableCell>
                  </TableRow>
                ) : (
                  customers.map((customer) => (
                    <TableRow key={customer.id}>
                      <TableCell className="font-medium">
                        <Link
                          to={`/customers/${customer.id}`}
                          className="hover:underline"
                        >
                          {customer.name}
                        </Link>
                        {!customer.is_active && (
                          <Badge variant="destructive" className="ml-2">Inactive</Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {customer.account_number || "—"}
                      </TableCell>
                      <TableCell>
                        <div>{customer.contact_name || "—"}</div>
                        {customer.email && (
                          <div className="text-xs text-muted-foreground">{customer.email}</div>
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {customer.city && customer.state
                          ? `${customer.city}, ${customer.state}`
                          : customer.city || customer.state || "—"}
                      </TableCell>
                      <TableCell>{statusBadge(customer.account_status)}</TableCell>
                      <TableCell className="text-right font-mono">
                        {customer.credit_limit !== null &&
                        customer.current_balance > customer.credit_limit ? (
                          <span className="inline-flex items-center gap-1 text-red-600 dark:text-red-400">
                            <AlertTriangle className="size-3.5" />
                            {formatCurrency(customer.current_balance)}
                          </span>
                        ) : (
                          formatCurrency(customer.current_balance)
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {customer.payment_terms || "—"}
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
        </>
      )}

      {/* Tab: Contractors */}
      {activeTab === "contractors" && (
        <>
          {!contractorsBannerDismissed && (
            <div className="flex items-start gap-3 rounded-lg border border-blue-200 bg-blue-50 p-4">
              <Info className="h-5 w-5 text-blue-500 shrink-0 mt-0.5" />
              <div className="flex-1 text-sm text-blue-800">
                <p className="font-medium">Contractors are now visible</p>
                <p className="mt-0.5">These customers work with product lines beyond burial vaults. They appear here because you have at least one product-line extension active.</p>
              </div>
              <button
                onClick={dismissContractorsBanner}
                className="shrink-0 text-blue-400 hover:text-blue-600"
                aria-label="Dismiss"
              >
                ×
              </button>
            </div>
          )}

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-2">
            <Input
              placeholder="Search contractors..."
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
              <option value="active">Active</option>
              <option value="hold">On Hold</option>
              <option value="suspended">Suspended</option>
            </select>
            <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={includeInactive}
                onChange={(e) => {
                  setIncludeInactive(e.target.checked);
                  setPage(1);
                }}
                className="size-4 rounded border-input"
              />
              Include inactive
            </label>
          </div>

          {/* Contractor Table */}
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Account #</TableHead>
                  <TableHead>Contact</TableHead>
                  <TableHead>City / State</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Balance</TableHead>
                  <TableHead>Terms</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center">Loading...</TableCell>
                  </TableRow>
                ) : customers.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center">No contractors found</TableCell>
                  </TableRow>
                ) : (
                  customers.map((customer) => (
                    <TableRow key={customer.id}>
                      <TableCell className="font-medium">
                        <Link to={`/customers/${customer.id}`} className="hover:underline">
                          {customer.name}
                        </Link>
                        {!customer.is_active && (
                          <Badge variant="destructive" className="ml-2">Inactive</Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {customer.account_number || "—"}
                      </TableCell>
                      <TableCell>
                        <div>{customer.contact_name || "—"}</div>
                        {customer.email && (
                          <div className="text-xs text-muted-foreground">{customer.email}</div>
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {customer.city && customer.state
                          ? `${customer.city}, ${customer.state}`
                          : customer.city || customer.state || "—"}
                      </TableCell>
                      <TableCell>{statusBadge(customer.account_status)}</TableCell>
                      <TableCell className="text-right font-mono">
                        {customer.credit_limit !== null &&
                        customer.current_balance > customer.credit_limit ? (
                          <span className="inline-flex items-center gap-1 text-red-600 dark:text-red-400">
                            <AlertTriangle className="size-3.5" />
                            {formatCurrency(customer.current_balance)}
                          </span>
                        ) : (
                          formatCurrency(customer.current_balance)
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {customer.payment_terms || "—"}
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
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {page} of {totalPages}
              </span>
              <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
                Next
              </Button>
            </div>
          )}
        </>
      )}

      {/* Tab: Cemeteries */}
      {activeTab === "cemeteries" && (
        <CemeteriesTab canCreate={canCreate} />
      )}
    </div>
  );
}
