import { useCallback, useEffect, useState } from "react";
import {
  LinkIcon,
  PlusIcon,
  Trash2Icon,
  UnlinkIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { getApiErrorMessage } from "@/lib/api-error";
import apiClient from "@/lib/api-client";
import { toast } from "sonner";

interface EquipmentRecord {
  id: string;
  name: string;
  serial_number: string | null;
  type: string | null;
  description: string | null;
  status: string;
  assigned_to: string | null;
  assigned_date: string | null;
  created_at: string;
}

const STATUS_STYLES: Record<string, string> = {
  available: "bg-green-100 text-green-800",
  assigned: "bg-blue-100 text-blue-800",
  maintenance: "bg-yellow-100 text-yellow-800",
  retired: "bg-gray-100 text-gray-800",
};

interface EquipmentSectionProps {
  userId: string;
  canEdit: boolean;
}

export default function EquipmentSection({
  userId,
  canEdit,
}: EquipmentSectionProps) {
  const [equipment, setEquipment] = useState<EquipmentRecord[]>([]);
  const [allEquipment, setAllEquipment] = useState<EquipmentRecord[]>([]);
  const [loading, setLoading] = useState(true);

  // Assign dialog
  const [assignDialogOpen, setAssignDialogOpen] = useState(false);
  const [selectedEquipmentId, setSelectedEquipmentId] = useState("");

  // Create dialog
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSerial, setNewSerial] = useState("");
  const [newType, setNewType] = useState("");
  const [creating, setCreating] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [assignedRes, allRes] = await Promise.all([
        apiClient.get<EquipmentRecord[]>("/equipment", {
          params: { assigned_to: userId },
        }),
        apiClient.get<EquipmentRecord[]>("/equipment"),
      ]);
      setEquipment(assignedRes.data);
      setAllEquipment(allRes.data);
    } catch {
      // Non-critical
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const availableEquipment = allEquipment.filter(
    (e) => e.status === "available"
  );

  async function handleAssign() {
    if (!selectedEquipmentId) return;
    try {
      await apiClient.post(`/equipment/${selectedEquipmentId}/assign`, {
        assigned_to: userId,
        assigned_date: new Date().toISOString().split("T")[0],
      });
      toast.success("Equipment assigned");
      setAssignDialogOpen(false);
      setSelectedEquipmentId("");
      await loadData();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to assign equipment"));
    }
  }

  async function handleUnassign(equipmentId: string) {
    try {
      await apiClient.post(`/equipment/${equipmentId}/assign`, {
        assigned_to: null,
        assigned_date: null,
      });
      toast.success("Equipment unassigned");
      await loadData();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to unassign equipment"));
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await apiClient.post("/equipment", {
        name: newName.trim(),
        serial_number: newSerial.trim() || null,
        type: newType.trim() || null,
      });
      toast.success("Equipment created");
      setCreateDialogOpen(false);
      setNewName("");
      setNewSerial("");
      setNewType("");
      await loadData();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to create equipment"));
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(equipmentId: string) {
    if (!confirm("Delete this equipment?")) return;
    try {
      await apiClient.delete(`/equipment/${equipmentId}`);
      toast.success("Equipment deleted");
      await loadData();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to delete equipment"));
    }
  }

  if (loading) {
    return (
      <p className="text-sm text-muted-foreground">Loading equipment...</p>
    );
  }

  return (
    <div className="space-y-3">
      {canEdit && (
        <div className="flex gap-2">
          <Dialog open={assignDialogOpen} onOpenChange={setAssignDialogOpen}>
            <DialogTrigger
              render={<Button type="button" variant="outline" size="sm" />}
            >
              <LinkIcon className="mr-1.5 size-4" />
              Assign Equipment
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Assign Equipment</DialogTitle>
                <DialogDescription>
                  Select available equipment to assign to this employee.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-3">
                <Label>Available Equipment</Label>
                <select
                  value={selectedEquipmentId}
                  onChange={(e) => setSelectedEquipmentId(e.target.value)}
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-[color,box-shadow] focus-visible:border-ring focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
                >
                  <option value="">Select equipment...</option>
                  {availableEquipment.map((e) => (
                    <option key={e.id} value={e.id}>
                      {e.name}
                      {e.serial_number ? ` (${e.serial_number})` : ""}
                    </option>
                  ))}
                </select>
                {availableEquipment.length === 0 && (
                  <p className="text-xs text-muted-foreground">
                    No available equipment. Create new equipment first.
                  </p>
                )}
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  onClick={handleAssign}
                  disabled={!selectedEquipmentId}
                >
                  Assign
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
            <DialogTrigger
              render={<Button type="button" variant="ghost" size="sm" />}
            >
              <PlusIcon className="mr-1.5 size-4" />
              New Equipment
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add Equipment</DialogTitle>
                <DialogDescription>
                  Add a new piece of equipment to your inventory.
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={handleCreate} className="space-y-4">
                <div className="space-y-2">
                  <Label>Name</Label>
                  <Input
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="e.g. MacBook Pro 16"
                    required
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Serial Number (optional)</Label>
                    <Input
                      value={newSerial}
                      onChange={(e) => setNewSerial(e.target.value)}
                      placeholder="SN-12345"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Type (optional)</Label>
                    <Input
                      value={newType}
                      onChange={(e) => setNewType(e.target.value)}
                      placeholder="e.g. laptop, phone"
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button type="submit" disabled={creating}>
                    {creating ? "Creating..." : "Add Equipment"}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      )}

      {equipment.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No equipment assigned.
        </p>
      ) : (
        <div className="space-y-2">
          {equipment.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between rounded-md border p-2.5 text-sm"
            >
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{item.name}</span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[item.status] || STATUS_STYLES.available}`}
                  >
                    {item.status}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">
                  {item.serial_number && `SN: ${item.serial_number}`}
                  {item.serial_number && item.type && " · "}
                  {item.type && `Type: ${item.type}`}
                  {item.assigned_date &&
                    ` · Since ${new Date(item.assigned_date).toLocaleDateString()}`}
                </p>
              </div>
              {canEdit && (
                <div className="flex items-center gap-1 shrink-0">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => handleUnassign(item.id)}
                    title="Unassign"
                  >
                    <UnlinkIcon className="size-3.5" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => handleDelete(item.id)}
                    title="Delete"
                  >
                    <Trash2Icon className="size-3.5 text-destructive" />
                  </Button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
