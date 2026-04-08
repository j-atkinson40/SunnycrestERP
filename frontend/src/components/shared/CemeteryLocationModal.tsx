import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { apiClient } from "@/lib/api-client";
import { toast } from "sonner";
import { MapPin } from "lucide-react";

interface Location {
  id: string;
  name: string;
}

interface CemeteryLocationModalProps {
  open: boolean;
  cemeteryId: string;
  cemeteryName: string;
  onConfirm: (locationId: string) => void;
  onDismiss: () => void;
}

export function CemeteryLocationModal({
  open,
  cemeteryId,
  cemeteryName,
  onConfirm,
  onDismiss,
}: CemeteryLocationModalProps) {
  const [locations, setLocations] = useState<Location[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      apiClient
        .get("/companies/locations")
        .then((r) => setLocations(r.data || []))
        .catch(() => {
          // Fallback: fetch the company itself as a single location
          apiClient.get("/companies/settings").then((r) => {
            if (r.data?.id) {
              setLocations([{ id: r.data.id, name: r.data.name }]);
            }
          });
        });
    }
  }, [open]);

  const handleSave = async () => {
    if (!selectedId) return;
    setSaving(true);
    try {
      await apiClient.patch(`/cemeteries/${cemeteryId}/location`, {
        fulfilling_location_id: selectedId,
      });
      toast.success("Cemetery location saved");
      onConfirm(selectedId);
    } catch {
      toast.error("Failed to save cemetery location");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onDismiss()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MapPin className="h-5 w-5 text-amber-500" />
            Cemetery Location Not Configured
          </DialogTitle>
          <DialogDescription>
            <strong>{cemeteryName}</strong> hasn't been assigned to a
            fulfillment location yet. Which location handles jobs at this
            cemetery?
          </DialogDescription>
        </DialogHeader>

        <RadioGroup value={selectedId} onValueChange={setSelectedId} className="space-y-2 py-4">
          {locations.map((loc) => (
            <div key={loc.id} className="flex items-center space-x-3 rounded-md border p-3 hover:bg-muted/50">
              <RadioGroupItem value={loc.id} id={loc.id} />
              <Label htmlFor={loc.id} className="cursor-pointer font-medium">
                {loc.name}
              </Label>
            </div>
          ))}
          {locations.length === 0 && (
            <p className="text-sm text-muted-foreground py-2">
              No locations found. Ensure your company has location records configured.
            </p>
          )}
        </RadioGroup>

        <DialogFooter>
          <Button variant="outline" onClick={onDismiss}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={!selectedId || saving}>
            {saving ? "Saving..." : "Save & Continue"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Hook to check if a cemetery needs location mapping.
 * Returns { needsMapping, openModal } to control the CemeteryLocationModal.
 */
export function useCemeteryLocation(cemeteryId: string | null | undefined) {
  const [needsMapping, setNeedsMapping] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => {
    if (!cemeteryId) {
      setNeedsMapping(false);
      return;
    }
    apiClient
      .get(`/cemeteries/${cemeteryId}`)
      .then((r) => {
        setNeedsMapping(!r.data?.fulfilling_location_id);
      })
      .catch(() => setNeedsMapping(false));
  }, [cemeteryId]);

  return {
    needsMapping,
    modalOpen,
    openModal: () => setModalOpen(true),
    closeModal: () => setModalOpen(false),
    onConfirm: (locationId: string) => {
      setNeedsMapping(false);
      setModalOpen(false);
    },
  };
}
