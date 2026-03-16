import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/contexts/auth-context";
import { deliveryService } from "@/services/delivery-service";
import { getApiErrorMessage } from "@/lib/api-error";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
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
import type { Carrier, CarrierCreate, CarrierUpdate } from "@/types/delivery";

function carrierTypeBadge(type: string) {
  if (type === "third_party") {
    return <Badge className="bg-orange-100 text-orange-800">Third Party</Badge>;
  }
  return <Badge className="bg-blue-100 text-blue-800">Own Fleet</Badge>;
}

export default function CarriersPage() {
  const { hasPermission } = useAuth();
  const canCreate = hasPermission("carriers.create");
  const canEdit = hasPermission("carriers.edit");

  const [carriers, setCarriers] = useState<Carrier[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const perPage = 50;

  // Create/Edit dialog
  const [showDialog, setShowDialog] = useState(false);
  const [editingCarrier, setEditingCarrier] = useState<Carrier | null>(null);
  const [formName, setFormName] = useState("");
  const [formContactName, setFormContactName] = useState("");
  const [formContactPhone, setFormContactPhone] = useState("");
  const [formContactEmail, setFormContactEmail] = useState("");
  const [formCarrierType, setFormCarrierType] = useState("third_party");
  const [formNotes, setFormNotes] = useState("");
  const [saving, setSaving] = useState(false);

  const loadCarriers = useCallback(async () => {
    try {
      setLoading(true);
      const res = await deliveryService.getCarriers(
        page,
        perPage,
        !includeInactive,
        typeFilter || undefined,
      );
      setCarriers(res.items);
      setTotal(res.total);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [page, typeFilter, includeInactive]);

  useEffect(() => {
    loadCarriers();
  }, [loadCarriers]);

  const openCreate = () => {
    setEditingCarrier(null);
    setFormName("");
    setFormContactName("");
    setFormContactPhone("");
    setFormContactEmail("");
    setFormCarrierType("third_party");
    setFormNotes("");
    setShowDialog(true);
  };

  const openEdit = (carrier: Carrier) => {
    setEditingCarrier(carrier);
    setFormName(carrier.name);
    setFormContactName(carrier.contact_name || "");
    setFormContactPhone(carrier.contact_phone || "");
    setFormContactEmail(carrier.contact_email || "");
    setFormCarrierType(carrier.carrier_type);
    setFormNotes(carrier.notes || "");
    setShowDialog(true);
  };

  const handleSave = async () => {
    if (!formName.trim()) {
      toast.error("Carrier name is required");
      return;
    }
    try {
      setSaving(true);
      if (editingCarrier) {
        const data: CarrierUpdate = {
          name: formName,
          contact_name: formContactName || undefined,
          contact_phone: formContactPhone || undefined,
          contact_email: formContactEmail || undefined,
          carrier_type: formCarrierType,
          notes: formNotes || undefined,
        };
        await deliveryService.updateCarrier(editingCarrier.id, data);
        toast.success("Carrier updated");
      } else {
        const data: CarrierCreate = {
          name: formName,
          contact_name: formContactName || undefined,
          contact_phone: formContactPhone || undefined,
          contact_email: formContactEmail || undefined,
          carrier_type: formCarrierType,
          notes: formNotes || undefined,
        };
        await deliveryService.createCarrier(data);
        toast.success("Carrier created");
      }
      setShowDialog(false);
      loadCarriers();
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async (carrier: Carrier) => {
    try {
      await deliveryService.updateCarrier(carrier.id, { active: !carrier.active });
      toast.success(carrier.active ? "Carrier deactivated" : "Carrier activated");
      loadCarriers();
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    }
  };

  const totalPages = Math.ceil(total / perPage);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Carriers</h1>
          <p className="text-sm text-muted-foreground">
            Manage own-fleet and third-party carriers
          </p>
        </div>
        {canCreate && (
          <Button onClick={openCreate}>Add Carrier</Button>
        )}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <select
          value={typeFilter}
          onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
          className="rounded-md border bg-background px-3 py-2 text-sm"
        >
          <option value="">All Types</option>
          <option value="own_fleet">Own Fleet</option>
          <option value="third_party">Third Party</option>
        </select>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(e) => { setIncludeInactive(e.target.checked); setPage(1); }}
          />
          Show inactive
        </label>
      </div>

      {/* Table */}
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Contact</TableHead>
              <TableHead>Phone</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && carriers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground">
                  Loading...
                </TableCell>
              </TableRow>
            ) : carriers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground">
                  No carriers found
                </TableCell>
              </TableRow>
            ) : (
              carriers.map((c) => (
                <TableRow key={c.id} className={!c.active ? "opacity-50" : ""}>
                  <TableCell className="font-medium">{c.name}</TableCell>
                  <TableCell>{carrierTypeBadge(c.carrier_type)}</TableCell>
                  <TableCell className="text-sm">{c.contact_name || "—"}</TableCell>
                  <TableCell className="text-sm">{c.contact_phone || "—"}</TableCell>
                  <TableCell className="text-sm">{c.contact_email || "—"}</TableCell>
                  <TableCell>
                    {c.active ? (
                      <Badge variant="default">Active</Badge>
                    ) : (
                      <Badge variant="secondary">Inactive</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      {canEdit && (
                        <>
                          <Button variant="outline" size="sm" onClick={() => openEdit(c)}>
                            Edit
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleToggleActive(c)}
                          >
                            {c.active ? "Deactivate" : "Activate"}
                          </Button>
                        </>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <p className="text-muted-foreground">
            Page {page} of {totalPages} ({total} carriers)
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingCarrier ? "Edit Carrier" : "Add Carrier"}</DialogTitle>
            <DialogDescription>
              {editingCarrier
                ? "Update carrier information"
                : "Add a new carrier to manage deliveries"}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>Name *</Label>
              <Input
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="Carrier name"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Type</Label>
              <select
                value={formCarrierType}
                onChange={(e) => setFormCarrierType(e.target.value)}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              >
                <option value="own_fleet">Own Fleet</option>
                <option value="third_party">Third Party</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Contact Name</Label>
                <Input
                  value={formContactName}
                  onChange={(e) => setFormContactName(e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label>Phone</Label>
                <Input
                  value={formContactPhone}
                  onChange={(e) => setFormContactPhone(e.target.value)}
                  placeholder="(555) 555-5555"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Email</Label>
              <Input
                type="email"
                value={formContactEmail}
                onChange={(e) => setFormContactEmail(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Notes</Label>
              <textarea
                value={formNotes}
                onChange={(e) => setFormNotes(e.target.value)}
                rows={2}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? "Saving..." : editingCarrier ? "Update" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
