import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Edit2, Package, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import apiClient from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error";

type FulfillmentMode = "produce" | "purchase" | "hybrid";
type DeliverySchedule = "on_demand" | "fixed_days";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

const MODE_LABELS: Record<FulfillmentMode, string> = {
  produce: "Produce our own vaults",
  purchase: "Purchase from supplier",
  hybrid: "Both — produce and purchase",
};

interface VaultSupplier {
  id: string;
  vendor_id: string;
  order_quantity: number;
  lead_time_days: number;
  delivery_schedule: string;
  delivery_days: string[];
  is_primary: boolean;
  notes: string | null;
}

interface EditState {
  order_quantity: string;
  lead_time_days: string;
  delivery_schedule: DeliverySchedule;
  delivery_days: string[];
  notes: string;
}

function SupplierCard({
  supplier,
  onSave,
  onDelete,
}: {
  supplier: VaultSupplier;
  onSave: (id: string, data: Partial<VaultSupplier>) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<EditState>({
    order_quantity: String(supplier.order_quantity),
    lead_time_days: String(supplier.lead_time_days),
    delivery_schedule: (supplier.delivery_schedule as DeliverySchedule) || "on_demand",
    delivery_days: supplier.delivery_days || [],
    notes: supplier.notes || "",
  });

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(supplier.id, {
        order_quantity: parseInt(form.order_quantity) || supplier.order_quantity,
        lead_time_days: parseInt(form.lead_time_days) || supplier.lead_time_days,
        delivery_schedule: form.delivery_schedule,
        delivery_days: form.delivery_schedule === "fixed_days" ? form.delivery_days : [],
        notes: form.notes || null,
      });
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  if (!editing) {
    return (
      <Card className="p-4">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Package className="w-4 h-4 text-muted-foreground" />
              <span className="font-medium text-sm">
                Vendor ID: <span className="font-mono text-xs">{supplier.vendor_id}</span>
              </span>
              {supplier.is_primary && (
                <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">
                  Primary
                </span>
              )}
            </div>
            <div className="text-sm text-muted-foreground">
              Order size: <strong>{supplier.order_quantity}</strong> vaults &bull; Lead time:{" "}
              <strong>{supplier.lead_time_days}</strong> days
            </div>
            <div className="text-sm text-muted-foreground">
              Schedule:{" "}
              {supplier.delivery_schedule === "on_demand"
                ? "On demand"
                : `Fixed days: ${(supplier.delivery_days || []).join(", ") || "none set"}`}
            </div>
            {supplier.notes && (
              <div className="text-sm text-muted-foreground italic">{supplier.notes}</div>
            )}
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setEditing(true)}
            >
              <Edit2 className="w-3.5 h-3.5" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="text-red-600 hover:text-red-700"
              onClick={() => onDelete(supplier.id)}
            >
              <Trash2 className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-4 space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">
            Order quantity (vaults)
          </label>
          <input
            type="number"
            min="1"
            className="w-full rounded-md border bg-background px-3 py-1.5 text-sm"
            value={form.order_quantity}
            onChange={(e) => setForm((f) => ({ ...f, order_quantity: e.target.value }))}
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Lead time (days)</label>
          <input
            type="number"
            min="1"
            className="w-full rounded-md border bg-background px-3 py-1.5 text-sm"
            value={form.lead_time_days}
            onChange={(e) => setForm((f) => ({ ...f, lead_time_days: e.target.value }))}
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <label className="text-xs font-medium text-muted-foreground">Delivery schedule</label>
        <div className="flex gap-4">
          {(["on_demand", "fixed_days"] as const).map((sched) => (
            <label key={sched} className="flex items-center gap-1.5 cursor-pointer text-sm">
              <input
                type="radio"
                name={`delivery_schedule_${supplier.id}`}
                checked={form.delivery_schedule === sched}
                onChange={() => setForm((f) => ({ ...f, delivery_schedule: sched }))}
                className="size-3.5"
              />
              {sched === "on_demand" ? "On demand" : "Fixed days"}
            </label>
          ))}
        </div>
      </div>

      {form.delivery_schedule === "fixed_days" && (
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground">Delivery days</label>
          <div className="grid grid-cols-4 gap-1.5">
            {DAYS.map((day) => (
              <label key={day} className="flex items-center gap-1 cursor-pointer text-xs">
                <input
                  type="checkbox"
                  checked={form.delivery_days.includes(day)}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      delivery_days: e.target.checked
                        ? [...f.delivery_days, day]
                        : f.delivery_days.filter((d) => d !== day),
                    }))
                  }
                  className="size-3.5 rounded"
                />
                {day.slice(0, 3)}
              </label>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-1">
        <label className="text-xs font-medium text-muted-foreground">Notes (optional)</label>
        <input
          type="text"
          className="w-full rounded-md border bg-background px-3 py-1.5 text-sm"
          placeholder="e.g. Call 24h before large orders"
          value={form.notes}
          onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
        />
      </div>

      <div className="flex gap-2">
        <Button size="sm" onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : "Save"}
        </Button>
        <Button size="sm" variant="outline" onClick={() => setEditing(false)}>
          Cancel
        </Button>
      </div>
    </Card>
  );
}

export default function VaultSupplierSettingsPage() {
  const [suppliers, setSuppliers] = useState<VaultSupplier[]>([]);
  const [fulfillmentMode, setFulfillmentMode] = useState<FulfillmentMode>("produce");
  const [modeLoading, setModeLoading] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [vendors, setVendors] = useState<Array<{ id: string; name: string }>>([]);
  const [vendorSearch, setVendorSearch] = useState("");
  const [vendorId, setVendorId] = useState("");
  const [addForm, setAddForm] = useState({
    order_quantity: "22",
    lead_time_days: "3",
    delivery_schedule: "on_demand" as DeliverySchedule,
    delivery_days: [] as string[],
    notes: "",
  });
  const [addSaving, setAddSaving] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [suppliersRes, companyRes] = await Promise.all([
        apiClient.get("/vault-supplier/"),
        apiClient.get("/auth/me"),
      ]);
      setSuppliers(suppliersRes.data || []);
      setFulfillmentMode(
        (companyRes.data?.company?.vault_fulfillment_mode as FulfillmentMode) || "produce"
      );
    } catch {
      // silently ignore
    }
  };

  const searchVendors = useCallback(async (q: string) => {
    setVendorSearch(q);
    if (q.length < 2) {
      setVendors([]);
      return;
    }
    try {
      const r = await apiClient.get(`/vendors?search=${encodeURIComponent(q)}&limit=10`);
      setVendors(r.data?.items || r.data || []);
    } catch {
      setVendors([]);
    }
  }, []);

  const handleModeChange = async (mode: FulfillmentMode) => {
    setModeLoading(true);
    try {
      await apiClient.patch("/vault-supplier/fulfillment-mode", {
        vault_fulfillment_mode: mode,
      });
      setFulfillmentMode(mode);
      toast.success("Fulfillment mode updated");
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to update mode"));
    } finally {
      setModeLoading(false);
    }
  };

  const handleSaveSupplier = async (id: string, data: Partial<VaultSupplier>) => {
    try {
      const r = await apiClient.patch(`/vault-supplier/${id}`, data);
      setSuppliers((prev) => prev.map((s) => (s.id === id ? r.data : s)));
      toast.success("Supplier updated");
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to update supplier"));
      throw err;
    }
  };

  const handleDeleteSupplier = async (id: string) => {
    try {
      await apiClient.delete(`/vault-supplier/${id}`);
      setSuppliers((prev) => prev.filter((s) => s.id !== id));
      toast.success("Supplier removed");
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to remove supplier"));
    }
  };

  const handleAddSupplier = async () => {
    if (!vendorId) {
      toast.error("Please select a vendor");
      return;
    }
    setAddSaving(true);
    try {
      const r = await apiClient.post("/vault-supplier/", {
        vendor_id: vendorId,
        order_quantity: parseInt(addForm.order_quantity) || 22,
        lead_time_days: parseInt(addForm.lead_time_days) || 3,
        delivery_schedule: addForm.delivery_schedule,
        delivery_days:
          addForm.delivery_schedule === "fixed_days" ? addForm.delivery_days : [],
        notes: addForm.notes || null,
        is_primary: suppliers.length === 0,
      });
      setSuppliers((prev) => [...prev, r.data]);
      setShowAddForm(false);
      setVendorId("");
      setVendorSearch("");
      setAddForm({
        order_quantity: "22",
        lead_time_days: "3",
        delivery_schedule: "on_demand",
        delivery_days: [],
        notes: "",
      });
      toast.success("Supplier added");
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to add supplier"));
    } finally {
      setAddSaving(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Vault Supplier Settings</h1>
        <p className="text-muted-foreground mt-1">
          Configure how your operation receives vault inventory.
        </p>
      </div>

      {/* Fulfillment Mode */}
      <div className="space-y-3">
        <h2 className="text-base font-semibold">Fulfillment Mode</h2>
        <div className="space-y-2">
          {(["produce", "purchase", "hybrid"] as const).map((m) => (
            <label key={m} className="flex items-center gap-3 cursor-pointer">
              <input
                type="radio"
                name="fulfillment_mode"
                checked={fulfillmentMode === m}
                onChange={() => handleModeChange(m)}
                disabled={modeLoading}
                className="size-4"
              />
              <span className="text-sm">{MODE_LABELS[m]}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Suppliers */}
      {(fulfillmentMode === "purchase" || fulfillmentMode === "hybrid") && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold">Vault Suppliers</h2>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setShowAddForm((v) => !v)}
            >
              <Plus className="w-3.5 h-3.5 mr-1" />
              Add Supplier
            </Button>
          </div>

          {suppliers.length === 0 && !showAddForm && (
            <p className="text-sm text-muted-foreground">
              No suppliers configured. Add one to enable replenishment intelligence.
            </p>
          )}

          {suppliers.map((s) => (
            <SupplierCard
              key={s.id}
              supplier={s}
              onSave={handleSaveSupplier}
              onDelete={handleDeleteSupplier}
            />
          ))}

          {showAddForm && (
            <Card className="p-4 space-y-3 border-dashed">
              <h3 className="text-sm font-semibold">Add New Supplier</h3>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">Vendor</label>
                <input
                  type="text"
                  className="w-full rounded-md border bg-background px-3 py-1.5 text-sm"
                  placeholder="Search vendors..."
                  value={vendorSearch}
                  onChange={(e) => searchVendors(e.target.value)}
                />
                {vendors.length > 0 && (
                  <div className="border rounded-md bg-background shadow-sm max-h-36 overflow-y-auto">
                    {vendors.map((v) => (
                      <button
                        key={v.id}
                        type="button"
                        className="w-full text-left px-3 py-2 text-sm hover:bg-muted"
                        onClick={() => {
                          setVendorId(v.id);
                          setVendorSearch(v.name);
                          setVendors([]);
                        }}
                      >
                        {v.name}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">
                    Order quantity
                  </label>
                  <input
                    type="number"
                    min="1"
                    className="w-full rounded-md border bg-background px-3 py-1.5 text-sm"
                    value={addForm.order_quantity}
                    onChange={(e) =>
                      setAddForm((f) => ({ ...f, order_quantity: e.target.value }))
                    }
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">
                    Lead time (days)
                  </label>
                  <input
                    type="number"
                    min="1"
                    className="w-full rounded-md border bg-background px-3 py-1.5 text-sm"
                    value={addForm.lead_time_days}
                    onChange={(e) =>
                      setAddForm((f) => ({ ...f, lead_time_days: e.target.value }))
                    }
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">
                  Delivery schedule
                </label>
                <div className="flex gap-4">
                  {(["on_demand", "fixed_days"] as const).map((sched) => (
                    <label
                      key={sched}
                      className="flex items-center gap-1.5 cursor-pointer text-sm"
                    >
                      <input
                        type="radio"
                        name="add_delivery_schedule"
                        checked={addForm.delivery_schedule === sched}
                        onChange={() =>
                          setAddForm((f) => ({ ...f, delivery_schedule: sched }))
                        }
                        className="size-3.5"
                      />
                      {sched === "on_demand" ? "On demand" : "Fixed days"}
                    </label>
                  ))}
                </div>
              </div>

              {addForm.delivery_schedule === "fixed_days" && (
                <div className="grid grid-cols-4 gap-1.5">
                  {DAYS.map((day) => (
                    <label key={day} className="flex items-center gap-1 cursor-pointer text-xs">
                      <input
                        type="checkbox"
                        checked={addForm.delivery_days.includes(day)}
                        onChange={(e) =>
                          setAddForm((f) => ({
                            ...f,
                            delivery_days: e.target.checked
                              ? [...f.delivery_days, day]
                              : f.delivery_days.filter((d) => d !== day),
                          }))
                        }
                        className="size-3.5 rounded"
                      />
                      {day.slice(0, 3)}
                    </label>
                  ))}
                </div>
              )}

              <div className="flex gap-2">
                <Button size="sm" onClick={handleAddSupplier} disabled={addSaving}>
                  {addSaving ? "Saving..." : "Add Supplier"}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setShowAddForm(false)}
                >
                  Cancel
                </Button>
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
