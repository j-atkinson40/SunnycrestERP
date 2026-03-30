import { useCallback, useEffect, useState } from "react";
import { Building2, MapPin, Plus } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { cemeteryService } from "@/services/cemetery-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type { Cemetery, CemeteryCreate } from "@/types/customer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
} from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Cemetery Detail Dialog
// ---------------------------------------------------------------------------

interface CemeteryDialogProps {
  cemetery?: Cemetery | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
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
// Page
// ---------------------------------------------------------------------------

export default function CemeteryDeliverySettingsPage() {
  const { hasPermission } = useAuth();
  const canCreate = hasPermission("customers.create");

  const [cemeteries, setCemeteries] = useState<Cemetery[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <MapPin className="size-6 text-muted-foreground" />
            <h1 className="text-3xl font-bold">Cemetery Delivery Settings</h1>
          </div>
          <p className="mt-1 text-muted-foreground">
            Configure equipment rules and delivery settings for each cemetery you service.
          </p>
        </div>
        {canCreate && (
          <Button onClick={openCreate}>
            <Plus className="mr-1 size-4" />
            Add Cemetery
          </Button>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Total Cemeteries</p>
          <p className="text-2xl font-bold">{total}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Full Service</p>
          <p className="text-2xl font-bold text-green-600 dark:text-green-400">
            {cemeteries.filter(
              (c) =>
                !c.cemetery_provides_lowering_device &&
                !c.cemetery_provides_grass &&
                !c.cemetery_provides_tent &&
                !c.cemetery_provides_chairs,
            ).length}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">With Equipment Provided</p>
          <p className="text-2xl font-bold text-amber-600 dark:text-amber-400">
            {cemeteries.filter(
              (c) =>
                c.cemetery_provides_lowering_device ||
                c.cemetery_provides_grass ||
                c.cemetery_provides_tent ||
                c.cemetery_provides_chairs,
            ).length}
          </p>
        </Card>
      </div>

      {/* Search */}
      <div className="flex items-center gap-2">
        <Input
          placeholder="Search cemeteries..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm"
        />
        <p className="text-sm text-muted-foreground">{total} cemeteries</p>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>County</TableHead>
              <TableHead>City / State</TableHead>
              <TableHead>Contact</TableHead>
              <TableHead>Equipment</TableHead>
              {canCreate && <TableHead className="w-20" />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={canCreate ? 6 : 5} className="text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : cemeteries.length === 0 ? (
              <TableRow>
                <TableCell colSpan={canCreate ? 6 : 5} className="py-12 text-center">
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
                  <TableCell className="text-muted-foreground">
                    {c.city && c.state
                      ? `${c.city}, ${c.state}`
                      : c.city || c.state || "—"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {c.contact_name || "—"}
                  </TableCell>
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
      />
    </div>
  );
}
