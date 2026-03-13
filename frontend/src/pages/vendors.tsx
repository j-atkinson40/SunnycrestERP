import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { UploadIcon } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { vendorService } from "@/services/vendor-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type {
  VendorImportResult,
  VendorListItem,
  VendorStats,
} from "@/types/vendor";
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
import { toast } from "sonner";

function statusBadge(status: string) {
  switch (status) {
    case "active":
      return <Badge variant="default">Active</Badge>;
    case "on_hold":
      return (
        <Badge
          variant="secondary"
          className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200"
        >
          On Hold
        </Badge>
      );
    case "inactive":
      return <Badge variant="destructive">Inactive</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

export default function VendorsPage() {
  const { hasPermission } = useAuth();
  const canCreate = hasPermission("vendors.create");

  // Vendor list state
  const [vendors, setVendors] = useState<VendorListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [loading, setLoading] = useState(true);

  // Stats
  const [stats, setStats] = useState<VendorStats | null>(null);

  // Create vendor dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [newVendor, setNewVendor] = useState({
    name: "",
    account_number: "",
    contact_name: "",
    email: "",
    phone: "",
    city: "",
    state: "",
    payment_terms: "",
    lead_time_days: "",
    minimum_order: "",
  });
  const [createError, setCreateError] = useState("");

  // Import CSV dialog
  const [importOpen, setImportOpen] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<VendorImportResult | null>(
    null,
  );
  const [importError, setImportError] = useState("");

  const loadVendors = useCallback(async () => {
    setLoading(true);
    try {
      const data = await vendorService.getVendors(
        page,
        20,
        search || undefined,
        filterStatus || undefined,
        includeInactive,
      );
      setVendors(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page, search, filterStatus, includeInactive]);

  const loadStats = useCallback(async () => {
    try {
      const data = await vendorService.getStats();
      setStats(data);
    } catch {
      // Stats may fail — non-critical
    }
  }, []);

  useEffect(() => {
    loadVendors();
  }, [loadVendors]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  async function handleCreateVendor() {
    setCreateError("");
    try {
      await vendorService.createVendor({
        name: newVendor.name,
        account_number: newVendor.account_number.trim() || undefined,
        contact_name: newVendor.contact_name.trim() || undefined,
        email: newVendor.email.trim() || undefined,
        phone: newVendor.phone.trim() || undefined,
        city: newVendor.city.trim() || undefined,
        state: newVendor.state.trim() || undefined,
        payment_terms: newVendor.payment_terms.trim() || undefined,
        lead_time_days: newVendor.lead_time_days.trim()
          ? parseInt(newVendor.lead_time_days)
          : undefined,
        minimum_order: newVendor.minimum_order.trim()
          ? parseFloat(newVendor.minimum_order)
          : undefined,
      });
      setCreateOpen(false);
      setNewVendor({
        name: "",
        account_number: "",
        contact_name: "",
        email: "",
        phone: "",
        city: "",
        state: "",
        payment_terms: "",
        lead_time_days: "",
        minimum_order: "",
      });
      toast.success("Vendor created");
      loadVendors();
      loadStats();
    } catch (err: unknown) {
      setCreateError(getApiErrorMessage(err, "Failed to create vendor"));
    }
  }

  async function handleImport() {
    if (!importFile) return;
    setImporting(true);
    setImportError("");
    setImportResult(null);
    try {
      const result = await vendorService.importVendors(importFile);
      setImportResult(result);
      if (result.created > 0) {
        toast.success(`Imported ${result.created} vendors`);
        loadVendors();
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Vendors</h1>
          <p className="text-muted-foreground">{total} total vendors</p>
        </div>
        {canCreate && (
          <div className="flex items-center gap-2">
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
                  <DialogTitle>Import Vendors from CSV</DialogTitle>
                  <DialogDescription>
                    Upload a CSV file to bulk-create vendors. Duplicate account
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
                        contact_name, city, state, zip_code, payment_terms,
                        lead_time_days, minimum_order
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Column headers are flexible — e.g. "Vendor Name",
                        "Account #", "Phone Number" all work.
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
                              <span className="font-medium">
                                Row {err.row}:
                              </span>{" "}
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
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
              <DialogTrigger render={<Button />}>Add Vendor</DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create New Vendor</DialogTitle>
                  <DialogDescription>
                    Add a new vendor to the database.
                  </DialogDescription>
                </DialogHeader>
                {createError && (
                  <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                    {createError}
                  </div>
                )}
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>Vendor Name</Label>
                    <Input
                      value={newVendor.name}
                      onChange={(e) =>
                        setNewVendor({ ...newVendor, name: e.target.value })
                      }
                      placeholder="e.g. ABC Supply Co"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Account #</Label>
                      <Input
                        value={newVendor.account_number}
                        onChange={(e) =>
                          setNewVendor({
                            ...newVendor,
                            account_number: e.target.value,
                          })
                        }
                        placeholder="e.g. VEND-001"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Contact Name</Label>
                      <Input
                        value={newVendor.contact_name}
                        onChange={(e) =>
                          setNewVendor({
                            ...newVendor,
                            contact_name: e.target.value,
                          })
                        }
                        placeholder="e.g. Jane Doe"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Email</Label>
                      <Input
                        type="email"
                        value={newVendor.email}
                        onChange={(e) =>
                          setNewVendor({
                            ...newVendor,
                            email: e.target.value,
                          })
                        }
                        placeholder="vendor@example.com"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Phone</Label>
                      <Input
                        value={newVendor.phone}
                        onChange={(e) =>
                          setNewVendor({
                            ...newVendor,
                            phone: e.target.value,
                          })
                        }
                        placeholder="(555) 123-4567"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>City</Label>
                      <Input
                        value={newVendor.city}
                        onChange={(e) =>
                          setNewVendor({
                            ...newVendor,
                            city: e.target.value,
                          })
                        }
                        placeholder="e.g. Springfield"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>State</Label>
                      <Input
                        value={newVendor.state}
                        onChange={(e) =>
                          setNewVendor({
                            ...newVendor,
                            state: e.target.value,
                          })
                        }
                        placeholder="e.g. IL"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Payment Terms</Label>
                      <Input
                        value={newVendor.payment_terms}
                        onChange={(e) =>
                          setNewVendor({
                            ...newVendor,
                            payment_terms: e.target.value,
                          })
                        }
                        placeholder="e.g. Net 30"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Lead Time (days)</Label>
                      <Input
                        type="number"
                        min="0"
                        value={newVendor.lead_time_days}
                        onChange={(e) =>
                          setNewVendor({
                            ...newVendor,
                            lead_time_days: e.target.value,
                          })
                        }
                        placeholder="e.g. 7"
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label>Minimum Order ($)</Label>
                    <Input
                      type="number"
                      step="0.01"
                      min="0"
                      value={newVendor.minimum_order}
                      onChange={(e) =>
                        setNewVendor({
                          ...newVendor,
                          minimum_order: e.target.value,
                        })
                      }
                      placeholder="0.00"
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
                    onClick={handleCreateVendor}
                    disabled={!newVendor.name.trim()}
                  >
                    Create Vendor
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        )}
      </div>

      {/* Stats bar */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Total Vendors</p>
            <p className="text-2xl font-bold">{stats.total_vendors}</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Active</p>
            <p className="text-2xl font-bold text-green-600 dark:text-green-400">
              {stats.active_vendors}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">On Hold</p>
            <p className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
              {stats.on_hold}
            </p>
          </Card>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <Input
          placeholder="Search vendors..."
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
          <option value="on_hold">On Hold</option>
          <option value="inactive">Inactive</option>
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

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Account #</TableHead>
              <TableHead>Contact</TableHead>
              <TableHead>Phone</TableHead>
              <TableHead>City / State</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Terms</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : vendors.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  No vendors found
                </TableCell>
              </TableRow>
            ) : (
              vendors.map((vendor) => (
                <TableRow key={vendor.id}>
                  <TableCell className="font-medium">
                    <Link
                      to={`/vendors/${vendor.id}`}
                      className="hover:underline"
                    >
                      {vendor.name}
                    </Link>
                    {!vendor.is_active && (
                      <Badge variant="destructive" className="ml-2">
                        Inactive
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {vendor.account_number || "\u2014"}
                  </TableCell>
                  <TableCell>
                    <div>{vendor.contact_name || "\u2014"}</div>
                    {vendor.email && (
                      <div className="text-xs text-muted-foreground">
                        {vendor.email}
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {vendor.phone || "\u2014"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {vendor.city && vendor.state
                      ? `${vendor.city}, ${vendor.state}`
                      : vendor.city || vendor.state || "\u2014"}
                  </TableCell>
                  <TableCell>{statusBadge(vendor.vendor_status)}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {vendor.payment_terms || "\u2014"}
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
